"""Slack routes — OAuth connection and interactions."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user, get_optional_user
from models.user import User
from repositories.token_repo import TokenRepository
from services.slack_auth import (
    generate_slack_authorization_url,
    exchange_slack_code_for_tokens,
)
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/slack", tags=["Slack"])


@router.get("/login")
async def login(
    request: Request,
    redirect_uri: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user)
):
    """Generate the Slack OAuth login/authorization URL."""
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

    if not settings.SLACK_CLIENT_ID or not settings.SLACK_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Slack OAuth is not configured. Please set SLACK_CLIENT_ID and SLACK_CLIENT_SECRET.",
        )

    try:
        url, state = generate_slack_authorization_url(
            state=token,
            redirect_uri=redirect_uri,
            request=request
        )
    except Exception as exc:
        logger.error("Failed to generate Slack authorization URL: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not generate Slack authorization URL. Check configurations.",
        )
    return {"authorization_url": url, "state": state}


@router.get("/callback")
@router.get("/callback/")
async def callback(
    request: Request,
    code: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    state: str = Query(default=""),
    redirect_uri: Optional[str] = Query(None),
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Exchange the Slack OAuth code for tokens and store them."""
    if error:
        logger.warning("Slack OAuth callback returned error: %s", error)
        return HTMLResponse(
            content=f"""
            <html>
                <body style="font-family: sans-serif; text-align: center; padding-top: 50px; background-color: #121214; color: #ffffff;">
                    <h2>Slack Authorization Cancelled</h2>
                    <p>Error from Slack: {error}</p>
                    <p>You may close this window and try again.</p>
                </body>
            </html>
            """,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing 'code' query parameter in Slack callback.",
        )

    user_id = None
    if current_user:
        user_id = current_user.id
    elif state:
        from services.auth import decode_access_token
        user_id_str = decode_access_token(state)
        if user_id_str:
            try:
                user_id = int(user_id_str)
            except (ValueError, TypeError):
                user_id = user_id_str

    if not user_id:
        logger.error("Slack OAuth callback failed: User could not be identified.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User session not found. Please log in again and reconnect.",
        )

    try:
        await exchange_slack_code_for_tokens(
            code=code,
            db=db,
            user_id=user_id,
            redirect_uri=redirect_uri,
            request=request
        )
    except Exception as exc:
        logger.error("Slack OAuth exchange failed for user %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to exchange authorization code: {exc}",
        )
    
    # Return HTML response that automatically closes the popup window
    return HTMLResponse(
        content="""
        <html>
            <head>
                <title>Authentication Successful</title>
                <script type="text/javascript">
                    if (window.opener) {
                        window.opener.postMessage("slack-connected", "*");
                    }
                    window.close();
                </script>
            </head>
            <body style="font-family: sans-serif; text-align: center; padding-top: 50px; background-color: #121214; color: #ffffff;">
                <h2>Slack account connected successfully!</h2>
                <p>This window will close automatically.</p>
            </body>
        </html>
        """
    )


@router.delete("/disconnect")
async def disconnect(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke and delete stored Slack credentials."""
    deleted = TokenRepository.delete(db, user_id=current_user.id, provider="slack")
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Slack account connected.",
        )
    return {"status": "disconnected"}
