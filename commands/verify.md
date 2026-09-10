---
description: Run the three-agent verification gate (QA, security, performance) over the current change
argument-hint: [scope, e.g. staged | branch | path/to/dir]
---

Run the verification gate over: **${ARGUMENTS:-the uncommitted changes on this branch}**

Load the `taurus` skill, then read `references/verification-gate.md` and follow it exactly.

1. Establish scope with `git status --porcelain` and `git diff` (or `git diff main...HEAD`
   for branch scope). List the files in scope.
2. Run the project's build, full test suite, lint, and type check yourself. Paste
   the real output. Stop and fix if anything is red, then start again.
3. Spawn `qa-verifier`, `security-auditor`, and `performance-auditor` in a single
   message so they run concurrently. Give each: the scope, the diff, the invariants
   this change must hold, and the commands to build and test.
4. Verify every finding against the code yourself before acting on it. Agents
   produce false positives, and fixing a false positive adds a defect.
5. Fix all critical and high findings. Record medium and low findings with a reason
   when deferring.
6. Report in `references/verification-gate.md` format.

The gate passes only with zero open critical and zero open high findings.
