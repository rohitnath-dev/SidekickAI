"""
Slack OAuth Service.
Handles:
  1. URL generation for Slack authorization redirect flow.
  2. Exchange of authorization code for user access token.
  3. Securely saving credentials to the database.
"""

from __future__ import annotations

import json
import logging
import urllib.parse
from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from config import settings
from models.token import OAuthToken
from repositories.token_repo import TokenRepository

logger = logging.getLogger(__name__)


def generate_slack_authorization_url(state: Optional[str] = None) -> tuple[str, str]:
    """
    Generate the redirect URL for Slack OAuth.
    """
    if not settings.SLACK_CLIENT_ID:
        raise ValueError("SLACK_CLIENT_ID is not configured in settings.")

    base_url = "https://slack.com/oauth/v2/authorize"
    
    # User scopes to fetch DMs and channel histories
    user_scopes = [
        "im:read",
        "im:history",
        "users:read",
        "channels:read",
        "channels:history",
    ]
    
    params = {
        "client_id": settings.SLACK_CLIENT_ID,
        "redirect_uri": settings.SLACK_REDIRECT_URI,
        "user_scope": ",".join(user_scopes),
    }

    if state:
        params["state"] = state

    query_str = urllib.parse.urlencode(params)
    auth_url = f"{base_url}?{query_str}"
    
    return auth_url, state or ""


async def exchange_slack_code_for_tokens(
    code: str,
    db: Session,
    user_id: int
) -> OAuthToken:
    """
    Exchange the Slack authorization code for access tokens and save them.
    """
    if not settings.SLACK_CLIENT_ID or not settings.SLACK_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Slack Client ID or Client Secret is not configured."
        )

    async with httpx.AsyncClient(timeout=30.0) as client:
        token_url = "https://slack.com/api/oauth.v2.access"
        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.SLACK_REDIRECT_URI,
            "client_id": settings.SLACK_CLIENT_ID,
            "client_secret": settings.SLACK_CLIENT_SECRET,
        }
        
        try:
            logger.info("Exchanging auth code for Slack access token...")
            res = await client.post(token_url, data=token_data)
            res.raise_for_status()
            res_data = res.json()
        except Exception as exc:
            logger.error("Failed Slack token exchange: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to exchange authorization code with Slack: {str(exc)}"
            )

        if not res_data.get("ok"):
            logger.error("Slack OAuth response error: %s", res_data.get("error"))
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Slack OAuth error: {res_data.get('error')}"
            )

        # In Slack OAuth v2, user token resides in authed_user block
        authed_user = res_data.get("authed_user") or {}
        access_token = authed_user.get("access_token") or res_data.get("access_token")
        
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Slack response did not contain an access_token."
            )

        scopes_str = authed_user.get("scope", "") or res_data.get("scope", "")
        scopes_list = [s.strip() for s in scopes_str.split(",") if s.strip()]

        token = TokenRepository.upsert(
            db=db,
            user_id=user_id,
            provider="slack",
            access_token=access_token,
            refresh_token=None,
            token_uri=token_url,
            scopes=json.dumps(scopes_list),
            expires_at=None
        )
        
        logger.info("Successfully connected Slack and saved credentials for user_id=%d", user_id)
        return token
