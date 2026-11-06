"""OPSFORGE v0.3 — Enterprise AI Agent Layer.

A controlled agent architecture built on three principles:

1. **Agents are defined, not improvised.** Every agent is registered with a
   fixed plan of steps and explicit tools. Nothing outside the plan executes.
2. **Humans gate sensitive outcomes.** Steps marked ``requires_approval``
   pause the run until a named person approves or rejects. Agents cannot
   self-approve.
3. **Everything is traceable.** Each run, step, tool output, approval and
   audit event is persisted — a complete execution ledger.

The AI layer ships with a deterministic provider (template-driven, no
external calls). A real LLM provider can be plugged in later by registering
a class in ``PROVIDERS`` — no other code changes required.
"""

from __future__ import annotations

import json
import os
import threading

from ..db import Database, new_id, now
from . import qa as qa_service
from . import processes, readiness, roi, segmentation
from .adapters import AdapterError, MockCRMAdapter
from .sop import create_evidence, generate_sop, save_sop_evidence

# ---------------------------------------------------------------------------
# AI provider interface (pluggable, deterministic by default)
# ---------------------------------------------------------------------------
class LLMProvider:
    name = "base"

    def compose(self, instruction: str, context: dict) -> str:
        raise NotImplementedError


class DeterministicLLM(LLMProvider):
    """Template-driven provider. No network, no randomness — safe for enterprise demos."""

    name = "deterministic"

    def compose(self, instruction: str, context: dict) -> str:
        lines = [f"## {instruction}", ""]
        for key, value in context.items():
            if isinstance(value, dict):
                lines.append(f"- **{key}:**")
                for k, v in value.items():
                    lines.append(f"  - {k}: {v}")
            else:
                lines.append(f"- **{key}:** {value}")
        lines += ["", "*Composed by the deterministic provider (no external LLM).*"]
        return "\n".join(lines)


PROVIDERS: dict[str, LLMProvider] = {p.name: p for p in (DeterministicLLM(),)}


def get_provider() -> LLMProvider:
    chosen = os.environ.get("OPSFORGE_LLM_PROVIDER", "deterministic")
    provider = PROVIDERS.get(chosen)
    if provider is None:
        raise ValueError(f"Unknown OPSFORGE_LLM_PROVIDER '{chosen}'. Available: {', '.join(PROVIDERS)}")
    return provider


# ---------------------------------------------------------------------------
# agent definitions — explicit plans, explicit tools
# ---------------------------------------------------------------------------
SAMPLE_CSV = (
    "email,consent\n"
    "alex@example.com,yes\n"
    "blake@example.com,yes\n"
    "alex@example.com,yes\n"          # duplicate -> warn
    "casey@example.com,\n"            # consent missing -> blocked
    "not-an-email,yes\n"              # invalid format -> warn
)

SAMPLE_CAMPAIGN_BAD = MockCRMAdapter().get_campaign("CMP-1002")
SAMPLE_CAMPAIGN_GOOD = MockCRMAdapter().get_campaign("CMP-1001")


def _sample_task(agent_id: str) -> dict:
    """Deterministic sample tasks so every agent can be demonstrated safely."""
    if agent_id == "qa_agent":
        return {"campaign": SAMPLE_CAMPAIGN_BAD, "use_sample": True}
    if agent_id == "sop_agent":
        return {
            "process": {
                "name": "Campaign QA (sample)",
                "description": "Pre-deployment quality assurance for email campaigns.",
                "owner": "Marketing Operations",
            }
        }
    if agent_id == "segmentation_agent":
        return {"csv": SAMPLE_CSV}
    if agent_id == "readiness_agent":
        return {
            "checks": {
                "audience_validated": True,
                "consent_confirmed": True,
                "subject_line_final": True,
                "urls_tested": False,
                "tracking_configured": None,
                "html_reviewed": True,
                "personalisation_tested": True,
                "assets_approved": True,
                "rollback_plan": None,
            }
        }
    if agent_id == "reporting_agent":
        return {"period": "current"}
    raise ValueError(f"No sample task defined for agent '{agent_id}'.")


