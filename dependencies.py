"""
Sidekick AI — FastAPI dependency functions.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from services.auth import decode_access_token

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login", auto_error=False
)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve JWT bearer token to an active User. Raises 401 on failure."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user_id_str = decode_access_token(token)
    if user_id_str is None:
        raise credentials_exception

    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise credentials_exception

    user: Optional[User] = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        raise credentials_exception

    return user


async def get_optional_user(
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Like get_current_user but returns None instead of raising on missing/invalid token."""
    if token is None:
        return None
    user_id_str = decode_access_token(token)
    if user_id_str is None:
        return None
    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        return None
    return db.query(User).filter(User.id == user_id, User.is_active == True).first()
