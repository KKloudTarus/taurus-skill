#!/usr/bin/env python3
"""Tests for hooks/gate-report.py."""

import json
import os
import subprocess
import sys
import tempfile
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "hooks", "gate-report.py")


class GateReportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = self.tmp.name
        subprocess.run(["git", "init", "-q", self.repo], check=True)
        subprocess.run(["git", "-C", self.repo, "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "-C", self.repo, "config", "user.name", "Test"], check=True)
        with open(os.path.join(self.repo, "seed.txt"), "w", encoding="utf-8") as fh:
            fh.write("seed\n")
        subprocess.run(["git", "-C", self.repo, "add", "seed.txt"], check=True)
        subprocess.run(["git", "-C", self.repo, "commit", "-qm", "chore: seed"], check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def input(self, tier=2, reviewers=None, domains=None, findings=None):
        risk_domains = domains or ["documentation"]
        return {
            "tier": tier,
            "tier_reason": "documentation-only change",
            "scope": "working tree",
            "risk_domains": risk_domains,
            "primary_risk": risk_domains[0],
            "checks": {
                "build": {"status": "not_applicable", "reason": "no build step"},
                "tests": {"status": "pass", "command": "python3 -m unittest", "exit_code": 0, "evidence": "6 passed"},
                "lint": {"status": "pass", "command": "ruff check .", "exit_code": 0, "evidence": "clean"},
                "typecheck": {"status": "not_applicable", "reason": "no type checker"},
            },
            "domain_checks": {},
            "reviewers": reviewers or [],
            "self_review": {"status": "pass", "evidence": "read the complete diff"},
            "findings": findings or [],
        }

    def run_script(self, *args):
        return subprocess.run(
            [sys.executable, SCRIPT, "--root", self.repo, *args],
            capture_output=True, text=True, timeout=30,
        )

    def write(self, data):
        path = os.path.join(self.tmp.name, "input.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        return self.run_script("write", path)

    def report_path(self):
        return os.path.join(self.repo, ".git", "taurus", "verification.json")

    def reviewer(self, agent, verdict="pass"):
        return {
            "agent": agent, "verdict": verdict,
            "critical": 0, "high": 0, "medium": 0, "low": 0,
            "evidence": "reviewed the diff and ran the focused test",
        }

    def passing_check(self, command="verify-domain"):
        return {"status": "pass", "command": command, "exit_code": 0, "evidence": "passed"}

    def test_tier_two_report_writes_and_validates(self):
        written = self.write(self.input())
        self.assertEqual(written.returncode, 0, written.stderr)
        checked = self.run_script("validate")
        self.assertEqual(checked.returncode, 0, checked.stderr)
        with open(self.report_path(), encoding="utf-8") as fh:
            report = json.load(fh)
        self.assertEqual(report["gate"], "pass")
        self.assertEqual(report["schema_version"], 2)
        self.assertEqual(len(report["worktree_fingerprint"]), 64)

    def test_report_becomes_stale_after_worktree_change(self):
        self.assertEqual(self.write(self.input()).returncode, 0)
        with open(os.path.join(self.repo, "seed.txt"), "a", encoding="utf-8") as fh:
            fh.write("changed\n")
        checked = self.run_script("validate")
        self.assertEqual(checked.returncode, 1)
        self.assertIn("report is stale", checked.stderr)

    def test_tier_one_requires_a_targeted_reviewer(self):
        written = self.write(self.input(tier=1))
        self.assertEqual(written.returncode, 1)
        with open(self.report_path(), encoding="utf-8") as fh:
            report = json.load(fh)
        self.assertIn("tier 1 requires", " ".join(report["validation_errors"]))

    def test_tier_one_reviewer_matches_the_primary_risk(self):
        data = self.input(
            tier=1,
            reviewers=[self.reviewer("architecture-critic")],
            domains=["behavior"],
        )
        written = self.write(data)
        self.assertEqual(written.returncode, 1)
        with open(self.report_path(), encoding="utf-8") as fh:
            report = json.load(fh)
        self.assertIn("qa-verifier", " ".join(report["validation_errors"]))

    def test_tier_two_rejects_behavior_risk(self):
        written = self.write(self.input(domains=["behavior"]))
        self.assertEqual(written.returncode, 1)
        with open(self.report_path(), encoding="utf-8") as fh:
            report = json.load(fh)
        self.assertIn("tier 2 only permits", " ".join(report["validation_errors"]))

    def test_tier_zero_requires_the_full_core_set(self):
        reviewers = [
            self.reviewer("qa-verifier"),
            self.reviewer("security-auditor"),
            self.reviewer("performance-auditor"),
        ]
        data = self.input(tier=0, reviewers=reviewers)
        data["tier_reason"] = "correctness-critical authorization change"
        data["risk_domains"] = ["security"]
        data["primary_risk"] = "security"
        data["panel"] = {
            "verdict": "pass",
            "agents": ["architecture-critic", "qa-verifier", "security-auditor"],
            "evidence": "three panel reports synthesized",
        }
        written = self.write(data)
        self.assertEqual(written.returncode, 0, written.stderr)

    def test_tier_zero_requires_a_passing_panel(self):
        reviewers = [
            self.reviewer("qa-verifier"),
            self.reviewer("security-auditor"),
            self.reviewer("performance-auditor"),
        ]
        data = self.input(tier=0, reviewers=reviewers, domains=["security"])
        written = self.write(data)
        self.assertEqual(written.returncode, 1)
        with open(self.report_path(), encoding="utf-8") as fh:
            report = json.load(fh)
        self.assertIn("passing review panel", " ".join(report["validation_errors"]))

    def test_reliability_risk_requires_reliability_auditor(self):
        data = self.input(tier=1, reviewers=[self.reviewer("qa-verifier")], domains=["migration"])
        written = self.write(data)
        self.assertEqual(written.returncode, 1)
        with open(self.report_path(), encoding="utf-8") as fh:
            report_text = fh.read()
        self.assertIn("reliability-auditor", written.stderr + report_text)

    def test_new_risk_domains_require_their_specialists(self):
        cases = {
            "infrastructure": ("platform-auditor", "plan"),
            "supply_chain": ("platform-auditor", "provenance"),
            "sre": ("reliability-auditor", "slo"),
            "observability": ("reliability-auditor", "telemetry"),
            "frontend": ("frontend-quality-auditor", "browser"),
            "accessibility": ("frontend-quality-auditor", "accessibility"),
            "data": ("ai-ml-verifier", "evaluation"),
            "model": ("ai-ml-verifier", "evaluation"),
            "ml": ("ai-ml-verifier", "evaluation"),
            "ai_safety": ("ai-ml-verifier", "safety_eval"),
            "api_contract": ("qa-verifier", "contract"),
            "llm_security": ("security-auditor", "security_eval"),
            "cost": ("performance-auditor", "cost"),
        }
        for domain, (agent, check) in cases.items():
            with self.subTest(domain=domain):
                data = self.input(tier=1, reviewers=[self.reviewer(agent)], domains=[domain])
                data["domain_checks"][check] = self.passing_check()
                written = self.write(data)
                self.assertEqual(written.returncode, 0, written.stderr)

    def test_infrastructure_domain_requires_a_plan_check(self):
        data = self.input(
            tier=1,
            reviewers=[self.reviewer("platform-auditor")],
            domains=["infrastructure"],
        )
        written = self.write(data)
        self.assertEqual(written.returncode, 1)
        with open(self.report_path(), encoding="utf-8") as fh:
            errors = " ".join(json.load(fh)["validation_errors"])
        self.assertIn("domain_checks.plan", errors)

    def test_secondary_specialist_domain_cannot_be_hidden_by_primary_risk(self):
        data = self.input(
            tier=1,
            reviewers=[self.reviewer("qa-verifier")],
            domains=["behavior", "infrastructure"],
        )
        data["domain_checks"]["plan"] = self.passing_check("terraform plan")
        written = self.write(data)
        self.assertEqual(written.returncode, 1)
        with open(self.report_path(), encoding="utf-8") as fh:
            errors = " ".join(json.load(fh)["validation_errors"])
        self.assertIn("platform-auditor", errors)

    def test_duplicate_reviewer_does_not_count_twice(self):
        reviewer = self.reviewer("qa-verifier")
        data = self.input(tier=1, reviewers=[reviewer, dict(reviewer)], domains=["behavior"])
        written = self.write(data)
        self.assertEqual(written.returncode, 1)
        with open(self.report_path(), encoding="utf-8") as fh:
            errors = " ".join(json.load(fh)["validation_errors"])
        self.assertIn("duplicate agent", errors)

    def test_boolean_is_not_accepted_as_a_numeric_schema_value(self):
        data = self.input()
        data["tier"] = True
        data["checks"]["tests"]["exit_code"] = False
        written = self.write(data)
        self.assertEqual(written.returncode, 1)
        with open(self.report_path(), encoding="utf-8") as fh:
            errors = " ".join(json.load(fh)["validation_errors"])
        self.assertIn("tier must be", errors)
        self.assertIn("exit_code must be an integer", errors)

    def test_open_high_finding_keeps_gate_red(self):
        finding = {"severity": "high", "title": "lost update", "disposition": "open"}
        written = self.write(self.input(findings=[finding]))
        self.assertEqual(written.returncode, 1)
        with open(self.report_path(), encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["gate"], "fail")

    def test_open_medium_finding_keeps_gate_red(self):
        finding = {"severity": "medium", "title": "retry gap", "disposition": "open"}
        written = self.write(self.input(findings=[finding]))
        self.assertEqual(written.returncode, 1)

    def test_deferred_high_finding_keeps_gate_red(self):
        finding = {
            "severity": "high",
            "title": "lost update",
            "disposition": "deferred",
            "reason": "scheduled for later",
        }
        written = self.write(self.input(findings=[finding]))
        self.assertEqual(written.returncode, 1)

    def test_failed_check_requires_command_and_evidence(self):
        data = self.input()
        data["checks"]["tests"] = {"status": "fail"}
        written = self.write(data)
        self.assertEqual(written.returncode, 1)
        with open(self.report_path(), encoding="utf-8") as fh:
            errors = " ".join(json.load(fh)["validation_errors"])
        self.assertIn("checks.tests.command", errors)
        self.assertIn("checks.tests.evidence", errors)
        self.assertIn("checks.tests.exit_code", errors)


if __name__ == "__main__":
    unittest.main(verbosity=2)
