---
description: Run a task end to end under the Taurus delivery standard - interrogate, design, test, implement, verify, review
argument-hint: <what to build or fix>
---

Deliver this under the Taurus standard: **$ARGUMENTS**

Load the `taurus` skill, then read `references/engineering-baseline.md` and follow it. Work through these phases and
report at each boundary.

## 1. Interrogate

Answer the six questions from `references/engineering-baseline.md` section 1 in the response, in
under fifteen lines: real outcome, blast radius, what already exists in this
codebase, invariants, workload numbers, out of scope.

Search the codebase before answering "what already exists". Assign the rigor tier
and say why.

## 2. Design

Tier 0 and tier 1: write the design note (problem, invariants, approach, two
rejected alternatives with reasons, failure modes, rollback). Load `references/system-design.md`
when the change crosses a service, API, schema, or async boundary. Load
`references/clean-architecture.md` for placement, `references/algorithm-rigor.md` for anything with a
complexity worth stating.

Tier 0: run the design through `references/review-panel.md` before writing code.

## 3. Tests first

Read `references/test-discipline.md`. Write the tests that would fail today: the invariant, the
boundaries, the failure paths, the concurrency behavior. Run them and show them failing.

## 4. Implement

Smallest change that makes the tests pass and holds the dependency direction. No
speculative generality. Match the surrounding code's idiom.

## 5. Self-review

Read the whole diff as if someone else wrote it. Check it against the
`references/engineering-baseline.md` definition of done. Fix what you find before spending agent time.

## 6. Verification gate

Read `references/verification-gate.md`. Run build, full test suite, lint, and type check yourself
first, then spawn `qa-verifier`, `security-auditor`, and `performance-auditor` in a
single message. Verify each finding against the code before acting on it. Report
the gate result.

## 7. Review panel

Tier 0, or any decision made along the way: load `references/review-panel.md`, run 2 to 3
independent agents, synthesize against the code without deferring to any of them.

## 8. Report

```
TIER: <n>  <one-line reason>
CHANGED: <files>
TESTS: <n added>  suite: <n passed, n failed>
GATE: <qa / security / performance results>
OPEN: <deferred findings with reasons, or none>
```

Do not commit unless asked. When asked, follow `references/git-discipline.md`.
