"""
LinkedIn OAuth Service.
Handles:
  1. URL generation for LinkedIn authorization redirect flow.
  2. Exchange of authorization code for user access token.
  3. Securely saving credentials to the database.
"""

from __future__ import annotations

import json
import logging
import urllib.parse
from datetime import datetime, timedelta
from typing import Optional

import httpx
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from config import settings
from models.token import OAuthToken
from repositories.token_repo import TokenRepository

logger = logging.getLogger(__name__)


def generate_linkedin_authorization_url(state: Optional[str] = None) -> tuple[str, str]:
    """
    Generate the manual redirect URL for LinkedIn OAuth.

    Returns:
        (authorization_url, state)
    """
    if not settings.LINKEDIN_CLIENT_ID:
        raise ValueError("LINKEDIN_CLIENT_ID is not configured in settings.")

    base_url = "https://www.linkedin.com/oauth/v2/authorization"
    
    # We request permissions required to identify user, read profile/email and write posts
    scopes = ["openid", "profile", "email", "w_member_social"]
    
    params = {
        "response_type": "code",
        "client_id": settings.LINKEDIN_CLIENT_ID,
        "redirect_uri": settings.LINKEDIN_REDIRECT_URI,
        "scope": " ".join(scopes)
    }

    if state:
        params["state"] = state

    query_str = urllib.parse.urlencode(params)
    auth_url = f"{base_url}?{query_str}"
    
    return auth_url, state or ""


async def exchange_linkedin_code_for_tokens(
    code: str,
    db: Session,
    user_id: int
) -> OAuthToken:
    """
    Exchange the LinkedIn auth code for a user access token and save to the database.
    """
    if not settings.LINKEDIN_CLIENT_ID or not settings.LINKEDIN_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="LinkedIn Client ID or Client Secret is not configured."
        )

    async with httpx.AsyncClient(timeout=30.0) as client:
        token_url = "https://www.linkedin.com/oauth/v2/accessToken"
        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.LINKEDIN_REDIRECT_URI,
            "client_id": settings.LINKEDIN_CLIENT_ID,
            "client_secret": settings.LINKEDIN_CLIENT_SECRET,
        }
        
        try:
            logger.info("Exchanging auth code for LinkedIn access token...")
            res = await client.post(token_url, data=token_data)
            res.raise_for_status()
            res_data = res.json()
        except Exception as exc:
            logger.error("Failed LinkedIn token exchange: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to exchange authorization code with LinkedIn: {str(exc)}"
            )

        access_token = res_data.get("access_token")
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="LinkedIn response did not contain an access_token."
            )

        expires_in = res_data.get("expires_in")
        expires_at = None
        if expires_in:
            expires_at = datetime.utcnow() + timedelta(seconds=int(expires_in))

        scopes_str = res_data.get("scope", "")
        if scopes_str:
            if "," in scopes_str:
                scopes_list = [s.strip() for s in scopes_str.split(",")]
            else:
                scopes_list = scopes_str.split(" ")
        else:
            scopes_list = ["openid", "profile", "email", "w_member_social"]

        refresh_token = res_data.get("refresh_token")

        token = TokenRepository.upsert(
            db=db,
            user_id=user_id,
            provider="linkedin",
            access_token=access_token,
            refresh_token=refresh_token,
            token_uri=token_url,
            scopes=json.dumps(scopes_list),
            expires_at=expires_at
        )
        
        logger.info("Successfully connected LinkedIn and saved credentials for user_id=%d", user_id)
        return token
