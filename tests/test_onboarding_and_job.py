"""Unit tests for SidekickAI Onboarding, Application Integrations, Job Manager, and Tenant Isolation."""

import os
import unittest
import asyncio
from datetime import datetime, timedelta

os.environ["SECRET_KEY"] = "test_secret_key_for_sidekick_ai_units_12345"
os.environ["DATABASE_URL"] = "sqlite:///./test_sidekick_onboarding.db"

from fastapi.testclient import TestClient
from app import app
from database import Base, engine, SessionLocal
from models.user import User
from models.ai_config import UserAIConfig
from models.session import UserSession
from models.token import OAuthToken
from models.message import Message, MessageSource, MessagePriority, MessageStatus
from services.job_manager import job_manager, AIJobState, HOURS_LOOKBACK
from services.auth import create_access_token


class TestOnboardingAndJobManager(unittest.TestCase):

    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        self.client = TestClient(app)

        # Create user
        self.user = User(
            id="onboarding-user-uuid-101",
            email="onboarding@example.com",
            hashed_password="hashed_pass_onboarding",
            full_name="Onboarding Tester",
            is_active=True,
            onboarding_completed=False,
        )
        self.db.add(self.user)
        self.db.commit()

        self.token = create_access_token(self.user.id)
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)

    def test_24_hour_window_constant(self):
        self.assertEqual(HOURS_LOOKBACK, 24)

    def test_job_manager_zero_integrations_skip_path(self):
        # User has zero connected OAuth tokens
        job = asyncio.run(job_manager.start_job(self.user.id, self.db))
        self.assertEqual(job.user_id, self.user.id)
        
        # Poll status via API
        resp = self.client.get("/api/v1/ai/job/status", headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["has_job"])
        self.assertIn("job_id", data)

    def test_job_manager_idempotency_duplicate_start_protection(self):
        job1 = asyncio.run(job_manager.start_job(self.user.id, self.db))
        job2 = asyncio.run(job_manager.start_job(self.user.id, self.db))
        
        # Second call returns same active job ID
        self.assertEqual(job1.job_id, job2.job_id)

    def test_stale_job_recovery(self):
        job = asyncio.run(job_manager.start_job(self.user.id, self.db))
        # Artificially age the job updated_at timestamp by 15 minutes
        job.updated_at = datetime.utcnow() - timedelta(minutes=15)
        
        fetched = job_manager.get_job(self.user.id)
        self.assertEqual(fetched.state, AIJobState.STALE)

    def test_complete_onboarding_endpoint(self):
        res = self.client.post("/api/v1/auth/complete-onboarding", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["onboarding_completed"])


if __name__ == "__main__":
    unittest.main()
