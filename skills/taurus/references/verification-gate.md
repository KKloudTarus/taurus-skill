> Load when: Collecting evidence before declaring work complete or ready to ship. Defines tier-aware checks, reviewer selection, finding resolution, and the machine-readable verification artifact tied to the current Git worktree.

# Verification gate

Verification scales with the risk tier selected in `references/engineering-baseline.md`.
Every tier records what was checked, but only tier 0 always runs QA, security, and
performance reviewers.

## Establish scope

Read the status and diff before running commands. Record the tier, changed surface,
invariants, risk domains, and one primary risk. Supported labels are:

```text
behavior       security        performance      architecture
algorithm      database        migration        operations
reliability    sre             observability    infrastructure
supply_chain   frontend        accessibility    api_contract
data           model           ml               ai_safety
llm_security   cost            documentation    mechanical
```

Run each project check that applies to the changed surface. The artifact has slots for
`build`, `tests`, `lint`, and `typecheck`. Use `not_applicable` only when the project
has no corresponding command or the changed surface cannot exercise it, and record a
reason. A failing applicable check keeps the gate red.

## Review by tier

**Tier 0.** Run `qa-verifier`, `security-auditor`, and `performance-auditor`
concurrently after local checks pass. Add `reliability-auditor` when a database,
migration, SRE, observability, operational, or reliability domain is in scope. Add
`platform-auditor` for infrastructure or supply-chain risk,
`frontend-quality-auditor` for frontend or accessibility risk, and `ai-ml-verifier`
for data, model, ML, or AI-safety risk. Run the review panel required by the baseline.

**Tier 1.** Run one reviewer matched to the primary risk. A secondary domain that has
a dedicated specialist also requires that specialist. Escalate to tier 0 when the
change exposes two independent high-impact risks.

**Tier 2.** Perform self-review and focused validation. Do not spawn a reviewer unless
the diff reveals behavior or risk that changes the tier.

Give each reviewer the same scope, relevant invariants, diff, and commands. Verify
every finding against the code or a reproduction before accepting it.

## Resolve findings

| Severity | Required action |
|---|---|
| Critical | Fix before completion; data loss, money loss, corruption, or auth bypass keeps the gate red |
| High | Fix before completion; real wrong behavior or expected-load failure keeps the gate red |
| Medium | Fix or defer with a concrete reason and follow-up |
| Low | Fix when useful, or record why it does not belong in this change |

Agreement between reviewers is not evidence by itself. Mark each finding as fixed,
deferred, or rejected and preserve the reason.

## Machine-readable report

Prepare a JSON input document with this shape:

```json
{
  "tier": 1,
  "tier_reason": "user-visible checkout behavior",
  "scope": "working tree",
  "risk_domains": ["behavior"],
  "primary_risk": "behavior",
  "checks": {
    "build": {"status": "pass", "command": "npm run build", "exit_code": 0, "evidence": "build completed"},
    "tests": {"status": "pass", "command": "npm test", "exit_code": 0, "evidence": "214 passed"},
    "lint": {"status": "pass", "command": "npm run lint", "exit_code": 0, "evidence": "0 findings"},
    "typecheck": {"status": "not_applicable", "reason": "project has no type checker"}
  },
  "domain_checks": {},
  "reviewers": [
    {"agent": "qa-verifier", "verdict": "pass", "critical": 0, "high": 0, "medium": 0, "low": 0, "evidence": "boundary and failure tests passed"}
  ],
  "self_review": {"status": "pass", "evidence": "complete diff read after tests"},
  "findings": []
}
```

Add the check required by each selected specialist domain. It uses the same `status`,
`command`, `exit_code`, `evidence`, and `not_applicable` rules as the base checks.

| Risk domain | Required domain check |
|---|---|
| `infrastructure` | `plan` |
| `supply_chain` | `provenance` |
| `sre` | `slo` |
| `observability` | `telemetry` |
| `frontend` | `browser` |
| `accessibility` | `accessibility` |
| `api_contract` | `contract` |
| `data`, `model`, `ml` | `evaluation` |
| `ai_safety` | `safety_eval` |
| `llm_security` | `security_eval` |
| `cost` | `cost` |

For example, an infrastructure report records the exact current plan:

```json
{
  "domain_checks": {
    "plan": {
      "status": "pass",
      "command": "tofu plan -out=review.tfplan",
      "exit_code": 0,
      "evidence": "2 add, 1 change, 0 destroy"
    }
  }
}
```

Tier 0 also includes a panel record with its actual participants:

```json
{
  "panel": {
    "verdict": "pass",
    "agents": ["architecture-critic", "qa-verifier", "security-auditor"],
    "evidence": "three independent reports checked against the final diff"
  }
}
```

Write the report after all checks and finding resolution:

```
python3 ~/.claude/taurus/hooks/gate-report.py write /tmp/taurus-gate-input.json
python3 ~/.claude/taurus/hooks/gate-report.py validate
```

The default output is `.git/taurus/verification.json`. The writer adds UTC time,
repository root, HEAD, and a fingerprint covering tracked changes, staged changes,
untracked paths, and untracked file content. `validate` fails when the report is red,
the schema is incomplete, the tier lacks its required reviewers, or the worktree has
changed since the report was written.

The artifact records evidence; it does not make an unverified claim true. Command
status, exit codes, and reviewer counts must come from actual output. Every finding
must be fixed, deferred with a reason, or rejected with a reason before the report can
pass. Critical and high findings cannot be deferred.

## Human report

Summarize the same artifact without pasting raw reviewer output:

```
TIER: <0|1|2> - <reason>
CHECKS: build <status>, tests <status>, lint <status>, typecheck <status>, domain <statuses>
REVIEWERS: <agents and verdicts, or self-review>
FINDINGS: <fixed, deferred, rejected; none open>
ARTIFACT: .git/taurus/verification.json - current
GATE: pass | fail
```
