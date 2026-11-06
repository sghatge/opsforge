"""OPSFORGE — database layer.

SQLite-backed persistence with a simple audit event log.
No third-party dependencies; Python 3.10+ standard library only.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS processes (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    owner TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS assessments (
    id TEXT PRIMARY KEY,
    process_id TEXT NOT NULL,
    scores TEXT NOT NULL,
    total INTEGER NOT NULL,
    level TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    ref_id TEXT DEFAULT '',
    title TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS qa_rules (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    target TEXT NOT NULL,
    rule_type TEXT NOT NULL,
    params TEXT DEFAULT '{}',
    severity TEXT DEFAULT 'error',
    enabled INTEGER DEFAULT 1,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    task TEXT NOT NULL,
    status TEXT NOT NULL,
    current_step INTEGER DEFAULT 0,
    result TEXT DEFAULT 'null',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_steps (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    name TEXT NOT NULL,
    tool TEXT NOT NULL,
    requires_approval INTEGER DEFAULT 0,
    status TEXT NOT NULL,
    input TEXT DEFAULT 'null',
    output TEXT DEFAULT 'null',
    error TEXT DEFAULT '',
    started_at REAL,
    finished_at REAL
);

CREATE TABLE IF NOT EXISTS approvals (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    step_seq INTEGER NOT NULL,
    approver TEXT NOT NULL,
    decision TEXT NOT NULL,
    comment TEXT DEFAULT '',
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS adapters (
    name TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    mode TEXT NOT NULL,
    capabilities TEXT NOT NULL,
    status TEXT DEFAULT 'unverified',
    last_check TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS audit_events (
    id TEXT PRIMARY KEY,
    ts REAL NOT NULL,
    event TEXT NOT NULL,
    payload TEXT NOT NULL
);
"""

_DEFAULT_QA_RULES = [
    ("Subject line present", "subject", "required", {}, "error"),
    ("Subject line length", "subject", "max_length", {"max": 60}, "warn"),
    ("Personalisation variables balanced", "personalization", "balanced_tags", {}, "error"),
    ("URL format valid", "urls", "url_format", {}, "error"),
    ("Unsubscribe link present", "urls", "contains_url", {"pattern": "unsubscribe"}, "error"),
    ("Tracking parameters present", "tracking", "truthy", {}, "warn"),
    ("Consent flag set", "consent", "truthy", {}, "error"),
    ("HTML title present", "html", "regex_match", {"pattern": "<title>[^<]+</title>"}, "warn"),
    ("No spam markers in subject", "subject", "regex_forbid", {"pattern": "(?i)free!!|act now|win a prize"}, "warn"),
]


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def now() -> float:
    return time.time()


class Database:
    """Thin thread-safe wrapper over sqlite3 with JSON-aware helpers."""

    def __init__(self, path: str = ":memory:") -> None:
        self.path = path
        self._lock = threading.RLock()
        if path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()
        self._seed()

    # -- low level helpers ------------------------------------------------
    def execute(self, sql: str, params: tuple = ()) -> None:
        with self._lock:
            self._conn.execute(sql, params)
            self._conn.commit()

    def query(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def query_one(self, sql: str, params: tuple = ()) -> dict[str, Any] | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    # -- audit -------------------------------------------------------------
    def audit(self, event: str, payload: dict | None = None) -> None:
        self.execute(
            "INSERT INTO audit_events (id, ts, event, payload) VALUES (?, ?, ?, ?)",
            (new_id("evt"), now(), event, json.dumps(payload or {})),
        )

    def audit_trail(self, limit: int = 100) -> list[dict]:
        rows = self.query("SELECT * FROM audit_events ORDER BY ts DESC LIMIT ?", (limit,))
        for r in rows:
            r["payload"] = json.loads(r["payload"])
        return rows

    # -- seeds --------------------------------------------------------------
    def _seed(self) -> None:
        if self.query_one("SELECT id FROM qa_rules LIMIT 1") is None:
            for name, target, rtype, params, severity in _DEFAULT_QA_RULES:
                self.execute(
                    "INSERT INTO qa_rules (id, name, target, rule_type, params, severity, enabled, created_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
                    (new_id("rule"), name, target, rtype, json.dumps(params), severity, now()),
                )
            self.audit("qa_rules.seeded", {"count": len(_DEFAULT_QA_RULES)})
