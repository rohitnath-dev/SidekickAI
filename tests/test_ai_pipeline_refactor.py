"""Unit and integration tests for AI Pipeline Refactor, Fast-Path states, Draft Quality, and Health checks."""

import os
import unittest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

os.environ["SECRET_KEY"] = "test_secret_key_for_sidekick_ai_units_12345"
os.environ["DATABASE_URL"] = "sqlite:///./test_sidekick_pipeline.db"

from fastapi.testclient import TestClient
from app import app
from database import Base, engine, SessionLocal
from models.user import User
from models.ai_config import UserAIConfig
from models.message import Message, MessageSource, MessagePriority
from services.job_manager import job_manager, AIJobState, ProcessingJob
from services.ai_pipeline import analyze_message_single_pass, process_message_ai
from agents.reply_agent import _clean_reply_text, ReplyAgent
from agents.planner_agent import PlannerAgent
from services.auth import create_access_token


class TestAIPipelineRefactor(unittest.TestCase):

    def setUp(self):
        job_manager._user_jobs.clear()
        job_manager._running_tasks.clear()
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        self.client = TestClient(app)

        self.user = User(
            id="refactor-user-uuid-999",
            email="refactor@example.com",
            hashed_password="hashed_pass",
            full_name="Refactor Tester",
            is_active=True,
            onboarding_completed=True,
        )
        self.db.add(self.user)
        self.db.commit()

        self.token = create_access_token(self.user.id)
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)

    def test_clean_reply_text(self):
        # Case A: Plain text
        raw1 = "Hi John,\n\nThanks for reaching out! Let's connect tomorrow.\n\nBest,\nUser"
        self.assertEqual(_clean_reply_text(raw1), raw1)

        # Case B: Markdown code block fence
        raw2 = "```\nHi John,\nThanks for the update!\n```"
        self.assertEqual(_clean_reply_text(raw2), "Hi John,\nThanks for the update!")

        # Case C: JSON formatted string output
        raw3 = '{"reply": "I have received the budget report and will review it."}'
        self.assertEqual(_clean_reply_text(raw3), "I have received the budget report and will review it.")

        # Case D: Preamble prefix
        raw4 = "Here is a suggested reply:\nThanks for your message!"
        self.assertEqual(_clean_reply_text(raw4), "Thanks for your message!")

    def test_single_pass_analysis_mocked(self):
        msg = Message(
            user_id=self.user.id,
            source=MessageSource.GMAIL,
            message_id="msg-single-pass-1",
            sender="boss@example.com",
            subject="Urgent Project Deadline",
            body="Can you please send the Q3 roadmap slides by 4pm today?",
            received_at=datetime.utcnow(),
            is_processed=False,
        )
        self.db.add(msg)
        self.db.commit()

        mock_llm_response = '''{
            "score": 90,
            "priority_level": "critical",
            "requires_reply": true,
            "reason": "Direct request from boss for Q3 slides with 4pm deadline.",
            "summary": "Sender requested Q3 roadmap slides by 4pm today.",
            "sentiment": "urgent",
            "category": "work",
            "action_items": ["Send Q3 roadmap slides by 4pm"]
        }'''

        mock_client = MagicMock()
        mock_client.chat = AsyncMock(return_value=mock_llm_response)

        res = asyncio.run(analyze_message_single_pass(self.db, msg, llm_client=mock_client))

        self.assertEqual(res["score"], 90)
        self.assertEqual(res["priority_level"], "critical")
        self.assertTrue(res["requires_reply"])
        
        # Verify DB persistence
        self.db.refresh(msg)
        self.assertTrue(msg.is_processed)
        self.assertEqual(msg.priority, MessagePriority.CRITICAL)
        self.assertEqual(msg.summary, "Sender requested Q3 roadmap slides by 4pm today.")
        self.assertIn("Send Q3 roadmap slides", msg.action_items)

    def test_active_task_prevents_false_stale(self):
        job = ProcessingJob("job-active-1", self.user.id)
        job.state = AIJobState.PROCESSING
        job.updated_at = datetime.utcnow() - timedelta(minutes=5)
        job_manager._user_jobs[self.user.id] = job

        # Create a mock running task
        mock_task = MagicMock()
        mock_task.done.return_value = False
        job_manager._running_tasks[self.user.id] = mock_task

        # get_job should recognize active task and NOT mark it STALE
        fetched = job_manager.get_job(self.user.id)
        self.assertNotEqual(fetched.state, AIJobState.STALE)
        self.assertEqual(fetched.state, AIJobState.PROCESSING)

    def test_ai_health_endpoint_fast(self):
        # Default config check
        resp = self.client.get("/api/v1/ai/health", headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "ok")

        # Configured openrouter missing key
        config = UserAIConfig(
            user_id=self.user.id,
            provider="openrouter",
            api_key="",
            model="openrouter/free",
        )
        self.db.add(config)
        self.db.commit()

        resp2 = self.client.get("/api/v1/ai/health", headers=self.headers)
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.json()
        self.assertEqual(data2["status"], "error")
        self.assertIn("missing", data2["reason"])

    def test_planner_agent_reuses_db_fields(self):
        # Seed 1 processed message
        msg1 = Message(
            user_id=self.user.id,
            source=MessageSource.GMAIL,
            message_id="msg-plan-1",
            sender="client@example.com",
            subject="Invoice Request",
            body="Please send invoice for July.",
            summary="Client requested July invoice.",
            priority=MessagePriority.HIGH,
            confidence_score=80.0,
            received_at=datetime.utcnow(),
            is_processed=True,
        )
        self.db.add(msg1)
        self.db.commit()

        planner = PlannerAgent()

        mock_briefing = '''{
            "date": "2026-08-26",
            "executive_summary": "1 high priority request from client.",
            "critical_items": ["Send invoice to client"],
            "recommended_priorities": ["Process July invoice"],
            "pending_work": [],
            "upcoming_deadlines": [],
            "risks": [],
            "next_actions": ["Email client"]
        }'''

        with patch("services.llm.LLMClient.chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = mock_briefing
            res = asyncio.run(planner.generate_daily_briefing(self.user.id, self.db))

            self.assertEqual(res["executive_summary"], "1 high priority request from client.")
            # Verify LLM chat was called ONLY ONCE for the final briefing
            self.assertEqual(mock_chat.call_count, 1)


if __name__ == "__main__":
    unittest.main()
