> Load when: Choosing and justifying algorithms, data structures, indexes, and design patterns against the actual workload. Load when writing a loop over data that grows, picking a data structure, adding a query or index, implementing anything with a complexity worth stating, or reaching for a design pattern. Requires stated complexity, stated N, and a measurement for any performance claim.

# Algorithm rigor

## The requirement

Every algorithmic choice comes with three things written down:

1. **N** - the actual size, today and at the growth horizon. orders per customer: 50 today, 5k at the p99 tenant.
2. **Complexity** - time and space, worst case and expected. O(n log n) time, O(n) space.
3. **Why this one** - the alternative considered and the reason it lost.

One line in a comment or the PR body. Without N, complexity is decoration: an
O(n²) pass over 20 items is correct, and an O(n log n) pass over 50 million with a
per-element allocation is a production incident.

## Choosing

Start from access patterns, not from familiarity.

| Access pattern | Structure |
|---|---|
| Membership, dedup | hash set, O(1) expected |
| Key lookup, unordered | hash map |
| Ordered iteration, range query, predecessor | sorted structure, B-tree, skip list |
| Top-k, scheduling, expiry | heap, O(log n) push and pop |
| FIFO, work queue | ring buffer, deque |
| Prefix match, autocomplete | trie |
| Membership with a false-positive budget | Bloom or cuckoo filter |
| Connected groups, merging | union-find |
| Interval overlap | interval tree, or sort plus sweep |

Common corrections:

- Nested loop over two collections. Build a map from one, then one pass. O(n·m) to O(n+m).
- Sort inside a loop. Sort once outside it.
- Linear scan for membership in a hot path. Set.
- Repeated recomputation of a pure function. Memoize, and bound the cache.
- Loading a whole table to filter in application code. Filter in the query, with an index.
- String concatenation in a loop. Builder, or preallocate.
- Reading a file or a response fully into memory when a stream works.

## Databases

The query plan is the algorithm. Read it.

- EXPLAIN ANALYZE every new query that runs on a request path, and paste the plan
  in the PR when the change is performance-relevant.
- A sequential scan on a table that grows is a defect. Add the index, and state its
  selectivity.
- Composite index column order follows the query: equality columns first, then
  range, then sort.
- An index that duplicates a prefix of another index gets dropped.
- N+1 is a defect, not an optimization opportunity. Batch, join, or use a dataloader.
- Pagination is keyset based on an indexed column. OFFSET 100000 scans 100000 rows.
- Every unbounded query gets a LIMIT and a documented maximum.
- Write amplification counts: each index slows every insert and update.

## Concurrency

- Name the shared state. Name what protects it: a lock, a channel, a transaction, or
  single ownership.
- Prefer no sharing. Partition by key, then no lock is needed.
- Lock ordering is documented and consistent, or deadlock is a matter of time.
- Hold locks for the shortest possible span, and never across a network call.
- Optimistic concurrency (version column, compare-and-swap) for low contention.
  Pessimistic row locks for high contention on a hot row.
- Every goroutine, thread, task, and channel is bounded. Unbounded concurrency
  turns a traffic spike into an outage.
- Any change to shared state ships with a test under -race or the equivalent.

## Correctness before speed

For a non-obvious algorithm, state the invariant that holds at every iteration and
the reason it terminates. Prove the boundaries: empty input, one element, all
duplicates, maximum size, overflow.

Watch the classics: integer overflow in (lo + hi) / 2, off-by-one at the last
element, floating point for money, unstable sort where stability was assumed,
mutation of a collection during iteration, and time zones or DST in date math.

## Design patterns

A pattern is used when the problem it solves is present. Applying one because it is
familiar adds indirection without buying anything.

| Problem | Pattern |
|---|---|
| One algorithm varies by case, chosen at runtime | strategy |
| Creating an object needs rules or validation | factory, builder |
| Steps are fixed, the details vary | template method |
| Cross-cutting behavior around a call | decorator, middleware |
| Something must react to a state change | observer, domain event |
| The external API shape mismatches the domain | adapter, anti-corruption layer |
| A multi-step operation spanning services must be undoable | saga with compensation |
| Reads and writes have different shapes and loads | CQRS, applied selectively |

Avoid: a singleton where a parameter works, a factory that only ever builds one
type, an abstract base class with one implementation, an event bus that hides
control flow, and inheritance where composition is simpler.

Two occurrences are a coincidence. Abstract on the third, when the axis of variation
is known. A wrong abstraction costs more than the duplication it removed.

## Performance claims

Any claim that something is faster comes with a measurement: same input, same
machine, before and after, with the variance. Benchmark the workload, never a
synthetic loop. Profile before optimizing, because the bottleneck is somewhere
other than where it feels. Optimize the hot path only, and keep the readable
version in a comment or a test when the fast version is hard to follow.
