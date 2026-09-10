#!/usr/bin/env python3
"""Write and validate a Taurus verification report bound to a Git worktree."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional


CHECKS = ("build", "tests", "lint", "typecheck")
STATUSES = {"pass", "fail", "not_applicable"}
CORE_TIER_ZERO = {"qa-verifier", "security-auditor", "performance-auditor"}
KNOWN_REVIEWERS = CORE_TIER_ZERO | {
    "architecture-critic",
    "algorithm-verifier",
    "reliability-auditor",
    "platform-auditor",
    "frontend-quality-auditor",
    "ai-ml-verifier",
}
KNOWN_PANEL_AGENTS = KNOWN_REVIEWERS | {"decision-analyst"}
DOMAIN_REVIEWER = {
    "behavior": "qa-verifier",
    "security": "security-auditor",
    "performance": "performance-auditor",
    "architecture": "architecture-critic",
    "algorithm": "algorithm-verifier",
    "database": "reliability-auditor",
    "migration": "reliability-auditor",
    "operations": "reliability-auditor",
    "reliability": "reliability-auditor",
    "sre": "reliability-auditor",
    "observability": "reliability-auditor",
    "infrastructure": "platform-auditor",
    "supply_chain": "platform-auditor",
    "frontend": "frontend-quality-auditor",
    "accessibility": "frontend-quality-auditor",
    "api_contract": "qa-verifier",
    "data": "ai-ml-verifier",
    "model": "ai-ml-verifier",
    "ml": "ai-ml-verifier",
    "ai_safety": "ai-ml-verifier",
    "llm_security": "security-auditor",
    "cost": "performance-auditor",
}
KNOWN_DOMAINS = set(DOMAIN_REVIEWER) | {"documentation", "mechanical"}
REQUIRED_DOMAIN_CHECKS = {
    "infrastructure": "plan",
    "supply_chain": "provenance",
    "sre": "slo",
    "observability": "telemetry",
    "frontend": "browser",
    "accessibility": "accessibility",
    "api_contract": "contract",
    "data": "evaluation",
    "model": "evaluation",
    "ml": "evaluation",
    "ai_safety": "safety_eval",
    "llm_security": "security_eval",
    "cost": "cost",
}
SPECIALIST_DOMAINS = {
    "reliability-auditor": {
        "database", "migration", "operations", "reliability", "sre", "observability"
    },
    "platform-auditor": {"infrastructure", "supply_chain"},
    "frontend-quality-auditor": {"frontend", "accessibility"},
    "ai-ml-verifier": {"data", "model", "ml", "ai_safety"},
}
SEVERITIES = {"critical", "high", "medium", "low"}
DISPOSITIONS = {"open", "fixed", "deferred", "rejected"}


class ReportError(ValueError):
    pass


def validate_check(item: object, path: str, errors: list[str]) -> None:
    if not isinstance(item, dict):
        errors.append(f"{path} is required")
        return
    status = item.get("status")
    if status not in STATUSES:
        errors.append(f"{path}.status must be pass, fail, or not_applicable")
    if status in ("pass", "fail") and not str(item.get("command", "")).strip():
        errors.append(f"{path}.command is required when status is {status}")
    if status in ("pass", "fail") and not str(item.get("evidence", "")).strip():
        errors.append(f"{path}.evidence is required when status is {status}")
    exit_code = item.get("exit_code")
    if status in ("pass", "fail") and type(exit_code) is not int:
        errors.append(f"{path}.exit_code must be an integer when status is {status}")
    if status == "pass" and type(exit_code) is int and exit_code != 0:
        errors.append(f"{path}.exit_code must be 0 when status is pass")
    if status == "fail" and type(exit_code) is int and exit_code == 0:
        errors.append(f"{path}.exit_code must be non-zero when status is fail")
    if status == "not_applicable" and not str(item.get("reason", "")).strip():
        errors.append(f"{path}.reason is required when status is not_applicable")


def git(root: Path, *args: str, check: bool = True) -> bytes:
    proc = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, check=False
    )
    if check and proc.returncode != 0:
        raise ReportError(proc.stderr.decode("utf-8", "replace").strip() or "git command failed")
    return proc.stdout


def repository_root(start: Optional[str] = None) -> Path:
    base = Path(start or os.getcwd()).resolve()
    out = git(base, "rev-parse", "--show-toplevel")
    return Path(out.decode().strip()).resolve()


def default_report_path(root: Path) -> Path:
    path = git(root, "rev-parse", "--git-path", "taurus/verification.json").decode().strip()
    candidate = Path(path)
    return candidate if candidate.is_absolute() else root / candidate


def worktree_fingerprint(root: Path) -> str:
    """Hash HEAD, index/worktree diff, status, and untracked file contents."""
    digest = hashlib.sha256()
    head = git(root, "rev-parse", "HEAD", check=False).strip()
    status = git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    diff = git(root, "diff", "--binary", "HEAD", "--", check=False)
    digest.update(b"head\0" + head + b"\0status\0" + status + b"\0diff\0" + diff)

    for entry in status.split(b"\0"):
        if not entry.startswith(b"?? "):
            continue
        raw_path = entry[3:]
        path = root / os.fsdecode(raw_path)
        digest.update(b"\0untracked\0" + raw_path + b"\0")
        try:
            if path.is_symlink():
                digest.update(b"link\0" + os.fsencode(os.readlink(path)))
            elif path.is_file():
                digest.update(path.read_bytes())
            else:
                digest.update(b"special")
        except OSError as exc:
            raise ReportError(f"cannot fingerprint {path}: {exc}") from exc
    return digest.hexdigest()


def validate_input(data: dict) -> list[str]:
    errors = []
    tier = data.get("tier")
    if type(tier) is not int or tier not in (0, 1, 2):
        errors.append("tier must be 0, 1, or 2")
    if not isinstance(data.get("tier_reason"), str) or not data["tier_reason"].strip():
        errors.append("tier_reason must be a non-empty string")
    if not isinstance(data.get("scope"), str) or not data["scope"].strip():
        errors.append("scope must be a non-empty string")

    domains = data.get("risk_domains")
    if not isinstance(domains, list) or not domains or not all(isinstance(item, str) for item in domains):
        errors.append("risk_domains must be a non-empty list of strings")
        domains = []
    else:
        if len(domains) != len(set(domains)):
            errors.append("risk_domains must not contain duplicates")
        unknown_domains = sorted(set(domains) - KNOWN_DOMAINS)
        if unknown_domains:
            errors.append("unknown risk domains: " + ", ".join(unknown_domains))
    primary_risk = data.get("primary_risk")
    if primary_risk not in domains:
        errors.append("primary_risk must name one entry from risk_domains")

    checks = data.get("checks")
    if not isinstance(checks, dict):
        errors.append("checks must be an object")
        checks = {}
    for name in CHECKS:
        validate_check(checks.get(name), f"checks.{name}", errors)

    domain_checks = data.get("domain_checks")
    if not isinstance(domain_checks, dict):
        errors.append("domain_checks must be an object")
        domain_checks = {}
    for name, item in domain_checks.items():
        if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", name):
            errors.append(f"invalid domain check name: {name}")
            continue
        validate_check(item, f"domain_checks.{name}", errors)
    required_domain_checks = {
        REQUIRED_DOMAIN_CHECKS[domain]
        for domain in domains
        if domain in REQUIRED_DOMAIN_CHECKS
    }
    for name in sorted(required_domain_checks - set(domain_checks)):
        errors.append(f"domain_checks.{name} is required for the selected risk domains")

    reviewers = data.get("reviewers")
    if not isinstance(reviewers, list):
        errors.append("reviewers must be a list")
        reviewers = []
    names = set()
    for index, reviewer in enumerate(reviewers):
        if not isinstance(reviewer, dict):
            errors.append(f"reviewers[{index}] must be an object")
            continue
        agent = reviewer.get("agent")
        if not isinstance(agent, str) or not agent:
            errors.append(f"reviewers[{index}].agent is required")
            continue
        if agent in names:
            errors.append(f"reviewers contains duplicate agent: {agent}")
        names.add(agent)
        if agent not in KNOWN_REVIEWERS:
            errors.append(f"reviewers[{index}].agent is unknown: {agent}")
        if reviewer.get("verdict") not in ("pass", "fail"):
            errors.append(f"reviewers[{index}].verdict must be pass or fail")
        if not str(reviewer.get("evidence", "")).strip():
            errors.append(f"reviewers[{index}].evidence is required")
        for severity in SEVERITIES:
            count = reviewer.get(severity)
            if type(count) is not int or count < 0:
                errors.append(f"reviewers[{index}].{severity} must be a non-negative integer")

    if tier == 0:
        missing = sorted(CORE_TIER_ZERO - names)
        if missing:
            errors.append("tier 0 requires reviewers: " + ", ".join(missing))
    if tier == 1 and len(names) < 1:
        errors.append("tier 1 requires at least one targeted reviewer")
    expected_reviewer = DOMAIN_REVIEWER.get(primary_risk)
    if tier == 1 and not expected_reviewer:
        errors.append("tier 1 primary_risk must map to a targeted reviewer")
    if tier == 1 and expected_reviewer and expected_reviewer not in names:
        errors.append(f"primary risk {primary_risk} requires {expected_reviewer}")
    if tier == 2 and set(domains) - {"documentation", "mechanical"}:
        errors.append("tier 2 only permits documentation or mechanical risk")
    for agent, required_domains in SPECIALIST_DOMAINS.items():
        matched = sorted(required_domains.intersection(domains))
        if matched and agent not in names:
            errors.append(f"risk domains {', '.join(matched)} require {agent}")

    self_review = data.get("self_review")
    if not isinstance(self_review, dict) or self_review.get("status") != "pass":
        errors.append("self_review.status must be pass")
    elif not str(self_review.get("evidence", "")).strip():
        errors.append("self_review.evidence is required")

    panel = data.get("panel")
    if tier == 0:
        if not isinstance(panel, dict) or panel.get("verdict") != "pass":
            errors.append("tier 0 requires a passing review panel")
        else:
            if not str(panel.get("evidence", "")).strip():
                errors.append("panel.evidence is required for tier 0")
            panel_agents = panel.get("agents")
            if (
                not isinstance(panel_agents, list)
                or not 2 <= len(panel_agents) <= 3
                or not all(isinstance(item, str) and item for item in panel_agents)
            ):
                errors.append("panel.agents must list 2 to 3 agents for tier 0")
            elif len(set(panel_agents)) != len(panel_agents):
                errors.append("panel.agents must be distinct")
            elif unknown_panel_agents := sorted(set(panel_agents) - KNOWN_PANEL_AGENTS):
                errors.append("panel.agents contains unknown agents: " + ", ".join(unknown_panel_agents))

    findings = data.get("findings")
    if not isinstance(findings, list):
        errors.append("findings must be a list")
    else:
        for index, finding in enumerate(findings):
            if not isinstance(finding, dict):
                errors.append(f"findings[{index}] must be an object")
                continue
            if finding.get("severity") not in SEVERITIES:
                errors.append(f"findings[{index}].severity is invalid")
            if finding.get("disposition") not in DISPOSITIONS:
                errors.append(f"findings[{index}].disposition is invalid")
            if not str(finding.get("title", "")).strip():
                errors.append(f"findings[{index}].title is required")
            if finding.get("disposition") in ("deferred", "rejected") and not str(finding.get("reason", "")).strip():
                errors.append(f"findings[{index}].reason is required for deferred or rejected findings")
    return errors


def gate_status(data: dict, errors: list[str]) -> str:
    if errors:
        return "fail"
    all_checks = list(data["checks"].values()) + list(data["domain_checks"].values())
    if any(item["status"] == "fail" for item in all_checks):
        return "fail"
    if any(item["verdict"] == "fail" for item in data["reviewers"]):
        return "fail"
    if any(item["disposition"] == "open" for item in data["findings"]):
        return "fail"
    if any(
        item["severity"] in ("critical", "high") and item["disposition"] == "deferred"
        for item in data["findings"]
    ):
        return "fail"
    return "pass"


def write_report(input_path: str, output_path: Optional[str], root_arg: Optional[str]) -> int:
    root = repository_root(root_arg)
    try:
        with open(input_path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise ReportError(f"cannot read input: {exc}") from exc
    if not isinstance(data, dict):
        raise ReportError("input must be a JSON object")

    errors = validate_input(data)
    report = dict(data)
    report.update({
        "schema_version": 2,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "repository": str(root),
        "head": git(root, "rev-parse", "HEAD", check=False).decode().strip() or None,
        "worktree_fingerprint": worktree_fingerprint(root),
        "validation_errors": errors,
        "gate": gate_status(data, errors),
    })
    output = Path(output_path).resolve() if output_path else default_report_path(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)
    return 0 if report["gate"] == "pass" else 1


def validate_report(path_arg: Optional[str], root_arg: Optional[str]) -> int:
    root = repository_root(root_arg)
    path = Path(path_arg).resolve() if path_arg else default_report_path(root)
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReportError(f"cannot read report: {exc}") from exc
    errors = validate_input(report) if isinstance(report, dict) else ["report must be an object"]
    if isinstance(report, dict):
        if report.get("schema_version") != 2:
            errors.append("schema_version must be 2")
        if report.get("repository") != str(root):
            errors.append("report belongs to a different repository")
        if report.get("worktree_fingerprint") != worktree_fingerprint(root):
            errors.append("report is stale: worktree fingerprint changed")
        expected = gate_status(report, errors)
        if report.get("gate") != expected or report.get("gate") != "pass":
            errors.append("gate is not pass")
    if errors:
        for error in dict.fromkeys(errors):
            print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"valid: {path}")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", help="repository path; defaults to the current repository")
    sub = parser.add_subparsers(dest="command", required=True)
    write = sub.add_parser("write")
    write.add_argument("input")
    write.add_argument("--output")
    validate = sub.add_parser("validate")
    validate.add_argument("report", nargs="?")
    sub.add_parser("fingerprint")
    args = parser.parse_args(argv)
    try:
        if args.command == "write":
            return write_report(args.input, args.output, args.root)
        if args.command == "validate":
            return validate_report(args.report, args.root)
        print(worktree_fingerprint(repository_root(args.root)))
        return 0
    except ReportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
