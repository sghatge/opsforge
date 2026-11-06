"""OPSFORGE v0.4 - failed-result override control tests.

A human must never silently sign off a failing QA report or a NOT READY
release assessment: approval requires a written override reason, and the
override is recorded as its own audit event.
"""

import unittest

from opsforge.db import Database
from opsforge.services import agents
from opsforge.services.agents import approve_step, reject_step, start_run


def _gate_seq(run):
    return next(s["seq"] for s in run["steps"] if s["status"] == "pending_approval")


class TestOverrideControl(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")

    def test_failing_qa_is_flagged_on_gate(self):
        run = start_run(self.db, "qa_agent", {"use_sample": True})
        gate = run["gate"]
        self.assertEqual(gate["verdict"], "fail")
        self.assertEqual(gate["severity"], "block")
        self.assertTrue(gate["override_required"])

    def test_failing_qa_cannot_be_approved_without_reason(self):
        run = start_run(self.db, "qa_agent", {"use_sample": True})
        with self.assertRaises(ValueError) as ctx:
            approve_step(self.db, run["id"], _gate_seq(run), "Sangram", "looks fine")
        self.assertIn("override", str(ctx.exception))
        self.assertEqual(agents.get_run(self.db, run["id"])["status"], "pending_approval")

    def test_short_reason_is_rejected(self):
        run = start_run(self.db, "qa_agent", {"use_sample": True})
        with self.assertRaises(ValueError):
            approve_step(self.db, run["id"], _gate_seq(run), "Sangram", override_reason="ok, ship it")

    def test_override_with_reason_completes_and_is_audited(self):
        run = start_run(self.db, "qa_agent", {"use_sample": True})
        reason = "Known footer link issue accepted by legal for this send only"
        done = approve_step(self.db, run["id"], _gate_seq(run), "Sangram", override_reason=reason)
        self.assertEqual(done["status"], "completed")
        self.assertTrue(done["approvals"][0]["comment"].startswith("[OVERRIDE: fail]"))
        events = [e for e in self.db.audit_trail(50) if e["event"] == "approval.override"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["payload"]["reason"], reason)
        self.assertEqual(events[0]["payload"]["approver"], "Sangram")
        granted = [e for e in self.db.audit_trail(50) if e["event"] == "approval.granted"]
        self.assertEqual(granted, [])

    def test_not_ready_release_requires_override(self):
        run = start_run(self.db, "readiness_agent", {"use_sample": True})
        self.assertEqual(run["gate"]["verdict"], "not_ready")
        with self.assertRaises(ValueError):
            approve_step(self.db, run["id"], _gate_seq(run), "Sangram")

    def test_review_verdict_needs_no_override(self):
        checks = {p: True for p in ("audience_validated", "consent_confirmed", "subject_line_final",
                                    "urls_tested", "tracking_configured", "html_reviewed",
                                    "personalisation_tested", "assets_approved")}
        run = start_run(self.db, "readiness_agent", {"checks": checks})  # rollback_plan missing
        self.assertEqual(run["gate"]["severity"], "caution")
        done = approve_step(self.db, run["id"], _gate_seq(run), "Sangram", "reviewed")
        self.assertEqual(done["status"], "completed")

    def test_rejection_never_needs_override(self):
        run = start_run(self.db, "qa_agent", {"use_sample": True})
        rejected = reject_step(self.db, run["id"], _gate_seq(run), "Sangram", "fix the links")
        self.assertEqual(rejected["status"], "rejected")


if __name__ == "__main__":
    unittest.main()