AGENT_CATALOG: dict[str, dict] = {
    "qa_agent": {
        "id": "qa_agent",
        "name": "Campaign QA Agent",
        "role": "Runs rule-driven campaign QA and files evidence; escalates sign-off to a human.",
        "plan": [
            {"name": "Run campaign QA", "tool": "qa.run_email_qa", "requires_approval": False},
            {"name": "File QA evidence", "tool": "evidence.create", "requires_approval": False},
            {"name": "QA sign-off", "tool": "qa.signoff", "requires_approval": True},
        ],
    },
    "sop_agent": {
        "id": "sop_agent",
        "name": "SOP Drafting Agent",
        "role": "Drafts a human-readable SOP for a process and files it as evidence.",
        "plan": [
            {"name": "Generate SOP draft", "tool": "sop.generate", "requires_approval": False},
            {"name": "File SOP evidence", "tool": "sop.evidence", "requires_approval": False},
        ],
    },
    "segmentation_agent": {
        "id": "segmentation_agent",
        "name": "Audience Validation Agent",
        "role": "Validates audience CSVs for structure, duplicates and consent before campaign use.",
        "plan": [
            {"name": "Validate audience", "tool": "segmentation.validate", "requires_approval": False},
            {"name": "File validation evidence", "tool": "evidence.create", "requires_approval": False},
        ],
    },
    "readiness_agent": {
        "id": "readiness_agent",
        "name": "Deployment Readiness Agent",
        "role": "Nine-point release readiness assessment; recommendation only — humans deploy.",
        "plan": [
            {"name": "Assess deployment readiness", "tool": "deployment.assess", "requires_approval": False},
            {"name": "File readiness evidence", "tool": "evidence.create", "requires_approval": False},
            {"name": "Release recommendation sign-off", "tool": "deployment.signoff", "requires_approval": True},
        ],
    },
    "reporting_agent": {
        "id": "reporting_agent",
        "name": "Operations Reporting Agent",
        "role": "Collects operational KPIs and composes a management summary via the AI provider.",
        "plan": [
            {"name": "Collect metrics", "tool": "metrics.collect", "requires_approval": False},
            {"name": "Compose summary", "tool": "report.compose", "requires_approval": False},
            {"name": "File report evidence", "tool": "evidence.create", "requires_approval": False},
        ],
    },
}


# ---------------------------------------------------------------------------
# tool registry — every tool receives (db, task, previous_output)
# ---------------------------------------------------------------------------
def _tool_qa_email(db: Database, task: dict, _prev) -> dict:
    campaign = task.get("campaign")
    if not campaign:
        raise ValueError("Task requires a 'campaign' object.")
    return qa_service.run_email_qa(db, campaign)


def _tool_evidence_create(db: Database, task: dict, prev) -> dict:
    kind = task.get("evidence_kind") or "agent_output"
    title = task.get("evidence_title") or f"{kind} — {now():.0f}"
    payload = prev if isinstance(prev, dict) else {"output": prev}
    return create_evidence(db, {"kind": kind, "title": title, "payload": payload})


def _tool_qa_signoff(db: Database, task: dict, prev) -> dict:
    """Executes only after human approval — records the sign-off against the run."""
    approval = db.query_one(
        "SELECT * FROM approvals WHERE run_id = ? AND decision = 'approve'"
        " ORDER BY created_at DESC LIMIT 1",
        (_current_run_id(db),),
    )
    return {
        "sign_off": "approved_by_human",
        "approver": approval["approver"] if approval else None,
        "note": "QA outcome accepted by a named human; OPSFORGE never approves itself.",
        "prior_result": prev,
    }


def _tool_sop_generate(db: Database, task: dict, _prev) -> dict:
    process_id = task.get("process_id")
    if not process_id and isinstance(task.get("process"), dict):
        process_id = processes.create_process(db, task["process"])["id"]
    if not process_id:
        raise ValueError("Task requires 'process_id' or a 'process' object.")
    return generate_sop(db, process_id)


