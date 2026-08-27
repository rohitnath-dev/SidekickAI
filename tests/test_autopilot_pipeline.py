"""
Sidekick AI — Production Auto Pilot Feature Test Suite
Tests AutoPilotConfig persistence, AutoPilotActivity logging, deduplication, background cycle policies, and API endpoints.
"""

import pytest
import asyncio
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from models.user import User
from models.message import Message, MessagePriority, MessageSource
from models.token import OAuthToken
from models.autopilot_config import AutoPilotConfig
from models.autopilot_activity import AutoPilotActivity
from services.autopilot_service import AutoPilotService


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
        id="test-autopilot-user-uuid",
        email="autopilotuser@example.com",
        hashed_password="hashed_pass_123",
        full_name="Auto Pilot Tester",
    )
    db_session.add(user)
    db_session.commit()
    return user


# ============================================================================
# 1. Config Persistence & Toggle
# ============================================================================
def test_autopilot_config_and_toggle(db_session, test_user):
    user_id = test_user.id

    # Get or create config
    cfg = AutoPilotService.get_or_create_config(db_session, user_id)
    assert cfg.user_id == user_id
    assert cfg.is_enabled is True
    assert cfg.last_status == "active"

    # Toggle to False
    updated_cfg = AutoPilotService.toggle_autopilot(db_session, user_id, is_enabled=False)
    assert updated_cfg.is_enabled is False
    assert updated_cfg.last_status == "paused"

    # Toggle back to True
    re_enabled = AutoPilotService.toggle_autopilot(db_session, user_id, is_enabled=True)
    assert re_enabled.is_enabled is True
    assert re_enabled.last_status == "active"


# ============================================================================
# 2. Activity Logging & Deduplication
# ============================================================================
def test_autopilot_activity_logging_and_deduplication(db_session, test_user):
    user_id = test_user.id

    act1 = AutoPilotService.log_activity(
        db=db_session,
        user_id=user_id,
        source="gmail",
        action_type="classified_newsletter",
        title="Classified newsletter from Marketing",
        description="Low priority newsletter",
        status="auto_executed",
        source_item_id="msg_9999",
    )
    assert act1.id is not None
    assert act1.action_type == "classified_newsletter"

    # Attempt to log duplicate activity for same source_item_id & action_type
    act2 = AutoPilotService.log_activity(
        db=db_session,
        user_id=user_id,
        source="gmail",
        action_type="classified_newsletter",
        title="Classified newsletter from Marketing (Updated)",
        status="auto_executed",
        source_item_id="msg_9999",
    )
    # Must update existing activity instead of creating duplicate row
    assert act2.id == act1.id
    assert act2.title == "Classified newsletter from Marketing (Updated)"

    activities = db_session.query(AutoPilotActivity).filter(AutoPilotActivity.user_id == user_id).all()
    assert len(activities) == 1


# ============================================================================
# 3. Background Cycle: Zero Integrations
# ============================================================================
@pytest.mark.asyncio
async def test_autopilot_cycle_zero_integrations(db_session, test_user):
    user_id = test_user.id

    res = await AutoPilotService.run_autopilot_cycle(db_session, user_id)
    assert res["status"] == "waiting_for_connection"

    cfg = AutoPilotService.get_or_create_config(db_session, user_id)
    assert cfg.last_status == "waiting_for_connection"


# ============================================================================
# 4. Background Cycle: Auto Pilot Disabled
# ============================================================================
@pytest.mark.asyncio
async def test_autopilot_cycle_disabled(db_session, test_user):
    user_id = test_user.id
    AutoPilotService.toggle_autopilot(db_session, user_id, is_enabled=False)

    res = await AutoPilotService.run_autopilot_cycle(db_session, user_id)
    assert res["status"] == "paused"


# ============================================================================
# 5. Dashboard Summary Consolidation
# ============================================================================
def test_get_dashboard_summary(db_session, test_user):
    user_id = test_user.id

    # Add active token so monitored_sources shows 1 connected source
    token = OAuthToken(
        user_id=user_id,
        provider="google",
        access_token="valid_token",
        refresh_token="valid_refresh",
    )
    db_session.add(token)
    db_session.commit()

    summary = AutoPilotService.get_dashboard_summary(db_session, user_id)
    assert summary["is_enabled"] is True
    assert summary["active_sources_count"] == 1
    assert "monitored_sources" in summary
    assert "pending_review_items" in summary
    assert "recent_activities" in summary
