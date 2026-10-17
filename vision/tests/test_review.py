"""Unit tests for ReviewQueue (M3)."""

import time

import pytest

from zoneshield.review import ReviewItem, ReviewQueue, ReviewStatus


def test_review_queue_create_and_get():
    q = ReviewQueue()
    item = q.create(
        decision_id="dec_1",
        track_id=1,
        evidence_ids=["ev1"],
        recommendation="intercept",
        deadline_ms=time.perf_counter() * 1000.0 + 5000.0,
    )
    assert item.id == "review_000001"
    assert item.decision_id == "dec_1"
    assert item.status == ReviewStatus.PENDING

    fetched = q.get(item.id)
    assert fetched is not None
    assert fetched.id == item.id


def test_review_queue_list_pending():
    q = ReviewQueue()
    q.create("dec_1", 1, ["ev1"], "intercept",
             deadline_ms=time.perf_counter() * 1000.0 + 5000.0)
    q.create("dec_2", 2, ["ev2"], "monitor",
             deadline_ms=time.perf_counter() * 1000.0 + 5000.0)
    pending = q.list_pending()
    assert len(pending) == 2


def test_review_queue_resolve():
    q = ReviewQueue()
    item = q.create("dec_1", 1, ["ev1"], "intercept",
                    deadline_ms=time.perf_counter() * 1000.0 + 5000.0)
    ok = q.resolve(item.id, "operator_1", ReviewStatus.APPROVED, "looks like a threat")
    assert ok is True
    item = q.get(item.id)
    assert item.status == ReviewStatus.APPROVED
    assert item.resolved_by == "operator_1"
    assert item.resolved_at_ms is not None


def test_review_queue_resolve_nonexistent():
    q = ReviewQueue()
    ok = q.resolve("review_999999", "operator_1", ReviewStatus.APPROVED)
    assert ok is False


def test_review_queue_expire_stale():
    q = ReviewQueue(default_timeout_ms=100.0)
    item = q.create("dec_1", 1, ["ev1"], "intercept",
                    deadline_ms=time.perf_counter() * 1000.0 + 50.0)
    time.sleep(0.2)
    expired = q.expire_stale()
    assert item.id in expired
    item = q.get(item.id)
    assert item.status == ReviewStatus.EXPIRED


def test_review_queue_count_by_status():
    q = ReviewQueue()
    now = time.perf_counter() * 1000.0
    q.create("dec_1", 1, ["ev1"], "intercept", deadline_ms=now + 5000.0)
    q.create("dec_2", 2, ["ev2"], "monitor", deadline_ms=now + 5000.0)
    counts = q.count_by_status()
    assert counts.get("pending", 0) == 2