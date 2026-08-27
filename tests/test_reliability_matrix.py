"""
Sidekick AI — Production Reliability & Bug Fix Test Matrix
Tests requirements A through K from the 14-point test matrix.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from models.user import User
from models.message import Message, MessagePriority, MessageSource
from models.token import OAuthToken
from models.ai_run import AIRun
from services.job_manager import AIJobManager, AIJobState, ProcessingJob, persist_ai_run_stage
from services.llm import (
    LLMClient,
    LLMRateLimitError,
    LLMAuthenticationError,
    LLMResponseError,
    LLMConnectionError,
    LLMException,
)
from services.ai_pipeline import analyze_message_single_pass, process_message_ai


@pytest.fixture
def db_session():
    """In-memory SQLite database session for unit tests."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def test_user(db_session):
    user = User(
        id="test-matrix-user-uuid",
        email="testmatrix@example.com",
        hashed_password="hashed_pass_123",
        full_name="Matrix Tester",
    )
    db_session.add(user)
    db_session.commit()
    return user


# ============================================================================
# A. No integrations connected -> truthful empty state, no fake AI result
# ============================================================================
@pytest.mark.asyncio
async def test_matrix_a_no_integrations(db_session, test_user):
    user_id = test_user.id
    with patch("services.job_manager.SessionLocal", return_value=db_session):
        manager = AIJobManager()
        job = await manager.start_job(user_id=user_id, db=db_session)
        await asyncio.sleep(0.1)

        job_state = manager.get_job(user_id)
        assert job_state.state in (AIJobState.COMPLETED, AIJobState.CHECKING_CONNECTIONS, AIJobState.QUEUED, AIJobState.STARTING)
        assert len(job_state.connected_integrations) == 0


