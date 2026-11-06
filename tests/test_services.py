"""OPSFORGE — baseline service tests (v0.1/v0.2 capability set)."""

import unittest

from opsforge.db import Database
from opsforge.services import processes, qa, readiness, roi, segmentation
from opsforge.services.sop import create_evidence, generate_sop, list_evidence, save_sop_evidence


class BaseTestCase(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")


class TestProcesses(BaseTestCase):
    def test_create_and_list(self):
        p = processes.create_process(self.db, {"name": "Campaign QA", "owner": "MO Team"})
        self.assertTrue(p["id"].startswith("prc_"))
        self.assertEqual(len(processes.list_processes(self.db)), 1)

    def test_name_required(self):
        with self.assertRaises(ValueError):
            processes.create_process(self.db, {"name": "  "})

    def test_assessment_levels(self):
        p = processes.create_process(self.db, {"name": "Reporting"})
        a = processes.assess_process(self.db, p["id"], {
            "documentation": 2, "standardization": 2, "automation": 1,
            "measurement": 2, "governance": 2})
        self.assertEqual(a["total"], 9)
        self.assertEqual(a["level"], "Manual")
        with self.assertRaises(ValueError):
            processes.assess_process(self.db, p["id"], {"documentation": 9})

    def test_get_missing_process(self):
        with self.assertRaises(LookupError):
            processes.get_process(self.db, "prc_nope")


class TestSop(BaseTestCase):
    def test_generate_contains_sections(self):
        p = processes.create_process(self.db, {"name": "Campaign QA"})
        sop = generate_sop(self.db, p["id"])
        for section in ("## 1. Process", "## 5. Procedure", "## 8. Review cycle", "Campaign QA"):
            self.assertIn(section, sop["sop_markdown"])

    def test_sop_evidence(self):
        p = processes.create_process(self.db, {"name": "Campaign QA"})
        sop = generate_sop(self.db, p["id"])
        ev = save_sop_evidence(self.db, sop)
        self.assertEqual(ev["kind"], "sop_draft")
        self.assertEqual(len(list_evidence(self.db)), 1)

    def test_evidence_requires_fields(self):
        with self.assertRaises(ValueError):
            create_evidence(self.db, {"kind": "", "title": ""})


class TestQaEngine(BaseTestCase):
    GOOD = {
        "name": "Autumn",
        "subject": "Your autumn update",
        "html": "<html><head><title>Autumn</title></head><body>Hi</body></html>",
        "urls": ["https://example.com/offer", "https://example.com/unsubscribe"],
        "personalization": "<% FirstName %>",
        "tracking": True,
        "consent": True,
    }

    def test_good_campaign_passes(self):
        report = qa.run_email_qa(self.db, self.GOOD)
        self.assertEqual(report["overall"], "pass")
        self.assertEqual(report["summary"]["failed"], 0)

    def test_bad_campaign_fails(self):
        bad = {**self.GOOD, "subject": "ACT NOW free!!!", "urls": ["not-a-url"], "consent": False}
        report = qa.run_email_qa(self.db, bad)
        self.assertEqual(report["overall"], "fail")
        self.assertGreaterEqual(report["summary"]["failed"], 3)

    def test_uncertain_results_flagged_for_review(self):
        report = qa.run_email_qa(self.db, {**self.GOOD, "consent": "maybe"})
        self.assertEqual(report["overall"], "flagged_for_review")

    def test_empty_campaign_rejected(self):
        with self.assertRaises(ValueError):
            qa.run_email_qa(self.db, {})


class TestQaRules(BaseTestCase):
    def test_crud_lifecycle(self):
        rule = qa.create_rule(self.db, {
            "name": "No ftp URLs", "target": "urls", "rule_type": "url_format", "severity": "error"})
        self.assertIn(rule["id"], [r["id"] for r in qa.list_rules(self.db)])
        updated = qa.update_rule(self.db, rule["id"], {"enabled": False})
        self.assertEqual(updated["enabled"], 0)
        qa.delete_rule(self.db, rule["id"])
        with self.assertRaises(LookupError):
            qa.get_rule(self.db, rule["id"])

    def test_invalid_rule_type_rejected(self):
        with self.assertRaises(ValueError):
            qa.create_rule(self.db, {"name": "x", "target": "subject", "rule_type": "magic"})

    def test_custom_rule_changes_qa_outcome(self):
        campaign = {"name": "T", "subject": "Hello", "html": "<title>x</title>",
                    "urls": ["https://ok.example.com/unsubscribe"], "personalization": "",
                    "tracking": True, "consent": True}
        base = qa.run_email_qa(self.db, campaign)
        self.assertEqual(base["overall"], "pass")
        qa.create_rule(self.db, {
            "name": "Brand domain required", "target": "urls",
            "rule_type": "contains_url", "params": {"pattern": "brand.com"}, "severity": "error"})
        after = qa.run_email_qa(self.db, campaign)
        self.assertEqual(after["overall"], "fail")


class TestSegmentation(BaseTestCase):
    def test_valid_passes(self):
        r = segmentation.validate_segmentation(self.db, {"csv": "email,consent\na@x.com,yes\nb@x.com,yes\n"})
        self.assertEqual(r["overall"], "pass")
        self.assertEqual(r["summary"]["unique_valid_emails"], 2)

    def test_duplicate_and_bad_email_warn(self):
        r = segmentation.validate_segmentation(self.db, {"csv": "email,consent\na@x.com,yes\na@x.com,yes\nbad,yes\n"})
        self.assertEqual(r["overall"], "warn")
        self.assertEqual(r["summary"]["duplicates"], 1)

    def test_missing_consent_blocks(self):
        r = segmentation.validate_segmentation(self.db, {"csv": "email,consent\na@x.com,\n"})
        self.assertEqual(r["overall"], "fail")

    def test_missing_column_blocks(self):
        r = segmentation.validate_segmentation(self.db, {"csv": "name\nabc\n"})
        self.assertEqual(r["overall"], "fail")

    def test_volume_cap(self):
        csv = "email,consent\n" + "".join(f"u{i}@x.com,yes\n" for i in range(5))
        r = segmentation.validate_segmentation(self.db, {"csv": csv, "volume_cap": 3})
        self.assertEqual(r["overall"], "warn")

    def test_empty_csv_rejected(self):
        with self.assertRaises(ValueError):
            segmentation.validate_segmentation(self.db, {"csv": "   "})


class TestReadiness(BaseTestCase):
    def _checks(self, **overrides):
        base = {k: True for k in readiness.POINTS}
        base.update(overrides)
        return base

    def test_all_pass_ready(self):
        r = readiness.assess_deployment(self.db, {"checks": self._checks()})
        self.assertEqual(r["status"], "ready")
        self.assertEqual(r["score"], "9/9")

    def test_fail_blocks(self):
        r = readiness.assess_deployment(self.db, {"checks": self._checks(rollback_plan=False)})
        self.assertEqual(r["status"], "not_ready")

    def test_unclear_needs_review(self):
        r = readiness.assess_deployment(self.db, {"checks": self._checks(rollback_plan=None)})
        self.assertEqual(r["status"], "needs_human_review")


class TestRoi(BaseTestCase):
    def test_net_value_math(self):
        r = roi.calculate_roi(self.db, {
            "hours_manual_per_week": 10, "reduction_pct": 50, "hourly_cost": 40,
            "implementation_cost": 2000, "maintenance_cost_year": 400, "review_cost_year": 300})
        # 10 * 0.5 * 48 = 240 h; 240 * 40 = 9600 gross; net = 9600 - 2000 - 400 - 300 = 6900
        self.assertEqual(r["hours_released_per_year"], 240.0)
        self.assertEqual(r["net_first_year_value"], 6900.0)
        self.assertEqual(r["payback_months"], 2.5)

    def test_validation(self):
        with self.assertRaises(ValueError):
            roi.calculate_roi(self.db, {"reduction_pct": 150})


class TestAudit(BaseTestCase):
    def test_events_recorded(self):
        processes.create_process(self.db, {"name": "X"})
        events = self.db.audit_trail()
        self.assertTrue(any(e["event"] == "process.created" for e in events))


if __name__ == "__main__":
    unittest.main()
