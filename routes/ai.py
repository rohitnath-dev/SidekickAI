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

from collections import defaultdict
import asyncio

_ai_run_locks = defaultdict(asyncio.Lock)
class TestPromptRequest(BaseModel):
    prompt: Optional[str] = "Hello, are you working?"

class AnalyzeMessageRequest(BaseModel):
    message_id: Optional[int] = None

@router.get("/health")
async def ai_health(current_user: User = Depends(get_current_user)):
    """Check health of the active LLM provider connection."""
    try:
        return await llm.health_check_details()
    except Exception as exc:
        logger.error("LLM health check exception: %s", exc, exc_info=True)
        return {
            "status": "error",
            "provider": "Unknown",
            "reason": f"Connection check failed: {exc}"
        }

@router.post("/test")
async def ai_test(
    request: TestPromptRequest,
    current_user: User = Depends(get_current_user)
):
    """Send a test prompt to verify LLM responsiveness."""
    from config import settings
    
    has_or_key = bool(llm.api_key and llm.api_key.strip() != "")
    has_gemini_key = bool(settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip() != "")
    
    if not has_or_key and not has_gemini_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No LLM API key configured. Please set OPENROUTER_API_KEY or GEMINI_API_KEY."
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
    lock = _ai_run_locks[current_user.id]
    if lock.locked():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="AI processing is already in progress. Please wait."
        )
        
    async with lock:
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


@router.post("/run")
async def run_ai_pipeline(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Run the full AI processing pipeline:
    1. Process all unprocessed messages (run priority, summary, suggested reply drafts, etc.)
    2. Generate/regenerate the daily executive briefing and save it to the cache.
    """
    lock = _ai_run_locks[current_user.id]
    if lock.locked():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="AI processing is already in progress. Please wait."
        )

    async with lock:
        from models.message import Message
        from services.ai_pipeline import process_message_ai
        from agents.planner_agent import PlannerAgent
        
        # 1. Process all unprocessed messages
        unprocessed = db.query(Message).filter(
            Message.user_id == current_user.id,
            Message.is_processed == False
        ).all()
        
        processed_count = 0
        errors = []
        
        for msg in unprocessed:
            try:
                logger.info("Running process_message_ai for message_id=%d", msg.id)
                await process_message_ai(db, msg)
                processed_count += 1
            except Exception as exc:
                logger.error("AI pipeline failed for message %d: %s", msg.id, exc, exc_info=True)
                errors.append(f"Message {msg.id}: {str(exc)}")
                
        # 2. Generate/regenerate the daily executive briefing
        briefing_status = "success"
        briefing_data = None
        try:
            from routes.planner import cache_briefing
            from services.oauth import get_credentials
            
            logger.info("Regenerating daily briefing as part of Run AI for user %d", current_user.id)
            creds = get_credentials(current_user.id, db)
            briefing_data = await PlannerAgent().generate_daily_briefing(
                user_id=current_user.id,
                db=db,
                creds=creds
            )
            
            # Cache the newly generated briefing
            cache_briefing(current_user.id, briefing_data)
        except Exception as exc:
            logger.error("Failed to generate daily briefing: %s", exc, exc_info=True)
            errors.append(f"Briefing: {str(exc)}")
            briefing_status = "failed"
            
        status_str = "success" if not errors else "partial_failure"
        if len(errors) > 0 and processed_count == 0 and briefing_status == "failed":
            status_str = "failure"
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"AI pipeline run failed: {'; '.join(errors)}"
            )
            
        return {
            "status": status_str,
            "processed_count": processed_count,
            "briefing_status": briefing_status,
            "briefing": briefing_data,
            "errors": errors
        }
