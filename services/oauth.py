"""
Sidekick AI — Google OAuth Service

Handles the full OAuth 2.0 flow:
  1. generate_authorization_url() — redirect the user to Google
  2. exchange_code_for_tokens()   — exchange the callback code for tokens
  3. get_credentials()            — restore credentials from the database
  4. refresh_credentials()        — refresh an expired access token
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from config import settings
from models.token import OAuthToken

import os
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = 'True'

logger = logging.getLogger(__name__)

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/contacts.readonly",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]

CLIENT_CONFIG = {
    "web": {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
    }
}


def _build_flow() -> Flow:
    return Flow.from_client_config(
        CLIENT_CONFIG,
        scopes=GOOGLE_SCOPES,
        redirect_uri=settings.GOOGLE_REDIRECT_URI,
        autogenerate_code_verifier=False,
    )


def generate_authorization_url(state: Optional[str] = None) -> tuple[str, str]:
    """
    Build the Google OAuth consent URL.

    Returns:
        (authorization_url, state) — redirect the user to authorization_url
        and store state to validate the callback.
    """
    flow = _build_flow()
    url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
    )
    return url, state


def exchange_code_for_tokens(code: str, state: str, db: Session, user_id: int) -> OAuthToken:
    """
    Exchange an OAuth authorization code for access + refresh tokens
    and persist them to the database.

    Returns:
        The created or updated OAuthToken record.
    """
    flow = _build_flow()
    flow.fetch_token(code=code)
    creds: Credentials = flow.credentials

    expires_at: Optional[datetime] = None
    if creds.expiry:
        expires_at = creds.expiry.replace(tzinfo=None)

    token: Optional[OAuthToken] = (
        db.query(OAuthToken)
        .filter_by(user_id=user_id, provider="google")
        .first()
    )

    if token is None:
        token = OAuthToken(user_id=user_id, provider="google")
        db.add(token)

    token.access_token = creds.token
    token.refresh_token = creds.refresh_token or token.refresh_token
    token.token_uri = creds.token_uri
    token.scopes = json.dumps(list(creds.scopes or []))
    token.expires_at = expires_at

    db.commit()
    db.refresh(token)
    logger.info("Google OAuth tokens saved for user_id=%d", user_id)
    return token


def get_credentials(user_id: int, db: Session) -> Optional[Credentials]:
    """
    Load stored Google credentials for a user.
    Refreshes the access token if expired.

    Returns None if the user has not connected Google.
    """
    token: Optional[OAuthToken] = (
        db.query(OAuthToken)
        .filter_by(user_id=user_id, provider="google")
        .first()
    )
    if token is None:
        return None

    scopes = json.loads(token.scopes) if token.scopes else GOOGLE_SCOPES

    creds = Credentials(
        token=token.access_token,
        refresh_token=token.refresh_token,
        token_uri=token.token_uri or "https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        scopes=scopes,
    )

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            # Persist the refreshed token
            token.access_token = creds.token
            if creds.expiry:
                token.expires_at = creds.expiry.replace(tzinfo=None)
            db.commit()
            logger.info("Google access token refreshed for user_id=%d", user_id)
        except Exception as exc:
            logger.error("Failed to refresh Google token for user_id=%d: %s", user_id, exc)
            return None

    return creds


def revoke_credentials(user_id: int, db: Session) -> bool:
    """Delete stored Google credentials for a user."""
    token: Optional[OAuthToken] = (
        db.query(OAuthToken)
        .filter_by(user_id=user_id, provider="google")
        .first()
    )
    if token is None:
        return False
    db.delete(token)
    db.commit()
    logger.info("Google credentials revoked for user_id=%d", user_id)
    return True


def handle_google_error(exc: Exception):
    """
    Analyzes a Google API exception and raises a clean, structured HTTPException
    that can be easily parsed by the frontend.
    """
    from googleapiclient.errors import HttpError
    from google.auth.exceptions import RefreshError, GoogleAuthError

    # 1. Invalid or expired/revoked credentials
    if isinstance(exc, (RefreshError, GoogleAuthError)) or "invalid_grant" in str(exc) or "authError" in str(exc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "GOOGLE_SESSION_EXPIRED",
                "message": "Google session expired. Please reconnect your account.",
                "action": "reconnect",
            }
        )

    # 2. API calls failing due to Google HTTP Error (403, 429, etc.)
    if isinstance(exc, HttpError):
        status_code = exc.resp.status
        content = exc.content.decode("utf-8") if isinstance(exc.content, bytes) else str(exc.content)
        uri = getattr(exc, 'uri', '')

        # Check if the API is disabled
        if "accessNotConfigured" in content or "has not been used in project" in content or "disabled" in content:
            api_name = "Gmail API" if "gmail" in uri else ("Calendar API" if "calendar" in uri else "Google API")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "GOOGLE_API_DISABLED",
                    "message": f"The {api_name} has not been enabled in the Google Cloud Console. Please enable it to proceed.",
                    "action": "enable_api",
                    "action_url": f"https://console.developers.google.com/apis/api/{'gmail' if 'gmail' in uri else 'calendar'}.googleapis.com/overview",
                }
            )

        # Check for rate limits / quota exceeded
        if status_code == 429 or "rateLimitExceeded" in content or "quotaExceeded" in content:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "code": "GOOGLE_RATE_LIMIT",
                    "message": "Google API rate limit or quota exceeded. Please try again shortly.",
                    "action": "wait",
                }
            )

        # Other Google HttpErrors
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": f"GOOGLE_HTTP_ERROR_{status_code}",
                "message": f"Google service returned an error ({status_code}). Please try again.",
                "action": "retry",
            }
        )

    # 3. Generic/unexpected exception
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={
            "code": "EXTERNAL_INTEGRATION_ERROR",
            "message": f"External integration error: {str(exc)}",
            "action": "retry",
        }
    )

