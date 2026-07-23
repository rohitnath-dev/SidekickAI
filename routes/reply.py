import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from agents.reply_agent import (
    generate_reply,
    regenerate_reply,
    improve_reply,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/reply",
    tags=["Reply"],
)


class ReplyRequest(BaseModel):
    recipient_name: str = Field(..., min_length=1, max_length=100)
    email_content: str = Field(..., min_length=1)
    context: str | None = None
    tone: str = Field(default="professional")
    language: str = Field(default="English")


class ImproveReplyRequest(BaseModel):
    original_email: str = Field(..., min_length=1)
    reply_draft: str = Field(..., min_length=1)


class ReplyResponse(BaseModel):
    reply: str


@router.post(
    "/generate",
    response_model=ReplyResponse,
    status_code=status.HTTP_200_OK,
)
async def generate(
    request: ReplyRequest,
    db: Session = Depends(get_db),
):
    try:
        result = generate_reply(
            recipient_name=request.recipient_name,
            email_content=request.email_content,
            context=request.context,
            tone=request.tone,
            language=request.language,
            db=db,
        )
    except Exception as exc:
        logger.error("Failed to generate reply: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to generate reply.",
        )

    reply_text = _extract_reply_text(result)

    if not reply_text:
        logger.error("Reply generation returned no usable reply text.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Reply generation returned no usable reply text.",
        )

    return ReplyResponse(reply=reply_text)


@router.post(
    "/improve",
    response_model=ReplyResponse,
    status_code=status.HTTP_200_OK,
)
async def improve(
    request: ImproveReplyRequest,
    db: Session = Depends(get_db),
):
    try:
        result = improve_reply(
            original_email=request.original_email,
            reply_draft=request.reply_draft,
            db=db,
        )
    except Exception as exc:
        logger.error("Failed to improve reply: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to improve reply.",
        )

    reply_text = _extract_reply_text(result)

    if not reply_text:
        logger.error("Reply improvement returned no usable reply text.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Reply improvement returned no usable reply text.",
        )

    return ReplyResponse(reply=reply_text)


@router.post(
    "/regenerate",
    response_model=ReplyResponse,
    status_code=status.HTTP_200_OK,
)
async def regenerate(
    request: ReplyRequest,
    db: Session = Depends(get_db),
):
    try:
        result = regenerate_reply(
            recipient_name=request.recipient_name,
            email_content=request.email_content,
            context=request.context,
            tone=request.tone,
            language=request.language,
            db=db,
        )
    except Exception as exc:
        logger.error("Failed to regenerate reply: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to regenerate reply.",
        )

    reply_text = _extract_reply_text(result)

    if not reply_text:
        logger.error("Reply regeneration returned no usable reply text.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Reply regeneration returned no usable reply text.",
        )

    return ReplyResponse(reply=reply_text)


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
)
async def health():
    return {"status": "ok", "service": "Reply API"}


def _extract_reply_text(result) -> str | None:
    if isinstance(result, dict):
        reply_text = result.get("reply")
    else:
        reply_text = getattr(result, "reply", None)

    if not isinstance(reply_text, str):
        return None

    if not reply_text.strip():
        return None

    return reply_text