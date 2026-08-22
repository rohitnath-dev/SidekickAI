"""Authentication routes — register, login, profile management."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from dependencies import get_current_user
from models.user import User
from models.session import UserSession
from repositories.user_repo import UserRepository
from services.auth import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    decode_access_token,
)


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

    # User.id is UUID/string in models/user.py
    user_id: str

    email: str


class UserResponse(BaseModel):
    # User.id is UUID/string in models/user.py
    id: str

    email: str
    full_name: Optional[str]
    is_active: bool
    is_admin: bool
    created_at: datetime
    has_ai_config: bool
    onboarding_completed: bool = False


class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    response: Response,
    request: RegisterRequest,
    db: Session = Depends(get_db),
):
    """
    Create a new user account, return an access token,
    and set httpOnly secure cookies.
    """
    from datetime import datetime, timedelta

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

    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)

    expires_at = datetime.utcnow() + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )

    session_record = UserSession(
        user_id=user.id,
        refresh_token=refresh_token,
        expires_at=expires_at,
    )

    db.add(session_record)
    db.commit()

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=15 * 60,
        expires=15 * 60,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
    )

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        expires=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
    )

    logger.info(
        "New user registered and session created: %s (id=%s)",
        user.email,
        user.id,
    )

    return TokenResponse(
        access_token=access_token,
        user_id=user.id,
        email=user.email,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Authenticate with email + password, return an access token,
    and set httpOnly secure cookies.
    """
    from datetime import datetime, timedelta

    user = UserRepository.get_by_email(db, form_data.username)

    if user is None or not verify_password(
        form_data.password,
        user.hashed_password,
    ):
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

    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)

    expires_at = datetime.utcnow() + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )

    session_record = UserSession(
        user_id=user.id,
        refresh_token=refresh_token,
        expires_at=expires_at,
    )

    db.add(session_record)
    db.commit()

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=15 * 60,
        expires=15 * 60,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
    )

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        expires=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
    )

    logger.info(
        "User logged in and session created: %s (id=%s)",
        user.email,
        user.id,
    )

    return TokenResponse(
        access_token=access_token,
        user_id=user.id,
        email=user.email,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the profile of the current logged-in user."""

    from models.ai_config import UserAIConfig
<<<<<<< HEAD
    ai_config = db.query(UserAIConfig).filter_by(user_id=current_user.id).first()
    is_onboarding_completed = getattr(current_user, "onboarding_completed", False)
=======

    ai_config = (
        db.query(UserAIConfig)
        .filter_by(user_id=current_user.id)
        .first()
    )

>>>>>>> f639053 (fix: align auth schemas with UUID user IDs)
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        is_admin=current_user.is_admin,
        created_at=current_user.created_at,
        has_ai_config=ai_config is not None,
        onboarding_completed=is_onboarding_completed,
    )


@router.post("/complete-onboarding", response_model=UserResponse)
async def complete_onboarding(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark onboarding as completed for the current user."""
    current_user.onboarding_completed = True
    db.commit()
    db.refresh(current_user)

    from models.ai_config import UserAIConfig
    ai_config = db.query(UserAIConfig).filter_by(user_id=current_user.id).first()
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        is_admin=current_user.is_admin,
        created_at=current_user.created_at,
        has_ai_config=ai_config is not None,
        onboarding_completed=True,
    )


