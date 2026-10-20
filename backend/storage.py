"""Storage repositories for ZoneShield AI.

Implements SQLite (WAL mode) persistence with repositories:
- SessionRepo
- DecisionRepo
- TraceRepo
- ReviewRepo
- BenchmarkRepo
- EvalRepo
- AuditRepo (append-only)
- EvidenceStore (local disk storage with URI generation)
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional
from uuid import UUID

from backend.models import (
    AgentTrace,
    AuditEvent,
    BenchmarkRun,
    Decision,
    EvalRun,
    Evidence,
    ReviewItem,
    Session,
)


class SQLiteStorage:
    """Thread-safe SQLite storage manager with WAL mode enabled."""

    def __init__(self, db_path: str | Path = "data/zoneshield.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return self._local.conn

    def _init_db(self) -> None:
        conn = self.get_connection()
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    source TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    config_hash TEXT,
                    scenario_id TEXT,
                    calibration_id TEXT
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS decisions (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    track_id INTEGER NOT NULL,
                    state_from TEXT NOT NULL,
                    state_to TEXT NOT NULL,
                    action TEXT NOT NULL,
                    tier TEXT NOT NULL,
                    confidence_before REAL NOT NULL,
                    confidence_after REAL,
                    reason TEXT NOT NULL,
                    evidence_ids TEXT NOT NULL,
                    trace_id TEXT,
                    t_ms REAL NOT NULL
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_traces (
                    id TEXT PRIMARY KEY,
                    decision_id TEXT NOT NULL,
                    steps TEXT NOT NULL,
                    fallback_used INTEGER NOT NULL,
                    fallback_reason TEXT,
                    model_id TEXT NOT NULL,
                    latency_ms REAL NOT NULL,
                    tokens_in INTEGER NOT NULL,
                    tokens_out INTEGER NOT NULL
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS review_items (
                    id TEXT PRIMARY KEY,
                    decision_id TEXT NOT NULL,
                    evidence_ids TEXT NOT NULL,
                    recommendation TEXT NOT NULL,
                    deadline_ms REAL NOT NULL,
                    status TEXT NOT NULL,
                    resolved_by TEXT,
                    resolved_at_ms REAL
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS benchmark_runs (
                    id TEXT PRIMARY KEY,
                    config TEXT NOT NULL,
                    env_fingerprint TEXT NOT NULL,
                    cool_proof TEXT,
                    results_uri TEXT,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS eval_runs (
                    id TEXT PRIMARY KEY,
                    suite TEXT NOT NULL,
                    seeds TEXT NOT NULL,
                    metrics TEXT NOT NULL,
                    confusion TEXT,
                    failure_cases TEXT NOT NULL,
                    status TEXT NOT NULL
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_events (
                    id TEXT PRIMARY KEY,
                    t_ms REAL NOT NULL,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT,
                    details TEXT NOT NULL
                );
            """)


class SessionRepo:
    def __init__(self, storage: SQLiteStorage) -> None:
        self.storage = storage

    def save(self, session: Session) -> None:
        conn = self.storage.get_connection()
        with conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO sessions 
                (id, name, source, state, created_at, config_hash, scenario_id, calibration_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(session.id),
                    session.name,
                    session.source.value if hasattr(session.source, "value") else str(session.source),
                    session.state.value if hasattr(session.state, "value") else str(session.state),
                    session.created_at.isoformat(),
                    session.config_hash,
                    session.scenario_id,
                    session.calibration_id,
                ),
            )

    def get(self, session_id: str | UUID) -> Optional[Session]:
        conn = self.storage.get_connection()
        cur = conn.execute("SELECT * FROM sessions WHERE id = ?", (str(session_id),))
        row = cur.fetchone()
        if not row:
            return None
        return Session(
            id=UUID(row["id"]),
            name=row["name"],
            source=row["source"],
            state=row["state"],
            created_at=datetime.fromisoformat(row["created_at"]),
            config_hash=row["config_hash"],
            scenario_id=row["scenario_id"],
            calibration_id=row["calibration_id"],
        )

    def list_all(self) -> list[Session]:
        conn = self.storage.get_connection()
        cur = conn.execute("SELECT * FROM sessions ORDER BY created_at DESC")
        results = []
        for row in cur.fetchall():
            results.append(
                Session(
                    id=UUID(row["id"]),
                    name=row["name"],
                    source=row["source"],
                    state=row["state"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    config_hash=row["config_hash"],
                    scenario_id=row["scenario_id"],
                    calibration_id=row["calibration_id"],
                )
            )
        return results

    def delete(self, session_id: str | UUID) -> bool:
        conn = self.storage.get_connection()
        with conn:
            cur = conn.execute("DELETE FROM sessions WHERE id = ?", (str(session_id),))
            return cur.rowcount > 0


class DecisionRepo:
    def __init__(self, storage: SQLiteStorage) -> None:
        self.storage = storage

    def save(self, dec: Decision) -> None:
        conn = self.storage.get_connection()
        with conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO decisions
                (id, session_id, track_id, state_from, state_to, action, tier, confidence_before, confidence_after, reason, evidence_ids, trace_id, t_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(dec.id),
                    str(dec.session_id),
                    dec.track_id,
                    dec.state_from,
                    dec.state_to,
                    dec.action.value if hasattr(dec.action, "value") else str(dec.action),
                    dec.tier.value if hasattr(dec.tier, "value") else str(dec.tier),
                    dec.confidence_before,
                    dec.confidence_after,
                    dec.reason,
                    json.dumps([str(eid) for eid in dec.evidence_ids]),
                    str(dec.trace_id) if dec.trace_id else None,
                    dec.t_ms,
                ),
            )

    def get(self, decision_id: str | UUID) -> Optional[dict]:
        conn = self.storage.get_connection()
        cur = conn.execute("SELECT * FROM decisions WHERE id = ?", (str(decision_id),))
        row = cur.fetchone()
        if not row:
            return None
        return dict(row)

    def list_by_session(self, session_id: str | UUID, limit: int = 100) -> list[dict]:
        conn = self.storage.get_connection()
        cur = conn.execute(
            "SELECT * FROM decisions WHERE session_id = ? ORDER BY t_ms DESC LIMIT ?",
            (str(session_id), limit),
        )
        return [dict(r) for r in cur.fetchall()]


