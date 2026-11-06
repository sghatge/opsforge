"""OPSFORGE — campaign email QA engine.

Quality Assurance module. Since v0.3 the engine is rule-driven: checks are
stored in the qa_rules table and can be added, edited, disabled or removed
through the API without touching code. Every check returns structured
evidence; anything the engine cannot determine is flagged for human review
rather than guessed.
"""

from __future__ import annotations

import json
import re

from ..db import Database, new_id, now

REQUIRED_TARGETS = ("subject", "html", "urls", "personalization", "tracking", "consent")


# ---------------------------------------------------------------------------
# rule evaluation
# ---------------------------------------------------------------------------
def _eval_rule(rule: dict, campaign: dict) -> dict:
    """Evaluate a single rule against a campaign payload.

    Returns {rule_id, rule, severity, status, detail} where status is one of
    pass | fail | warn | review.
    """
    target = rule["target"]
    rtype = rule["rule_type"]
    params = json.loads(rule["params"] or "{}")
    value = campaign.get(target)
    base = {"rule_id": rule["id"], "rule": rule["name"], "severity": rule["severity"]}

    def fail(detail: str) -> dict:
        return {**base, "status": "fail", "detail": detail}

    def pas(detail: str) -> dict:
        return {**base, "status": "pass", "detail": detail}

    def warn(detail: str) -> dict:
        return {**base, "status": "warn", "detail": detail}

    def review(detail: str) -> dict:
        return {**base, "status": "review", "detail": detail}

    try:
        if rtype == "required":
            if value is None or value == "" or value == []:
                return fail(f"Field '{target}' is missing or empty.")
            return pas(f"Field '{target}' present.")

        if rtype == "max_length":
            limit = int(params.get("max", 0))
            text = value if isinstance(value, str) else ""
            if not text:
                return fail(f"Field '{target}' is empty; cannot check length.")
            if len(text) > limit:
                return warn(f"'{target}' is {len(text)} chars (recommended max {limit}).")
            return pas(f"'{target}' length {len(text)} within limit {limit}.")

        if rtype == "regex_match":
            pattern = params.get("pattern", "")
            text = value if isinstance(value, str) else ""
            if not text:
                return fail(f"Field '{target}' is empty; cannot match pattern.")
            return pas("Pattern matched.") if re.search(pattern, text) else fail(
                f"Field '{target}' does not match required pattern."
            )

        if rtype == "regex_forbid":
            pattern = params.get("pattern", "")
            text = value if isinstance(value, str) else ""
            if not text:
                return pas("Field empty — nothing to forbid.")
            return fail("Forbidden pattern found.") if re.search(pattern, text) else pas(
                "No forbidden pattern found."
            )

        if rtype == "balanced_tags":
            text = value if isinstance(value, str) else ""
            if not text.strip():
                return pas("No personalisation text supplied.")
            opens = len(re.findall(r"<%=?", text)) + len(re.findall(r"\{\{", text))
            closes = len(re.findall(r"%>", text)) + len(re.findall(r"}}", text))
            if opens != closes:
                return fail(f"Unbalanced personalisation tags: {opens} opened, {closes} closed.")
            return pas(f"Personalisation tags balanced ({opens} pairs).")

        if rtype == "url_format":
            urls = value if isinstance(value, list) else []
            if not urls:
                return review("No URLs supplied for validation.")
            bad = [u for u in urls if not re.match(r"^https?://\S+$", str(u))]
            if bad:
                return fail(f"Invalid URL format: {bad}")
            return pas(f"All {len(urls)} URL(s) well-formed.")

        if rtype == "contains_url":
            urls = campaign.get("urls") if isinstance(campaign.get("urls"), list) else []
            pattern = params.get("pattern", "")
            for u in urls:
                if pattern.lower() in str(u).lower():
                    return pas(f"URL matching '{pattern}' found.")
            return fail(f"No URL containing '{pattern}' found.")

        if rtype == "truthy":
            if value in (True, 1, "true", "yes"):
                return pas(f"'{target}' is set.")
            if value in (False, 0, None):
                return fail(f"'{target}' must be set to true.")
            return review(f"'{target}' has unclear value {value!r}; needs human confirmation.")

        return review(f"Unknown rule type '{rtype}' — flagged for human review.")

    except Exception as exc:  # never let one broken rule crash a QA run
        return review(f"Rule evaluation error: {exc}")


