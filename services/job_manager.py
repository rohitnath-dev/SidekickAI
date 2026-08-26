"""
Sidekick AI — Authoritative Processing Job Manager

Manages long-running Sync & AI processing jobs per user.
Provides idempotency, state recovery, stale job cleanup,
and 24-hour data window configuration.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from enum import Enum
import logging
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy.orm import Session

from database import SessionLocal
from config import settings

logger = logging.getLogger(__name__)

# Configurable processing window (24 hours default)
HOURS_LOOKBACK = 24


class AIJobState(str, Enum):
    QUEUED = "queued"
    STARTING = "starting"
    CHECKING_CONNECTIONS = "checking_connections"
    SYNCING = "syncing"
    PROCESSING = "processing"
    DASHBOARD_READY = "dashboard_ready"
    BACKGROUND_PROCESSING = "background_processing"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    STALE = "stale"


class ProcessingJob:
    """In-memory authoritative processing job object per user."""

    def __init__(self, job_id: str, user_id: str):
        self.job_id: str = job_id
        self.user_id: str = user_id
        self.state: AIJobState = AIJobState.QUEUED
        self.current_stage: str = "Job initialized"
        self.connected_integrations: List[Dict[str, Any]] = []
        self.total_items_discovered: int = 0
        self.items_processed: int = 0
        self.errors: List[str] = []
        self.briefing: Optional[Dict[str, Any]] = None
        self.created_at: datetime = datetime.utcnow()
        self.updated_at: datetime = datetime.utcnow()
        self.completed_at: Optional[datetime] = None

    def update_stage(
        self,
        state: AIJobState,
        stage: str,
        discovered: Optional[int] = None,
        processed: Optional[int] = None,
    ):
        self.state = state
        self.current_stage = stage
        if discovered is not None:
            self.total_items_discovered = discovered
        if processed is not None:
            self.items_processed = processed
        self.updated_at = datetime.utcnow()

    def add_error(self, error_msg: str):
        self.errors.append(error_msg)
        self.updated_at = datetime.utcnow()

    def heartbeat(self):
        self.updated_at = datetime.utcnow()

    def mark_dashboard_ready(self, briefing_data: Optional[Dict[str, Any]] = None):
        self.state = AIJobState.DASHBOARD_READY
        self.current_stage = "Dashboard data ready. Continuing background processing..."
        if briefing_data:
            self.briefing = briefing_data
        self.updated_at = datetime.utcnow()

    def mark_completed(self, briefing_data: Optional[Dict[str, Any]] = None):
        self.state = AIJobState.COMPLETED
        self.current_stage = "Processing completed successfully"
        if briefing_data:
            self.briefing = briefing_data
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def mark_failed(self, error_msg: str):
        self.state = AIJobState.FAILED
        self.current_stage = f"Failed: {error_msg}"
        self.add_error(error_msg)
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "user_id": self.user_id,
            "state": self.state.value,
            "current_stage": self.current_stage,
            "connected_integrations": self.connected_integrations,
            "total_items_discovered": self.total_items_discovered,
            "items_processed": self.items_processed,
            "errors": self.errors,
            "briefing": self.briefing,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "has_connected_sources": len(self.connected_integrations) > 0,
        }


class AIJobManager:
    """Manages active jobs and prevents duplicate runs per user."""

    def __init__(self):
        self._user_jobs: Dict[str, ProcessingJob] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._running_tasks: Dict[str, asyncio.Task] = {}

    def _get_lock(self, user_id: str) -> asyncio.Lock:
        if user_id not in self._locks:
            self._locks[user_id] = asyncio.Lock()
        return self._locks[user_id]

    def get_job(self, user_id: str) -> Optional[ProcessingJob]:
        user_id_str = str(user_id)
        job = self._user_jobs.get(user_id_str)
        if not job:
            return None

        # Check active background task handle
        task = self._running_tasks.get(user_id_str)
        if task and not task.done():
            # Task is actively running, ensure heartbeat is fresh
            if (datetime.utcnow() - job.updated_at) > timedelta(seconds=30):
                job.heartbeat()
            return job

        # Check for genuine stale job (>120s without update while task is dead/inactive)
        if (
            job.state not in (AIJobState.COMPLETED, AIJobState.FAILED, AIJobState.CANCELLED, AIJobState.STALE)
            and (datetime.utcnow() - job.updated_at) > timedelta(seconds=120)
        ):
            logger.warning("Job %s for user %s detected as stale (inactive >120s). Marking STALE.", job.job_id, user_id_str)
            job.state = AIJobState.STALE
            job.current_stage = "Job timed out / stale"

        return job

    async def start_job(
        self,
        user_id: str | int,
        db: Session,
        llm_config: Optional[Any] = None,
    ) -> ProcessingJob:
        user_id_str = str(user_id)
        lock = self._get_lock(user_id_str)

        async with lock:
            existing = self.get_job(user_id_str)
            if existing and existing.state not in (
                AIJobState.COMPLETED,
                AIJobState.FAILED,
                AIJobState.CANCELLED,
                AIJobState.STALE,
            ):
                logger.info("Reusing active processing job %s for user_id=%s", existing.job_id, user_id_str)
                return existing

            # Create new job
            job_id = f"job-{uuid.uuid4().hex[:12]}"
            job = ProcessingJob(job_id=job_id, user_id=user_id_str)
            self._user_jobs[user_id_str] = job

            # Launch async background task for sync & processing
            task = asyncio.create_task(self._run_job_lifecycle(job_id, user_id_str, llm_config))
            self._running_tasks[user_id_str] = task
            return job

    async def cancel_job(self, user_id: str | int) -> bool:
        job = self.get_job(str(user_id))
        if job and job.state not in (AIJobState.COMPLETED, AIJobState.FAILED, AIJobState.CANCELLED):
            job.state = AIJobState.CANCELLED
            job.current_stage = "Job cancelled by user"
            job.updated_at = datetime.utcnow()
            return True
        return False

    async def _run_job_lifecycle(self, job_id: str, user_id: str, llm_config: Optional[Any]):
        job = self._user_jobs.get(user_id)
        if not job or job.job_id != job_id:
            return

        start_time = datetime.utcnow()
        logger.info("Starting AI job lifecycle job_id=%s user_id=%s", job_id, user_id)

        try:
            job.update_stage(AIJobState.STARTING, "Initializing processing pipeline...")

            # Stage 1: Detect connected integrations
            job.update_stage(AIJobState.CHECKING_CONNECTIONS, "Checking connected integrations...")
            
            with SessionLocal() as db:
                from repositories.token_repo import TokenRepository
                tokens = TokenRepository.list_by_user(db, user_id)

                connected_services: List[Dict[str, Any]] = []

                # Gmail
                gmail_tok = next((t for t in tokens if t.provider == "google"), None)
                if gmail_tok and gmail_tok.access_token and gmail_tok.access_token != "disabled":
                    connected_services.append({"provider": "gmail", "name": "Google / Gmail", "status": "pending", "synced": 0})

                # Telegram
                if any(t.provider == "telegram" and t.access_token and t.access_token != "disabled" for t in tokens):
                    connected_services.append({"provider": "telegram", "name": "Telegram", "status": "pending", "synced": 0})

                # Slack
                slack_tok = next((t for t in tokens if t.provider == "slack"), None)
                if slack_tok and slack_tok.access_token and slack_tok.access_token != "disabled":
                    connected_services.append({"provider": "slack", "name": "Slack", "status": "pending", "synced": 0})

                # Twitter
                if settings.TWITTER_BEARER_TOKEN and settings.TWITTER_USER_ID:
                    disabled_tok = next((t for t in tokens if t.provider == "twitter"), None)
                    if not (disabled_tok and disabled_tok.access_token == "disabled"):
                        connected_services.append({"provider": "twitter", "name": "Twitter / X", "status": "pending", "synced": 0})

                job.connected_integrations = connected_services

            # Case A: Zero connected applications
            if not connected_services:
                logger.info("Job %s: Zero connected applications found for user %s.", job_id, user_id)
                job.mark_completed()
                job.current_stage = "No connected applications found. You can connect services later from Settings."
                return

            if job.state == AIJobState.CANCELLED:
                return

            # Stage 2: Sync 24-hour data from connected services
            job.update_stage(AIJobState.SYNCING, "Syncing recent data from connected services...")
            total_discovered = 0

            with SessionLocal() as db:
                from models.user import User as UserModel
                current_user = db.query(UserModel).filter_by(id=user_id).first()

                for service in connected_services:
                    if job.state == AIJobState.CANCELLED:
                        return

                    provider = service["provider"]
                    service["status"] = "syncing"
                    job.update_stage(AIJobState.SYNCING, f"Syncing {service['name']}...")

                    try:
                        synced_count = 0
                        if provider == "gmail":
                            from services.oauth import get_credentials
                            from agents.gmail_agent import GmailAgent
                            creds = get_credentials(user_id, db)
                            if creds:
                                agent = GmailAgent()
                                res = await agent.sync_messages(creds=creds, db=db, user_id=user_id, limit=20)
                                synced_count = res.get("synced", 0) if isinstance(res, dict) else 0

                        elif provider == "telegram":
                            from routes.telegram import sync_telegram
                            if current_user:
                                res = await sync_telegram(current_user=current_user, db=db)
                                synced_count = getattr(res, "synced", 0) if hasattr(res, "synced") else (res.get("synced", 0) if isinstance(res, dict) else 0)

                        elif provider == "slack":
                            from agents.slack_agent import SlackAgent
                            slack_t = next((t for t in tokens if t.provider == "slack"), None)
                            if slack_t and slack_t.access_token:
                                agent = SlackAgent()
                                res = await agent.sync_slack(access_token=slack_t.access_token, db=db, user_id=user_id, limit=20)
                                synced_count = res.get("synced", 0) if isinstance(res, dict) else 0

                        elif provider == "twitter":
                            from routes.twitter import sync_twitter_mentions
                            if current_user:
                                res = await sync_twitter_mentions(current_user=current_user, db=db)
                                synced_count = res.get("synced", 0) if isinstance(res, dict) else 0

                        service["status"] = "synced"
                        service["synced"] = synced_count
                        total_discovered += synced_count

                    except Exception as sync_err:
                        logger.error("Job %s: Sync failed for provider %s: %s", job_id, provider, sync_err)
                        service["status"] = "failed"
                        service["error"] = str(sync_err)
                        job.add_error(f"{service['name']}: {str(sync_err)}")

            job.total_items_discovered = total_discovered

            if job.state == AIJobState.CANCELLED:
                return

            # Stage 3: CRITICAL FAST PATH (Analyzing top candidate messages + generating Executive Briefing)
            job.update_stage(AIJobState.PROCESSING, "Running fast-path AI analysis...", discovered=total_discovered, processed=0)

            with SessionLocal() as db:
                from models.message import Message
                from services.ai_pipeline import analyze_message_single_pass
                from services.llm import (
                    LLMClient,
                    LLMRateLimitError,
                    LLMAuthenticationError,
                    LLMConnectionError,
                    LLMResponseError,
                    LLMException,
                )

                cutoff_24h = datetime.utcnow() - timedelta(hours=HOURS_LOOKBACK)
                unprocessed = (
                    db.query(Message)
                    .filter(
                        Message.user_id == user_id,
                        Message.is_processed == False,
                        Message.received_at >= cutoff_24h,
                    )
                    .order_by(Message.received_at.desc())
                    .limit(20)
                    .all()
                )

                if not unprocessed:
                    unprocessed = (
                        db.query(Message)
                        .filter(
                            Message.user_id == user_id,
                            Message.is_processed == False,
                        )
                        .order_by(Message.received_at.desc())
                        .limit(20)
                        .all()
                    )

                try:
                    client = LLMClient(user_id=user_id)
                except LLMException as exc:
                    error_msg = f"AI provider configuration error: {str(exc)}"
                    logger.warning("Job %s: LLM client creation failed for user %s: %s", job_id, user_id, exc)
                    job.mark_failed(error_msg)
                    return

                processed_count = 0
                failed_count = 0

                # Fast Path: Process top 5 urgent communications first
                fast_path_batch = unprocessed[:5]
                background_batch = unprocessed[5:]

                for msg in fast_path_batch:
                    if job.state == AIJobState.CANCELLED:
                        return
                    try:
                        await analyze_message_single_pass(db=db, message=msg, llm_client=client)
                        processed_count += 1
                        job.update_stage(
                            AIJobState.PROCESSING,
                            f"Analyzed fast-path communication {processed_count} of {len(fast_path_batch)}",
                            processed=processed_count,
                        )
                    except LLMRateLimitError as exc:
                        error_msg = "Your AI provider is temporarily rate-limiting requests. You can retry when processing becomes available."
                        logger.warning("Rate limit encountered in job %s for user %s: %s", job_id, user_id, exc)
                        job.mark_failed(error_msg)
                        return
                    except LLMAuthenticationError as exc:
                        error_msg = "AI provider authentication failed. Please check your API key in Settings."
                        logger.warning("Auth error in job %s for user %s: %s", job_id, user_id, exc)
                        job.mark_failed(error_msg)
                        return
                    except (LLMConnectionError, LLMResponseError, LLMException, Exception) as exc:
                        failed_count += 1
                        logger.error("AI fast-path processing failed for msg %s in job %s: %s", msg.id, job_id, exc)
                        job.add_error(f"Message {msg.id}: {str(exc)}")

                # Generate Executive Daily Briefing for Fast Path
                job.heartbeat()
                briefing_data = None
                try:
                    from agents.planner_agent import PlannerAgent
                    from routes.planner import cache_briefing
                    from services.oauth import get_credentials

                    creds = get_credentials(user_id, db)
                    planner_agent = PlannerAgent(llm_client=client)
                    briefing_data = await planner_agent.generate_daily_briefing(user_id=user_id, db=db, creds=creds)
                    cache_briefing(user_id, briefing_data)
                except Exception as briefing_err:
                    logger.error("Job %s: Fast-path briefing generation failed: %s", job_id, briefing_err)
                    job.add_error("Daily briefing generation failed.")

                # Mark DASHBOARD_READY: User can now load the executive dashboard!
                job.mark_dashboard_ready(briefing_data=briefing_data)
                logger.info("Job %s reached DASHBOARD_READY for user_id=%s in %.2fs", job_id, user_id, (datetime.utcnow() - start_time).total_seconds())

                if job.state == AIJobState.CANCELLED:
                    return

                # Stage 4: BACKGROUND DEFERRED PATH (Process remaining messages & memories)
                if background_batch:
                    job.update_stage(
                        AIJobState.BACKGROUND_PROCESSING,
                        f"Continuing background processing ({len(background_batch)} items remaining)...",
                        processed=processed_count,
                    )

                    for msg in background_batch:
                        if job.state == AIJobState.CANCELLED:
                            return
                        try:
                            await analyze_message_single_pass(db=db, message=msg, llm_client=client)
                            processed_count += 1
                            job.update_stage(
                                AIJobState.BACKGROUND_PROCESSING,
                                f"Processed communication {processed_count} of {len(unprocessed)}",
                                processed=processed_count,
                            )
                        except Exception as bg_err:
                            logger.error("Background AI processing failed for msg %s: %s", msg.id, bg_err)

                # Extract and persist long-term memories in background
                from agents.memory_agent import MemoryAgent
                memory_agent = MemoryAgent(llm_client=client)
                for msg in (fast_path_batch + background_batch):
                    if job.state == AIJobState.CANCELLED:
                        return
                    try:
                        await memory_agent.extract_and_save_memory(message=msg, user_id=user_id, db=db)
                        job.heartbeat()
                    except Exception as mem_err:
                        logger.warning("Background memory extraction error for msg %s: %s", msg.id, mem_err)

            # Stage 5: Mark Completed
            job.mark_completed(briefing_data=briefing_data)
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info("Job %s completed successfully for user_id=%s in %.2fs (provider=%s)", job_id, user_id, duration, getattr(client, "provider", "unknown"))

        except asyncio.CancelledError:
            logger.info("Job %s for user_id=%s was cancelled", job_id, user_id)
            if job.state not in (AIJobState.COMPLETED, AIJobState.FAILED, AIJobState.CANCELLED):
                job.state = AIJobState.CANCELLED
                job.current_stage = "Job cancelled"
        except Exception as fatal_err:
            logger.error("Job %s encountered fatal error for user_id=%s: %s", job_id, user_id, fatal_err, exc_info=True)
            job.mark_failed(f"AI processing pipeline error: {str(fatal_err)}")


# Global Singleton Manager Instance
job_manager = AIJobManager()
