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
        job_manager._user_jobs.clear()
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
        # Keep job in active processing state
        job1.state = AIJobState.PROCESSING
        job2 = asyncio.run(job_manager.start_job(self.user.id, self.db))
        
        # Second call returns same active job ID
        self.assertEqual(job1.job_id, job2.job_id)

    def test_stale_job_recovery(self):
        job = asyncio.run(job_manager.start_job(self.user.id, self.db))
        # Set to active processing state and age updated_at timestamp by 3 minutes (>120s)
        job.state = AIJobState.PROCESSING
        job.updated_at = datetime.utcnow() - timedelta(minutes=3)
        
        fetched = job_manager.get_job(self.user.id)
        self.assertEqual(fetched.state, AIJobState.STALE)

    def test_tenant_isolation_job_status(self):
        # Create second user
        user2 = User(
            id="user-2-uuid-202",
            email="user2@example.com",
            hashed_password="hashed_pass_user2",
            full_name="User Two",
            is_active=True,
        )
        self.db.add(user2)
        self.db.commit()
        token2 = create_access_token(user2.id)
        headers2 = {"Authorization": f"Bearer {token2}"}

        # User 1 starts job
        job1 = asyncio.run(job_manager.start_job(self.user.id, self.db))

        # User 2 checks status -> should have no job or user2's job
        resp2 = self.client.get("/api/v1/ai/job/status", headers=headers2)
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.json()
        self.assertFalse(data2["has_job"])

    def test_job_retry_clears_stale_and_starts_new_job(self):
        job1 = asyncio.run(job_manager.start_job(self.user.id, self.db))
        job1.state = AIJobState.FAILED
        
        # Retry endpoint
        resp = self.client.post("/api/v1/ai/job/retry", json={}, headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertNotEqual(data["job_id"], job1.job_id)

    def test_job_failed_state_allows_new_job(self):
        job1 = asyncio.run(job_manager.start_job(self.user.id, self.db))
        job1.mark_failed("Test error")
        
        job2 = asyncio.run(job_manager.start_job(self.user.id, self.db))
        self.assertNotEqual(job1.job_id, job2.job_id)

    def test_complete_onboarding_endpoint(self):
        res = self.client.post("/api/v1/auth/complete-onboarding", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["onboarding_completed"])


if __name__ == "__main__":
    unittest.main()