def _tool_sop_evidence(db: Database, _task: dict, prev) -> dict:
    if not isinstance(prev, dict) or "sop_markdown" not in prev:
        raise ValueError("SOP evidence requires the output of sop.generate.")
    return save_sop_evidence(db, prev)


def _tool_segmentation(db: Database, task: dict, _prev) -> dict:
    return segmentation.validate_segmentation(db, {"csv": task.get("csv", ""), **{
        k: v for k, v in task.items() if k == "volume_cap"
    }})


def _tool_deployment_assess(db: Database, task: dict, _prev) -> dict:
    return readiness.assess_deployment(db, task.get("checks") or task)


def _tool_deployment_signoff(db: Database, _task: dict, prev) -> dict:
    approval = db.query_one(
        "SELECT * FROM approvals WHERE run_id = ? AND decision = 'approve'"
        " ORDER BY created_at DESC LIMIT 1",
        (_current_run_id(db),),
    )
    return {
        "sign_off": "approved_by_human",
        "approver": approval["approver"] if approval else None,
        "note": "Release recommendation accepted by a named human. Deployment itself remains a human action.",
        "prior_result": prev,
    }


def _collect_metrics(db: Database) -> dict:
    def count(table: str) -> int:
        row = db.query_one(f"SELECT COUNT(*) AS n FROM {table}")
        return int(row["n"]) if row else 0

    return {
        "processes": count("processes"),
        "assessments": count("assessments"),
        "evidence_records": count("evidence"),
        "qa_rules": count("qa_rules"),
        "agent_runs": count("agent_runs"),
        "approvals": count("approvals"),
        "audit_events": count("audit_events"),
    }


def _tool_metrics(db: Database, task: dict, _prev) -> dict:
    return {"period": task.get("period", "current"), "metrics": _collect_metrics(db)}


def _tool_report_compose(db: Database, task: dict, prev) -> dict:
    provider = get_provider()
    summary = provider.compose(
        "Operations summary", prev.get("metrics", {}) if isinstance(prev, dict) else {}
    )
    return {"provider": provider.name, "report_markdown": summary}


TOOLS = {
    "qa.run_email_qa": _tool_qa_email,
    "evidence.create": _tool_evidence_create,
    "qa.signoff": _tool_qa_signoff,
    "sop.generate": _tool_sop_generate,
    "sop.evidence": _tool_sop_evidence,
    "segmentation.validate": _tool_segmentation,
    "deployment.assess": _tool_deployment_assess,
    "deployment.signoff": _tool_deployment_signoff,
    "metrics.collect": _tool_metrics,
    "report.compose": _tool_report_compose,
}

# bookkeeping used by sign-off tools to locate the current run (per thread,
# because the HTTP server handles requests concurrently)
_RUN_ID_CONTEXT = threading.local()


def _current_run_id(db: Database) -> str | None:
    return getattr(_RUN_ID_CONTEXT, "current", None)


# ---------------------------------------------------------------------------
# orchestrator — the run state machine
# ---------------------------------------------------------------------------
def list_agents() -> list[dict]:
    return list(AGENT_CATALOG.values())


def get_agent(agent_id: str) -> dict:
    agent = AGENT_CATALOG.get(agent_id)
    if agent is None:
        raise LookupError(f"Agent '{agent_id}' is not registered.")
    return agent


