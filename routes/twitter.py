"""Twitter / X routes."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from config import settings
from dependencies import get_current_user
from models.user import User

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
