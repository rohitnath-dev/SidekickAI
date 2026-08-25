"""Unit tests for message tenant isolation and repository safety."""

import os
import unittest
from datetime import datetime

os.environ["SECRET_KEY"] = "test_secret_key_for_sidekick_ai_units_12345"
os.environ["DATABASE_URL"] = "sqlite:///./test_sidekick.db"

from database import Base, engine, SessionLocal
from models.user import User
from models.message import Message, MessageSource, MessagePriority, MessageStatus
from repositories.message_repo import MessageRepository


class TestMessageTenantIsolation(unittest.TestCase):

    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()

        # Create two distinct users
        self.user1 = User(
            id="user-uuid-111",
            email="user1@example.com",
            hashed_password="hashed_pass_1",
            full_name="User One",
        )
        self.user2 = User(
            id="user-uuid-222",
            email="user2@example.com",
            hashed_password="hashed_pass_2",
            full_name="User Two",
        )
        self.db.add_all([self.user1, self.user2])
        self.db.commit()

        # Create messages for user1 (including a whatsapp message)
        self.msg1 = Message(
            user_id="user-uuid-111",
            message_id="ext-msg-1",
            source=MessageSource.GMAIL,
            sender="alice@example.com",
            body="User 1 Gmail message",
            received_at=datetime.utcnow(),
        )
        self.msg2 = Message(
            user_id="user-uuid-111",
            message_id="ext-msg-2",
            source=MessageSource.WHATSAPP,
            sender="+1234567890",
            body="User 1 WhatsApp message",
            received_at=datetime.utcnow(),
        )
        # Create message for user2
        self.msg3 = Message(
            user_id="user-uuid-222",
            message_id="ext-msg-3",
            source=MessageSource.WHATSAPP,
            sender="+0987654321",
            body="User 2 WhatsApp message",
            received_at=datetime.utcnow(),
        )
        self.db.add_all([self.msg1, self.msg2, self.msg3])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)

    def test_user1_cannot_access_user2_whatsapp_messages(self):
        # User 1 listing messages should only return User 1's messages
        user1_messages = MessageRepository.list_by_user(self.db, user_id="user-uuid-111")
        user1_ids = [m.id for m in user1_messages]

        self.assertIn(self.msg1.id, user1_ids)
        self.assertIn(self.msg2.id, user1_ids)
        self.assertNotIn(self.msg3.id, user1_ids)

    def test_get_by_id_enforces_user_isolation(self):
        # User 2 trying to get User 1's message by ID should return None
        fetched = MessageRepository.get_by_id(self.db, message_id=self.msg1.id, user_id="user-uuid-222")
        self.assertIsNone(fetched)

        # User 1 getting own message returns the message
        fetched_own = MessageRepository.get_by_id(self.db, message_id=self.msg1.id, user_id="user-uuid-111")
        self.assertIsNotNone(fetched_own)
        self.assertEqual(fetched_own.id, self.msg1.id)


if __name__ == "__main__":
    unittest.main()
