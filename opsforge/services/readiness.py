"""OPSFORGE — deployment readiness assessment.

Nine-point readiness gate for a campaign release. Every point yields
pass / fail / review; a release recommendation is produced only for human
decision-making — OPSFORGE never deploys anything itself.
"""

from __future__ import annotations

from ..db import Database

POINTS = (
    "audience_validated",
    "consent_confirmed",
    "subject_line_final",
    "urls_tested",
    "tracking_configured",
    "html_reviewed",
    "personalisation_tested",
    "assets_approved",
    "rollback_plan",
)


def assess_deployment(db: Database, data: dict) -> dict:
    # accept either {"checks": {...}} or a flat dict of check names
    source = data.get("checks") if isinstance(data.get("checks"), dict) else data
    checks: dict[str, str] = {}
    for point in POINTS:
        value = source.get(point)
        if value is True:
            checks[point] = "pass"
        elif value is False:
            checks[point] = "fail"
        else:
            # missing or unclear — absence of evidence is uncertainty, not failure
            checks[point] = "review"

    passed = sum(1 for v in checks.values() if v == "pass")
    review = [k for k, v in checks.items() if v == "review"]
    failed = [k for k, v in checks.items() if v == "fail"]

    if failed:
        status = "not_ready"
    elif review:
        status = "needs_human_review"
    else:
        status = "ready"

    db.audit("deployment.assessed", {"status": status, "passed": passed})
    return {
        "status": status,
        "score": f"{passed}/{len(POINTS)}",
        "checks": checks,
        "failed_points": failed,
        "review_points": review,
        "recommendation": (
            "Do not deploy — blocking failures present."
            if status == "not_ready"
            else "Release decision requires named human approver." if status == "needs_human_review"
            else "All checks passed — proceed with named human approval."
        ),
        "note": "OPSFORGE provides a readiness opinion only; deployment is executed by humans.",
    }