@router.patch("/me", response_model=UserResponse)
async def update_me(
    request: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update the current user's profile information."""

    updates = {}

    if request.full_name is not None:
        updates["full_name"] = request.full_name

    if request.new_password:
        if not request.current_password:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Current password is required to set a new password.",
            )

        if not verify_password(
            request.current_password,
            current_user.hashed_password,
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect.",
            )

        if len(request.new_password) < 8:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="New password must be at least 8 characters.",
            )

        updates["hashed_password"] = hash_password(
            request.new_password
        )

    if updates:
        current_user = UserRepository.update(
            db,
            current_user,
            **updates,
        )

    from models.ai_config import UserAIConfig

    ai_config = (
        db.query(UserAIConfig)
        .filter_by(user_id=current_user.id)
        .first()
    )

    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        is_admin=current_user.is_admin,
        created_at=current_user.created_at,
        has_ai_config=ai_config is not None,
        onboarding_completed=getattr(current_user, "onboarding_completed", False),
    )


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deactivate the current user's account."""

    UserRepository.update(
        db,
        current_user,
        is_active=False,
    )

    logger.info(
        "User deactivated: %s (id=%s)",
        current_user.email,
        current_user.id,
    )


@router.post("/refresh")
async def refresh_session(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Explicitly refresh the access token using the refresh token
    from httpOnly cookie.
    """
    from datetime import datetime, timedelta

    refresh_token = request.cookies.get("refresh_token")

    if not refresh_token:
        logger.warning(
            "Refresh session failed: missing refresh_token cookie."
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid. Please login again.",
        )

    refresh_sub = decode_access_token(refresh_token)

    if not refresh_sub:
        logger.warning(
            "Refresh session failed: refresh_token cookie decode failed."
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid. Please login again.",
        )

    session_record = (
        db.query(UserSession)
        .filter(
            UserSession.refresh_token == refresh_token,
            UserSession.expires_at > datetime.utcnow(),
        )
        .first()
    )

    if not session_record:
        logger.warning(
            "Refresh session failed: active session not found "
            "in database or has expired."
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid. Please login again.",
        )

    # User IDs are strings/UUIDs.
    user = (
        db.query(User)
        .filter(User.id == refresh_sub)
        .first()
    )

    if not user:
        # Backward-compatible fallback for any legacy numeric token.
        try:
            user_id = int(refresh_sub)
            user = (
                db.query(User)
                .filter(User.id == user_id)
                .first()
            )
        except (ValueError, TypeError):
            user = None

    if not user or not user.is_active:
        logger.warning(
            "Refresh session failed: user is deactivated or not found."
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid. Please login again.",
        )

    new_access = create_access_token(user.id)
    new_refresh = create_refresh_token(user.id)

    # Rotate refresh token in DB.
    session_record.refresh_token = new_refresh
    session_record.expires_at = datetime.utcnow() + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )

    db.commit()

    # Write cookies on outgoing Response.
    response.set_cookie(
        key="access_token",
        value=new_access,
        httponly=True,
        max_age=15 * 60,
        expires=15 * 60,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
    )

    response.set_cookie(
        key="refresh_token",
        value=new_refresh,
        httponly=True,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        expires=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
    )

    logger.info(
        "Successfully refreshed session for user_id=%s",
        user.id,
    )

    return {
        "status": "success",
        "user_id": user.id,
        "email": user.email,
        "access_token": new_access,
    }


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Invalidate current refresh session in DB
    and clear browser auth cookies.
    """

    refresh_token = request.cookies.get("refresh_token")

    if refresh_token:
        # Delete session from DB.
        (
            db.query(UserSession)
            .filter(UserSession.refresh_token == refresh_token)
            .delete(synchronize_session=False)
        )

        db.commit()

        logger.info(
            "Successfully invalidated session in database on explicit logout."
        )
    else:
<<<<<<< HEAD
        logger.info("Logout called without a refresh token cookie.")
        
    # Clear cookies
=======
        logger.info(
            "Logout called without a refresh token cookie."
        )

    # Clear cookies.
>>>>>>> f639053 (fix: align auth schemas with UUID user IDs)
    response.delete_cookie(
        "access_token",
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
    )
    response.delete_cookie(
        "refresh_token",
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
<<<<<<< HEAD
        domain=settings.COOKIE_DOMAIN,
    )
    
=======
    )

>>>>>>> f639053 (fix: align auth schemas with UUID user IDs)
    logger.info("Successfully cleared client cookies on logout.")

    return {"status": "success"}