"""Unit and integration tests for Long-term Memory Pipeline."""

import os
import unittest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

os.environ["SECRET_KEY"] = "test_secret_key_for_sidekick_ai_units_12345"
os.environ["DATABASE_URL"] = "sqlite:///./test_sidekick_memory.db"

from fastapi.testclient import TestClient
from app import app
from database import Base, engine, SessionLocal
from models.user import User
from models.memory_item import MemoryItem
from agents.memory_agent import MemoryAgent
from repositories.memory_repo import MemoryRepository
from services.auth import create_access_token


class TestMemoryPipeline(unittest.TestCase):

    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        self.client = TestClient(app)

        self.user = User(
            id="mem-user-uuid-123",
            email="memory@example.com",
            hashed_password="hashed_pass",
            full_name="Memory Tester",
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

    def test_extract_from_text_hi_returns_empty_list(self):
        agent = MemoryAgent()

        mock_llm_response = '{"memories": []}'
        with patch.object(agent, "_call_llm", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_llm_response
            res = asyncio.run(agent.extract_from_text(text="Hi", user_id=self.user.id))
            self.assertEqual(res, [])

    def test_extract_endpoint_hi_returns_200_empty_list(self):
        with patch("agents.memory_agent.MemoryAgent.extract_from_text", new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = []
            resp = self.client.post(
                "/api/v1/memory/extract",
                json={"message_content": "Hi"},
                headers=self.headers,
            )
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json(), [])

    def test_extract_and_save_durable_fact(self):
        agent = MemoryAgent()
        fact = {
            "category": "personal",
            "content": "User prefers concise email responses.",
            "retention_value": "high",
            "confidence": 0.9,
        }
        with patch.object(agent, "_call_llm", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = '{"memories": [{"category": "personal", "content": "User prefers concise email responses.", "retention_value": "high", "confidence": 0.9}]}'
            memories = asyncio.run(agent.extract_from_text("I prefer concise email responses.", user_id=self.user.id))
            self.assertEqual(len(memories), 1)

            saved = asyncio.run(agent.save_memories(memories=memories, user_id=self.user.id, db=self.db))
            self.assertEqual(len(saved), 1)
            self.assertEqual(saved[0].content, "User prefers concise email responses.")

    def test_save_memories_deduplication(self):
        agent = MemoryAgent()
        fact = {
            "category": "personal",
            "content": "User prefers concise email responses.",
            "confidence": 0.9,
        }
        # First save
        saved1 = asyncio.run(agent.save_memories([fact], user_id=self.user.id, db=self.db))
        self.assertEqual(len(saved1), 1)

        # Second save (duplicate)
        saved2 = asyncio.run(agent.save_memories([fact], user_id=self.user.id, db=self.db))
        self.assertEqual(len(saved2), 0)


if __name__ == "__main__":
    unittest.main()
