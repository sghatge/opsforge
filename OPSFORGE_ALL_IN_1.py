"""
OPSFORGE — ALL IN ONE
Prompt + policy + four missions + local Streamlit UI.
Run: streamlit run OPSFORGE_ALL_IN_1.py
Test: python OPSFORGE_ALL_IN_1.py --test

Operating contract:
NEWS + IDEA + EXECUTING STEPS + FULL STOP.
File-first, gate-first, audit-first. AI news only in the existing
08:00 Asia/Kolkata daily briefing. Synthetic data only; no production connector.

This is a local portfolio/demo application, not a production authorization service.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any

POLICIES: dict[str, dict[str, dict[str, str]]] = {
    "default": {
        "campaign_discover": {"decision": "allow", "reason": "read-only"},
        "schema_browse": {"decision": "allow", "reason": "read-only"},
        "query_run": {"decision": "allow_masked", "reason": "mask PII in samples"},
        "delivery_qa": {"decision": "allow", "reason": "deterministic QA"},
        "delivery_send": {"decision": "needs_approval", "reason": "send requires human approval"},
        "workflow_control": {"decision": "needs_approval", "reason": "workflow control requires review"},
        "js_execute": {"decision": "dry_run", "reason": "analysis only"},
    },
    "workspace": {
        "gmail.read": {"decision": "allow", "reason": "read-only"},
        "gmail.send": {"decision": "needs_approval", "reason": "send requires human approval"},
        "gmail.send_external": {"decision": "block", "reason": "external send blocked"},
        "drive.read": {"decision": "allow_masked", "reason": "mask PII in samples"},
        "drive.share": {"decision": "needs_approval", "reason": "sharing requires human approval"},
        "drive.share_public": {"decision": "block", "reason": "public sharing blocked"},
        "docs.read": {"decision": "allow", "reason": "read-only"},
        "docs.create": {"decision": "dry_run", "reason": "draft analysis only"},
        "sheets.read": {"decision": "allow_masked", "reason": "mask PII"},
        "calendar.read": {"decision": "allow", "reason": "read-only"},
    },
    "coworker": {
        "coworker.draft": {"decision": "allow", "reason": "draft only"},
        "delivery_qa": {"decision": "allow", "reason": "deterministic QA"},
        "delivery_send": {"decision": "needs_approval", "reason": "send requires two humans and signed permit"},
        "workflow_control": {"decision": "needs_approval", "reason": "workflow control requires human review"},
        "genstudio.publish": {"decision": "needs_approval", "reason": "publishing requires human review"},
        "js_execute": {"decision": "dry_run", "reason": "analysis only"},
        "query_run": {"decision": "allow_masked", "reason": "mask PII"},
    },
    "crm": {
        "crm.read": {"decision": "allow", "reason": "read-only"},
        "crm.recommend": {"decision": "allow", "reason": "advisory only"},
        "crm.write_to_production": {"decision": "block", "reason": "advisory-only agent"},
        "crm.execute": {"decision": "block", "reason": "execution disabled"},
    },
    "analytics": {
        "analytics.calculate": {"decision": "allow", "reason": "deterministic calculation"},
        "analytics.narrate": {"decision": "allow", "reason": "narrative is not evidence"},
        "analytics.claim_without_data": {"decision": "block", "reason": "no invented metrics"},
        "creative.claim": {"decision": "dry_run", "reason": "verify before trust"},
    },
}

PII_PATTERNS = {
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "phone": re.compile(r"(?<!\d)(?:\+?91[- ]?)?[6-9]\d{9}(?!\d)"),
    "aadhaar": re.compile(r"(?<!\d)\d{4}\s\d{4}\s\d{4}(?!\d)"),
    "pan": re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),
}
WRITE_KEYS = {
    "send", "share", "publish", "write", "execute", "delete", "update",
    "insert", "drop", "truncate", "workflow_start", "workflow_stop",
    "xtk.session.write", "crm.write", "campaign.send",
}
DECISIONS = {"allow", "allow_masked", "dry_run", "needs_approval", "block"}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def mask_pii(payload: Any) -> Any:
    raw = canonical_json(payload)
    for name, pattern in PII_PATTERNS.items():
        raw = pattern.sub("[MASKED_" + name + "]", raw)
    return json.loads(raw)


def is_write_like(payload: Any) -> bool:
    """Inspect structured operation fields, not arbitrary prose/body text."""
    if isinstance(payload, dict):
        for key, value in payload.items():
            k = str(key).strip().lower()
            if k in WRITE_KEYS or k.endswith(("_write", "_send", "_publish", "_execute", "_delete")):
                if value not in (False, None, "", 0, [], {}):
                    return True
            if k in {"operation", "action", "method", "tool"} and isinstance(value, str):
                if value.strip().lower() in WRITE_KEYS:
                    return True
            if is_write_like(value):
                return True
    elif isinstance(payload, list):
        return any(is_write_like(item) for item in payload)
    return False


class AuditLog:
    """Append-only JSONL hash chain. Local demo storage; protect file permissions."""
    def __init__(self, path: str | Path = "out/audit.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.prev_hash = "GENESIS"
        if self.path.exists() and self.path.stat().st_size:
            ok, detail = self.verify(self.path)
            if not ok:
                raise ValueError("Audit chain invalid; refusing to append: " + detail)
            last = json.loads(self.path.read_text(encoding="utf-8").splitlines()[-1])
            self.prev_hash = last["hash"]

    def append(self, entry: dict[str, Any]) -> dict[str, Any]:
        clean = dict(entry)
        clean.pop("hash", None)
        clean.pop("prev_hash", None)
        blob = canonical_json(clean) + self.prev_hash
        digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()
        record = {**clean, "prev_hash": self.prev_hash, "hash": digest}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(canonical_json(record) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self.prev_hash = digest
        return record

    @staticmethod
    def verify(path: str | Path = "out/audit.jsonl") -> tuple[bool, str]:
        target = Path(path)
        if not target.exists():
            return True, "No audit entries yet"
        prev = "GENESIS"
        raw = target.read_text(encoding="utf-8")
        for number, line in enumerate(raw.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                if record.get("prev_hash") != prev:
                    return False, "Previous hash mismatch at line " + str(number)
                clean = {k: v for k, v in record.items() if k not in {"prev_hash", "hash"}}
                expected = hashlib.sha256((canonical_json(clean) + prev).encode("utf-8")).hexdigest()
                if not hmac.compare_digest(expected, str(record.get("hash", ""))):
                    return False, "Content hash mismatch at line " + str(number)
                prev = expected
            except (ValueError, TypeError, KeyError):
                return False, "Malformed audit record at line " + str(number)
        return True, "Audit chain verifies"


class Gate:
    def __init__(self, policy_name: str = "default", audit_path: str | Path = "out/audit.jsonl"):
        if policy_name not in POLICIES:
            raise ValueError("Unknown policy profile: fail closed")
        self.policy_name = policy_name
        self.rules = POLICIES[policy_name]
        self.audit = AuditLog(audit_path)

    def policy_digest(self) -> str:
        return hashlib.sha256(canonical_json(self.rules).encode("utf-8")).hexdigest()

    def check(self, tool: str, payload: dict[str, Any], actor: str = "agent") -> dict[str, Any]:
        rule = self.rules.get(tool)
        rule_id = self.policy_name + "." + tool
        if not rule:
            decision, reason = "block", "FAIL-CLOSED: tool absent from policy"
        else:
            decision, reason = rule.get("decision", "block"), rule.get("reason", "")
            if decision not in DECISIONS:
                decision, reason = "block", "Invalid policy decision; fail closed"
            if is_write_like(payload) and decision in {"allow", "allow_masked"}:
                decision, reason = "needs_approval", reason + " | structured write intent detected"
        safe_payload = mask_pii(payload) if decision == "allow_masked" else payload
        event = {
            "timestamp_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "policy_profile": self.policy_name, "policy_digest": self.policy_digest(),
            "rule_id": rule_id, "tool": tool, "decision": decision,
            "reason": reason, "risk_score": 100 if decision == "block" else 70 if decision == "needs_approval" else 25 if decision == "dry_run" else 5,
            "actor": actor, "payload_sha256": hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest(),
        }
        self.audit.append(event)
        return {
            "decision": decision, "reason": reason, "rule_id": rule_id,
            "allowed": decision in {"allow", "allow_masked"},
            "needs_approval": decision == "needs_approval",
            "payload": safe_payload, "policy_digest": self.policy_digest(),
        }

    def recheck_at_execution(self, tool: str, payload: dict[str, Any], expected_digest: str) -> dict[str, Any]:
        if not hmac.compare_digest(self.policy_digest(), expected_digest):
            return {"decision": "block", "reason": "Policy changed after approval; fresh review required"}
        return self.check(tool, payload, actor="execution-recheck")


def check_delivery(delivery: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    body = str(delivery.get("body", ""))
    subject = str(delivery.get("subject", ""))
    if not re.search(r"unsubscriptionlink|unsubscribe", body, re.I):
        blockers.append("missing_unsubscribe_link")
    if not re.search(r"legal entity", body, re.I):
        blockers.append("missing_legal_footer")
    for field, code in [
        ("consent_filter", "no_consent_filter"),
        ("proof_sent", "no_proof_signoff"),
        ("seed_list", "no_seed_list"),
        ("typology", "missing_typology"),
    ]:
        if not delivery.get(field):
            blockers.append(code)
    if len(subject) > 50:
        warnings.append("subject_gt_50_chars")
    scheduled = str(delivery.get("scheduled_local", ""))
    try:
        parsed = datetime.strptime(scheduled, "%Y-%m-%d %H:%M")
        if parsed.hour >= 22 or parsed.hour < 8:
            blockers.append("quiet_hours_violation")
    except ValueError:
        blockers.append("invalid_or_missing_schedule")
    return {
        "status": "hold" if blockers else "eligible_for_review",
        "blockers": blockers, "warnings": warnings,
        "checks_total": 7, "checks_blocked": len(blockers),
        "note": "Eligible for human review is NOT send approval",
    }


class ResearchAgent:
    def __init__(self, audit_path: str | Path = "out/workspace_audit.jsonl"):
        self.gate = Gate("workspace", audit_path)
    def run(self, tool: str, payload: dict[str, Any]) -> dict[str, Any]:
        result = self.gate.check(tool, payload)
        if result["decision"] == "block":
            return {"status": "blocked", "decision": "block", "reason": result["reason"]}
        if result["decision"] == "needs_approval":
            return {"status": "queued_for_human_approval", "decision": "needs_approval", "reason": result["reason"]}
        if result["decision"] == "dry_run":
            return {"status": "dry_run", "decision": "dry_run", "reason": result["reason"]}
        return {"status": "completed", "decision": result["decision"], "payload": result["payload"]}


class AdobeCampaignQAAgent:
    def run(self, data: dict[str, Any], **_: Any) -> dict[str, Any]:
        return check_delivery(data.get("delivery", {}))


class CRMOperationsAgent:
    def run(self, data: dict[str, Any], **_: Any) -> dict[str, Any]:
        return {
            "objective": data.get("objective", ""),
            "recommendations": [
                {"priority": 1, "action": "Enforce Workspace and Campaign Gate on all agent write paths", "owner": "Ops"},
                {"priority": 2, "action": "Require independent dual approval for high-risk sends", "owner": "QA"},
                {"priority": 3, "action": "Publish weekly audit-chain verification evidence", "owner": "Ops"},
            ],
            "roadmap": {"30d": "Gate all writes", "60d": "Dual approval and permit validation", "90d": "Audit reporting and analytics controls"},
            "risks": ["Prompt injection in untrusted content", "Unauthorized external sharing"],
            "evidence_gaps": ["No operational metrics supplied; no performance claims made"],
            "executed": False,
        }


class MarketingAnalyticsAgent:
    def run(self, data: dict[str, Any], **_: Any) -> dict[str, Any]:
        campaigns = data.get("campaigns", [])
        if not isinstance(campaigns, list):
            raise ValueError("campaigns must be a list")
        fields = ("sends", "delivered", "opens", "clicks", "conversions", "bounces", "revenue")
        totals = {field: sum(float(c.get(field, 0) or 0) for c in campaigns) for field in fields}
        def rate(n: float, denominator: float) -> float | None:
            return round(n / denominator * 100, 2) if denominator else None
        sends, delivered, opens = totals["sends"], totals["delivered"], totals["opens"]
        clicks, conversions, bounces, revenue = (totals[k] for k in ("clicks", "conversions", "bounces", "revenue"))
        return {
            "totals": totals,
            "overall": {
                "delivery_rate": rate(delivered, sends),
                "bounce_rate": rate(bounces, sends),
                "open_rate": rate(opens, delivered),
                "ctr": rate(clicks, delivered),
                "ctor": rate(clicks, opens),
                "conversion_rate": rate(conversions, clicks),
                "revenue_per_1000": round(revenue / sends * 1000, 2) if sends else None,
            },
            "authoritative": "deterministic calculation from supplied data",
        }


class Orchestrator:
    def __init__(self, audit_path: str | Path = "out/workspace_audit.jsonl"):
        self.agents = {
            "research": ResearchAgent(audit_path),
            "adobe_campaign_qa": AdobeCampaignQAAgent(),
            "crm_operations": CRMOperationsAgent(),
            "marketing_analytics": MarketingAnalyticsAgent(),
        }

    def execute(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        if name not in self.agents:
            raise ValueError("Unknown mission: fail closed")
        agent = self.agents[name]
        if name == "research":
            return agent.run(payload.get("tool", "gmail.read"), payload.get("payload", {}))
        return agent.run(payload)


def run_tests() -> None:
    print("OPSFORGE ALL-IN-1 — automated tests")
    with tempfile.TemporaryDirectory() as temp:
        audit_path = Path(temp) / "audit.jsonl"
        gate = Gate("workspace", audit_path)
        assert gate.check("unknown.tool", {})["decision"] == "block"
        print("PASS fail-closed unknown tool")
        masked = gate.check("drive.read", {"email": "person@example.com"})
        assert "[MASKED_email]" in str(masked["payload"])
        print("PASS PII masking")
        assert gate.check("gmail.send", {"to": "test@example.com"})["decision"] == "needs_approval"
        print("PASS send requires approval")
        assert gate.check("gmail.read", {"operation": "delete"})["decision"] == "needs_approval"
        print("PASS structured write intent escalates")
        qa = AdobeCampaignQAAgent().run({"delivery": {
            "subject": "Hello", "body": "no link", "proof_sent": True,
            "consent_filter": True, "seed_list": True, "typology": "TY_TEST",
            "scheduled_local": "2026-11-27 10:00",
        }})
        assert "missing_unsubscribe_link" in qa["blockers"]
        print("PASS deterministic QA blocker")
        malformed = AdobeCampaignQAAgent().run({"delivery": {"body": "unsubscribe Legal entity", "consent_filter": True, "proof_sent": True, "seed_list": True, "typology": "TY", "scheduled_local": "bad"}})
        assert "invalid_or_missing_schedule" in malformed["blockers"]
        print("PASS malformed schedule fails closed")
        analytics = MarketingAnalyticsAgent().run({"campaigns": [{
            "sends": 10000, "delivered": 9800, "opens": 4900, "clicks": 980,
            "conversions": 98, "bounces": 200, "revenue": 250000,
        }]})
        assert analytics["overall"]["open_rate"] == 50.0
        assert analytics["overall"]["ctr"] == 10.0
        print("PASS deterministic analytics")
        zero = MarketingAnalyticsAgent().run({"campaigns": [{"sends": 0}]})
        assert zero["overall"]["delivery_rate"] is None
        print("PASS zero denominator returns null")
        crm = CRMOperationsAgent().run({"objective": "QA"})
        assert crm["executed"] is False
        print("PASS CRM agent advisory-only")
        assert AuditLog.verify(audit_path)[0]
        print("PASS audit chain verification")
        lines = audit_path.read_text(encoding="utf-8").splitlines()
        record = json.loads(lines[0]); record["decision"] = "allow"
        lines[0] = canonical_json(record)
        audit_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        assert not AuditLog.verify(audit_path)[0]
        print("PASS audit tamper detection")
    print("ALL TESTS PASSED — FULL STOP.")


def run_space() -> None:
    import streamlit as st
    st.set_page_config(page_title="OPSFORGE Command Centre — ALL IN 1", page_icon="🛡️", layout="wide")
    st.title("OPSFORGE Command Centre — ALL IN 1")
    st.caption("Four missions | Policy-as-code | Fail closed | Evidence over trust")
    st.warning("Synthetic/local demonstration only. No production Adobe Campaign, Workspace, CRM or email connector.")
    st.info("Daily briefing contract is unchanged: AI news only, global coverage, 08:00 Asia/Kolkata.")
    orch = Orchestrator()
    t1, t2, t3, t4, ta = st.tabs(["01 Workspace Gate", "02 Campaign QA", "03 CRM Operations", "04 Marketing Analytics", "Audit"])
    with t1:
        st.subheader("MISSION 01 — Research / Workspace Gate")
        tool = st.selectbox("Workspace operation", list(POLICIES["workspace"]))
        payload_text = st.text_area("Payload JSON", '{"to":"sample@example.test","subject":"Draft"}')
        if st.button("Evaluate Workspace Gate"):
            try:
                payload = json.loads(payload_text)
                if not isinstance(payload, dict): raise ValueError("Payload must be a JSON object")
                st.json(orch.execute("research", {"tool": tool, "payload": payload}))
            except (ValueError, json.JSONDecodeError) as exc:
                st.error(str(exc))
    with t2:
        st.subheader("MISSION 02 — Adobe Campaign QA / Coworker Gate")
        st.caption("Deterministic QA is authoritative. A clean result is eligible for human review only.")
        subject = st.text_input("Subject", "Black Friday — 50% Off")
        body = st.text_area("Body", "<footer>Legal entity Example Ltd. UnsubscriptionLink</footer>")
        proof = st.checkbox("Proof sign-off completed", True)
        consent = st.checkbox("Consent filter configured", True)
        seed = st.checkbox("Seed list configured", True)
        schedule = st.text_input("Scheduled local", "2026-11-27 10:00")
        typology = st.text_input("Typology", "TY_MARKETING")
        if st.button("Run deterministic QA"):
            result = orch.execute("adobe_campaign_qa", {"delivery": {
                "subject": subject, "body": body, "proof_sent": proof,
                "consent_filter": consent, "seed_list": ["synthetic-seed@example.test"] if seed else [],
                "scheduled_local": schedule, "typology": typology,
            }})
            st.json(result)
            if result["status"] == "hold": st.error("HOLD — resolve every blocker")
            else: st.success("Eligible for human review only — NOT send approval")
    with t3:
        st.subheader("MISSION 03 — CRM Operations")
        objective = st.text_input("Objective", "Reduce pre-send QA defects")
        if st.button("Generate advisory plan"):
            st.json(orch.execute("crm_operations", {"objective": objective}))
    with t4:
        st.subheader("MISSION 04 — Marketing Analytics")
        cols = st.columns(4)
        labels = ["Sends", "Delivered", "Opens", "Clicks", "Conversions", "Bounces", "Revenue"]
        defaults = [10000, 9800, 4900, 980, 98, 200, 250000]
        values = [cols[i % 4].number_input(labels[i], min_value=0, value=defaults[i], key="metric_" + labels[i]) for i in range(7)]
        if st.button("Calculate metrics"):
            keys = ["sends", "delivered", "opens", "clicks", "conversions", "bounces", "revenue"]
            st.json(orch.execute("marketing_analytics", {"campaigns": [dict(zip(keys, values))]}))
    with ta:
        st.subheader("Hash-chained audit verification")
        if st.button("Verify Workspace audit"):
            ok, detail = AuditLog.verify("out/workspace_audit.jsonl")
            st.success(detail) if ok else st.error(detail)
        st.caption("This local hash chain detects modification; it is not a tamper-proof external WORM archive.")
    st.divider()
    st.caption("FULL STOP: QA → independent approval in ACC Agent Gate → signed permit → mock execution → audit. This one-file app does not implement production approvals or execution.")
    with st.expander("Operating prompt"):
        st.code(__doc__ or "", language="markdown")


if __name__ == "__main__":
    if "--test" in sys.argv:
        run_tests()
    else:
        try:
            run_space()
        except ImportError:
            print("Install Streamlit: python -m pip install streamlit")
            print("Run: streamlit run OPSFORGE_ALL_IN_1.py")
            print("Test: python OPSFORGE_ALL_IN_1.py --test")
