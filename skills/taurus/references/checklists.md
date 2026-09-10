> Load when: reviewing someone else's code, debugging, refactoring, adding a dependency, reviewing a migration, or handling an incident.

# Checklists

Load when running one of these specific activities.

## Reviewing someone else's code

Read the PR description first, then the tests, then the implementation. Tests read
before implementation tell you what the author believed the behavior should be.

- Does the change do what the description claims, and only that?
- Is there a test that fails if the behavior breaks? Check one by reading the assertion.
- What input makes this wrong? Empty, maximum, concurrent, retried, malformed.
- What happens when each dependency it calls is slow, down, or returns garbage?
- Does the dependency direction hold? Does business logic sit in an adapter?
- Is any error swallowed, converted to a zero value, or logged and ignored?
- Are new resources (connections, goroutines, subscriptions, timers) bounded and closed?
- Is anything logged that should not be: tokens, PII, payment payloads, full request bodies?
- Does a new query have an index, and did anyone read the plan?
- Would a new engineer understand why this code exists in six months?

Comment with the file, the line, the scenario, and the fix. A comment without a
scenario is an opinion.

## Debugging

- Reproduce it first. A fix for a bug you cannot reproduce is a guess.
- Write the failing test from the reproduction before touching the code.
- Read the actual error and the actual stack. Do not pattern match on the symptom.
- Bisect: git history, input size, feature flag, or the code path itself.
- Form one hypothesis, name the observation that would falsify it, then check.
- When the fix works, explain why it works. A fix you cannot explain is a coincidence.
- Ask what else has the same shape. One off-by-one usually has siblings.
- The regression test stays in the suite with the bug reference.

## Refactoring

- Green tests before you start. No refactor on a red suite.
- Behavior does not change. If behavior changes, it is a feature, and it needs its
  own commit and its own tests.
- One transformation at a time, tests green between each.
- Characterization tests first when the code has no tests and you do not fully
  understand it.
- The refactor commit and the behavior commit stay separate, so a revert is surgical.
- Stop when the code is clear enough for the next change. Refactoring has no
  natural end point, so pick one.

## Adding a dependency

- What exactly does it replace, and how many lines would that be to write?
- Last release date, open issue count, maintainer count, license.
- Transitive dependency count. Install scripts. Known CVEs.
- Bundle or binary size impact.
- What is the exit cost if it is abandoned in two years?
- Pin the exact version. Record the answers in the PR.

## Reviewing a migration

- Is it reversible? If not, what is the forward fix?
- Does it lock a large table on a live path? ALTER TABLE ... ADD COLUMN with a
  default, index creation without CONCURRENTLY, and type changes all block.
- Expand, migrate, contract: does old code still work against the new schema, and
  new code against the old one, during the deploy window?
- Is the backfill batched, resumable, and throttled?
- Was it tested against a copy with production-scale data?
- Does the rollback plan cover data written after the migration ran?

## Handling an incident

- Stop the bleeding first. Roll back, flip the flag, shed load. Diagnose after.
- Record the timeline as it happens: what was observed, what was changed, when.
- One person changes things at a time, and says what they are changing.
- Preserve evidence before restarting anything: logs, heap, queue depth, plan.
- Write the postmortem on mechanism and missing guardrail, never on the person.
- The action items are code and alerts, not "be more careful".
