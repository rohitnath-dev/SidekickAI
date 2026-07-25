"""Authentication routes — register, login, profile management."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models.user import User
from repositories.user_repo import UserRepository
from services.auth import create_access_token, hash_password, verify_password

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None

    model_config = {"str_min_length": 1}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    email: str


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    is_active: bool
    created_at: datetime


class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """Create a new user account and return an access token."""
    if len(request.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 8 characters.",
        )
    existing = UserRepository.get_by_email(db, request.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )
    user = UserRepository.create(
        db,
        email=request.email,
        hashed_password=hash_password(request.password),
        full_name=request.full_name,
    )
    token = create_access_token(subject=user.id)
    logger.info("New user registered: %s (id=%d)", user.email, user.id)
    return TokenResponse(access_token=token, user_id=user.id, email=user.email)


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Authenticate with email + password and return an access token."""
    user = UserRepository.get_by_email(db, form_data.username)
    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated.",
        )
    token = create_access_token(subject=user.id)
    logger.info("User logged in: %s (id=%d)", user.email, user.id)
    return TokenResponse(access_token=token, user_id=user.id, email=user.email)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Return the authenticated user's profile."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
    )


@router.put("/me", response_model=UserResponse)
async def update_me(
    request: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update full name or password."""
    updates: dict = {}

    if request.full_name is not None:
        updates["full_name"] = request.full_name

    if request.new_password:
        if not request.current_password:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Current password required to set a new password.",
            )
        if not verify_password(request.current_password, current_user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect.",
            )
        if len(request.new_password) < 8:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="New password must be at least 8 characters.",
            )
        updates["hashed_password"] = hash_password(request.new_password)

    if updates:
        current_user = UserRepository.update(db, current_user, **updates)

    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
    )


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deactivate the current user's account."""
    UserRepository.update(db, current_user, is_active=False)
    logger.info("User deactivated: %s (id=%d)", current_user.email, current_user.id)
