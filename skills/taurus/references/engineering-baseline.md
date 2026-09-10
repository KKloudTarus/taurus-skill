> Load when: Starting implementation, a bug fix, refactor, technical design, or delivery task. Owns the single authoritative rigor-tier matrix, the amount of discovery and verification each tier requires, escalation rules, work sequences, and tier-specific definitions of done.

# Engineering baseline

Choose the smallest process that protects the user from the actual blast radius. The
tier is a risk decision, not a measure of diff size: a one-line authorization change
can be tier 0, while a large documentation edit can remain tier 2.

## Understand the work

Before editing, answer only the questions that can change the implementation or the
tier. Keep the answers brief for routine work and make them explicit for tier 0.

1. What outcome does the user need beyond the solution they named?
2. What could break: data, money, security, availability, compatibility, or only presentation?
3. What code, convention, or tool already handles part of this?
4. Which invariants must remain true?
5. What workload or boundary matters: volume, concurrency, latency, size, or rate?
6. What is outside the requested scope?

Do not demand invented workload numbers. If a number would change the design and is
unknown, record the uncertainty and identify the cheapest measurement that would
settle it.

## Rigor tiers

This table is the source of truth for tier behavior everywhere in the pack.

| Tier | Typical risk | Required work |
|---|---|---|
| 0, correctness-critical | Money, authorization, tenant isolation, destructive infrastructure or migrations, inventory, concurrency, irreversible data changes, high-impact ML decisions, autonomous consequential actions | Explicit outcome and invariants; design note; failure and concurrency tests where applicable; full project checks; QA, security, and performance reviewers; every specialist required by the risk domains; 2–3 agent review panel; current gate artifact |
| 1, user-visible behavior | API or UI behavior, business rules, jobs, non-destructive infrastructure or schema additions, request-path changes, bounded model or prompt changes | Acceptance criteria; short design note when a real choice exists; behavior or evaluation tests; relevant project checks; one reviewer matched to the primary risk plus a specialist for any secondary domain that requires one; current gate artifact |
| 2, low risk | Docs, copy, formatting, local cleanup, diagnostic logging, safe config defaults | Focused validation for the changed surface; self-review; current gate artifact; no reviewer or panel unless risk emerges |

State the tier and its concrete reason in one sentence. Escalate immediately when the
work reveals a higher-risk invariant, a hard-to-reverse decision, cross-service state,
or uncertainty that cannot be bounded. Never lower a tier to save agent calls.

## Choose the reviewer

Tier 1 uses one reviewer by default:

| Primary risk | Reviewer |
|---|---|
| Behavior, edge cases, tests | `qa-verifier` |
| Authentication, input, secrets, tenant data | `security-auditor` |
| Latency, allocations, queries, load | `performance-auditor` |
| Boundaries, coupling, dependency direction | `architecture-critic` |
| Algorithm, data structure, concurrency correctness | `algorithm-verifier` |
| Database safety, migration, recovery, operability | `reliability-auditor` |
| SLO, alerts, observability, capacity, incident readiness | `reliability-auditor` |
| Terraform, OpenTofu, Pulumi, Kubernetes, CI/CD, cloud IAM | `platform-auditor` |
| Browser behavior, accessibility, frontend experience | `frontend-quality-auditor` |
| Data, features, models, ML evaluation, LLM, RAG, agent safety | `ai-ml-verifier` |

A change with two independent high-impact risks belongs in tier 0 or needs a second
reviewer. A mechanical tier 2 change does not gain quality from a ceremonial agent run.

## Work sequence

Tier 0:

```
inspect -> invariants -> design -> design panel -> tests -> implement -> self-review
  -> full checks -> full verification gate -> final panel -> gate artifact
```

Tier 1:

```
inspect -> acceptance criteria -> design when needed -> tests -> implement
  -> self-review -> relevant checks -> targeted reviewer -> gate artifact
```

Tier 2:

```
inspect -> edit -> focused validation -> self-review -> gate artifact
```

Tests precede implementation when behavior changes and a failing test can express the
defect. Documentation, formatting, and equivalent non-behavioral work do not need a
manufactured red-test phase.

## Engineering constraints

- A behavior change ships with a regression test at the narrowest useful layer.
- Domain policy does not depend on framework, transport, database, or SDK types.
- Shared mutable state names its protection mechanism. Work creation and retries are bounded.
- Errors remain errors until a layer can make a recovery, retry, or user-facing decision.
- Complexity and performance claims name the input that grows and the evidence available.
- A new dependency has a concrete benefit, maintenance state, license, and exit cost.
- Secrets and sensitive user data stay out of code, fixtures, logs, and reports.
- Infrastructure source changes do not authorize apply, destroy, state mutation, model
  promotion, paid evaluation, or another external action.
- Match the surrounding repository unless doing so would preserve a demonstrated defect.

## Definition of done

Every tier must satisfy these outcomes:

- The requested outcome is present and the diff stays within scope.
- Verification matches the chosen tier and the actual project capabilities.
- Every reported command, measurement, and reviewer result came from a real run.
- No finding remains open. Deferred or rejected findings include a reason.
- `.git/taurus/verification.json` validates against the current worktree fingerprint.

Tier 0 additionally requires the full reviewer set and panel. Tier 1 requires the
matched reviewer. Tier 2 requires focused checks and self-review, with no implied
three-agent gate. Git and PR requirements apply only when the user asks to ship.
