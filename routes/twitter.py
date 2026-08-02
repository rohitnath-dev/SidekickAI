"""Twitter / X routes."""

from __future__ import annotations

import logging
import hmac
import hashlib
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, BackgroundTasks, status
from pydantic import BaseModel

from config import settings
from dependencies import get_current_user
from models.user import User
from sqlalchemy.orm import Session
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


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _require_twitter():
    if not settings.TWITTER_BEARER_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Twitter/X is not configured. Set TWITTER_BEARER_TOKEN in your environment.",
        )


def _require_twitter_write():
    if not all([
        settings.TWITTER_API_KEY,
        settings.TWITTER_API_SECRET,
        settings.TWITTER_ACCESS_TOKEN,
        settings.TWITTER_ACCESS_SECRET,
    ]):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Twitter/X write credentials not configured. Set TWITTER_API_KEY/SECRET and TWITTER_ACCESS_TOKEN/SECRET.",
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/mentions", response_model=list[TweetResponse])
async def get_mentions(
    user_id: str = Query(..., description="Twitter user ID to fetch mentions for"),
    max_results: int = Query(default=10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    """Fetch recent mentions for a Twitter user."""
    from agents.twitter_agent import TwitterAgent

    _require_twitter()
    try:
        tweets = await TwitterAgent().get_mentions(
            bearer_token=settings.TWITTER_BEARER_TOKEN,
            user_id=user_id,
            max_results=max_results,
        )
    except Exception as exc:
        logger.error("Twitter mentions fetch failed: %s", exc)
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
    user_id: str = Query(...),
    max_results: int = Query(default=10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    """Fetch recent tweets from a user's timeline."""
    from agents.twitter_agent import TwitterAgent

    _require_twitter()
    try:
        tweets = await TwitterAgent().get_timeline(
            bearer_token=settings.TWITTER_BEARER_TOKEN,
            user_id=user_id,
            max_results=max_results,
        )
    except Exception as exc:
        logger.error("Twitter timeline fetch failed: %s", exc)
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
        )
    except Exception as exc:
        logger.error("Twitter reply generation failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    return ReplyResponse(reply_text=reply_text, posted=False, tweet_id=None)


@router.post("/reply/post", response_model=ReplyResponse)
async def post_reply(
    request: ReplyRequest,
    current_user: User = Depends(get_current_user),
):
    """Generate an AI reply to a tweet and post it."""
    from agents.twitter_agent import TwitterAgent

    _require_twitter()
    _require_twitter_write()

    agent = TwitterAgent()
    try:
        reply_text = await agent.generate_reply_text(
            post_content=request.post_content,
            author_handle=request.author_handle,
            context=request.context,
        )
        result = await agent.post_reply(
            api_key=settings.TWITTER_API_KEY,
            api_secret=settings.TWITTER_API_SECRET,
            access_token=settings.TWITTER_ACCESS_TOKEN,
            access_secret=settings.TWITTER_ACCESS_SECRET,
            tweet_id=request.tweet_id,
            text=reply_text,
        )
    except Exception as exc:
        logger.error("Twitter post reply failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    posted_id = result.get("data", {}).get("id") if isinstance(result, dict) else None
    return ReplyResponse(reply_text=reply_text, posted=True, tweet_id=posted_id)


@router.post("/sync")
async def sync_twitter_mentions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually fetch new Twitter mentions and store them in the database."""
    from agents.twitter_agent import TwitterAgent
    from models.message import Message, MessageSource, MessagePriority, MessageStatus
    from datetime import datetime
    from services.ai_pipeline import process_message_ai

    _require_twitter()
    twitter_user_id = settings.TWITTER_USER_ID
    if not twitter_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TWITTER_USER_ID is not configured in settings."
        )

    try:
        tweets = await TwitterAgent().get_mentions(
            bearer_token=settings.TWITTER_BEARER_TOKEN,
            user_id=twitter_user_id,
            max_results=10,
        )
    except Exception as exc:
        logger.error("Twitter sync get_mentions failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    synced_count = 0
    for t in tweets:
        tweet_id = t.get("id")
        if not tweet_id:
            continue

        existing = db.query(Message).filter_by(message_id=tweet_id, source=MessageSource.TWITTER).first()
        if existing:
            continue

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
        # Run AI pipeline
        try:
            await process_message_ai(db, db_msg)
        except Exception as e:
            logger.error("Twitter sync AI pipeline failed for tweet %s: %s", tweet_id, e)

    return {"synced": synced_count, "total_stored": synced_count, "status": "success"}


async def verify_twitter_signature(request: Request) -> bytes:
    """Validate signature to ensure incoming payload is genuinely from Twitter/X."""
    signature = request.headers.get("X-Twitter-Webhooks-Signature")
    if not signature:
        logger.warning("Twitter Webhook: Missing signature header.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing signature header."
        )

    received_sig = signature.split("sha256=")[1] if "sha256=" in signature else signature
    raw_body = await request.body()
    secret = settings.TWITTER_API_SECRET or "twitter_api_secret"
    
    computed_sig = hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(received_sig, computed_sig):
        logger.warning("Twitter Webhook: HMAC signature validation failed.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="HMAC signature validation failed."
        )

    return raw_body


async def process_twitter_payload_async(body: dict) -> None:
    """Asynchronously process incoming Twitter webhook payload."""
    from database import SessionLocal
    from models.message import Message, MessageSource, MessagePriority, MessageStatus
    from datetime import datetime
    from services.ai_pipeline import process_message_ai
    from models.user import User

    db = SessionLocal()
    try:
        tweet_id = body.get("tweet_id")
        author_id = body.get("author_id", "TwitterUser")
        text = body.get("text", "")

        if not tweet_id:
            logger.warning("Twitter Webhook: Missing tweet_id in payload.")
            return

        logger.info("Background Twitter processing: tweet %s from %s", tweet_id, author_id)

        # Skip if already exists
        existing = db.query(Message).filter_by(message_id=tweet_id, source=MessageSource.TWITTER).first()
        if existing:
            logger.info("Twitter message %s already exists in database.", tweet_id)
            return

        # Find user
        user = db.query(User).first()
        user_id = user.id if user else 1

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

        # Trigger AI pipeline
        try:
            await process_message_ai(db, db_msg)
        except Exception as e:
            logger.error("Failed to run AI pipeline for Twitter message %s: %s", tweet_id, e)

    except Exception as exc:
        logger.error("Background Twitter processing error: %s", exc)
    finally:
        db.close()


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def twitter_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """
    Handle incoming Twitter mentions/DMs webhook.
    Verifies signature and processes the payload asynchronously in the background.
    """
    raw_body = await verify_twitter_signature(request)
    try:
        body = json.loads(raw_body.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON payload: {exc}"
        )

    background_tasks.add_task(process_twitter_payload_async, body)
    return {"status": "ok"}
