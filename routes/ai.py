"""AI/LLM debugging and testing routes."""

from __future__ import annotations

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models.user import User
from services.llm import llm, LLMException
from models.message import Message
from services.ai_pipeline import process_message_ai

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["AI"])

class TestPromptRequest(BaseModel):
    prompt: Optional[str] = "Hello, are you working?"

class AnalyzeMessageRequest(BaseModel):
    message_id: Optional[int] = None

@router.get("/health")
async def ai_health(current_user: User = Depends(get_current_user)):
    """Check health of the LLM provider connection."""
    if not llm.api_key:
        return {
            "status": "error",
            "provider": "OpenRouter",
            "reason": "API key is not configured in environment variables (OPENROUTER_API_KEY)."
        }
    
    try:
        # Perform actual ping call
        alive = await llm.health_check()
        if alive:
            return {
                "status": "ok",
                "provider": "OpenRouter",
                "model": llm.model
            }
        else:
            return {
                "status": "error",
                "provider": "OpenRouter",
                "reason": "Health check request did not return a successful result."
            }
    except Exception as exc:
        logger.error("LLM health check exception: %s", exc, exc_info=True)
        return {
            "status": "error",
            "provider": "OpenRouter",
            "reason": f"Connection check failed: {exc}"
        }

@router.post("/test")
async def ai_test(
    request: TestPromptRequest,
    current_user: User = Depends(get_current_user)
):
    """Send a test prompt to verify LLM responsiveness."""
    if not llm.api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="LLM API key is missing. Please configure OPENROUTER_API_KEY in settings/environment."
        )
    
    prompt = request.prompt or "Hello, are you working?"
    logger.info("Executing LLM test with prompt: '%s'", prompt)
    
    try:
        response_text = await llm.chat(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100
        )
        return {
            "status": "success",
            "prompt": prompt,
            "response": response_text
        }
    except Exception as exc:
        logger.error("LLM test request failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM request failed: {exc}"
        )

@router.post("/analyze")
async def analyze_messages(
    request: AnalyzeMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Manually trigger AI pipeline processing on a specific message
    or on all unprocessed messages for the user.
    """
    if request.message_id is not None:
        msg = db.query(Message).filter(Message.id == request.message_id, Message.user_id == current_user.id).first()
        if not msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Message with ID {request.message_id} not found."
            )
        try:
            logger.info("Manually running process_message_ai for message_id=%d", msg.id)
            await process_message_ai(db, msg)
            return {"status": "success", "processed_count": 1}
        except Exception as exc:
            logger.error("AI pipeline failed manually for message %d: %s", msg.id, exc, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"AI pipeline failed: {exc}"
            )
    else:
        unprocessed = db.query(Message).filter(
            Message.user_id == current_user.id,
            Message.is_processed == False
        ).all()
        
        if not unprocessed:
            return {"status": "success", "processed_count": 0, "detail": "No unprocessed messages found."}
            
        count = 0
        for msg in unprocessed:
            try:
                logger.info("Manually running process_message_ai for message_id=%d", msg.id)
                await process_message_ai(db, msg)
                count += 1
            except Exception as exc:
                logger.error("AI pipeline failed manually in batch for message %d: %s", msg.id, exc, exc_info=True)
                
        return {"status": "success", "processed_count": count}