class ReviewRepo:
    def __init__(self, storage: SQLiteStorage) -> None:
        self.storage = storage

    def save(self, item: ReviewItem) -> None:
        conn = self.storage.get_connection()
        with conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO review_items
                (id, decision_id, evidence_ids, recommendation, deadline_ms, status, resolved_by, resolved_at_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(item.id),
                    str(item.decision_id),
                    json.dumps([str(eid) for eid in item.evidence_ids]),
                    item.recommendation,
                    item.deadline_ms,
                    item.status.value if hasattr(item.status, "value") else str(item.status),
                    item.resolved_by,
                    item.resolved_at_ms,
                ),
            )

    def get(self, item_id: str | UUID) -> Optional[dict]:
        conn = self.storage.get_connection()
        cur = conn.execute("SELECT * FROM review_items WHERE id = ?", (str(item_id),))
        row = cur.fetchone()
        return dict(row) if row else None

    def list_pending(self) -> list[dict]:
        conn = self.storage.get_connection()
        cur = conn.execute("SELECT * FROM review_items WHERE status = 'pending' ORDER BY deadline_ms ASC")
        return [dict(r) for r in cur.fetchall()]


class AuditRepo:
    """Append-only audit repository."""

    def __init__(self, storage: SQLiteStorage) -> None:
        self.storage = storage

    def append(self, event: AuditEvent) -> None:
        conn = self.storage.get_connection()
        with conn:
            conn.execute(
                """
                INSERT INTO audit_events
                (id, t_ms, actor, action, entity_type, entity_id, details)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(event.id),
                    event.t_ms,
                    event.actor,
                    event.action,
                    event.entity_type,
                    event.entity_id,
                    json.dumps(event.details),
                ),
            )

    def list_recent(self, limit: int = 100) -> list[dict]:
        conn = self.storage.get_connection()
        cur = conn.execute("SELECT * FROM audit_events ORDER BY t_ms DESC LIMIT ?", (limit,))
        return [dict(r) for r in cur.fetchall()]


class BenchmarkRepo:
    def __init__(self, storage: SQLiteStorage) -> None:
        self.storage = storage

    def save(self, run: BenchmarkRun) -> None:
        conn = self.storage.get_connection()
        with conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO benchmark_runs
                (id, config, env_fingerprint, cool_proof, results_uri, status, started_at, finished_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(run.id),
                    run.config,
                    json.dumps(run.env_fingerprint),
                    json.dumps(run.cool_proof) if run.cool_proof else None,
                    run.results_uri,
                    run.status,
                    run.started_at.isoformat(),
                    run.finished_at.isoformat() if run.finished_at else None,
                ),
            )

    def get(self, run_id: str | UUID) -> Optional[dict]:
        conn = self.storage.get_connection()
        cur = conn.execute("SELECT * FROM benchmark_runs WHERE id = ?", (str(run_id),))
        row = cur.fetchone()
        return dict(row) if row else None

    def list_all(self) -> list[dict]:
        conn = self.storage.get_connection()
        cur = conn.execute("SELECT * FROM benchmark_runs ORDER BY started_at DESC")
        return [dict(r) for r in cur.fetchall()]


class EvalRepo:
    def __init__(self, storage: SQLiteStorage) -> None:
        self.storage = storage

    def save(self, run: EvalRun) -> None:
        conn = self.storage.get_connection()
        with conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO eval_runs
                (id, suite, seeds, metrics, confusion, failure_cases, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(run.id),
                    run.suite,
                    json.dumps(run.seeds),
                    json.dumps(run.metrics),
                    json.dumps(run.confusion) if run.confusion else None,
                    json.dumps(run.failure_cases),
                    run.status,
                ),
            )

    def get(self, run_id: str | UUID) -> Optional[dict]:
        conn = self.storage.get_connection()
        cur = conn.execute("SELECT * FROM eval_runs WHERE id = ?", (str(run_id),))
        row = cur.fetchone()
        return dict(row) if row else None

    def list_all(self) -> list[dict]:
        conn = self.storage.get_connection()
        cur = conn.execute("SELECT * FROM eval_runs")
        return [dict(r) for r in cur.fetchall()]


class EvidenceStore:
    """Local file evidence store."""

    def __init__(self, base_dir: str | Path = "data/evidence") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_crop(self, evidence_id: str, image_bytes: bytes) -> str:
        file_path = self.base_dir / f"{evidence_id}.jpg"
        with open(file_path, "wb") as f:
            f.write(image_bytes)
        return str(file_path)

    def get_path(self, evidence_id: str) -> Optional[Path]:
        p = self.base_dir / f"{evidence_id}.jpg"
        return p if p.exists() else None
