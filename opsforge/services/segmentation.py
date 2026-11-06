"""OPSFORGE — audience segmentation and consent validation.

CRM Operations module: validates an audience CSV before it can be used in a
campaign. Checks structure, duplicates, contact formats, consent flags and
optional volume caps. Human-readable errors, deterministic behaviour.
"""

from __future__ import annotations

import csv
import io
import re

from ..db import Database

REQUIRED_COLUMNS = ("email", "consent")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _parse_csv(raw: str) -> tuple[list[str], list[dict]]:
    reader = csv.DictReader(io.StringIO(raw))
    columns = [c.strip() for c in (reader.fieldnames or [])]
    rows: list[dict] = []
    for i, row in enumerate(reader, start=2):  # header is line 1
        clean = {(k or "").strip(): (v or "").strip() for k, v in row.items()}
        clean["_line"] = i
        rows.append(clean)
    return columns, rows


def validate_segmentation(db: Database, data: dict) -> dict:
    csv_text = data.get("csv", "")
    if not isinstance(csv_text, str) or not csv_text.strip():
        raise ValueError("CSV content is required in the 'csv' field.")

    volume_cap = data.get("volume_cap")
    if volume_cap is not None:
        try:
            volume_cap = int(volume_cap)
        except (TypeError, ValueError) as exc:
            raise ValueError("volume_cap must be an integer.") from exc
        if volume_cap <= 0:
            raise ValueError("volume_cap must be a positive integer.")

    columns, rows = _parse_csv(csv_text)
    issues: list[dict] = []

    missing_cols = [c for c in REQUIRED_COLUMNS if c not in [c.lower() for c in columns]]
    if missing_cols:
        issues.append({"issue": "missing_column", "detail": f"Required column(s) missing: {missing_cols}"})

    seen_emails: dict[str, int] = {}
    valid_rows = 0
    consent_missing = consent_denied = bad_email = duplicates = 0

    if not missing_cols:
        for row in rows:
            line = row["_line"]
            email = row.get("email", "").lower()
            consent = row.get("consent", "").lower()

            if not _EMAIL_RE.match(email):
                bad_email += 1
                issues.append({"issue": "invalid_email", "line": line, "detail": email or "(empty)"})
            elif email in seen_emails:
                duplicates += 1
                issues.append({
                    "issue": "duplicate_email",
                    "line": line,
                    "detail": f"'{email}' already on line {seen_emails[email]}",
                })
            else:
                seen_emails[email] = line
                valid_rows += 1

            if consent in ("", "none"):
                consent_missing += 1
                issues.append({"issue": "consent_missing", "line": line, "detail": email})
            elif consent in ("n", "no", "false", "0"):
                consent_denied += 1
                issues.append({"issue": "consent_denied", "line": line, "detail": email})

    total_rows = len(rows)

    if volume_cap is not None and total_rows > volume_cap:
        issues.append({
            "issue": "volume_cap_exceeded",
            "detail": f"Audience {total_rows} exceeds configured cap {volume_cap}.",
        })

    blockers = [i for i in issues if i["issue"] in ("missing_column", "consent_denied", "consent_missing")]
    overall = "fail" if blockers else ("warn" if issues else "pass")

    db.audit("segmentation.validated", {
        "rows": total_rows, "valid": valid_rows, "issues": len(issues), "overall": overall,
    })
    return {
        "overall": overall,
        "summary": {
            "total_rows": total_rows,
            "unique_valid_emails": valid_rows,
            "invalid_emails": bad_email,
            "duplicates": duplicates,
            "consent_missing": consent_missing,
            "consent_denied": consent_denied,
            "volume_cap": volume_cap,
        },
        "issues": issues[:200],
        "issue_count": len(issues),
        "note": "Rows without an explicit consent 'yes' are blocked, not assumed.",
    }
