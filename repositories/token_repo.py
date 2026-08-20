"""OAuth token repository."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from models.token import OAuthToken


class TokenRepository:

    @staticmethod
    def upsert(
        db: Session,
        user_id: str | int,
        provider: str,
        access_token: str,
        refresh_token: Optional[str] = None,
        token_uri: Optional[str] = None,
        scopes: Optional[str] = None,
        expires_at: Optional[datetime] = None,
    ) -> OAuthToken:
        token = (
            db.query(OAuthToken)
            .filter_by(user_id=user_id, provider=provider)
            .first()
        )
        if token is None:
            token = OAuthToken(user_id=user_id, provider=provider)
            db.add(token)

        token.access_token = access_token
        if refresh_token is not None:
            token.refresh_token = refresh_token
        if token_uri is not None:
            token.token_uri = token_uri
        if scopes is not None:
            token.scopes = scopes
        if expires_at is not None:
            token.expires_at = expires_at

        db.commit()
        db.refresh(token)
        return token

    @staticmethod
    def get(db: Session, user_id: str | int, provider: str) -> Optional[OAuthToken]:
        return (
            db.query(OAuthToken)
            .filter_by(user_id=user_id, provider=provider)
            .first()
        )

    @staticmethod
    def delete(db: Session, user_id: str | int, provider: str) -> bool:
        token = (
            db.query(OAuthToken)
            .filter_by(user_id=user_id, provider=provider)
            .first()
        )
        if token is None:
            return False
        db.delete(token)
        db.commit()
        return True

    @staticmethod
    def list_by_user(db: Session, user_id: str | int) -> list[OAuthToken]:
        return db.query(OAuthToken).filter_by(user_id=user_id).all()