def start_run(db: Database, agent_id: str, task: dict) -> dict:
    agent = get_agent(agent_id)
    if task.get("use_sample"):
        task = _sample_task(agent_id)
    if not isinstance(task, dict) or not task:
        raise ValueError("Run requires a task object (or use_sample: true).")

    run_id = new_id("run")
    ts = now()
    db.execute(
        "INSERT INTO agent_runs (id, agent_id, task, status, current_step, result, created_at, updated_at)"
        " VALUES (?, ?, ?, 'running', 0, 'null', ?, ?)",
        (run_id, agent_id, json.dumps(task), ts, ts),
    )
    for seq, step in enumerate(agent["plan"], start=1):
        db.execute(
            "INSERT INTO agent_steps (id, run_id, seq, name, tool, requires_approval, status,"
            " input, output, error, started_at, finished_at)"
            " VALUES (?, ?, ?, ?, ?, ?, 'pending', 'null', 'null', '', NULL, NULL)",
            (new_id("stp"), run_id, seq, step["name"], step["tool"],
             1 if step["requires_approval"] else 0),
        )
    db.audit("agent_run.started", {"run_id": run_id, "agent_id": agent_id})
    _advance(db, run_id)
    return get_run(db, run_id)


def _advance(db: Database, run_id: str) -> None:
    """Execute the run's plan step by step, pausing at approval gates."""
    run = db.query_one("SELECT * FROM agent_runs WHERE id = ?", (run_id,))
    if run is None:
        raise LookupError(f"Run {run_id} not found.")
    if run["status"] in ("completed", "failed", "rejected"):
        return

    steps = db.query("SELECT * FROM agent_steps WHERE run_id = ? ORDER BY seq", (run_id,))
    result = None
    previous = None
    _RUN_ID_CONTEXT.current = run_id
    try:
        for step in steps:
            status = step["status"]
            if status == "done":
                result = json.loads(step["output"])
                previous = result
                continue
            if status == "pending_approval":
                approved = db.query_one(
                    "SELECT id FROM approvals WHERE run_id = ? AND step_seq = ? AND decision = 'approve'",
                    (run_id, step["seq"]),
                )
                if approved is None:
                    db.execute("UPDATE agent_runs SET status = 'pending_approval', updated_at = ? WHERE id = ?",
                               (now(), run_id))
                    return  # pause — a human must decide
            if status == "cancelled":
                continue

            if step["requires_approval"]:
                approved = db.query_one(
                    "SELECT id FROM approvals WHERE run_id = ? AND step_seq = ? AND decision = 'approve'",
                    (run_id, step["seq"]),
                )
                if approved is None:
                    db.execute("UPDATE agent_steps SET status = 'pending_approval' WHERE id = ?",
                               (step["id"],))
                    db.execute("UPDATE agent_runs SET status = 'pending_approval', current_step = ?,"
                               " updated_at = ? WHERE id = ?", (step["seq"], now(), run_id))
                    db.audit("agent_run.awaiting_approval",
                             {"run_id": run_id, "step": step["seq"], "tool": step["tool"]})
                    return

            # execute the tool
            db.execute("UPDATE agent_steps SET status = 'running', started_at = ? WHERE id = ?",
                       (now(), step["id"]))
            try:
                tool = TOOLS.get(step["tool"])
                if tool is None:
                    raise AdapterError(f"Tool '{step['tool']}' is not registered.")
                output = tool(db, json.loads(run["task"]), previous)
                previous = output
                result = output
                db.execute(
                    "UPDATE agent_steps SET status = 'done', output = ?, finished_at = ? WHERE id = ?",
                    (json.dumps(output), now(), step["id"]),
                )
                db.audit("agent_step.executed",
                         {"run_id": run_id, "seq": step["seq"], "tool": step["tool"]})
            except Exception as exc:
                db.execute(
                    "UPDATE agent_steps SET status = 'failed', error = ?, finished_at = ? WHERE id = ?",
                    (str(exc), now(), step["id"]),
                )
                db.execute("UPDATE agent_runs SET status = 'failed', result = ?, updated_at = ? WHERE id = ?",
                           (json.dumps({"error": str(exc)}), now(), run_id))
                db.audit("agent_step.failed", {"run_id": run_id, "seq": step["seq"], "error": str(exc)})
                return
    finally:
        _RUN_ID_CONTEXT.current = None

    db.execute("UPDATE agent_runs SET status = 'completed', result = ?, updated_at = ? WHERE id = ?",
               (json.dumps(result), now(), run_id))
    db.audit("agent_run.completed", {"run_id": run_id})


