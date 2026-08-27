"""
Sidekick AI — Complete AI Planner Upgrade Test Suite
Tests PlannerTask persistence, deduplication, extraction, conflict detection, time blocking, and endpoints.
"""

import pytest
import asyncio
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from models.user import User
from models.message import Message, MessagePriority, MessageSource
from models.planner_task import PlannerTask
from services.planner_service import PlannerService


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
        id="test-planner-user-uuid",
        email="planneruser@example.com",
        hashed_password="hashed_pass_123",
        full_name="Planner User",
    )
    db_session.add(user)
    db_session.commit()
    return user


# ============================================================================
# 1. PlannerTask Creation & Deduplication
# ============================================================================
def test_planner_task_creation_and_deduplication(db_session, test_user):
    user_id = test_user.id

    # Create task 1
    t1 = PlannerService.create_task(
        db=db_session,
        user_id=user_id,
        title="Review Q3 Proposal",
        source="gmail",
        source_item_id="msg_1001",
        priority="high",
        due_date=datetime.utcnow() + timedelta(days=1),
    )
    assert t1.id is not None
    assert t1.title == "Review Q3 Proposal"
    assert t1.priority == "high"

    # Attempt to create duplicate task with same source_item_id
    t2 = PlannerService.create_task(
        db=db_session,
        user_id=user_id,
        title="Review Q3 Proposal (Updated Title)",
        source="gmail",
        source_item_id="msg_1001",
        priority="critical",
    )
    # Must update existing task instead of creating new row!
    assert t2.id == t1.id
    assert t2.title == "Review Q3 Proposal (Updated Title)"
    assert t2.priority == "critical"

    # Total count in DB must remain 1
    all_tasks = db_session.query(PlannerTask).filter(PlannerTask.user_id == user_id).all()
    assert len(all_tasks) == 1


# ============================================================================
# 2. Message Task Extraction
# ============================================================================
def test_extract_tasks_from_messages(db_session, test_user):
    user_id = test_user.id

    msg = Message(
        user_id=user_id,
        message_id="msg_extracted_100",
        received_at=datetime.utcnow(),
        source=MessageSource.GMAIL,
        sender="boss@example.com",
        recipient="planneruser@example.com",
        subject="Urgent Budget Approval Needed",
        body="Please review the budget proposal by 5 PM.",
        action_items="Review budget proposal\nSend confirmation email",
        priority=MessagePriority.HIGH,
        is_processed=True,
        requires_reply=True,
    )
    db_session.add(msg)
    db_session.commit()

    extracted = PlannerService.extract_tasks_from_messages(db=db_session, user_id=user_id)
    assert len(extracted) >= 2
    titles = [t.title for t in extracted]
    assert "Review budget proposal" in titles
    assert "Send confirmation email" in titles


# ============================================================================
# 3. Briefing Task Extraction
# ============================================================================
def test_extract_tasks_from_briefing(db_session, test_user):
    user_id = test_user.id

    briefing_data = {
        "date": "2026-08-27",
        "executive_summary": "Daily briefing summary",
        "critical_items": [{"item": "Fix security vulnerability", "action": "Patch API endpoint"}],
        "recommended_priorities": ["Finalize Q3 Roadmap"],
        "next_actions": ["Sync with dev team"],
    }

    tasks = PlannerService.extract_tasks_from_briefing(db=db_session, user_id=user_id, briefing_data=briefing_data)
    assert len(tasks) == 3
    priorities = [t.priority for t in tasks]
    assert "critical" in priorities
    assert "high" in priorities
    assert "medium" in priorities


# ============================================================================
# 4. Next Best Action & Conflict Detection
# ============================================================================
def test_next_best_action_and_conflicts(db_session, test_user):
    user_id = test_user.id

    # Create tasks
    PlannerService.create_task(db=db_session, user_id=user_id, title="Low priority task", priority="low")
    PlannerService.create_task(db=db_session, user_id=user_id, title="Critical Security Hotfix", priority="critical")
    PlannerService.create_task(db=db_session, user_id=user_id, title="Overdue Client Report", priority="high", due_date=datetime.utcnow() - timedelta(days=2))

    all_tasks = db_session.query(PlannerTask).filter(PlannerTask.user_id == user_id).all()

    # Next best action should pick Critical or Overdue high priority task
    next_best = PlannerService.calculate_next_best_action(all_tasks)
    assert next_best is not None
    assert next_best["task"]["priority"] in ("critical", "high")

    # Conflict detection should identify overdue accumulation
    conflicts = PlannerService.detect_planning_conflicts(all_tasks)
    assert len(conflicts) > 0
    conflict_types = [c["type"] for c in conflicts]
    assert "overdue_accumulation" in conflict_types


# ============================================================================
# 5. Smart Time Blocks Generation
# ============================================================================
def test_generate_smart_time_blocks(db_session, test_user):
    user_id = test_user.id

    t = PlannerService.create_task(db=db_session, user_id=user_id, title="Focus: Write Documentation", priority="high")
    blocks = PlannerService.generate_smart_time_blocks([t])
    assert len(blocks) == 8
    # Lunch break block at 12:00
    lunch_blocks = [b for b in blocks if b["time_slot"].startswith("12:00")]
    assert len(lunch_blocks) > 0
    assert lunch_blocks[0]["category"] == "break"


# ============================================================================
# 6. Planner Dashboard Consolidated Data
# ============================================================================
def test_get_planner_dashboard_data(db_session, test_user):
    user_id = test_user.id

    PlannerService.create_task(db=db_session, user_id=user_id, title="Sample Task 1", priority="medium")
    data = PlannerService.get_planner_dashboard_data(db=db_session, user_id=user_id)

    assert "stats" in data
    assert "today_plan" in data
    assert "deadlines" in data
    assert "time_blocks" in data
    assert "weekly_overview" in data
    assert data["stats"]["total"] >= 1
