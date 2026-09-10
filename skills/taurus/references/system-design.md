> Load when: Designing services, APIs, schemas, and asynchronous flows so they stay correct under failure and load. Load when adding a service or module boundary, designing an API or event contract, planning a schema or migration, introducing a queue, cache, or retry, or answering a system design question. Pair with review-panel for the decision itself.

# System design

## Start from failure and load

Before drawing boxes, write down:

- **Workload**: requests per second at peak and at p99 burst, payload sizes, data
  volume today and in a year, read to write ratio.
- **Latency budget**: end to end, then split across hops. A 200ms budget with five
  serial hops leaves 40ms each.
- **Consistency requirement**: per operation. Which reads tolerate staleness, and
  for how long.
- **Failure tolerance**: what must survive a pod restart, an availability zone
  outage, a slow dependency, a poison message.
- **Correctness invariants**: the sentences that must never be false, in domain terms.

Capacity comes from a benchmark of the real workload. An assumed RPS number is a
guess wearing a unit.

## Boundaries

Services follow business capabilities, never entities. A service that owns one table
is a distributed function call with extra latency and a new failure mode.

- One writer per piece of data. Ownership is exclusive.
- No shared database across services. Cross-service reads go through an API or a
  replicated read model built from events.
- Dependency direction is acyclic. A cycle between services means the boundary is
  in the wrong place.
- Prefer a modular monolith until team structure or scaling pressure forces a split.
  Module boundaries with enforced imports give most of the benefit at a fraction of
  the operational cost.

## Data

- The relational store is the default. Add a specialized store only after a
  measurement shows the relational one cannot do the job.
- Model the invariant into the schema: unique constraints, foreign keys, check
  constraints, exclusion constraints. A constraint the database enforces cannot be
  bypassed by a new code path.
- Transaction boundaries stay inside one service and never span a network call to
  another service.
- Migrations are expand, migrate, contract: add nullable, backfill in batches,
  switch reads, then drop. Every migration is reversible or has a documented forward
  fix. Never a blocking ALTER on a large table on a live path.
- Money is an integer in minor units plus an ISO currency code. Timestamps are UTC
  with an explicit type. Identifiers are opaque strings to clients.

## Asynchronous work

- At-least-once delivery is the default assumption. Every consumer is idempotent,
  keyed on a business identifier or an event id, with the dedup record written in
  the same transaction as the effect.
- Publishing an event and committing a database write happen atomically through a
  transactional outbox. A publish after commit loses events on a crash.
- Ordering is per key, through the partition key. Global ordering is not available,
  so design so it is not needed.
- Every consumer has a retry policy with exponential backoff and jitter, a maximum
  attempt count, and a dead letter queue with an owner and a runbook.
- Long-running multi-step operations are a state machine with persisted state and
  explicit transitions. A chain of synchronous HTTP calls loses its state on the
  first timeout.
- Compensation, not two-phase commit. Each step has an inverse.

## Resilience

- Timeouts on every outbound call, sized per dependency. One global timeout is
  wrong for all of them.
- Retries only on idempotent operations, with backoff, jitter, and a budget. A retry
  on a non-idempotent write is a duplicate charge.
- Circuit breaker per dependency. Bulkhead so one slow dependency cannot exhaust the
  pool the rest of the system shares.
- Backpressure over buffering. A queue that grows without bound converts a spike
  into an outage plus data loss.
- Every degraded mode is designed on purpose: what the system serves when the cache
  is cold, the search index is stale, or a dependency is down.
- Load shedding at the edge, before traffic reaches the transactional core.

## API contracts

- Versioned path or media type. Additive changes only within a version.
- Breaking changes: removing or renaming a field, changing a type, changing enum
  semantics, making an optional field required, changing an error code for the same
  condition, changing idempotency or auth semantics. Each needs a deprecation plan.
- Errors carry a stable machine-readable code, a correlation id, and an explicit
  retryable flag. Clients branch on the code. HTTP status is transport only.
- Raw upstream, database, or vendor errors are never passed through.
- Mutations with side effects require an idempotency key, and the authoritative
  service persists the idempotency state. A cache at the edge is an optimization,
  never the source of truth.
- Cursor pagination with a bounded page size.

## Caching

- Cache is never the source of truth for anything that must be correct.
- Every cache entry has an owner, a TTL, and a documented invalidation path.
- Stampede protection on hot keys: single flight, or a jittered TTL.
- Read-through with an explicit stale window beats an ad hoc write-side invalidation
  scattered across the codebase.

## Observability

- Structured logs with a correlation id on every request. No tokens, no PII, no
  payment payloads.
- RED metrics per endpoint and per dependency: rate, errors, duration at p50, p95, p99.
- Business metrics for the invariants: holds created, holds expired, double-sell
  attempts blocked. A correctness bug shows up in a business metric before it shows
  up in a support ticket.
- Traces across service boundaries with the context propagated.
- Alerts fire on symptoms the user feels, and each one links a runbook.

## Design note format

Ten to thirty lines, in the PR or in docs/adr/.

```
Problem      what breaks today, with evidence
Constraints  workload numbers, latency budget, existing systems
Invariants   sentences that must stay true
Approach     the design, in five sentences
Rejected     option B, why it lost. option C, why it lost
Failure      what happens when each dependency fails
Rollout      flag, migration order, rollback steps
Open         what is unresolved, and what would settle it
```

Run the decision through review-panel.md before implementing it.
