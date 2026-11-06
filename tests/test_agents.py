"""OPSFORGE v0.3 — Enterprise AI Agent Layer tests."""

import unittest

from opsforge.db import Database
from opsforge.services import agents
from opsforge.services.agents import (
    AGENT_CATALOG, DeterministicLLM, approve_step, get_agent, get_run, list_agents,
    list_runs, reject_step, start_run, get_provider)
from opsforge.services import qa
from opsforge.services.adapters import (
    REGISTRY, AdapterError, AdobeCampaignAdapter, check_adapter, list_adapters)
from opsforge.services.sop import list_evidence


class BaseTestCase(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")


class TestCatalog(BaseTestCase):
    def test_five_agents_registered(self):
        ids = {a["id"] for a in list_agents()}
        self.assertEqual(ids, {"qa_agent", "sop_agent", "segmentation_agent",
                               "readiness_agent", "reporting_agent"})

    def test_sensitive_steps_are_gated(self):
        for agent_id in ("qa_agent", "readiness_agent"):
            agent = get_agent(agent_id)
            self.assertTrue(any(s["requires_approval"] for s in agent["plan"]))
        for agent_id in ("sop_agent", "segmentation_agent", "reporting_agent"):
            agent = get_agent(agent_id)
            self.assertFalse(any(s["requires_approval"] for s in agent["plan"]))

    def test_unknown_agent(self):
        with self.assertRaises(LookupError):
            get_agent("sky_agent")


class TestRuns(BaseTestCase):
    def test_sop_agent_completes_and_files_evidence(self):
        run = start_run(self.db, "sop_agent", {"use_sample": True})
        self.assertEqual(run["status"], "completed")
        self.assertEqual([s["status"] for s in run["steps"]], ["done", "done"])
        kinds = [e["kind"] for e in list_evidence(self.db)]
        self.assertIn("sop_draft", kinds)

    def test_segmentation_agent_with_sample(self):
        run = start_run(self.db, "segmentation_agent", {"use_sample": True})
        self.assertEqual(run["status"], "completed")
        report = run["steps"][0]["output"]  # step 1 holds the validation report
        self.assertEqual(report["summary"]["duplicates"], 1)
        self.assertEqual(report["overall"], "fail")  # sample contains a consent gap

    def test_qa_agent_pauses_at_signoff(self):
        run = start_run(self.db, "qa_agent", {"use_sample": True})
        self.assertEqual(run["status"], "pending_approval")
        gated = [s for s in run["steps"] if s["status"] == "pending_approval"]
        self.assertEqual(len(gated), 1)
        self.assertEqual(gated[0]["tool"], "qa.signoff")
        # QA + evidence steps completed before the gate
        self.assertEqual(run["steps"][0]["status"], "done")
        self.assertEqual(run["steps"][1]["status"], "done")

    def test_approval_completes_run(self):
        # a passing campaign needs no override
        run = start_run(self.db, "qa_agent", {"campaign": agents.SAMPLE_CAMPAIGN_GOOD})
        self.assertEqual(run["gate"]["verdict"], "pass")
        self.assertFalse(run["gate"]["override_required"])
        step_seq = next(s["seq"] for s in run["steps"] if s["status"] == "pending_approval")
        done = approve_step(self.db, run["id"], step_seq, "Sangram", "Accepted")
        self.assertEqual(done["status"], "completed")
        self.assertEqual(done["steps"][-1]["output"]["sign_off"], "approved_by_human")
        self.assertEqual(done["steps"][-1]["output"]["approver"], "Sangram")
        self.assertEqual(len(done["approvals"]), 1)

    def test_rejection_cancels_run(self):
        run = start_run(self.db, "readiness_agent", {"use_sample": True})
        step_seq = next(s["seq"] for s in run["steps"] if s["status"] == "pending_approval")
        rejected = reject_step(self.db, run["id"], step_seq, "Sangram", "Not this quarter")
        self.assertEqual(rejected["status"], "rejected")
        self.assertTrue(all(s["status"] == "cancelled" for s in rejected["steps"][step_seq - 1:]))

    def test_agent_cannot_self_approve(self):
        run = start_run(self.db, "qa_agent", {"use_sample": True})
        self.assertEqual(run["status"], "pending_approval")
        # a second _advance call must not bypass the gate
        agents._advance(self.db, run["id"])
        self.assertEqual(get_run(self.db, run["id"])["status"], "pending_approval")

    def test_approval_requires_named_human(self):
        run = start_run(self.db, "qa_agent", {"use_sample": True})
        step_seq = next(s["seq"] for s in run["steps"] if s["status"] == "pending_approval")
        with self.assertRaises(ValueError):
            approve_step(self.db, run["id"], step_seq, "  ")

    def test_reporting_agent_uses_provider(self):
        run = start_run(self.db, "reporting_agent", {"use_sample": True})
        self.assertEqual(run["status"], "completed")
        compose = next(s for s in run["steps"] if s["tool"] == "report.compose")
        self.assertEqual(compose["output"]["provider"], "deterministic")
        self.assertIn("Operations summary", compose["output"]["report_markdown"])

    def test_failed_tool_fails_run(self):
        run = start_run(self.db, "sop_agent", {"note": "no process supplied"})
        self.assertEqual(run["status"], "failed")
        self.assertIn("requires", run["result"]["error"])

    def test_run_ledger_listed(self):
        start_run(self.db, "sop_agent", {"use_sample": True})
        runs = list_runs(self.db)
        self.assertEqual(len(runs), 1)
        self.assertNotIn("steps", runs[0])  # list view is compact

    def test_non_gated_step_cannot_be_approved(self):
        run = start_run(self.db, "qa_agent", {"use_sample": True})
        with self.assertRaises(ValueError):
            approve_step(self.db, run["id"], 1, "Sangram")


class TestProvider(BaseTestCase):
    def test_deterministic_default(self):
        self.assertIsInstance(get_provider(), DeterministicLLM)

    def test_unknown_provider_rejected(self):
        import os
        old = os.environ.get("OPSFORGE_LLM_PROVIDER")
        os.environ["OPSFORGE_LLM_PROVIDER"] = "skynet"
        try:
            with self.assertRaises(ValueError):
                get_provider()
        finally:
            if old is None:
                os.environ.pop("OPSFORGE_LLM_PROVIDER", None)
            else:
                os.environ["OPSFORGE_LLM_PROVIDER"] = old


class TestAdapters(BaseTestCase):
    def test_registry_synced(self):
        names = [a["name"] for a in list_adapters(self.db)]
        self.assertIn("mock_crm", names)
        self.assertIn("adobe_campaign", names)

    def test_dry_run_check(self):
        result = check_adapter(self.db, "adobe_campaign")
        self.assertEqual(result["status"], "dry_run_ok")
        row = next(a for a in list_adapters(self.db) if a["name"] == "adobe_campaign")
        self.assertEqual(row["status"], "dry_run_ok")

    def test_live_calls_blocked(self):
        adapter = REGISTRY["adobe_campaign"]
        self.assertIsInstance(adapter, AdobeCampaignAdapter)
        with self.assertRaises(AdapterError):
            adapter.require_live()

    def test_unknown_adapter(self):
        with self.assertRaises(LookupError):
            check_adapter(self.db, "salesforce")


class TestRulesIntegration(BaseTestCase):
    def test_disabled_rules_do_not_fire(self):
        rules = qa.list_rules(self.db)
        target = next(r for r in rules if r["name"] == "Unsubscribe link present")
        qa.update_rule(self.db, target["id"], {"enabled": False})
        campaign = {"name": "T", "subject": "Hi", "html": "<title>x</title>",
                    "urls": ["https://x.example.com"], "personalization": "",
                    "tracking": True, "consent": True}
        report = qa.run_email_qa(self.db, campaign)
        self.assertNotIn("Unsubscribe link present", [c["rule"] for c in report["checks"]])


if __name__ == "__main__":
    unittest.main()
