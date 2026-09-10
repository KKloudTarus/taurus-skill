> Load when: Run any review, technology choice, architecture decision, or "which approach" question through 2 to 3 independent agents, then synthesize their reports without trusting any of them. Load whenever the task involves reviewing code or a design, comparing options, picking a library or datastore, resolving a disagreement, or deciding anything whose cost of being wrong is more than an hour of work.

# Review panel

One agent's opinion is one sample. Panels exist because a single reviewer, human or
model, misses defects at a rate that stays invisible until production. Independence
is what produces coverage: agents that see the same framing return the same blind spot.

## When to convene a panel

Mandatory:

- Any code review of a tier 0 change (payment, inventory, auth, permissions,
  migrations, concurrency, money math).
- Any architecture or system design decision.
- Choosing a datastore, queue, framework, or library that will be hard to replace.
- Any decision the user asked you to "review", "compare", "evaluate", or "decide".
- Any time two sources of guidance conflict.

Skip the panel for mechanical work with a single correct answer: renaming a symbol,
fixing a typo, applying a linter fix.

## Protocol

### Step 1. Freeze the question

Write the question in one sentence with a decidable outcome. Write the decision
criteria and their weights before seeing any answer, so the criteria cannot be bent
to fit a result you liked.

```
Question: Should seat holds expire via a Postgres partial index sweep or a Redis TTL keyspace notification?
Criteria: correctness under partition (40), operational load (25), p99 latency at 5k holds/s (20), rollback cost (15)
Constraints: Postgres 15, single region, existing Redis is cache-only
```

### Step 2. Brief the panel

Spawn 2 agents for a tier 1 decision, 3 for tier 0 or anything irreversible. Give
each the same facts and a different mandate. Send them in a single message so they
run concurrently.

Never tell a panelist what the other panelists think, what you think, or which
option you drafted. Frame the options neutrally: option A and option B, never
"my approach" and "the alternative".

Standard mandates for a code review:

| Panelist | Agent | Mandate |
|---|---|---|
| 1 | architecture-critic | Boundaries, dependency direction, coupling, whether this belongs here at all |
| 2 | qa-verifier | Correctness, edge cases, failure paths, test adequacy |
| 3 | security-auditor or performance-auditor | Whichever risk the change touches |

Standard mandates for a design or technology decision:

| Panelist | Mandate |
|---|---|
| 1 | Argue for option A. Find its strongest support and its cheapest failure mode |
| 2 | Argue for option B on the same terms |
| 3 | Attack both. Find the failure mode neither advocate would raise, and the option nobody proposed |

Every panelist returns the same shape:

```
VERDICT: <one line>
CONFIDENCE: high | medium | low
FINDINGS: each with file:line or a concrete scenario, severity, and why it is wrong
EVIDENCE: what was actually read, run, or measured
UNKNOWNS: what could not be checked, and what would settle it
```

A finding with no file reference, no reproducible scenario, and no measurement is
an opinion. Mark it as such.

### Step 3. Synthesize without deference

Read every report against the code, not against the other reports. Agreement
between two agents is not evidence: agents that share a prior share its errors.

For each finding, do the work yourself:

1. Open the file and the line. Does the claim hold?
2. Can it be reproduced, measured, or shown by a test?
3. Would the fix break an invariant from step 1?

Then classify:

| Class | Meaning | Action |
|---|---|---|
| Confirmed | Verified against the code or a run | Fix now, or list with a reason for deferring |
| Plausible | Consistent with the code, not yet reproduced | Write the test that decides it |
| Rejected | Verified false | Say why in one line |

Resolve conflicts by evidence, never by vote count and never by which agent sounded
more certain. Two agents against one is worthless when the one is the only one that
opened the file.

When the panel splits on a decision with no evidence to break the tie, run the
smallest experiment that produces evidence: a benchmark, a spike, a failing test.
Guessing at that point is where systems get built wrong.

### Step 4. Report

```
DECISION: <what, in one sentence>
BASIS: <the evidence that decided it, with numbers or file references>
CONFIRMED FINDINGS: n, all fixed | listed
REJECTED: <claim> - <why it is false>
UNRESOLVED: <what stays open, and what would settle it>
DISSENT: <a panelist position worth recording, and why it lost>
```

Record dissent even when you overrule it. The reason it lost is what a future reader
needs when the decision is revisited.

## Failure modes to avoid

- Spawning three agents with the same prompt. That is one opinion sampled three times.
- Accepting a finding because it sounds authoritative. Open the file.
- Dropping a finding because two agents did not mention it. One reader may be the
  only one who looked.
- Reporting the panel's output as your answer. The synthesis is your answer, and
  you own it.
- Letting a panel replace running the tests. Agents predict, tests decide.