def run_email_qa(db: Database, campaign: dict) -> dict:
    """Run every enabled QA rule against a campaign payload."""
    if not isinstance(campaign, dict) or not campaign:
        raise ValueError("Campaign payload must be a non-empty object.")

    rules = db.query("SELECT * FROM qa_rules WHERE enabled = 1 ORDER BY created_at, id")
    checks = [_eval_rule(r, campaign) for r in rules]

    failed = [c for c in checks if c["status"] == "fail"]
    warned = [c for c in checks if c["status"] == "warn"]
    review = [c for c in checks if c["status"] == "review"]

    if failed:
        overall = "fail"
    elif review:
        overall = "flagged_for_review"
    elif warned:
        overall = "pass_with_warnings"
    else:
        overall = "pass"

    db.audit("qa.executed", {"campaign": campaign.get("name", "unnamed"), "overall": overall})
    return {
        "campaign": campaign.get("name", "unnamed campaign"),
        "overall": overall,
        "summary": {
            "total_checks": len(checks),
            "failed": len(failed),
            "warnings": len(warned),
            "needs_review": len(review),
            "passed": sum(1 for c in checks if c["status"] == "pass"),
        },
        "checks": checks,
    }


# ---------------------------------------------------------------------------
# rule management
# ---------------------------------------------------------------------------
_RULE_TYPES = ("required", "max_length", "regex_match", "regex_forbid", "balanced_tags",
               "url_format", "contains_url", "truthy")


def create_rule(db: Database, data: dict) -> dict:
    name = (data.get("name") or "").strip()
    target = (data.get("target") or "").strip()
    rtype = (data.get("rule_type") or "").strip()
    if not name or not target or not rtype:
        raise ValueError("Rule requires 'name', 'target' and 'rule_type'.")
    if rtype not in _RULE_TYPES:
        raise ValueError(f"rule_type must be one of: {', '.join(_RULE_TYPES)}.")
    severity = data.get("severity", "error")
    if severity not in ("error", "warn"):
        raise ValueError("severity must be 'error' or 'warn'.")
    rule_id = new_id("rule")
    db.execute(
        "INSERT INTO qa_rules (id, name, target, rule_type, params, severity, enabled, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (rule_id, name, target, rtype, json.dumps(data.get("params") or {}), severity,
         1 if data.get("enabled", True) else 0, now()),
    )
    db.audit("qa_rule.created", {"id": rule_id, "name": name, "rule_type": rtype})
    return get_rule(db, rule_id)


def list_rules(db: Database) -> list[dict]:
    return db.query("SELECT * FROM qa_rules ORDER BY created_at, id")


def get_rule(db: Database, rule_id: str) -> dict:
    row = db.query_one("SELECT * FROM qa_rules WHERE id = ?", (rule_id,))
    if row is None:
        raise LookupError(f"QA rule {rule_id} not found.")
    return row


def update_rule(db: Database, rule_id: str, data: dict) -> dict:
    current = get_rule(db, rule_id)
    name = data.get("name", current["name"])
    severity = data.get("severity", current["severity"])
    if severity not in ("error", "warn"):
        raise ValueError("severity must be 'error' or 'warn'.")
    enabled = int(bool(data.get("enabled", current["enabled"])))
    params = json.dumps(data.get("params") or json.loads(current["params"] or "{}"))
    db.execute(
        "UPDATE qa_rules SET name = ?, severity = ?, enabled = ?, params = ? WHERE id = ?",
        (name, severity, enabled, params, rule_id),
    )
    db.audit("qa_rule.updated", {"id": rule_id, "name": name, "enabled": bool(enabled)})
    return get_rule(db, rule_id)


def delete_rule(db: Database, rule_id: str) -> dict:
    rule = get_rule(db, rule_id)
    db.execute("DELETE FROM qa_rules WHERE id = ?", (rule_id,))
    db.audit("qa_rule.deleted", {"id": rule_id, "name": rule["name"]})
    return {"deleted": rule_id}
