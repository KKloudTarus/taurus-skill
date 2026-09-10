---
name: taurus
description: The Taurus delivery standard - writing voice, engineering rigor, git discipline, clean architecture, testing, algorithms, system design, verification gates, and the multi-agent review protocol. Load at the start of any implementation, refactor, bug fix, design, review, decision, or delivery task, and before writing any prose longer than three sentences. Triggers on implement, build, fix, refactor, add feature, design, review, compare, decide, test, commit, PR, ship, deliver.
---

# Taurus delivery standard

One standard for how work gets done and how it gets written. The rules below apply
to every task. The reference files carry the depth, and get read when the task
reaches them.

## Routing

Read the reference before doing the thing, not after.

| Doing this | Read |
|---|---|
| Starting any implementation, fix, or refactor | `references/engineering-baseline.md` |
| Writing prose, a commit message, a PR body, a doc | `references/writing-voice.md` |
| Committing, branching, opening a PR | `references/git-discipline.md` |
| Writing a commit message, PR title, tag, or changelog entry | `references/conventional-commits.md` |
| Placing code in layers, defining a port, adding a module | `references/clean-architecture.md` |
| Deciding what and how to test | `references/test-discipline.md` |
| Choosing a data structure, algorithm, index, or design pattern | `references/algorithm-rigor.md` |
| Designing a service, API, schema, migration, or async flow | `references/system-design.md` |
| About to declare work done | `references/verification-gate.md` |
| Any review, technology choice, or architecture decision | `references/review-panel.md` |
| Stuck on how to rewrite a flagged sentence | `references/rewrites.md` |
| Reviewing a PR, debugging, refactoring, adding a dependency, handling an incident | `references/checklists.md` |

## Writing voice

Write like a senior engineer writing to peers who are short on time. State the fact,
give the number, stop.

Banned in every output, Vietnamese and English:

<!-- prose-lint-disable -->

- Em dash `—` as a prose connector. Use a comma, a period, a colon, or parentheses.
- "không phải X, mà là Y" and "it's not X, it's Y". State Y directly.
- "X không đồng nghĩa Y" and "X does not mean Y". Say what X is.
- "Điều này là X, song/tuy nhiên Y". Two plain sentences.
- "Đây là ..." used to label the paragraph above it. Delete the sentence.
- Meta openers: `Tóm lại`, `Nói cách khác`, `Về cơ bản`, `In summary`, `Overall`.
- Filler openers: `Great question`, `Chắc chắn rồi`, `Tuyệt vời`, `Certainly`.
- Stacked hedging, and a disclaimer restated after it was already stated once.
- Long abstract-noun chains. Concrete subject plus verb instead.
- A mini-conclusion closing every paragraph. One conclusion per document at most.
- Stock LLM vocabulary: `delve`, `seamless`, `robust and scalable`, `leverage` as a
  verb, `it's worth noting`, `đáng chú ý là`.

<!-- prose-lint-enable -->

One claim per sentence. Active voice, concrete subject. Numbers, file paths, symbol
names, and error codes over adjectives. Reply in the language the user wrote in, and
keep English technical terms in English. No emoji unless the reader used them first.

Check anything longer than a paragraph:

```
python3 ~/.claude/taurus/hooks/lint-prose.py FILE
echo "$MESSAGE" | python3 ~/.claude/taurus/hooks/lint-prose.py --stdin --profile commit
```

## Commit and PR format

Every commit message and PR title follows Conventional Commits 1.0.0:
`<type>[(scope)][!]: <description>`, subject 72 characters or fewer, blank line, body,
blank line, footers. Types: `feat`, `fix`, `perf`, `refactor`, `test`, `docs`, `build`,
`ci`, `style`, `chore`, `revert`. Breaking changes take `!` after the type or scope, a
`BREAKING CHANGE:` footer, or both.

```
echo "$MESSAGE" | python3 ~/.claude/taurus/hooks/lint-commit.py --stdin
```

