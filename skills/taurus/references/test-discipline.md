> Load when: What to test, how to write tests that catch real defects, and what makes a test suite worth keeping. Load before writing tests, when a change adds or modifies behavior, when a test is flaky or slow, or when deciding whether coverage is adequate. Every behavior change ships with tests in the same change.

# Test discipline

## The rule

A behavior change without a test is unfinished work. No exception for "small",
"obvious", "urgent", or "temporary".

Coverage percentage is a weak signal. The real question: if the behavior broke,
would a test fail? Verify it by breaking the behavior on purpose and watching the
test go red. A test that stays green when you delete the line it covers is dead weight.

## What to test, in order

1. **The invariant.** The sentence that must stay true. Test it directly, and test
   the concurrent and failure paths that could violate it.
2. **The boundaries.** Empty, one, many, maximum, over maximum, zero, negative,
   null, missing field, unicode, very long string, timezone boundary, leap day,
   currency rounding.
3. **The failure paths.** Dependency down, timeout, connection reset, partial write,
   malformed response, duplicate delivery, out-of-order arrival, retry storm.
4. **The happy path.** Last, because it is the one the implementation was written for.

## Shape

Arrange, act, assert. One behavior per test. The test name states the behavior and
the expected outcome.

```go
func TestHoldSeats_ConcurrentHoldsOnSameSeat_OnlyOneWins(t *testing.T)
func TestQuote_PriceExpired_ReturnsPriceQuoteExpired(t *testing.T)
```

Table-driven for input variation, one case per row, each row named. Assert on
behavior and observable output, never on internal call sequences. A test that
asserts "the repository was called with these arguments" breaks on every refactor
and catches no defect.

Tests are deterministic. No wall-clock time.Now() in an assertion, no random
without a fixed seed, no dependence on test execution order, no sleeps. Inject a
clock. Sleep-based tests are flaky by construction and get rewritten, never retried.

## Doubles

- Fake what you own: an in-memory implementation of your own port.
- Never mock a third-party type. Wrap it in your own port and fake the port.
- Prefer a real dependency in a container over a mock for outbound adapters.
  Testcontainers, a real Postgres, a real Redis. Mocks of a database encode your
  assumption about the database, which is the thing most likely to be wrong.
- No mock verification of internal calls. Assert on state and output.

## Layers

| Layer | What it proves | Speed |
|---|---|---|
| Unit (domain, application) | The rules are right | milliseconds, the bulk of the suite |
| Integration (outbound adapters) | The SQL, the serialization, the driver behave | seconds, one per adapter |
| Contract (inbound adapters, external APIs) | The wire shape has not drifted | seconds |
| End to end | The wiring holds on the critical paths | minutes, a handful only |
| Property, for algorithms and parsers | Invariants hold on generated input | as needed |
| Concurrency, for shared state | No lost update, no double sell | required for tier 0 |
| Load, for performance claims | The number in the PR is real | required when performance is claimed |

## Correctness-critical extras

For payment, inventory, auth, migrations, and money math:

- A concurrency test that runs N real concurrent operations and asserts the
  invariant. go test -race, or the language equivalent.
- An idempotency test: same key twice, one side effect.
- A crash-recovery test: kill between write and acknowledge, assert no double effect.
- A migration test: forward, backward, and forward again on a populated database.
- Money in minor units, integers only. A test that asserts a float never appears.

## Bug fixes

Write the failing test first, from the bug report. Watch it fail for the reported
reason. Fix. Watch it pass. The test stays in the suite with a reference to the bug.
A fix without a regression test invites the same bug back.

## Suite health

- The full suite runs in CI on every push and passes. A red suite gets fixed or
  reverted the same day.
- No skipped tests without an owner and a ticket in the skip reason.
- A flaky test is a defect in the test or in the code. Delete it or fix it. Retries
  hide real race conditions.
- Test code follows the same standards as production code: no duplication that
  hides intent, helpers named for what they set up, fixtures small and readable.
- Slow tests get a tag so the fast path stays fast.
