> Load when: The three mandatory checks that run before any change is declared done - QA correctness, security audit, performance audit - executed by independent agents in parallel and then verified against the code. Load before saying a task is finished, before marking a PR ready, and before any commit that changes behavior.

# Verification gate

Nothing is done until three independent checks have run against it and their
findings are resolved. Self-review by the author who wrote the code catches the
defects the author was already thinking about, which are the ones already fixed.

## Preconditions

Run these yourself first. A gate over a red build wastes three agents.

```
<build command>          # must pass
<test command>           # must pass, full suite, not a filtered subset
<lint + type check>      # must pass
git diff --stat          # know exactly what is in scope
```

Paste real output. Never describe a test run you did not perform.

## The three checks

Spawn all three in a single message so they run concurrently. Give each the diff
scope, the invariants from engineering-baseline.md, and the commands to run.

### QA correctness (qa-verifier)

Answers: does this do what it claims, and what input makes it fail?

- Acceptance criteria met, each one traced to a test
- Boundaries: empty, one, many, maximum, negative, zero, null, unicode, timezone
- Failure paths: dependency down, timeout, partial write, malformed input
- Concurrency: two writers, retry, duplicate delivery, out-of-order arrival
- Idempotency where the operation has side effects
- Regression risk in code paths the diff touches indirectly
- Test quality: does a test fail when the behavior is broken? Verify by breaking it.

### Security audit (security-auditor)

Answers: what can an attacker do that the author did not intend?

- Authentication and authorization on every new path, including the object level
- Input validation and output encoding: injection, SSRF, path traversal, deserialization
- Secrets: hardcoded, logged, in fixtures, in error messages, in URLs
- Data exposure: PII in logs, over-broad API responses, error messages that leak internals
- Crypto: no homemade schemes, no fixed IV, no MD5 or SHA1 for security, no math/random
- Dependencies: known CVEs, unpinned versions, install scripts
- Multi-tenancy: every query scoped to the tenant, no cross-tenant read
- Rate limits and resource bounds on anything reachable from outside

### Performance audit (performance-auditor)

Answers: what happens at 100x the current load?

- Complexity of every new loop, query, and recursion, stated with the expected N
- N+1 queries, missing indexes, full table scans, SELECT * on wide tables
- Allocations in hot paths, copies of large structures, unbounded buffers
- Blocking calls on request paths, serial calls that could be concurrent
- Connection pool, goroutine, thread, and queue bounds
- Cache correctness: invalidation, stampede, TTL under a cold start
- Payload size, N round trips, chattiness across a network boundary
- A measurement for any performance claim: before and after, same conditions

## Resolving findings

Every finding gets verified by you against the code before it is acted on. Agents
report false positives, and fixing a false positive adds a defect.

| Severity | Rule |
|---|---|
| Critical | Data loss, money loss, auth bypass, corruption. Fix before the gate can pass. |
| High | Wrong behavior on a real input, or a performance cliff under expected load. Fix now. |
| Medium | Edge case, missing test, avoidable cost. Fix now, or record the reason and the ticket. |
| Low | Style, naming, minor cleanup. Fix if the diff is already open. |

The gate passes when zero critical and zero high findings remain open.

## Report

```
GATE: pass | fail
Build: pass    Tests: 214 passed, 0 failed    Lint: clean

QA          - <n> findings: <n> fixed, <n> deferred, <n> rejected
Security    - <n> findings: ...
Performance - <n> findings: ...

Deferred: <finding> - <reason> - <ticket>
Rejected: <finding> - <why it is false>
```

For tier 0 changes, review-panel.md runs after this gate, with the gate reports as
input. The panel decides whether the fixes were the right fixes.
