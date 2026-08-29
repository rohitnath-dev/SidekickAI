"""
Twitter OAuth 2.0 Service

Handles OAuth 2.0 flow for per-user Twitter authentication.
"""

import logging
from typing import Optional
from datetime import datetime, timedelta
import httpx
import base64

from sqlalchemy.orm import Session

from config import settings
from models.token import OAuthToken

logger = logging.getLogger(__name__)

TWITTER_AUTH_URL = "https://twitter.com/i/oauth2/authorize"
TWITTER_TOKEN_URL = "https://api.twitter.com/2/oauth2/token"


def generate_twitter_authorization_url(state: Optional[str] = None) -> tuple[str, str]:
    """
    Generate Twitter OAuth2 authorization URL.
    
    User will be redirected to Twitter to authorize the app.
    After authorization, Twitter redirects to /twitter/callback with a code.
    
    Args:
        state: Optional state parameter to prevent CSRF (use JWT token or user_id)
    
    Returns:
        (authorization_url, state)
    """
    if not settings.TWITTER_CLIENT_ID:
        raise ValueError("TWITTER_CLIENT_ID not configured in environment")
    
    # Scopes needed for Sidekick
    scopes = [
        "tweet.read",           # Read tweets
        "tweet.write",          # Post tweets/replies
        "tweet.moderate.write", # Delete tweets
        "users.read",           # Read user info
        "follows.read",         # Read who user follows
        "follows.write",        # Follow/unfollow
        "mute.read",            # Read muted accounts
        "mute.write",           # Mute/unmute
        "block.read",           # Read blocked accounts
        "block.write",          # Block/unblock
        "offline.access",       # Refresh tokens
    ]
    
    state_param = state or "default"
    
    # PKCE code challenge (simple version)
    code_challenge = "challenge"  # In production, use random value
    
    url = (
        f"{TWITTER_AUTH_URL}"
        f"?client_id={settings.TWITTER_CLIENT_ID}"
        f"&redirect_uri={settings.TWITTER_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope={'+'.join(scopes)}"
        f"&state={state_param}"
        f"&code_challenge={code_challenge}"
        f"&code_challenge_method=plain"
    )
    
    logger.info("Generated Twitter OAuth URL for state=%s", state_param)
    return url, state_param


async def exchange_twitter_code_for_tokens(
    code: str,
    db: Session,
    user_id: int
) -> Optional[OAuthToken]:
    """
    Exchange OAuth2 authorization code for access token.
    
    Args:
        code: Authorization code from Twitter callback
        db: Database session
        user_id: User ID to associate tokens with
    
    Returns:
        OAuthToken object if successful, None otherwise
    """
    if not all([settings.TWITTER_CLIENT_ID, settings.TWITTER_CLIENT_SECRET, settings.TWITTER_REDIRECT_URI]):
        logger.error("Twitter OAuth credentials not configured")
        return None
    
        import base64
    
    # Twitter expects form-urlencoded data, NOT json
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.TWITTER_REDIRECT_URI,
        "client_id": settings.TWITTER_CLIENT_ID,
        "code_verifier": "challenge"
    }
    
    # Twitter requires Basic Auth header with base64(client_id:client_secret)
    credentials = base64.b64encode(
        f"{settings.TWITTER_CLIENT_ID}:{settings.TWITTER_CLIENT_SECRET}".encode()
    ).decode()
    
    headers = {
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                TWITTER_TOKEN_URL, 
                data=payload,      
                headers=headers    
            )
            response.raise_for_status()
            data = response.json()
            
            logger.info("Successfully exchanged Twitter code for tokens (user_id=%d)", user_id)
            
            # Check if token already exists for this user
            token = db.query(OAuthToken).filter_by(
                user_id=user_id,
                provider="twitter"
            ).first()
            
            if token is None:
                token = OAuthToken(user_id=user_id, provider="twitter")
                db.add(token)
                logger.info("Created new Twitter OAuth token record for user_id=%d", user_id)
            else:
                logger.info("Updated existing Twitter OAuth token for user_id=%d", user_id)
            
            # Store tokens
            token.access_token = data.get("access_token")
            token.refresh_token = data.get("refresh_token")
            
            # Store scopes
            scope_str = data.get("scope", "")
            if isinstance(scope_str, str):
                token.scopes = scope_str
            else:
                token.scopes = " ".join(scope_str) if isinstance(scope_str, list) else ""
            
            # Calculate expiry time
            expires_in = data.get("expires_in", 7200)  # Default 2 hours
            token.expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
            
            db.commit()
            db.refresh(token)
            
            logger.info(
                "Twitter token stored with expiry at %s for user_id=%d",
                token.expires_at,
                user_id
            )
            return token
            
    except httpx.HTTPStatusError as exc:
        logger.error("Twitter token exchange HTTP error: %s — %s", exc, exc.response.text)
        return None
    except Exception as exc:
        logger.error("Twitter token exchange failed: %s", exc)
        return None


def get_twitter_credentials(user_id: int, db: Session) -> Optional[str]:
    """
    Get valid Twitter access token for user.
    
    Returns None if:
    - Token doesn't exist
    - Token has expired
    
    Args:
        user_id: User ID to get token for
        db: Database session
    
    Returns:
        Access token string or None
    """
    token = db.query(OAuthToken).filter_by(
        user_id=user_id,
        provider="twitter"
    ).first()
    
    if not token:
        logger.warning("No Twitter token found for user_id=%d", user_id)
        return None
    
    # Check if expired
    if token.is_expired:
        logger.warning("Twitter token expired for user_id=%d (expires_at=%s)", user_id, token.expires_at)
        # TODO: Implement refresh token flow
        return None
    
    return token.access_token


async def refresh_twitter_token(user_id: int, db: Session) -> Optional[OAuthToken]:
    """
    Refresh an expired Twitter access token using refresh token.
    
    TODO: Implement this when needed
    """
    logger.warning("Twitter token refresh not yet implemented for user_id=%d", user_id)
    return None


def get_twitter_user_id_from_token(access_token: str) -> Optional[str]:
    """
    Get Twitter user ID from access token by calling /2/users/me endpoint.
    
    This is useful to store the user's Twitter handle/ID for future reference.
    """
    import asyncio
    return asyncio.run(_get_twitter_user_id_async(access_token))


async def _get_twitter_user_id_async(access_token: str) -> Optional[str]:
    """
    Fetch authenticated user's Twitter ID.
    
    Returns:
        Twitter user ID or None
    """
    url = "https://api.twitter.com/2/users/me"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            user_id = data.get("data", {}).get("id")
            logger.info("Retrieved Twitter user ID: %s", user_id)
            return user_id
    except Exception as exc:
        logger.error("Failed to get Twitter user ID: %s", exc)
        return None
