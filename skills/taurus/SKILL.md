---
name: taurus
description: Risk-tiered delivery for code changes and material engineering decisions. Load for implementation, fixes, refactors, design, review, or shipping, or when Taurus is named. Do not load for ordinary prose, summaries, or general questions.
---

# Taurus delivery standard

Use this skill to choose the right level of engineering rigor and load only the
guidance the current task needs. Detailed policy lives in the references; this file
owns routing and the small set of boundaries shared by every Taurus workflow.

## Start here

For implementation, fixes, refactors, or delivery work, read
`references/engineering-baseline.md` first. Inspect the repository before deciding
the rigor tier. The tier definitions, escalation rules, reviewer count, workflow, and
definition of done live only in `references/engineering-baseline.md`. Do not recreate
them from memory or apply the heaviest workflow by default.

At the first engineering progress update, expose the selection in one compact line:

```
TAURUS ROUTE: tier=<0|1|2>; refs=<loaded references>; review=<panel|agents|self>
```

Update the line only if discovery changes the tier or route. This is an execution trace,
not a request to explain the routing process.

## Route by task

Read a reference before doing the work it governs.

| Situation | Read |
|---|---|
| Implementation, fix, refactor, or delivery | `references/engineering-baseline.md` |
| Engineering prose or a `/style` review | `references/writing-voice.md` |
| Branching, staging, committing, or opening a PR | `references/git-discipline.md` |
| Commit message, PR title, tag, or changelog | `references/conventional-commits.md` |
| Layer, module, port, interface, or dependency placement | `references/clean-architecture.md` |
| Test selection, test design, flake, or coverage judgment | `references/test-discipline.md` |
| Algorithm, data structure, query, index, or concurrency primitive | `references/algorithm-rigor.md` |
| Service, API, schema, migration, queue, cache, or retry design | `references/system-design.md` |
| Terraform, OpenTofu, Pulumi, Kubernetes, CI/CD, or cloud infrastructure | `references/infrastructure-delivery.md` |
| SLO, alert, capacity, incident readiness, recovery, or production operation | `references/sre-operations.md` |
| Browser UX, accessibility, frontend async behavior, or Web Vitals | `references/frontend-quality.md` |
| Dataset, training, feature, model, drift, or predictive-ML workflow | `references/ml-engineering.md` |
| LLM, RAG, prompt, model gateway, memory, tool, or agent workflow | `references/genai-agent-systems.md` |
| Evidence required before completion | `references/verification-gate.md` |
| Tier 0 review, hard-to-reverse choice, explicit `/panel`, or unresolved material conflict | `references/review-panel.md` |
| Stiff or generic writing that needs a rewrite | `references/rewrites.md` |
| PR review, debugging, refactor, dependency, migration, or incident | `references/checklists.md` |

Choose the smallest sufficient set. Do not read adjacent references for background,
and do not reload a reference already present in the current context. A task may need
more than one domain reference only when its actual risks cross those domains.

## Shared boundaries

- Search the codebase before adding another abstraction, dependency, or convention.
- Write down the invariants that could be violated and test behavior at the level of
  risk selected in the baseline.
- Use evidence that exists. Never invent a command result, measurement, file path,
  benchmark, or reviewer finding.
- Verify agent findings against code or runtime evidence before acting on them.
- Preserve the user's scope and authorization. Never commit, push, open a PR, deploy,
  or mutate an external system unless the user requested that action.
- Treat project tooling and repository conventions as authoritative unless they
  conflict with a stated invariant or safety requirement.
- Before reporting completion, follow the tier-specific checks in
  `references/verification-gate.md` and write the machine-readable gate report. A
  stale report does not count.

## Writing and Git

Write like an experienced teammate responding to the person in front of you. Natural
transitions, contrasts, and warmth are allowed when they help. The prose linter offers
signals, not a substitute for judgment; `references/writing-voice.md` owns the voice.

Git rules are intentionally stricter because they protect shared history. Load
`references/git-discipline.md` before any write operation and
`references/conventional-commits.md` before composing a message. Repository hooks own
the enforceable policy. Fix a block at its cause rather than bypassing it.
