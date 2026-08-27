"""
Sidekick AI — Auto Pilot Service & Policy Engine

Core background automation engine responsible for:
- Continuous background monitoring of connected integrations (Gmail, Slack, Telegram, Twitter)
- Controlled decision hierarchy & risk validation (Low Risk = Auto Executed, Medium/High Risk = Proactive Action Queue)
- Automated newsletter classification, reply draft generation, memory extraction, and planner task extraction
- Persistent user toggle state & traceable activity logging
"""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from database import SessionLocal
from models.autopilot_config import AutoPilotConfig
from models.autopilot_activity import AutoPilotActivity
from models.message import Message, MessagePriority, MessageSource, MessageStatus
from models.token import OAuthToken
from models.user import User
from repositories.token_repo import TokenRepository
from services.llm import LLMClient
from services.planner_service import PlannerService

logger = logging.getLogger(__name__)


class AutoPilotService:
    """Service layer executing Auto Pilot background automation and policy evaluation."""

    @staticmethod
    def get_or_create_config(db: Session, user_id: str) -> AutoPilotConfig:
        """Fetch or initialize the user's AutoPilotConfig."""
        user_id_str = str(user_id)
        config = db.query(AutoPilotConfig).filter_by(user_id=user_id_str).first()
        if not config:
            config = AutoPilotConfig(
                user_id=user_id_str,
                is_enabled=True,
                last_status="active",
            )
            db.add(config)
            db.commit()
            db.refresh(config)
        return config

    @staticmethod
    def toggle_autopilot(db: Session, user_id: str, is_enabled: bool) -> AutoPilotConfig:
        """Toggle Auto Pilot state with database persistence."""
        config = AutoPilotService.get_or_create_config(db, user_id)
        config.is_enabled = is_enabled
        config.last_status = "active" if is_enabled else "paused"
        config.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(config)
        logger.info("User %s toggled Auto Pilot: is_enabled=%s", user_id, is_enabled)
        return config

    @staticmethod
    def log_activity(
        db: Session,
        user_id: str,
        source: str,
        action_type: str,
        title: str,
        description: Optional[str] = None,
        status: str = "auto_executed",
        confidence_score: int = 90,
        risk_level: str = "low",
        source_item_id: Optional[str] = None,
    ) -> AutoPilotActivity:
        """Log a traceable Auto Pilot activity entry with deduplication on source_item_id."""
        user_id_str = str(user_id)

        if source_item_id:
            existing = (
                db.query(AutoPilotActivity)
                .filter(
                    AutoPilotActivity.user_id == user_id_str,
                    AutoPilotActivity.source_item_id == str(source_item_id),
                    AutoPilotActivity.action_type == action_type,
                )
                .first()
            )
            if existing:
                existing.status = status
                existing.title = title
                if description:
                    existing.description = description
                db.commit()
                db.refresh(existing)
                return existing

        activity = AutoPilotActivity(
            user_id=user_id_str,
            source=source,
            source_item_id=str(source_item_id) if source_item_id else None,
            action_type=action_type,
            title=title,
            description=description,
            status=status,
            confidence_score=confidence_score,
            risk_level=risk_level,
        )
        db.add(activity)
        db.commit()
        db.refresh(activity)
        return activity

    @staticmethod
    def get_active_monitored_sources(db: Session, user_id: str) -> List[Dict[str, Any]]:
        """Check active connected application accounts for the user."""
        user_id_str = str(user_id)
        sources = []

        # 1. Gmail / Google
        gmail_token = db.query(OAuthToken).filter_by(user_id=user_id_str, provider="google").first()
        if gmail_token and gmail_token.access_token:
            sources.append({"id": "gmail", "name": "Google / Gmail", "is_connected": True, "status": "Active"})
        else:
            sources.append({"id": "gmail", "name": "Google / Gmail", "is_connected": False, "status": "Offline"})

        # 2. Slack
        tokens = TokenRepository.list_by_user(db, user_id_str)
        slack_tok = next((t for t in tokens if t.provider == "slack" and t.access_token and t.access_token != "disabled"), None)
        if slack_tok:
            sources.append({"id": "slack", "name": "Slack", "is_connected": True, "status": "Active"})
        else:
            sources.append({"id": "slack", "name": "Slack", "is_connected": False, "status": "Offline"})

        # 3. Telegram
        telegram_tok = next((t for t in tokens if t.provider == "telegram" and t.access_token and t.access_token != "disabled"), None)
        if telegram_tok:
            sources.append({"id": "telegram", "name": "Telegram", "is_connected": True, "status": "Active"})
        else:
            sources.append({"id": "telegram", "name": "Telegram", "is_connected": False, "status": "Offline"})

        # 4. Twitter / X
        twitter_tok = next((t for t in tokens if t.provider == "twitter" and t.access_token and t.access_token != "disabled"), None)
        if twitter_tok:
            sources.append({"id": "twitter", "name": "Twitter / X", "is_connected": True, "status": "Active"})
        else:
            sources.append({"id": "twitter", "name": "Twitter / X", "is_connected": False, "status": "Offline"})

        return sources

    @staticmethod
    async def run_autopilot_cycle(db: Session, user_id: str) -> Dict[str, Any]:
        """
        Execute full asynchronous Auto Pilot background cycle:
        - Check active integrations
        - Check ON/OFF toggle state
        - Process unprocessed messages
        - Classify low-priority items
        - Generate reply drafts for Proactive Action Queue
        - Extract long-term memory & planner tasks
        - Update statistics & logs
        """
        user_id_str = str(user_id)
        config = AutoPilotService.get_or_create_config(db, user_id_str)

        if not config.is_enabled:
            config.last_status = "paused"
            db.commit()
            return {"status": "paused", "message": "Auto Pilot is disabled."}

        monitored_sources = AutoPilotService.get_active_monitored_sources(db, user_id_str)
        active_sources = [s for s in monitored_sources if s["is_connected"]]

        if not active_sources:
            config.last_status = "waiting_for_connection"
            db.commit()
            return {
                "status": "waiting_for_connection",
                "message": "No connected applications available for Auto Pilot.",
                "monitored_sources": monitored_sources,
            }

        config.last_status = "processing"
        db.commit()

        processed_count = 0
        actions_count = 0

        try:
            # Fetch unread / unprocessed messages
            unprocessed_msgs = (
                db.query(Message)
                .filter(Message.user_id == user_id_str, Message.is_processed == False)
                .order_by(Message.received_at.desc())
                .limit(20)
                .all()
            )

            llm_client = LLMClient()

            for msg in unprocessed_msgs:
                processed_count += 1
                source_name = msg.source.value if hasattr(msg.source, "value") else str(msg.source)
                msg_source_id = f"msg_{msg.id}"

                # 1. Run single-pass message analysis
                from services.ai_pipeline import analyze_message_single_pass
                await analyze_message_single_pass(db=db, message=msg, llm_client=llm_client)

                # 2. Automated sender / Newsletter policy check
                sender_lower = (msg.sender or "").lower()
                subject_lower = (msg.subject or "").lower()
                is_automated = any(k in sender_lower or k in subject_lower for k in ["noreply", "no-reply", "security alert", "receipt", "verification", "newsletter"])

                if is_automated:
                    msg.requires_reply = False
                    msg.suggested_reply = ""
                    db.commit()

                    AutoPilotService.log_activity(
                        db=db,
                        user_id=user_id_str,
                        source=source_name,
                        action_type="classified_newsletter",
                        title=f"Classified notification from {msg.sender}",
                        description=f"Subject: {msg.subject or '(no subject)'}",
                        status="auto_executed",
                        confidence_score=98,
                        risk_level="low",
                        source_item_id=f"auto_class_{msg.id}",
                    )
                    actions_count += 1

                # 3. Actionable reply request -> Route to Proactive Action Queue with reply draft
                elif msg.requires_reply:
                    if not msg.suggested_reply or len(msg.suggested_reply.strip()) < 10:
                        try:
                            from agents.reply_agent import ReplyAgent
                            draft = await ReplyAgent().generate_reply(
                                message=msg,
                                context="Generate a professional, concise executive response.",
                                user_id=user_id_str,
                                db=db,
                            )
                            if draft and not draft.startswith("Failed to generate"):
                                msg.suggested_reply = draft
                                db.commit()
                        except Exception as draft_err:
                            logger.warning("Auto Pilot reply draft generation failed for msg %s: %s", msg.id, draft_err)

                    AutoPilotService.log_activity(
                        db=db,
                        user_id=user_id_str,
                        source=source_name,
                        action_type="generated_reply_draft",
                        title=f"Reply draft created for {msg.sender}",
                        description=f"Subject: {msg.subject or '(no subject)'}",
                        status="pending_user_review",
                        confidence_score=90,
                        risk_level="medium",
                        source_item_id=f"auto_draft_{msg.id}",
                    )
                    actions_count += 1

                # 4. Long-term memory extraction
                if config.auto_extract_memory and msg.body and len(msg.body) > 30:
                    try:
                        from services.memory_pipeline import extract_and_save_durable_fact
                        saved_mems = await extract_and_save_durable_fact(db=db, user_id=user_id_str, source_text=msg.body, llm_client=llm_client)
                        if saved_mems:
                            AutoPilotService.log_activity(
                                db=db,
                                user_id=user_id_str,
                                source=source_name,
                                action_type="extracted_memory",
                                title=f"Saved {len(saved_mems)} memory item(s) from {msg.sender}",
                                description=f"Fact: {saved_mems[0].content}",
                                status="auto_executed",
                                confidence_score=85,
                                risk_level="low",
                                source_item_id=f"auto_mem_{msg.id}",
                            )
                            actions_count += 1
                    except Exception as mem_err:
                        logger.warning("Auto Pilot memory extraction failed for msg %s: %s", msg.id, mem_err)

                # 5. Planner task extraction
                if config.auto_extract_tasks:
                    try:
                        extracted_tasks = PlannerService.extract_tasks_from_messages(db=db, user_id=user_id_str)
                        if extracted_tasks:
                            AutoPilotService.log_activity(
                                db=db,
                                user_id=user_id_str,
                                source=source_name,
                                action_type="extracted_planner_task",
                                title=f"Extracted task: {extracted_tasks[0].title}",
                                description=f"Priority: {extracted_tasks[0].priority.upper()}",
                                status="auto_executed",
                                confidence_score=90,
                                risk_level="low",
                                source_item_id=f"auto_task_{msg.id}",
                            )
                            actions_count += 1
                    except Exception as task_err:
                        logger.warning("Auto Pilot task extraction failed for msg %s: %s", msg.id, task_err)

            # Finalize status & metrics
            config.last_run_at = datetime.utcnow()
            config.last_status = "active"
            config.processed_today_count += processed_count
            config.actions_taken_count += actions_count
            config.last_error = None
            db.commit()

            return {
                "status": "active",
                "processed_count": processed_count,
                "actions_count": actions_count,
                "monitored_sources": monitored_sources,
            }

        except Exception as exc:
            logger.error("Auto Pilot cycle encountered error for user %s: %s", user_id, exc, exc_info=True)
            config.last_status = "error"
            config.last_error = str(exc)
            db.commit()
            return {"status": "error", "error": str(exc), "monitored_sources": monitored_sources}

    @staticmethod
    def get_dashboard_summary(db: Session, user_id: str) -> Dict[str, Any]:
        """Consolidate Auto Pilot summary metrics specifically for Dashboard & management page."""
        user_id_str = str(user_id)
        config = AutoPilotService.get_or_create_config(db, user_id_str)
        monitored_sources = AutoPilotService.get_active_monitored_sources(db, user_id_str)
        active_sources = [s for s in monitored_sources if s["is_connected"]]

        # If zero connected integrations, override last_status
        effective_status = config.last_status
        if not active_sources:
            effective_status = "waiting_for_connection"
        elif not config.is_enabled:
            effective_status = "paused"

        # Action Queue items waiting for user review
        pending_review_items = (
            db.query(Message)
            .filter(
                Message.user_id == user_id_str,
                Message.requires_reply == True,
                Message.status == MessageStatus.UNREAD,
            )
            .order_by(Message.received_at.desc())
            .all()
        )

        # Recent activities
        recent_activities = (
            db.query(AutoPilotActivity)
            .filter(AutoPilotActivity.user_id == user_id_str)
            .order_by(AutoPilotActivity.created_at.desc())
            .limit(10)
            .all()
        )

        return {
            "is_enabled": config.is_enabled,
            "status": effective_status,
            "last_run_at": config.last_run_at.isoformat() if config.last_run_at else None,
            "last_error": config.last_error,
            "processed_today_count": config.processed_today_count,
            "actions_taken_count": config.actions_taken_count,
            "pending_review_count": len(pending_review_items),
            "monitored_sources": monitored_sources,
            "active_sources_count": len(active_sources),
            "pending_review_items": [
                {
                    "id": m.id,
                    "sender": m.sender,
                    "subject": m.subject,
                    "source": m.source.value if hasattr(m.source, "value") else str(m.source),
                    "suggested_reply": m.suggested_reply,
                    "received_at": m.received_at.isoformat() if m.received_at else None,
                }
                for m in pending_review_items[:5]
            ],
            "recent_activities": [a.to_dict() for a in recent_activities],
        }
