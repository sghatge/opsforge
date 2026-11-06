"""OPSFORGE — process register and CSA (Current State Assessment) scoring.

Operations Intelligence module: register business processes, assess their
standardisation / automation maturity and identify automation candidates.
"""

from __future__ import annotations

import json

from ..db import Database, new_id, now

# CSA dimensions scored 1-5: 1 = fully manual/undefined, 5 = automated/optimised.
DIMENSIONS = ("documentation", "standardization", "automation", "measurement", "governance")


def create_process(db: Database, data: dict) -> dict:
    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("Process name is required.")
    row = {
        "id": new_id("prc"),
        "name": name,
        "description": (data.get("description") or "").strip(),
        "owner": (data.get("owner") or "").strip(),
        "status": "active",
        "created_at": now(),
    }
    db.execute(
        "INSERT INTO processes (id, name, description, owner, status, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        tuple(row.values()),
    )
    db.audit("process.created", {"id": row["id"], "name": name})
    return row


def list_processes(db: Database) -> list[dict]:
    return db.query("SELECT * FROM processes ORDER BY created_at DESC")


def get_process(db: Database, process_id: str) -> dict:
    row = db.query_one("SELECT * FROM processes WHERE id = ?", (process_id,))
    if row is None:
        raise LookupError(f"Process {process_id} not found.")
    return row


def assess_process(db: Database, process_id: str, scores: dict) -> dict:
    """Score a process against the five CSA dimensions (each 1-5)."""
    process = get_process(db, process_id)
    clean: dict[str, int] = {}
    for dim in DIMENSIONS:
        value = scores.get(dim)
        if not isinstance(value, int) or not 1 <= value <= 5:
            raise ValueError(f"Score for '{dim}' must be an integer between 1 and 5.")
        clean[dim] = value

    total = sum(clean.values())
    level = _maturity_level(total)
    assessment = {
        "id": new_id("ass"),
        "process_id": process_id,
        "scores": clean,
        "total": total,
        "level": level,
        "created_at": now(),
    }
    db.execute(
        "INSERT INTO assessments (id, process_id, scores, total, level, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (
            assessment["id"],
            process_id,
            json.dumps(clean),
            total,
            level,
            assessment["created_at"],
        ),
    )
    db.audit("process.assessed", {"process_id": process_id, "total": total, "level": level})
    return assessment


def _maturity_level(total: int) -> str:
    if total <= 9:
        return "Manual"
    if total <= 15:
        return "Emerging"
    if total <= 20:
        return "Standardised"
    return "Optimised"
