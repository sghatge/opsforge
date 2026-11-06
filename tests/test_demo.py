"""OPSFORGE — demo data seeder tests."""

import unittest

from opsforge.db import Database
from opsforge.services import processes
from opsforge.services.agents import approve_step, list_runs
from opsforge.services.adapters import list_adapters
from opsforge.services.demo import seed_demo
from opsforge.services.sop import list_evidence
from opsforge.server import seed_demo_route


class TestDemoSeed(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")

    def test_seed_populates_every_module(self):
        result = seed_demo(self.db)
        self.assertTrue(result["seeded"])
        self.assertEqual(len(processes.list_processes(self.db)), 3)
        self.assertEqual(len(self.db.query("SELECT * FROM assessments")), 3)

        kinds = {e["kind"] for e in list_evidence(self.db)}
        self.assertTrue({"qa_report", "sop_draft", "audience_validation",
                         "readiness_assessment", "roi_analysis"} <= kinds)

        runs = list_runs(self.db)
        self.assertEqual(len(runs), 5)
        pending = [r for r in runs if r["status"] == "pending_approval"]
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["agent_id"], "readiness_agent")

        # one human-approved sign-off exists
        self.assertEqual(len(self.db.query("SELECT id FROM approvals")), 1)

        # both adapters verified during seeding
        adapters = list_adapters(self.db)
        self.assertTrue(all(a["status"] == "dry_run_ok" for a in adapters))

    def test_seed_is_idempotent(self):
        first = seed_demo(self.db)
        counts = {
            "processes": len(processes.list_processes(self.db)),
            "runs": len(list_runs(self.db)),
            "evidence": len(list_evidence(self.db)),
        }
        second = seed_demo(self.db)
        self.assertFalse(second["seeded"])
        self.assertEqual(len(processes.list_processes(self.db)), counts["processes"])
        self.assertEqual(len(list_runs(self.db)), counts["runs"])
        self.assertEqual(len(list_evidence(self.db)), counts["evidence"])
        self.assertTrue(first["summary"]["pending_approval"], 1)

    def test_pending_demo_run_can_be_approved(self):
        seed_demo(self.db)
        pending = next(r for r in list_runs(self.db) if r["status"] == "pending_approval")
        detail = self.db.query_one("SELECT seq FROM agent_steps WHERE run_id = ? AND status = 'pending_approval'",
                                   (pending["id"],))
        done = approve_step(self.db, pending["id"], detail["seq"], "Test Approver", "looks good")
        self.assertEqual(done["status"], "completed")

    def test_demo_data_created_through_services(self):
        """All demo QA reports must be genuine service output, not hand-written JSON."""
        seed_demo(self.db)
        qa_reports = [e for e in list_evidence(self.db) if e["kind"] == "qa_report"]
        overalls = {e["payload"]["overall"] for e in qa_reports}
        self.assertIn("pass", overalls)
        self.assertIn("fail", overalls)
        for report in qa_reports:
            self.assertIn("summary", report["payload"])
            self.assertIn("checks", report["payload"])

    def test_route_function_seeds_and_skips(self):
        status, first = seed_demo_route(Database(":memory:"), None, {})
        self.assertEqual(status, 200)
        self.assertTrue(first["seeded"])
        # route on an already-seeded database skips
        db2 = Database(":memory:")
        seed_demo(db2)
        status, second = seed_demo_route(db2, None, {})
        self.assertEqual(status, 200)
        self.assertFalse(second["seeded"])


if __name__ == "__main__":
    unittest.main()
