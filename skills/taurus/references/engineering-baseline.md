> Load when: The Taurus principal-engineer working standard. Load at the start of any implementation, refactor, bug fix, design, or delivery task, before writing code or a plan. Covers how to interrogate a request, how to sequence the work, what "done" requires, and which specialist skill to pull in next. Triggers on "implement", "build", "fix", "refactor", "add feature", "design", "ship", "deliver", and any task that will produce a commit.

# Engineering baseline

How work gets done here. Load this first, then pull the specialist skills it points at.

## 1. Interrogate before you build

Never start from the literal request alone. Spend the first minutes on these six
questions and write the answers down where the user can see them.

1. **What outcome does the user actually need?** Separate the stated solution from
   the underlying problem. If they asked for a cache and the real problem is an
   N+1 query, say so before building the cache.
2. **What breaks if I get this wrong?** Data loss, money, security, availability,
   or a cosmetic bug. The blast radius sets how much rigor the rest of the task gets.
3. **What is already in the codebase that does this?** Search before writing.
   Duplicating an existing abstraction is a defect.
4. **What are the invariants?** State them as sentences that must stay true.
   Every later decision gets checked against them.
5. **What is the workload?** Request rate, data volume, concurrency, latency
   budget, growth. Numbers, not adjectives. Without them, algorithm and storage
   choices are guesses.
6. **What is out of scope?** Name it, so scope creep is visible.

If a premise in the request is wrong, say it in one or two sentences, state the
assumption you will proceed under, and keep building. Do not stop and wait unless
proceeding either way would be unsafe or would waste the work.

## 2. Rigor tiers

Match effort to blast radius. Do not apply tier 0 ceremony to a copy change, and
never apply tier 2 casualness to money or auth.

| Tier | Examples | Required |
|---|---|---|
| 0 correctness-critical | payment, inventory, auth, permissions, migrations, concurrency, money math | design note + invariant list + tests including concurrency and failure paths + review-panel.md + full verification-gate.md |
| 1 user-visible behavior | API endpoints, business rules, background jobs, schema additions | tests + verification-gate.md + one reviewer agent |
| 2 low risk | copy, logging, docs, config defaults, formatting | tests where behavior changes, self-review against the checklist |

State which tier you picked and why, in one line.

## 3. Work sequence

```
interrogate -> design note (tier 0/1) -> tests -> implementation -> self-review
  -> verification-gate -> review-panel (tier 0, or any decision) -> commit -> PR
```

The design note for tier 0 and 1 is short: problem, invariants, chosen approach,
two rejected alternatives with the reason, failure modes, rollback. Ten to thirty
lines. Put it in the PR body, or in docs/adr/ when the decision outlives the PR.

## 4. Non-negotiables

- **Tests ship with the change.** A behavior change without a test is incomplete
  work. See test-discipline.md.
- **Dependency direction holds.** infrastructure -> adapters -> application -> domain.
  See clean-architecture.md.
- **Complexity is stated.** Any loop over a collection that can grow, any new index,
  any new query gets its complexity and its expected row count written down.
  See algorithm-rigor.md.
- **Errors are handled at the layer that can decide.** No swallowed exceptions, no
  catch {}, no error returned as nil.
- **Concurrency is explicit.** Name the shared state, name the lock or the channel
  or the transaction that protects it. Unbounded goroutines, threads, or promises
  are defects.
- **Nothing is reported done without running it.** Build, tests, and the actual
  code path. Paste failing output rather than describing it.
- **No new dependency without justification.** Size, maintenance status, license,
  and what it replaces. A 40-line utility beats a transitive tree.
- **Secrets never enter code, logs, tests, or fixtures.**

## 5. Code standards

- Names say what the thing is in the domain, not what type it is. seatHold, not
  dataObj. No abbreviations that the domain does not already use.
- Functions do one thing at one level of abstraction. If you cannot name it without
  "and", split it.
- Comments explain why, never what. A comment restating the code is deleted.
- Public API surface is minimal. Export what callers need, nothing else.
- No dead code, no commented-out code, no TODO without an owner and a ticket.
- Formatting and linting come from the project's own tooling. Run it, do not
  hand-format.
- Match the surrounding code's idiom. A file that uses one style does not get a
  second style introduced.

## 6. Definition of done

All of these, every time:

- [ ] The stated problem is solved, and the acceptance criteria are written down.
- [ ] Tests cover the happy path, the boundaries, the failure paths, and the
      concurrency behavior when concurrency exists.
- [ ] Build passes. Full test suite passes. Linter passes. Type checker passes.
- [ ] verification-gate.md ran: QA, security, and performance all reported.
- [ ] Every finding is fixed, or listed with a reason for deferring.
- [ ] The diff contains only what the task needs.
- [ ] Commit and PR follow git-discipline.md.
- [ ] Prose follows writing-voice.md.

## 7. Which skill next

| Situation | Skill |
|---|---|
| Writing any prose, commit, PR, doc | writing-voice.md |
| Committing, branching, opening a PR | git-discipline.md |
| Placing code in layers, defining ports | clean-architecture.md |
| Deciding what and how to test | test-discipline.md |
| Choosing a data structure, algorithm, index, or pattern | algorithm-rigor.md |
| Designing a service, API, schema, or async flow | system-design.md |
| Before declaring done | verification-gate.md |
| Any review, technology choice, or architecture decision | review-panel.md |
