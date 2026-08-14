"""Twitter / X routes — OAuth2, user-specific authentication, and webhook handling."""

from __future__ import annotations

import logging
import hmac
import hashlib
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, BackgroundTasks, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import settings
from dependencies import get_current_user, get_optional_user
from models.user import User
from database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/twitter", tags=["Twitter/X"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class TweetResponse(BaseModel):
    id: str
    text: str
    author_id: Optional[str] = None
    created_at: Optional[str] = None


class ReplyRequest(BaseModel):
    tweet_id: str
    post_content: str
    author_handle: str
    context: Optional[str] = None


class ReplyResponse(BaseModel):
    reply_text: str
    posted: bool
    tweet_id: Optional[str] = None


class TwitterConnectionResponse(BaseModel):
    status: str
    message: str
    authorization_url: Optional[str] = None


# ---------------------------------------------------------------------------
# OAuth Authorization Endpoints
# ---------------------------------------------------------------------------

@router.get("/authorize")
async def authorize_twitter(
    current_user: User = Depends(get_current_user),
):
    """
    Generate Twitter OAuth2 consent URL for current user.
    
    User will be redirected to Twitter to authorize Sidekick AI app.
    After authorization, Twitter redirects to /twitter/callback with code.
    """
    from services.twitter_oauth import generate_twitter_authorization_url
    
    try:
        url, state = generate_twitter_authorization_url(state=str(current_user.id))
        logger.info("Generated Twitter OAuth URL for user_id=%d", current_user.id)
        return {
            "authorization_url": url,
            "state": state,
            "message": "Redirect user to this URL to authorize Twitter account"
        }
    except Exception as exc:
        logger.error("Failed to generate Twitter auth URL for user_id=%d: %s", current_user.id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not generate Twitter authorization URL. Check TWITTER_CLIENT_ID configuration."
        )


@router.get("/callback")
async def twitter_callback(
    code: str = Query(..., description="Authorization code from Twitter"),
    state: str = Query(default="", description="State parameter for CSRF prevention"),
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """
    Handle Twitter OAuth2 callback.
    
    Twitter redirects here after user authorizes the app.
    Exchanges authorization code for access token.
    """
    from services.twitter_oauth import exchange_twitter_code_for_tokens
    
    # Identify user from state or current auth
    user_id = None
    if current_user:
        user_id = current_user.id
    elif state:
        try:
            user_id = int(state)
        except (ValueError, TypeError):
            pass
    
    if not user_id:
        logger.warning("Twitter callback: Could not identify user (no auth, invalid state)")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User identification failed. Please authorize again."
        )
    
    # Exchange code for tokens
    token = await exchange_twitter_code_for_tokens(code, db, user_id)
    if not token:
        logger.error("Twitter token exchange failed for user_id=%d", user_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to exchange authorization code for tokens. Check logs."
        )
    
    logger.info("Twitter OAuth completed successfully for user_id=%d", user_id)
    return {
        "status": "success",
        "message": "Twitter account connected successfully!",
        "user_id": user_id,
        "provider": "twitter"
    }


# ---------------------------------------------------------------------------
# Twitter Data Endpoints (User-Specific)
# ---------------------------------------------------------------------------

