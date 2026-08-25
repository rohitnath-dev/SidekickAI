"""Unit tests for SidekickAI authentication and security."""

import os
import unittest
from fastapi.testclient import TestClient

# Set testing environment variables
os.environ["SECRET_KEY"] = "test_secret_key_for_sidekick_ai_units_12345"
os.environ["DATABASE_URL"] = "sqlite:///./test_sidekick.db"

from app import app
from database import Base, engine, SessionLocal
from services.auth import hash_password, verify_password, create_access_token, decode_access_token


class TestAuthService(unittest.TestCase):

    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)

    def test_password_hashing(self):
        password = "SecurePassword123!"
        hashed = hash_password(password)
        self.assertTrue(verify_password(password, hashed))
        self.assertFalse(verify_password("WrongPassword", hashed))

    def test_jwt_token_creation_and_decoding(self):
        user_id = "test-uuid-12345"
        token = create_access_token(user_id)
        decoded_id = decode_access_token(token)
        self.assertEqual(decoded_id, user_id)

    def test_jwt_rejects_invalid_token(self):
        invalid_token = "invalid.jwt.token.string"
        decoded = decode_access_token(invalid_token)
        self.assertIsNone(decoded)


class TestAuthAPI(unittest.TestCase):

    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.client = TestClient(app)

    def tearDown(self):
        Base.metadata.drop_all(bind=engine)

    def test_registration_and_login_flow(self):
        email = "testuser@example.com"
        password = "Password123!"
        full_name = "Test User"

        # Register
        reg_resp = self.client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "full_name": full_name},
        )
        self.assertEqual(reg_resp.status_code, 201)
        reg_data = reg_resp.json()
        self.assertIn("access_token", reg_data)
        self.assertEqual(reg_data["email"], email)

        # Duplicate register fails
        dup_resp = self.client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "full_name": full_name},
        )
        self.assertEqual(dup_resp.status_code, 409)

        # Login
        login_resp = self.client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": password},
        )
        self.assertEqual(login_resp.status_code, 200)
        login_data = login_resp.json()
        self.assertIn("access_token", login_data)

        # Access protected route /me with bearer token
        token = login_data["access_token"]
        me_resp = self.client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(me_resp.status_code, 200)
        self.assertEqual(me_resp.json()["email"], email)

    def test_unauthenticated_request_fails(self):
        res = self.client.get("/api/v1/auth/me")
        self.assertEqual(res.status_code, 401)

    def test_x_user_id_header_is_ignored_without_auth(self):
        res = self.client.get(
            "/api/v1/auth/me",
            headers={"x-user-id": "fake-user-id"},
        )
        self.assertEqual(res.status_code, 401)


if __name__ == "__main__":
    unittest.main()
