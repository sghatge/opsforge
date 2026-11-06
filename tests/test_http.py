"""OPSFORGE — HTTP integration smoke tests.

Boots the real server on an ephemeral port and exercises every route family,
including the human approval workflow end to end.
"""

import json
import threading
import unittest
import urllib.error
import urllib.request

from opsforge import __version__
from opsforge.db import Database
from opsforge.server import create_server


class HttpTestCase(unittest.TestCase):
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

    def request(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict | str]:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            self.base + path, data=data, method=method,
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as res:
                raw = res.read().decode()
                return res.status, (json.loads(raw) if raw.strip().startswith(("{", "[")) else raw)
        except urllib.error.HTTPError as err:
            payload = err.read().decode()
            try:
                return err.code, json.loads(payload)
            except json.JSONDecodeError:
                return err.code, payload

    def test_01_health(self):
        status, body = self.request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["version"], __version__)

    def test_02_dashboard_served(self):
        status, html = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("OPS", html)
        self.assertIn("Agent Workspace", html)

    def test_03_process_crud(self):
        status, body = self.request("POST", "/api/processes",
                                    {"name": "Campaign QA", "owner": "MO"})
        self.assertEqual(status, 201)
        pid = body["id"]
        status, body = self.request("GET", f"/api/processes/{pid}")
        self.assertEqual(status, 200)
        status, body = self.request("POST", f"/api/processes/{pid}/assess",
                                    {"documentation": 3, "standardization": 3, "automation": 2,
                                     "measurement": 3, "governance": 3})
        self.assertEqual(status, 200)
        self.assertEqual(body["level"], "Emerging")

    def test_04_sop_generation(self):
        _, created = self.request("POST", "/api/processes", {"name": "SOP via HTTP"})
        status, body = self.request("POST", "/api/sop/generate", {"process_id": created["id"]})
        self.assertEqual(status, 200)
        self.assertIn("## 5. Procedure", body["sop_markdown"])

    def test_05_email_qa(self):
        campaign = {
            "name": "HTTP QA", "subject": "ACT NOW free!!!",
            "html": "<html><body>no title</body></html>",
            "urls": ["bad-url"], "personalization": "<% FirstName", "tracking": False,
            "consent": False}
        status, body = self.request("POST", "/api/qa/email", {"campaign": campaign})
        self.assertEqual(status, 200)
        self.assertEqual(body["overall"], "fail")

    def test_06_rules_crud(self):
        status, body = self.request("POST", "/api/qa/rules",
                                    {"name": "HTTP rule", "target": "subject",
                                     "rule_type": "max_length", "params": {"max": 10}})
        self.assertEqual(status, 201)
        rid = body["id"]
        status, body = self.request("PUT", f"/api/qa/rules/{rid}", {"enabled": False})
        self.assertEqual(body["enabled"], 0)
        status, body = self.request("DELETE", f"/api/qa/rules/{rid}")
        self.assertEqual(body["deleted"], rid)

    def test_07_segmentation_and_readiness(self):
        status, body = self.request("POST", "/api/segmentation/validate",
                                    {"csv": "email,consent\na@x.com,yes\n"})
        self.assertEqual(body["overall"], "pass")
        checks = {k: True for k in ("audience_validated", "consent_confirmed", "subject_line_final",
                                    "urls_tested", "tracking_configured", "html_reviewed",
                                    "personalisation_tested", "assets_approved", "rollback_plan")}
        status, body = self.request("POST", "/api/deployment/assess", {"checks": checks})
        self.assertEqual(body["status"], "ready")

    def test_08_roi(self):
        status, body = self.request("POST", "/api/roi/calculate",
                                    {"hours_manual_per_week": 10, "reduction_pct": 50,
                                     "hourly_cost": 40, "implementation_cost": 2000,
                                     "maintenance_cost_year": 400, "review_cost_year": 300})
        self.assertEqual(body["net_first_year_value"], 6900.0)

    def test_09_agents_and_full_approval_flow(self):
        status, body = self.request("GET", "/api/agents")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(body["agents"]), 5)

        status, run = self.request("POST", "/api/agents/qa_agent/run", {"use_sample": True})
        self.assertEqual(status, 201)
        self.assertEqual(run["status"], "pending_approval")
        run_id = run["id"]
        step_seq = next(s["seq"] for s in run["steps"] if s["status"] == "pending_approval")

        # approval without a named human must fail
        status, _ = self.request("POST", f"/api/runs/{run_id}/steps/{step_seq}/approve",
                                 {"approver": " "})
        self.assertEqual(status, 400)

        # the sample campaign fails QA: a plain approval is refused (v0.4 override control)
        status, err = self.request("POST", f"/api/runs/{run_id}/steps/{step_seq}/approve",
                                   {"approver": "Sangram", "comment": "ok"})
        self.assertEqual(status, 400)
        self.assertIn("override", err["error"])

        status, run = self.request("POST", f"/api/runs/{run_id}/steps/{step_seq}/approve",
                                   {"approver": "Sangram", "comment": "ok",
                                    "override_reason": "Accepted known issue for this test send"})
        self.assertEqual(status, 200)
        self.assertEqual(run["status"], "completed")

    def test_10_rejection_flow(self):
        _, run = self.request("POST", "/api/agents/readiness_agent/run", {"use_sample": True})
        step_seq = next(s["seq"] for s in run["steps"] if s["status"] == "pending_approval")
        status, run = self.request("POST", f"/api/runs/{run['id']}/steps/{step_seq}/reject",
                                   {"approver": "Sangram", "comment": "nope"})
        self.assertEqual(run["status"], "rejected")

    def test_11_runs_listing_and_detail(self):
        _, runs = self.request("GET", "/api/runs")
        self.assertGreaterEqual(len(runs["runs"]), 2)
        run_id = runs["runs"][0]["id"]
        status, detail = self.request("GET", f"/api/runs/{run_id}")
        self.assertEqual(status, 200)
        self.assertIn("steps", detail)

    def test_12_adapters_audit_metrics(self):
        status, body = self.request("GET", "/api/adapters")
        self.assertEqual(len(body["adapters"]), 2)
        status, body = self.request("POST", "/api/adapters/adobe_campaign/check", {})
        self.assertEqual(body["status"], "dry_run_ok")
        status, body = self.request("GET", "/api/audit")
        self.assertGreater(len(body["events"]), 5)
        status, body = self.request("GET", "/api/metrics")
        self.assertGreater(body["audit_events"], 5)

    def test_13_error_handling(self):
        status, body = self.request("GET", "/api/nope")
        self.assertEqual(status, 404)
        status, body = self.request("GET", "/api/processes/prc_missing")
        self.assertEqual(status, 404)
        status, body = self.request("POST", "/api/roi/calculate", {"reduction_pct": 999})
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