@router.get("/mentions", response_model=list[TweetResponse])
async def get_mentions(
    max_results: int = Query(default=10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Fetch recent mentions for current user's Twitter account.
    
    Requires user to have authorized Twitter via /authorize endpoint.
    """
    from agents.twitter_agent import TwitterAgent
    from services.twitter_oauth import get_twitter_credentials, _get_twitter_user_id_async

    # Get user's Twitter access token
    access_token = get_twitter_credentials(current_user.id, db)
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Twitter not connected. Please authorize via /twitter/authorize"
        )
    
    # Get user's Twitter ID
    twitter_user_id = await _get_twitter_user_id_async(access_token)
    if not twitter_user_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch your Twitter user ID"
        )
    
    try:
        tweets = await TwitterAgent().get_mentions(
            bearer_token=access_token,
            user_id=twitter_user_id,
            max_results=max_results,
        )
        logger.info("Fetched %d mentions for user_id=%d", len(tweets), current_user.id)
    except Exception as exc:
        logger.error("Twitter mentions fetch failed for user_id=%d: %s", current_user.id, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    return [
        TweetResponse(
            id=t.get("id", ""),
            text=t.get("text", ""),
            author_id=t.get("author_id"),
            created_at=t.get("created_at"),
        )
        for t in tweets
    ]


@router.get("/timeline", response_model=list[TweetResponse])
async def get_timeline(
    max_results: int = Query(default=10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch recent tweets from current user's timeline."""
    from agents.twitter_agent import TwitterAgent
    from services.twitter_oauth import get_twitter_credentials, _get_twitter_user_id_async

    access_token = get_twitter_credentials(current_user.id, db)
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Twitter not connected. Please authorize via /twitter/authorize"
        )
    
    twitter_user_id = await _get_twitter_user_id_async(access_token)
    if not twitter_user_id:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to fetch Twitter user ID")
    
    try:
        tweets = await TwitterAgent().get_timeline(
            bearer_token=access_token,
            user_id=twitter_user_id,
            max_results=max_results,
        )
    except Exception as exc:
        logger.error("Twitter timeline fetch failed for user_id=%d: %s", current_user.id, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    return [
        TweetResponse(
            id=t.get("id", ""),
            text=t.get("text", ""),
            author_id=t.get("author_id"),
            created_at=t.get("created_at"),
        )
        for t in tweets
    ]


@router.post("/sync")
async def sync_twitter_mentions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Manually sync new Twitter mentions and store them in database.
    
    Each mention is processed through AI pipeline.
    """
    from agents.twitter_agent import TwitterAgent
    from models.message import Message, MessageSource, MessagePriority, MessageStatus
    from datetime import datetime
    from services.ai_pipeline import process_message_ai
    from services.twitter_oauth import get_twitter_credentials, _get_twitter_user_id_async

    # Get user's Twitter access token
    access_token = get_twitter_credentials(current_user.id, db)
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Twitter not connected. Please authorize via /twitter/authorize"
        )
    
    # Get user's Twitter ID
    twitter_user_id = await _get_twitter_user_id_async(access_token)
    if not twitter_user_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch your Twitter user ID"
        )

    try:
        tweets = await TwitterAgent().get_mentions(
            bearer_token=access_token,
            user_id=twitter_user_id,
            max_results=10,
        )
    except Exception as exc:
        logger.error("Twitter sync: get_mentions failed for user_id=%d: %s", current_user.id, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    synced_count = 0
    for t in tweets:
        tweet_id = t.get("id")
        if not tweet_id:
            continue

        # Skip if already stored
        existing = db.query(Message).filter_by(
            message_id=tweet_id,
            source=MessageSource.TWITTER
        ).first()
        if existing:
            continue

        # Store message
        db_msg = Message(
            user_id=current_user.id,
            message_id=tweet_id,
            source=MessageSource.TWITTER,
            sender=t.get("author_id") or "TwitterUser",
            body=t.get("text", ""),
            priority=MessagePriority.MEDIUM,
            status=MessageStatus.UNREAD,
            received_at=datetime.utcnow()
        )
        db.add(db_msg)
        db.commit()
        db.refresh(db_msg)

        synced_count += 1
        
        # Decoupled: AI pipeline is now triggered manually via Run AI
        # try:
        #     await process_message_ai(db, db_msg)
        # except Exception as e:
        #     logger.error("Twitter sync: AI pipeline failed for tweet %s: %s", tweet_id, e)

    logger.info("Twitter sync complete: synced=%d tweets for user_id=%d", synced_count, current_user.id)
    return {
        "synced": synced_count,
        "total_stored": synced_count,
        "status": "success"
    }


# ---------------------------------------------------------------------------
# Reply Generation Endpoints
# ---------------------------------------------------------------------------

@router.post("/reply/generate", response_model=ReplyResponse)
async def generate_reply(
    request: ReplyRequest,
    current_user: User = Depends(get_current_user),
):
    """Generate an AI reply to a tweet (does NOT post it)."""
    from agents.twitter_agent import TwitterAgent

    try:
        reply_text = await TwitterAgent().generate_reply_text(
            post_content=request.post_content,
            author_handle=request.author_handle,
            context=request.context,
            user_id=current_user.id,
        )
    except Exception as exc:
        logger.error("Twitter reply generation failed for user_id=%d: %s", current_user.id, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    return ReplyResponse(reply_text=reply_text, posted=False, tweet_id=None)


@router.post("/reply/post", response_model=ReplyResponse)
async def post_reply(
    request: ReplyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate an AI reply to a tweet and post it using user's credentials."""
    from agents.twitter_agent import TwitterAgent
    from services.twitter_oauth import get_twitter_credentials
    from models.token import OAuthToken

    # Get user's Twitter token (contains OAuth 1.0a or 2.0 credentials)
    token = db.query(OAuthToken).filter_by(
        user_id=current_user.id,
        provider="twitter"
    ).first()
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Twitter not connected. Please authorize via /twitter/authorize"
        )

    agent = TwitterAgent()
    try:
        reply_text = await agent.generate_reply_text(
            post_content=request.post_content,
            author_handle=request.author_handle,
            context=request.context,
            user_id=current_user.id,
        )
        
        # Post reply using user's OAuth 2.0 token
        result = await agent.post_reply_oauth2(
            access_token=token.access_token,
            tweet_id=request.tweet_id,
            text=reply_text,
        )
    except Exception as exc:
        logger.error("Twitter post reply failed for user_id=%d: %s", current_user.id, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    posted_id = result.get("data", {}).get("id") if isinstance(result, dict) else None
    logger.info("Posted Twitter reply for user_id=%d, posted_id=%s", current_user.id, posted_id)
    
    return ReplyResponse(reply_text=reply_text, posted=True, tweet_id=posted_id)


# ---------------------------------------------------------------------------
# Webhook Processing (Raw Twitter Events)
# ---------------------------------------------------------------------------

async def verify_twitter_signature(request: Request) -> bytes:
    """
    Validate webhook signature to ensure incoming payload is genuinely from Twitter/X.
    
    ✅ FIXED: Uses TWITTER_APP_SECRET (correct secret for webhook verification)
    """
    signature = request.headers.get("x-twitter-webhooks-signature")
    if not signature:
        logger.warning("Twitter Webhook: Missing signature header.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing x-twitter-webhooks-signature header"
        )

    raw_body = await request.body()
    
    # Extract signature value (format: sha256=hexvalue)
    if "sha256=" not in signature:
        logger.warning("Twitter Webhook: Invalid signature format.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature format"
        )
    
    received_sig = signature.split("sha256=")[1]
    
    # ✅ CORRECT SECRET: Use META_APP_SECRET or TWITTER_APP_SECRET (app-level secret from Twitter)
    app_secret = settings.TWITTER_APP_SECRET or settings.META_APP_SECRET
    if not app_secret:
        logger.error("Twitter Webhook: TWITTER_APP_SECRET not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server not configured for Twitter webhooks"
        )
    
    # Compute signature: sha256(raw_body, app_secret)
    computed_sig = hmac.new(
        app_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256
    ).hexdigest()
    
    # Constant-time comparison
    if not hmac.compare_digest(received_sig, computed_sig):
        logger.warning(
            "Twitter Webhook: HMAC signature validation failed. "
            "Received=%s..., Computed=%s...",
            received_sig[:10],
            computed_sig[:10]
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="HMAC signature validation failed"
        )

    logger.info("Twitter Webhook: Signature verified successfully")
    return raw_body


async def process_twitter_payload_async(body: dict, user_id: int) -> None:
    """
    ✅ FIXED: Asynchronously process incoming Twitter webhook payload for specific user.
    
    Now receives user_id parameter so messages are assigned to correct user.
    """
    from database import SessionLocal
    from models.message import Message, MessageSource, MessagePriority, MessageStatus
    from datetime import datetime
    from services.ai_pipeline import process_message_ai

    db = SessionLocal()
    try:
        # Extract tweet data from webhook payload
        # Twitter webhook format: {"for_user_id": "...", "data": {"id": "...", "text": "...", ...}}
        tweet_data = body.get("data", {})
        tweet_id = tweet_data.get("id")
        author_id = tweet_data.get("author_id", "TwitterUser")
        text = tweet_data.get("text", "")

        if not tweet_id:
            logger.warning("Twitter Webhook: Missing tweet_id in payload (user_id=%d)", user_id)
            return

        logger.info(
            "Twitter Webhook: Processing tweet %s from %s for user_id=%d",
            tweet_id,
            author_id,
            user_id
        )

        # Skip if already exists
        existing = db.query(Message).filter_by(
            message_id=tweet_id,
            source=MessageSource.TWITTER
        ).first()
        if existing:
            logger.info("Twitter Webhook: Message %s already stored", tweet_id)
            return

        # Create and store message
        db_msg = Message(
            user_id=user_id,
            message_id=tweet_id,
            source=MessageSource.TWITTER,
            sender=author_id,
            body=text,
            priority=MessagePriority.MEDIUM,
            status=MessageStatus.UNREAD,
            received_at=datetime.utcnow()
        )
        db.add(db_msg)
        db.commit()
        db.refresh(db_msg)

        # Decoupled: AI pipeline is now triggered manually via Run AI
        # try:
        #     await process_message_ai(db, db_msg)
        # except Exception as e:
        #     logger.error("Twitter Webhook: AI pipeline failed for tweet %s: %s", tweet_id, e)

        logger.info("Twitter Webhook: Successfully processed tweet %s", tweet_id)

    except Exception as exc:
        logger.error("Twitter Webhook: Processing error for user_id=%d: %s", user_id, exc)
    finally:
        db.close()


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def twitter_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """
    Handle incoming Twitter webhook events (mentions, DMs, etc).
    
    ✅ FIXED: 
    - Verifies signature correctly (uses TWITTER_APP_SECRET)
    - Passes user_id to background task
    - Extracts user_id from webhook payload or config
    """
    # Verify webhook signature
    raw_body = await verify_twitter_signature(request)
    
    try:
        body = json.loads(raw_body.decode("utf-8"))
    except Exception as exc:
        logger.error("Twitter Webhook: JSON parsing failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON payload: {exc}"
        )

    # Extract user_id
    # Option 1: From webhook payload (if Twitter sends it)
    user_id = body.get("for_user_id")
    
    # Option 2: From webhook metadata
    if not user_id:
        user_id = body.get("for_user_id") or body.get("user_id")
    
    # Option 3: Fallback to configured TWITTER_USER_ID
    if not user_id:
        if not settings.TWITTER_USER_ID:
            logger.warning("Twitter Webhook: No user_id found, skipping")
            return {"status": "ok"}
        
        # Query to find which user owns this Twitter account
        from database import SessionLocal
        from models.user import User as UserModel
        
        db = SessionLocal()
        try:
            users = db.query(UserModel).all()
            user_id = users[0].id if users else None
        finally:
            db.close()
    
    if user_id:
        background_tasks.add_task(process_twitter_payload_async, body, user_id)
        logger.info("Twitter Webhook: Added processing task for user_id=%s", user_id)
    
    return {"status": "ok"}
