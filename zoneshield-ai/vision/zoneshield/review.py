"""Review queue: human override for ambiguous decisions.

ReviewItem represents a pending decision awaiting human resolution.
Status: pending | approved | dismissed | more_evidence | expired.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ReviewStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DISMISSED = "dismissed"
    MORE_EVIDENCE = "more_evidence"
    EXPIRED = "expired"


@dataclass
class ReviewItem:
    """A pending decision awaiting human resolution."""
    id: str
    decision_id: str
    track_id: int
    evidence_ids: list[str]
    recommendation: str  # monitor | intercept | gather_evidence
    deadline_ms: float
    status: ReviewStatus = ReviewStatus.PENDING
    resolved_by: Optional[str] = None
    resolved_at_ms: Optional[float] = None
    resolution_reason: Optional[str] = None
    created_at_ms: float = field(default_factory=lambda: time.perf_counter() * 1000.0)

    def is_expired(self) -> bool:
        return time.perf_counter() * 1000.0 > self.deadline_ms

    def resolve(
        self,
        operator: str,
        status: ReviewStatus,
        reason: Optional[str] = None,
    ) -> None:
        self.status = status
        self.resolved_by = operator
        self.resolved_at_ms = time.perf_counter() * 1000.0
        self.resolution_reason = reason


class ReviewQueue:
    """Manages review items for human override decisions."""

    def __init__(self, default_timeout_ms: float = 30000.0) -> None:
        self._items: dict[str, ReviewItem] = {}
        self._default_timeout_ms = default_timeout_ms
        self._counter = 0

    def create(
        self,
        decision_id: str,
        track_id: int,
        evidence_ids: list[str],
        recommendation: str,
        deadline_ms: Optional[float] = None,
    ) -> ReviewItem:
        self._counter += 1
        item_id = f"review_{self._counter:06d}"
        if deadline_ms is None:
            deadline_ms = time.perf_counter() * 1000.0 + self._default_timeout_ms
        item = ReviewItem(
            id=item_id,
            decision_id=decision_id,
            track_id=track_id,
            evidence_ids=list(evidence_ids),
            recommendation=recommendation,
            deadline_ms=deadline_ms,
        )
        self._items[item_id] = item
        return item

    def get(self, item_id: str) -> Optional[ReviewItem]:
        return self._items.get(item_id)

    def list_pending(self) -> list[ReviewItem]:
        now_ms = time.perf_counter() * 1000.0
        return [
            item for item in self._items.values()
            if item.status == ReviewStatus.PENDING and not item.is_expired()
        ]

    def list_expired(self) -> list[ReviewItem]:
        now_ms = time.perf_counter() * 1000.0
        return [
            item for item in self._items.values()
            if item.status == ReviewStatus.PENDING and item.is_expired()
        ]

    def expire_stale(self) -> list[str]:
        """Mark all expired pending items as expired. Returns their IDs."""
        expired_ids = []
        for item in self.list_expired():
            item.status = ReviewStatus.EXPIRED
            expired_ids.append(item.id)
        return expired_ids

    def resolve(
        self,
        item_id: str,
        operator: str,
        status: ReviewStatus,
        reason: Optional[str] = None,
    ) -> bool:
        item = self._items.get(item_id)
        if item is None or item.status != ReviewStatus.PENDING:
            return False
        item.resolve(operator, status, reason)
        return True

    def count_by_status(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in self._items.values():
            key = item.status.value
            counts[key] = counts.get(key, 0) + 1
        return counts