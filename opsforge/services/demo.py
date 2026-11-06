"""OPSFORGE — demo data seeder.

Populates an empty database with realistic, de-identified sample data by
calling the platform's own services and agents — exactly the path a real
user would take. Nothing is inserted directly behind the services' backs.

Idempotent: if the database already contains data, seeding is skipped.
Every demo record is clearly labelled "(demo)".
"""

from __future__ import annotations

from ..db import Database
from . import processes, qa, readiness, roi, segmentation
from .agents import approve_step, get_run, start_run
from .adapters import MockCRMAdapter, check_adapter, list_adapters
from .sop import create_evidence, generate_sop, save_sop_evidence

# ---------------------------------------------------------------------------
# sample content (de-identified, synthetic)
# ---------------------------------------------------------------------------
PROCESSES = [
    {
        "name": "Campaign Quality Assurance (demo)",
        "owner": "Marketing Operations",
        "description": "Pre-deployment QA for outbound email campaigns: content, links, tracking and compliance checks.",
        "scores": {"documentation": 3, "standardization": 2, "automation": 1, "measurement": 2, "governance": 2},
    },
    {
        "name": "Customer Data Validation (demo)",
        "owner": "CRM Data Team",
        "description": "Validation of customer records, consent status and contactability before campaign use.",
        "scores": {"documentation": 4, "standardization": 3, "automation": 2, "measurement": 3, "governance": 3},
    },
    {
        "name": "Executive Reporting (demo)",
        "owner": "Sales Operations",
        "description": "Weekly and monthly performance reporting assembled from campaign and CRM data.",
        "scores": {"documentation": 2, "standardization": 2, "automation": 1, "measurement": 1, "governance": 1},
    },
]

CLEAN_AUDIENCE_CSV = (
    "email,consent\n"
    "alex.example@example.com,yes\n"
    "blake.example@example.com,yes\n"
    "casey.example@example.com,yes\n"
    "devon.example@example.com,yes\n"
)

MIXED_AUDIENCE_CSV = (
    "email,consent\n"
    "alex.example@example.com,yes\n"
    "alex.example@example.com,yes\n"      # duplicate
    "casey.example@example.com,\n"        # consent missing
    "not-an-email,yes\n"                  # invalid format
)

READYNESS_CHECKS = {
    "audience_validated": True,
    "consent_confirmed": True,
    "subject_line_final": True,
    "urls_tested": True,
    "tracking_configured": True,
    "html_reviewed": True,
    "personalisation_tested": None,   # unclear -> human review
    "assets_approved": True,
    "rollback_plan": None,            # unclear -> human review
}

ROI_INPUTS = {
    "process": "Campaign Quality Assurance (demo)",
    "hours_manual_per_week": 10,
    "reduction_pct": 50,
    "hourly_cost": 40,
    "implementation_cost": 2000,
    "maintenance_cost_year": 400,
    "review_cost_year": 300,
}


def _good_campaign() -> dict:
    campaign = dict(MockCRMAdapter().get_campaign("CMP-1001"))
    campaign["name"] = "Autumn Newsletter (demo)"
    return campaign


def _bad_campaign() -> dict:
    campaign = dict(MockCRMAdapter().get_campaign("CMP-1002"))
    campaign["name"] = "Winback Series — failing sample (demo)"
    return campaign


# ---------------------------------------------------------------------------
# seeder
# ---------------------------------------------------------------------------
def seed_demo(db: Database) -> dict:
    if db.query_one("SELECT id FROM processes LIMIT 1") is not None:
        return {"seeded": False, "note": "Database already contains data — demo seed skipped."}

    # 1. processes, maturity assessments, SOP drafts
    process_ids = []
    for spec in PROCESSES:
        payload = {k: v for k, v in spec.items() if k != "scores"}
        row = processes.create_process(db, payload)
        process_ids.append(row["id"])
        if spec.get("scores"):
            processes.assess_process(db, row["id"], spec["scores"])
    sop = generate_sop(db, process_ids[0])
    save_sop_evidence(db, sop)

    # 2. one custom QA rule to show configuration
    qa.create_rule(db, {
        "name": "Brand domain required (demo)",
        "target": "urls",
        "rule_type": "contains_url",
        "params": {"pattern": "example.com"},
        "severity": "warn",
    })

    # 3. campaign QA reports (one passing, one failing) filed as evidence
    for campaign, label in ((_good_campaign(), "pass"), (_bad_campaign(), "fail")):
        report = qa.run_email_qa(db, campaign)
        create_evidence(db, {
            "kind": "qa_report",
            "ref_id": campaign["name"],
            "title": f"QA report — {campaign['name']} [{report['overall']}]",
            "payload": report,
        })

    # 4. audience validations (one clean, one problematic) filed as evidence
    for csv_text, label in ((CLEAN_AUDIENCE_CSV, "Q4 newsletter audience"), (MIXED_AUDIENCE_CSV, "winback audience")):
        result = segmentation.validate_segmentation(db, {"csv": csv_text})
        create_evidence(db, {
            "kind": "audience_validation",
            "ref_id": label,
            "title": f"Audience validation — {label} (demo) [{result['overall']}]",
            "payload": result,
        })

    # 5. readiness assessment filed as evidence
    readiness_result = readiness.assess_deployment(db, {"checks": READYNESS_CHECKS})
    create_evidence(db, {
        "kind": "readiness_assessment",
        "title": "Deployment readiness — Autumn Newsletter (demo)",
        "payload": readiness_result,
    })

    # 6. ROI analysis filed as evidence
    roi_result = roi.calculate_roi(db, ROI_INPUTS)
    create_evidence(db, {
        "kind": "roi_analysis",
        "title": "ROI analysis — Campaign QA automation (demo)",
        "payload": roi_result,
    })

    # 7. agent runs — created through the orchestrator, like real usage
    start_run(db, "sop_agent", {"process_id": process_ids[1]})
    start_run(db, "segmentation_agent", {
        "csv": CLEAN_AUDIENCE_CSV,
        "evidence_kind": "audience_validation",
        "evidence_title": "Agent validation — Q4 newsletter audience (demo)",
    })
    start_run(db, "reporting_agent", {"period": "Q4 (demo)"})

    # a completed, human-approved QA sign-off
    approved = start_run(db, "qa_agent", {
        "campaign": _good_campaign(),
        "evidence_kind": "qa_report",
        "evidence_title": "Agent QA report — Autumn Newsletter (demo)",
    })
    gate = next(s for s in approved["steps"] if s["status"] == "pending_approval")
    approve_step(db, approved["id"], gate["seq"], "Sangram (demo approver)", "Sample accepted")

    # one run left pending on purpose — the dashboard opens with a decision to make
    start_run(db, "readiness_agent", {"checks": READYNESS_CHECKS})

    # 8. adapter connectivity checks
    for name in ("mock_crm", "adobe_campaign"):
        check_adapter(db, name)

    summary = {
        "processes": len(process_ids),
        "evidence_records": len(db.query("SELECT id FROM evidence")),
        "agent_runs": len(db.query("SELECT id FROM agent_runs")),
        "pending_approval": len(db.query("SELECT id FROM agent_runs WHERE status = 'pending_approval'")),
        "approvals": len(db.query("SELECT id FROM approvals")),
        "qa_rules": len(db.query("SELECT id FROM qa_rules")),
    }
    db.audit("demo.seeded", summary)
    return {"seeded": True, "summary": summary}