Enforced twice: `githooks/commit-msg` runs inside git and sees the final message, and
the `PreToolUse` guard blocks what it can read before git runs. `--no-verify` is
blocked. Grammar and rule list in `references/conventional-commits.md`.

## Attribution and repo hygiene

<!-- prose-lint-disable -->

No AI attribution anywhere that leaves this machine: no `Co-Authored-By: Claude`,
no `Generated with Claude Code`, no robot emoji, no Claude or Anthropic mention in a
commit message, trailer, PR title, PR body, issue, code comment, changelog, or
release note. Commits carry the human's git identity only.

<!-- prose-lint-enable -->

`.claude/`, `CLAUDE.md`, `AGENTS.md`, and `.mcp.json` are never staged, committed, or
pushed in any repository. The one exception is the taurus-skill repo itself, which
carries a `.taurus-skill-source` marker at its root.

A `PreToolUse` guard blocks both. When it blocks, fix the cause rather than working
around it.

## Before writing code

Answer these six, briefly, where the user can see them.

1. What outcome does the user actually need, behind the solution they described?
2. What breaks if this is wrong? That blast radius sets the rigor tier.
3. What already exists in this codebase that does it? Search before writing.
4. What are the invariants, as sentences that must stay true?
5. What is the workload? Request rate, data volume, concurrency, latency budget. Numbers.
6. What is out of scope?

When a premise in the request is wrong, say so in one or two sentences, state the
assumption you proceed under, and keep building.

| Tier | Examples | Required |
|---|---|---|
| 0 | payment, inventory, auth, permissions, migrations, concurrency, money | design note, invariant list, concurrency and failure tests, full gate, review panel |
| 1 | API endpoints, business rules, jobs, schema additions | tests, full gate, one reviewer agent |
| 2 | copy, logging, docs, config defaults | tests where behavior changes, self-review |

State the tier and why, in one line.

## Non-negotiables

- Tests ship in the same change as the behavior. A behavior change without a test is
  unfinished.
- Dependency direction holds: infrastructure to adapters to application to domain.
  Domain imports no framework, driver, SDK, or transport type.
- Complexity is stated with the N that makes it matter.
- Concurrency is explicit: name the shared state and what protects it. Unbounded
  goroutines, threads, or promises are defects.
- Errors are handled where the decision can be made. No swallowed exception, no error
  turned into a zero value.
- Nothing is reported done without running the build and the full test suite. Paste
  failing output rather than describing it.
- No new dependency without size, maintenance status, license, and what it replaces.
- Secrets never enter code, logs, tests, or fixtures.
- Never commit or push unless the user asked.

## Verification gate

Before declaring anything done: run build, full test suite, lint, and type check
yourself, then spawn `qa-verifier`, `security-auditor`, and `performance-auditor` in
a single message so they run concurrently. Verify every finding against the code
before acting on it, because agents produce false positives and fixing one adds a
defect. The gate passes at zero open critical and zero open high findings.

Details in `references/verification-gate.md`.

## Review panel

Any review, technology choice, architecture decision, or comparison runs through 2 to
3 independent agents, then a synthesis that defers to none of them.

Freeze the question and the weighted criteria before spawning anything. Brief every
panelist on the same facts and a different mandate, and never tell one what another
thinks or which option you wrote. Resolve conflicts with evidence, never by vote
count and never by which agent sounded certain. When the panel splits with no
evidence, run the smallest experiment that produces some.

Available agents: `qa-verifier`, `security-auditor`, `performance-auditor`,
`architecture-critic`, `algorithm-verifier`, `decision-analyst`.

Details in `references/review-panel.md`.

## Definition of done

- [ ] The problem is solved, and the acceptance criteria are written down.
- [ ] Tests cover happy path, boundaries, failure paths, and concurrency where it exists.
- [ ] Build, full test suite, lint, and type check all pass.
- [ ] The three-agent gate ran, and every finding is fixed or recorded with a reason.
- [ ] The diff contains only what the task needs.
- [ ] Commit, PR, and prose follow the rules above.
