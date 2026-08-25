"""
Sidekick AI — FastAPI dependency functions.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, Response, status
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
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> User:
    """Resolve JWT bearer token or header to an active User. Silently refreshes via refresh_token if expired."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 1. Extract token from Authorization header, cookies, or query params
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header:
        parts = auth_header.split(" ")
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]

    if not token:
        token = request.cookies.get("access_token")

    if not token:
        token = request.query_params.get("token")

    user_id_str: Optional[str] = None
    if token:
        user_id_str = decode_access_token(token)

    if user_id_str is None:
        # Access token missing or invalid/expired. Try silent refresh with refresh_token cookie.
        logger.debug("Access token missing or invalid/expired. Checking refresh_token for silent refresh.")
        refresh_token = request.cookies.get("refresh_token")
        if refresh_token:
            refresh_sub = decode_access_token(refresh_token)
            if refresh_sub:
                from datetime import datetime, timedelta
                from models.session import UserSession
                from services.auth import create_access_token, create_refresh_token
                from config import settings

                session_record = db.query(UserSession).filter(
                    UserSession.refresh_token == refresh_token,
                    UserSession.expires_at > datetime.utcnow()
                ).first()

                if session_record:
                    user = db.query(User).filter(User.id == refresh_sub).first()
                    if user and user.is_active:
                        # Generate rotated tokens
                        new_access = create_access_token(user.id)
                        new_refresh = create_refresh_token(user.id)

                        try:
                            session_record.refresh_token = new_refresh
                            session_record.expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
                            db.commit()
                        except Exception as session_err:
                            db.rollback()
                            logger.error("Failed to commit rotated session token in dependencies: %s", session_err)

                        # Write cookies on outgoing Response
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
                        return user

        raise credentials_exception

    # Resolve database user by user_id_str
    user = db.query(User).filter(User.id == user_id_str).first()
    if not user or not user.is_active:
        raise credentials_exception

    return user


async def get_optional_user(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Like get_current_user but returns None instead of raising on missing/invalid token."""
    try:
        return await get_current_user(request=request, response=response, db=db)
    except HTTPException:
        return None