# ============================================================================
# B. One integration + new messages -> sync -> analysis -> briefing -> draft
# ============================================================================
@pytest.mark.asyncio
async def test_matrix_b_one_integration_pipeline(db_session, test_user):
    user_id = test_user.id
    # Add connected token
    token = OAuthToken(
        user_id=user_id,
        provider="google",
        access_token="valid_access_token",
        refresh_token="valid_refresh_token",
    )
    db_session.add(token)

    # Add urgent unread message
    msg = Message(
        user_id=user_id,
        message_id="msg_b_123",
        received_at=datetime.utcnow(),
        source=MessageSource.GMAIL,
        sender="client@example.com",
        recipient="testmatrix@example.com",
        subject="Project Quote Needed ASAP",
        body="Can you please send over the pricing quote by tomorrow morning?",
        is_processed=False,
    )
    db_session.add(msg)
    db_session.commit()

    mock_llm_json = '{"score": 90, "priority_level": "high", "requires_reply": true, "summary": "Client requested pricing quote.", "sentiment": "urgent", "category": "work", "action_items": ["Send pricing quote"]}'
    mock_reply_json = "Dear Client,\n\nI will send the pricing quote right away.\n\nBest regards,"

    with patch("services.llm.LLMClient.chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.side_effect = [mock_llm_json, mock_reply_json]

        client = LLMClient()
        await analyze_message_single_pass(db=db_session, message=msg, llm_client=client)

        db_session.refresh(msg)
        assert msg.is_processed is True
        assert msg.requires_reply is True
        assert msg.priority == MessagePriority.HIGH
        assert msg.summary == "Client requested pricing quote."
        assert "pricing quote" in msg.suggested_reply.lower()


# ============================================================================
# C. Connected + zero new messages -> up-to-date state, previous briefing preserved
# ============================================================================
@pytest.mark.asyncio
async def test_matrix_c_zero_new_messages_preserves_previous(db_session, test_user):
    user_id = test_user.id
    # Create persistent run with previous briefing
    run = AIRun(
        run_id="run-prev-123",
        user_id=user_id,
        status="completed",
        stage="Completed",
        briefing_data_json='{"date": "2026-08-26", "executive_summary": "Yesterday briefing"}',
    )
    db_session.add(run)
    db_session.commit()

    with patch("services.job_manager.SessionLocal", return_value=db_session):
        manager = AIJobManager()
        latest = manager.get_latest_db_run(user_id)
        assert latest is not None
        assert latest["briefing"]["executive_summary"] == "Yesterday briefing"


# ============================================================================
# D. Empty LLM response -> bounded retry/recovery, no raw provider error
# ============================================================================
@pytest.mark.asyncio
async def test_matrix_d_empty_llm_response_recovery():
    client = LLMClient(provider="openrouter", api_key="dummy_key")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        # Mock empty response 3 times
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": [{"message": {"content": ""}}]}
        mock_post.return_value = mock_resp

        with pytest.raises(LLMResponseError) as exc_info:
            await client._chat_openrouter([{"role": "user", "content": "hi"}])

        assert "empty response" in str(exc_info.value).lower()
        # Verify bounded retry executed (3 attempts total)
        assert mock_post.call_count == 3


# ============================================================================
# E. Rate limit -> concise message, no raw API dump
# ============================================================================
@pytest.mark.asyncio
async def test_matrix_e_rate_limit_handling():
    client = LLMClient(provider="openrouter", api_key="dummy_key")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.json.return_value = {"error": {"message": "Rate limit exceeded"}}
        mock_post.return_value = mock_resp

        with pytest.raises(LLMRateLimitError) as exc_info:
            await client._chat_openrouter([{"role": "user", "content": "hi"}])

        assert "AI limit reached" in str(exc_info.value)
        # Should not dump stack trace or raw body in string
        assert "choices" not in str(exc_info.value)


# ============================================================================
# F. AI succeeds after retry -> successful dashboard, no stale failure notice
# ============================================================================
@pytest.mark.asyncio
async def test_matrix_f_success_after_retry(db_session, test_user):
    client = LLMClient(provider="openrouter", api_key="dummy_key")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        empty_resp = MagicMock()
        empty_resp.status_code = 200
        empty_resp.json.return_value = {"choices": [{"message": {"content": ""}}]}

        valid_resp = MagicMock()
        valid_resp.status_code = 200
        valid_resp.json.return_value = {"choices": [{"message": {"content": "Success content"}}]}

        mock_post.side_effect = [empty_resp, valid_resp]

        res = await client._chat_openrouter([{"role": "user", "content": "hi"}])
        assert res == "Success content"


# ============================================================================
# G. Automated notifications/newsletters -> requires_reply=False
# ============================================================================
@pytest.mark.asyncio
async def test_matrix_g_automated_email_no_reply(db_session, test_user):
    user_id = test_user.id
    msg = Message(
        user_id=user_id,
        message_id="msg_g_123",
        received_at=datetime.utcnow(),
        source=MessageSource.GMAIL,
        sender="Google Security <security-noreply@google.com>",
        recipient="testmatrix@example.com",
        subject="Security alert: New sign-in detected",
        body="A new device signed into your Google account.",
        is_processed=False,
    )
    db_session.add(msg)
    db_session.commit()

    mock_llm_json = '{"score": 95, "priority_level": "critical", "requires_reply": true, "summary": "Security sign-in alert.", "category": "security"}'

    with patch("services.llm.LLMClient.chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = mock_llm_json
        client = LLMClient()
        await analyze_message_single_pass(db=db_session, message=msg, llm_client=client)

        db_session.refresh(msg)
        assert msg.is_processed is True
        # automated email rule must override LLM requires_reply to False!
        assert msg.requires_reply is False
        assert msg.suggested_reply == ""


# ============================================================================
# H. Background timeout -> stale state recovered, retry available
# ============================================================================
@pytest.mark.asyncio
async def test_matrix_h_stale_job_recovery(db_session, test_user):
    user_id = test_user.id
    with patch("services.job_manager.SessionLocal", return_value=db_session):
        manager = AIJobManager()
        job = ProcessingJob(job_id="job-stale-999", user_id=user_id)
        job.state = AIJobState.PROCESSING
        job.updated_at = datetime.utcnow() - timedelta(seconds=130)  # >120s inactive
        manager._user_jobs[user_id] = job

        # Fetching job must detect stale and transition
        updated_job = manager.get_job(user_id)
        assert updated_job.state == AIJobState.STALE

        # Starting a new job should succeed now
        new_job = await manager.start_job(user_id=user_id, db=db_session)
        assert new_job.job_id != "job-stale-999"


# ============================================================================
# I. Refresh during processing -> correct persisted progress
# ============================================================================
@pytest.mark.asyncio
async def test_matrix_i_refresh_during_processing(db_session, test_user):
    user_id = test_user.id
    with patch("services.job_manager.SessionLocal", return_value=db_session):
        manager = AIJobManager()
        job = ProcessingJob(job_id="job-active-100", user_id=user_id)
        job.update_stage(AIJobState.SYNCING, "Syncing Gmail messages...", discovered=15, processed=5)
        manager._user_jobs[user_id] = job

        # Simulate server restart / fresh manager instance querying DB
        fresh_manager = AIJobManager()
        latest_run = fresh_manager.get_latest_db_run(user_id)
        assert latest_run is not None
        assert latest_run["run_id"] == "job-active-100"
        assert latest_run["status"] == "syncing"
        assert latest_run["discovered_count"] == 15