# ---------------------------------------------------------------------------
# approval gate verdicts (v0.4) — a human cannot silently sign off a failure
# ---------------------------------------------------------------------------
OVERRIDE_MIN_CHARS = 15

# result value -> (severity, human label). "block" means approval needs an override reason.
_VERDICTS = {
    "fail": ("block", "Campaign QA failed"),
    "not_ready": ("block", "Deployment readiness: NOT READY"),
    "flagged_for_review": ("caution", "QA flagged items for human review"),
    "pass_with_warnings": ("caution", "QA passed with warnings"),
    "needs_human_review": ("caution", "Readiness needs human review"),
    "pass": ("ok", "Campaign QA passed"),
    "ready": ("ok", "Deployment readiness: READY"),
}


def assess_gate(db: Database, run_id: str) -> dict:
    """Summarise what the human is being asked to approve, from the run's own step outputs."""
    steps = db.query("SELECT * FROM agent_steps WHERE run_id = ? AND status = 'done' ORDER BY seq",
                     (run_id,))
    for step in steps:
        out = json.loads(step["output"])
        if not isinstance(out, dict):
            continue
        if step["tool"] == "qa.run_email_qa":
            value = out.get("overall")
            detail = out.get("summary", {})
        elif step["tool"] == "deployment.assess":
            value = out.get("status")
            detail = {"score": out.get("score"), "failed_points": out.get("failed_points"),
                      "review_points": out.get("review_points")}
        else:
            continue
        severity, label = _VERDICTS.get(value, ("caution", f"Unrecognised result: {value}"))
        return {
            "verdict": value,
            "severity": severity,
            "label": label,
            "source_tool": step["tool"],
            "detail": detail,
            "override_required": severity == "block",
            "override_min_chars": OVERRIDE_MIN_CHARS,
        }
    return {"verdict": None, "severity": "none", "label": "No assessed result to review",
            "source_tool": None, "detail": {}, "override_required": False,
            "override_min_chars": OVERRIDE_MIN_CHARS}


def approve_step(db: Database, run_id: str, step_seq: int, approver: str, comment: str = "",
                 override_reason: str = "") -> dict:
    run = db.query_one("SELECT * FROM agent_runs WHERE id = ?", (run_id,))
    if run is None:
        raise LookupError(f"Run {run_id} not found.")
    step = db.query_one("SELECT * FROM agent_steps WHERE run_id = ? AND seq = ?", (run_id, step_seq))
    if step is None:
        raise LookupError(f"Step {step_seq} not found in run {run_id}.")
    if step["requires_approval"] != 1:
        raise ValueError("This step does not require approval.")
    if step["status"] not in ("pending_approval",):
        raise ValueError(f"Step is not awaiting approval (status: {step['status']}).")
    if run["status"] != "pending_approval":
        raise ValueError(f"Run is not awaiting approval (status: {run['status']}).")
    if not (approver or "").strip():
        raise ValueError("A named human approver is required.")

    gate = assess_gate(db, run_id)
    reason = (override_reason or "").strip()
    if gate["override_required"] and len(reason) < OVERRIDE_MIN_CHARS:
        raise ValueError(
            f"{gate['label']}. Approving this result is an override and needs a written reason "
            f"of at least {OVERRIDE_MIN_CHARS} characters."
        )

    stored_comment = comment or ""
    if gate["override_required"]:
        stored_comment = f"[OVERRIDE: {gate['verdict']}] {reason}" + (f" | {comment}" if comment else "")

    db.execute(
        "INSERT INTO approvals (id, run_id, step_seq, approver, decision, comment, created_at)"
        " VALUES (?, ?, ?, ?, 'approve', ?, ?)",
        (new_id("apr"), run_id, step_seq, approver.strip(), stored_comment, now()),
    )
    if gate["override_required"]:
        db.audit("approval.override", {
            "run_id": run_id, "step_seq": step_seq, "approver": approver.strip(),
            "verdict": gate["verdict"], "reason": reason,
        })
    else:
        db.audit("approval.granted", {"run_id": run_id, "step_seq": step_seq,
                                      "approver": approver.strip(), "verdict": gate["verdict"]})
    _advance(db, run_id)
    return get_run(db, run_id)


