"""End-to-end HTTP tests for the governed Signal Triage Agent."""

import json
import threading
import unittest
import urllib.error
import urllib.request

from opsforge.db import Database
from opsforge.server import create_server


class SignalHttpIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = Database(":memory:")
        cls.server = create_server(cls.db, host="127.0.0.1", port=0)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def request(self, method, path, body=None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(
            self.base + path, data=data, method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read().decode("utf-8"))

    def test_notify_signal_completes_and_persists_evidence_and_audit(self):
        title = "HTTP integration — routine capacity review"
        status, run = self.request("POST", "/api/agents/signal_triage_agent/run", {
            "headline": "Adobe Campaign capacity review",
            "summary": "Routine CRM workload planning update.",
            "source": "HTTP integration fixture",
            "url": "https://example.com/capacity",
            "classification": "Notify",
            "evidence_kind": "signal",
            "evidence_title": title,
        })
        self.assertEqual(status, 201)
        self.assertEqual(run["status"], "completed")
        self.assertEqual(run["steps"][0]["output"]["classification"], "Notify")
        self.assertEqual(run["steps"][1]["status"], "done")
        self.assertEqual(run["steps"][2]["output"]["decision"], "no_human_gate_required")

        status, evidence = self.request("GET", "/api/evidence")
        self.assertEqual(status, 200)
        matching = [item for item in evidence["evidence"] if item["title"] == title]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["kind"], "signal")

        status, audit = self.request("GET", "/api/audit")
        self.assertEqual(status, 200)
        events = [item["event"] for item in audit["events"]]
        self.assertIn("agent_run.started", events)
        self.assertIn("agent_step.executed", events)
        self.assertIn("agent_run.completed", events)

    def test_high_risk_signal_pauses_then_requires_named_human_approval(self):
        title = "HTTP integration — SFTP production outage"
        status, run = self.request("POST", "/api/agents/signal_triage_agent/run", {
            "headline": "SFTP production outage",
            "summary": "Campaign exports are disrupted.",
            "source": "HTTP integration fixture",
            "url": "https://example.com/incident",
            "classification": "Notify",
            "evidence_kind": "signal",
            "evidence_title": title,
        })
        self.assertEqual(status, 201)
        self.assertEqual(run["status"], "pending_approval")
        self.assertEqual(run["steps"][0]["output"]["classification"], "Approve")
        gate = next(step for step in run["steps"] if step["status"] == "pending_approval")
        self.assertTrue(gate["requires_approval"])

        # Evidence is filed before the approval gate; sign-off has not run yet.
        status, evidence = self.request("GET", "/api/evidence")
        self.assertEqual(status, 200)
        matching = [item for item in evidence["evidence"] if item["title"] == title]
        self.assertEqual(len(matching), 1)
        self.assertEqual(run["steps"][2]["status"], "pending_approval")

        status, rejected = self.request(
            "POST", f"/api/runs/{run['id']}/steps/{gate['seq']}/approve",
            {"approver": " "},
        )
        self.assertEqual(status, 400)
        self.assertIn("named human", rejected["error"])

        status, completed = self.request(
            "POST", f"/api/runs/{run['id']}/steps/{gate['seq']}/approve",
            {"approver": "Sangram", "comment": "Reviewed incident evidence"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["steps"][2]["output"]["decision"], "approved_by_human")
        self.assertEqual(completed["steps"][2]["output"]["approver"], "Sangram")
        self.assertEqual(completed["steps"][2]["output"]["external_action"], "not_executed")

        status, audit = self.request("GET", "/api/audit")
        self.assertEqual(status, 200)
        approval_events = [
            item for item in audit["events"]
            if item["event"] == "approval.granted"
            and item["payload"].get("run_id") == run["id"]
        ]
        self.assertEqual(len(approval_events), 1)
        self.assertEqual(approval_events[0]["payload"]["approver"], "Sangram")


if __name__ == "__main__":
    unittest.main()
