---
description: Run the Taurus verification required by the change's rigor tier and write a worktree-bound JSON report
argument-hint: [scope, e.g. staged | branch | path/to/dir]
---

Verify: **${ARGUMENTS:-the uncommitted changes on this branch}**

Load the `taurus` skill, then read `references/engineering-baseline.md` and
`references/verification-gate.md`.

1. Inspect Git status and the complete diff for the requested scope. State the tier,
   invariants, risk domains, and primary risk. Report the selected references and
   review mode in the `TAURUS ROUTE` format. Escalate when the diff carries more risk
   than expected.
2. Run applicable project checks. Record `build`, `tests`, `lint`, and `typecheck` as
   `pass`, `fail`, or `not_applicable`; every `not_applicable` entry needs a reason.
3. Apply the tier policy:
   - Tier 0: run QA, security, and performance reviewers concurrently; add the
     reliability, platform, frontend-quality, or AI/ML specialist required by the
     risk domains; then run the panel.
   - Tier 1: run the reviewer matched to the primary risk and any specialist required
     by a secondary domain.
   - Tier 2: run focused validation and self-review without spawning agents.
4. Check every finding against code or runtime evidence. Leave no finding open;
   record each one as fixed, deferred with a reason, or rejected with a reason.
5. Create the JSON input described in `references/verification-gate.md`, then write
   and validate the worktree-bound artifact:

```
python3 ~/.claude/taurus/hooks/gate-report.py write /tmp/taurus-gate-input.json
python3 ~/.claude/taurus/hooks/gate-report.py validate
```

6. Return the human summary from the reference. The gate passes only when the report
   says `pass`, no finding remains open, and validation confirms that the worktree
   fingerprint is current.