def reject_step(db: Database, run_id: str, step_seq: int, approver: str, comment: str = "") -> dict:
    run = db.query_one("SELECT * FROM agent_runs WHERE id = ?", (run_id,))
    step = db.query_one("SELECT * FROM agent_steps WHERE run_id = ? AND seq = ?", (run_id, step_seq))
    if run is None or step is None:
        raise LookupError("Run or step not found.")
    if step["status"] not in ("pending_approval", "pending"):
        raise ValueError("This step cannot be rejected in its current state.")
    if not (approver or "").strip():
        raise ValueError("A named human approver is required.")

    db.execute(
        "INSERT INTO approvals (id, run_id, step_seq, approver, decision, comment, created_at)"
        " VALUES (?, ?, ?, ?, 'reject', ?, ?)",
        (new_id("apr"), run_id, step_seq, approver.strip(), comment or "", now()),
    )
    db.execute("UPDATE agent_steps SET status = 'cancelled', finished_at = ? WHERE id = ?",
               (now(), step["id"]))
    db.execute(
        "UPDATE agent_steps SET status = 'cancelled', finished_at = ?"
        " WHERE run_id = ? AND seq > ? AND status IN ('pending', 'pending_approval')",
        (now(), run_id, step_seq),
    )
    db.execute("UPDATE agent_runs SET status = 'rejected', updated_at = ? WHERE id = ?", (now(), run_id))
    db.audit("approval.rejected", {"run_id": run_id, "step_seq": step_seq, "approver": approver.strip()})
    return get_run(db, run_id)


def list_runs(db: Database, agent_id: str | None = None) -> list[dict]:
    if agent_id:
        rows = db.query("SELECT * FROM agent_runs WHERE agent_id = ? ORDER BY created_at DESC", (agent_id,))
    else:
        rows = db.query("SELECT * FROM agent_runs ORDER BY created_at DESC")
    return [_run_view(db, r, with_steps=False) for r in rows]


def get_run(db: Database, run_id: str) -> dict:
    run = db.query_one("SELECT * FROM agent_runs WHERE id = ?", (run_id,))
    if run is None:
        raise LookupError(f"Run {run_id} not found.")
    return _run_view(db, run, with_steps=True)


def _run_view(db: Database, run: dict, with_steps: bool) -> dict:
    view = {
        "id": run["id"],
        "agent_id": run["agent_id"],
        "status": run["status"],
        "current_step": run["current_step"],
        "task": json.loads(run["task"]),
        "result": json.loads(run["result"]),
        "created_at": run["created_at"],
        "updated_at": run["updated_at"],
    }
    if with_steps:
        steps = db.query("SELECT * FROM agent_steps WHERE run_id = ? ORDER BY seq", (run["id"],))
        for s in steps:
            s["output"] = json.loads(s["output"])
            s["input"] = json.loads(s["input"])
            s["requires_approval"] = bool(s["requires_approval"])
        view["steps"] = steps
        view["approvals"] = list_approvals(db, run["id"])
        view["gate"] = assess_gate(db, run["id"])
    return view


def list_approvals(db: Database, run_id: str | None = None) -> list[dict]:
    if run_id:
        rows = db.query("SELECT * FROM approvals WHERE run_id = ? ORDER BY created_at", (run_id,))
    else:
        rows = db.query("SELECT * FROM approvals ORDER BY created_at DESC")
    return rows


def list_audit(db: Database, limit: int = 100) -> list[dict]:
    return db.audit_trail(limit)
