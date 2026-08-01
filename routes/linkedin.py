"""LinkedIn routes — OAuth connection and interactions."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user, get_optional_user
from models.user import User
from repositories.token_repo import TokenRepository
from services.linkedin_auth import (
    generate_linkedin_authorization_url,
    exchange_linkedin_code_for_tokens,
)
from agents.linkedin_agent import LinkedInAgent
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/linkedin", tags=["LinkedIn"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CreatePostRequest(BaseModel):
    text: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/login")
async def login(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Generate the LinkedIn OAuth login/authorization URL."""
    # Resolve the JWT token to pass as OAuth state (CSRF and mapping)
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

    if not settings.LINKEDIN_CLIENT_ID or not settings.LINKEDIN_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LinkedIn OAuth is not configured. Please set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET.",
        )

    try:
        url, state = generate_linkedin_authorization_url(state=token)
    except Exception as exc:
        logger.error("Failed to generate LinkedIn authorization URL: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not generate LinkedIn authorization URL. Check configurations.",
        )
    return {"authorization_url": url, "state": state}


@router.get("/callback")
async def callback(
    code: str = Query(...),
    state: str = Query(default=""),
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Exchange the LinkedIn OAuth code for tokens and store them."""
    user_id = None
    if current_user:
        user_id = current_user.id
    elif state:
        # Resolve user ID from state JWT
        from services.auth import decode_access_token
        user_id_str = decode_access_token(state)
        if user_id_str:
            try:
                user_id = int(user_id_str)
            except (ValueError, TypeError):
                pass

    if not user_id:
        logger.error("LinkedIn OAuth callback failed: User could not be identified.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User session not found. Please log in again and reconnect.",
        )

    try:
        await exchange_linkedin_code_for_tokens(code=code, db=db, user_id=user_id)
    except Exception as exc:
        logger.error("LinkedIn OAuth exchange failed for user %s: %s", user_id, exc)
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
                        window.opener.postMessage("linkedin-connected", "*");
                    }
                    window.close();
                </script>
            </head>
            <body style="font-family: sans-serif; text-align: center; padding-top: 50px; background-color: #121214; color: #ffffff;">
                <h2>LinkedIn account connected successfully!</h2>
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
    """Revoke and delete stored LinkedIn credentials."""
    deleted = TokenRepository.delete(db, user_id=current_user.id, provider="linkedin")
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No LinkedIn account connected.",
        )
    return {"status": "disconnected"}


@router.get("/profile")
async def get_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch profile details for the connected LinkedIn member."""
    token = TokenRepository.get(db, user_id=current_user.id, provider="linkedin")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="LinkedIn account not connected.",
        )

    agent = LinkedInAgent()
    profile = await agent.get_profile(token.access_token)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to retrieve profile details from LinkedIn.",
        )
    return profile


@router.post("/post")
async def create_post(
    request: CreatePostRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Publish a post/share on LinkedIn on behalf of the member."""
    token = TokenRepository.get(db, user_id=current_user.id, provider="linkedin")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="LinkedIn account not connected.",
        )

    agent = LinkedInAgent()
    profile = await agent.get_profile(token.access_token)
    person_id = profile.get("sub") or profile.get("id")
    if not person_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not retrieve LinkedIn member ID.",
        )

    res = await agent.create_post(
        access_token=token.access_token,
        person_id=person_id,
        text=request.text,
    )

    if not res.get("success"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to create post on LinkedIn: {res.get('error')}",
        )
    return res


@router.get("/mentions")
async def get_mentions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch mentions for the connected LinkedIn member."""
    token = TokenRepository.get(db, user_id=current_user.id, provider="linkedin")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="LinkedIn account not connected.",
        )

    agent = LinkedInAgent()
    mentions = await agent.get_mentions(token.access_token)
    return {
        "mentions": mentions,
        "note": "LinkedIn public API does not support reading member notifications/mentions feed.",
    }
