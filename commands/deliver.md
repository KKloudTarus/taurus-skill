---
description: Deliver a change under a risk-tiered Taurus workflow, from repository inspection through current verification evidence
argument-hint: <what to build or fix>
---

Deliver this under the Taurus standard: **$ARGUMENTS**

Load the `taurus` skill and read `references/engineering-baseline.md`. Inspect the
repository, state the tier with its reason, then follow only that tier's workflow.

## Shared start

Clarify the outcome, existing implementation, relevant invariants, important workload
or boundary, and out-of-scope work. Keep this compact unless the change is tier 0.
Escalate the tier if investigation reveals more risk than the request suggested.

## Tier 0

Write the design note and run its decision through `references/review-panel.md` before
implementation. Read the architecture, system-design, testing, or algorithm reference
that matches the change, plus the routed infrastructure, SRE, frontend, ML, or GenAI
reference when one of those domains is in scope. Add failure and concurrency tests where
those risks exist.

After implementation and self-review, run all project checks and the full tier 0 gate
from `references/verification-gate.md`. Resolve findings, run the final panel, and
write the current gate artifact.

## Tier 1

Write acceptance criteria and a short design note only when the implementation has a
meaningful choice. Add behavior tests, implement the smallest complete change, and run
the project checks relevant to that surface. Model and GenAI changes use evaluation cases
as behavior tests. Ask the matched reviewer and any required secondary specialist to
inspect the change, resolve the findings, and write the gate artifact.

## Tier 2

Make the scoped edit directly. Do not manufacture a design note, red-test phase, or
agent panel for documentation, formatting, or another mechanical change. Run focused
validation, review the diff, and write a tier 2 gate artifact. Escalate if behavior
changed unexpectedly.

## Report

```
TAURUS ROUTE: tier=<0|1|2>; refs=<loaded references>; review=<panel|agents|self>
TIER: <0|1|2> - <reason>
CHANGED: <files>
CHECKS: <commands and results>
REVIEWERS: <agents, or self-review for tier 2>
GATE: <pass|fail> - .git/taurus/verification.json
OPEN: <deferred findings with reasons, or none>
```

Do not commit, push, open a PR, deploy, or mutate an external system unless the user
asked for that action. When asked to ship, read `references/git-discipline.md`.
