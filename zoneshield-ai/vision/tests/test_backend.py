"""Unit tests for ZoneShield AI backend service, storage, and worker."""

import time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.api import app
from backend.models import (
    AuditEvent,
    Decision,
    DecisionAction,
    DecisionTier,
    ReviewItem,
    ReviewStatus,
    Session,
    SessionState,
    SourceType,
)
from backend.storage import (
    AuditRepo,
    DecisionRepo,
    EvidenceStore,
    ReviewRepo,
    SessionRepo,
    SQLiteStorage,
)


@pytest.fixture
def temp_storage(tmp_path):
    db_file = tmp_path / "test_zoneshield.db"
    return SQLiteStorage(db_path=db_file)


def test_session_repo_crud(temp_storage):
    repo = SessionRepo(temp_storage)
    session = Session(
        id=uuid4(),
        name="Test Production Belt",
        source=SourceType.SIMULATOR,
        state=SessionState.READY,
    )
    repo.save(session)

    retrieved = repo.get(session.id)
    assert retrieved is not None
    assert retrieved.name == "Test Production Belt"
    assert retrieved.state == SessionState.READY

    all_sessions = repo.list_all()
    assert len(all_sessions) == 1

    deleted = repo.delete(session.id)
    assert deleted is True
    assert repo.get(session.id) is None


def test_decision_and_audit_repo(temp_storage):
    d_repo = DecisionRepo(temp_storage)
    a_repo = AuditRepo(temp_storage)
    s_id = uuid4()

    dec = Decision(
        id=uuid4(),
        session_id=s_id,
        track_id=10,
        state_from="assessing",
        state_to="intercepting",
        action=DecisionAction.INTERCEPT,
        tier=DecisionTier.TIER1,
        confidence_before=0.88,
        confidence_after=0.88,
        reason="Clear foreign object detected",
        t_ms=1000.0,
    )
    d_repo.save(dec)

    dec_list = d_repo.list_by_session(s_id)
    assert len(dec_list) == 1
    assert dec_list[0]["action"] == "intercept"

    audit_ev = AuditEvent(
        id=uuid4(),
        actor="system",
        action="intercept_actuation",
        entity_type="actuator",
        entity_id=str(s_id),
        details={"track_id": 10},
    )
    a_repo.append(audit_ev)

    audits = a_repo.list_recent()
    assert len(audits) == 1
    assert audits[0]["action"] == "intercept_actuation"


def test_review_repo(temp_storage):
    r_repo = ReviewRepo(temp_storage)
    rev = ReviewItem(
        id=uuid4(),
        decision_id=uuid4(),
        evidence_ids=[],
        recommendation="Check foreign contaminant crop",
        deadline_ms=time.time() * 1000 + 5000,
        status=ReviewStatus.PENDING,
    )
    r_repo.save(rev)

    pending = r_repo.list_pending()
    assert len(pending) == 1
    assert pending[0]["id"] == str(rev.id)


def test_fastapi_endpoints():
    client = TestClient(app)

    # Health & System info
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    info_resp = client.get("/api/v1/system/info")
    assert info_resp.status_code == 200
    assert "opencv_version" in info_resp.json()

    # Create session
    create_resp = client.post("/api/v1/sessions", json={"name": "Integration Test Session"})
    assert create_resp.status_code == 200
    sess_id = create_resp.json()["id"]

    # Kill switch toggle
    kill_resp = client.post("/api/v1/system/kill-switch", json={"reason": "Test emergency stop"})
    assert kill_resp.status_code == 200
    assert kill_resp.json()["status"] == "kill_switch_active"

    reset_resp = client.post("/api/v1/system/kill-switch/reset")
    assert reset_resp.status_code == 200
    assert reset_resp.json()["status"] == "kill_switch_reset"
