> Load when: Branching, commit, and pull request rules for every repository. Load before any git operation that writes: staging, committing, amending, rebasing, tagging, pushing, or opening a PR. Enforces no AI attribution, no local Claude config in any repo, atomic commits, Conventional Commits, and the PR template.

# Git discipline

## Hard rules

<!-- prose-lint-disable -->

**No AI attribution.** No Co-Authored-By: Claude, no Generated with Claude Code,
no 🤖, no Claude/Anthropic mention in a commit message, trailer, PR title, PR
body, issue, code comment, changelog, or release note. Commits carry the human's
configured git identity only. If tooling inserts such a line, delete it before
committing.

<!-- prose-lint-enable -->

**Local agent config never leaves the machine.** .claude/, CLAUDE.md,
AGENTS.md, and .mcp.json are never staged, committed, or pushed. `githooks/pre-commit`
refuses the staged tree and `githooks/pre-push` refuses the pushed range, history
included, since removing a file in a later commit leaves the blob behind. Both chain
to the repository's own hook of the same name. The single
exception is the taurus-skill repo itself, which carries a .taurus-skill-source
marker at its root.

Before the first commit in an unfamiliar repo:

```bash
grep -qE '^\.claude/?$' .gitignore || echo "check .gitignore"
git ls-files | grep -E '(^|/)(CLAUDE\.md|AGENTS\.md|\.mcp\.json|\.claude/)'
```

If those paths are already tracked, fix it in its own commit:

```bash
git rm -r --cached .claude CLAUDE.md AGENTS.md .mcp.json 2>/dev/null
printf '.claude/\nCLAUDE.md\nAGENTS.md\n.mcp.json\n' >> .gitignore
git add .gitignore && git commit -m "chore: stop tracking local agent config"
```

A PreToolUse guard blocks violations of both rules. When it blocks, fix the cause.
Never work around it.

**Never commit or push unless the user asked.** Running tests, reading, and editing
need no permission. Writing to history does.

**Never force-push a shared branch.** --force-with-lease on your own feature
branch only, and say so first.

## Branching

Branch off the repo's default branch. Never commit directly to main, master, or
production.

```
<type>/<short-kebab-summary>       feat/seat-hold-expiry
<type>/<ticket>-<summary>          fix/PLAT-812-duplicate-webhook
```

The branch type is one of the commit types in `conventional-commits.md`.

One branch, one purpose. When the work grows a second purpose, open a second branch.

## Commits

Conventional Commits 1.0.0 governs the message. `conventional-commits.md` carries the
full grammar: allowed types, scope rules, both breaking-change forms, footer tokens,
and the validator. Read it before the first commit in a repo.

```
feat(inventory): hold seats under a row-level lock

Redis held the seat state, so two checkouts on different pods could both
win the same seat. The hold now writes to inventory.seat_hold inside the
same transaction that checks availability.

Verified with a 200-goroutine contention test: 1 winner, 199 SEAT_UNAVAILABLE.

Refs: PLAT-812
```

The shape: `<type>[(scope)][!]: <description>`, subject 72 characters or fewer, imperative,
no trailing period, blank line, body, blank line, footers. Breaking changes take `!`
after the type or scope, a `BREAKING CHANGE:` footer, or both.

The guard runs `hooks/lint-commit.py` on every `git commit` and blocks a message that
breaks the grammar. Check a message before running the command:

```bash
python3 ~/.claude/taurus/hooks/lint-commit.py --stdin <<'EOF'
feat(inventory): hold seats under a row-level lock
EOF
```

Two layers enforce this. `githooks/commit-msg` runs inside git and sees the final
message, so nothing routes around it; `install.sh` wires it into every repo through
`core.hooksPath`. The `PreToolUse` guard is the fast layer in front, and it fails
closed: a command it cannot read gets blocked, not waved through. Two spellings always
work: one `-m` per paragraph, or a message file written in its own command and passed
with `-F <file>`. `conventional-commits.md` lists the refused forms.

`--no-verify` is blocked. It exists to skip the layer that actually holds.

Each commit compiles and passes tests on its own. Split by intent, never by file:
a refactor commit changes no behavior, and the behavior change lands separately.
Format-only churn goes in its own commit so the real diff stays readable.

Body answers why. The diff already says what.

Never stage with a bare `git add .` in a repo you have not just inspected. Run
`git status --porcelain` first, stage explicit paths, then read `git diff --cached`
before committing.

## Pull requests

The title follows the same grammar as the lead commit, since a squash merge turns it
into the commit subject.

```bash
python3 ~/.claude/taurus/hooks/lint-commit.py --stdin --pr-title <<< "$PR_TITLE"
```

```markdown
## Problem
What was broken or missing, with the evidence: error, metric, ticket.

## Approach
What the change does, in three to six sentences.

## Alternatives rejected
- Option B: rejected because <reason>.
- Option C: rejected because <reason>.

## Risk and rollback
Blast radius, feature flag, migration reversibility, rollback steps.

## Verification
- Tests added: <names>
- Full suite: pass
- QA / security / performance gate: <result>
- Benchmark, when performance is claimed: before -> after
```

A PR carrying a breaking change says so in the title with `!` and repeats the
`BREAKING CHANGE:` footer text under Risk and rollback.

No AI mention anywhere in it. Prose follows `writing-voice.md`.

Draft PRs for work in progress. Ready for review only after `verification-gate.md`
passes.

## Before every commit

- [ ] `git status --porcelain` reviewed, nothing unexpected staged
- [ ] `git diff --cached` read line by line
- [ ] No secrets, tokens, .env, keys, or dumps in the diff
- [ ] No .claude/, CLAUDE.md, AGENTS.md, .mcp.json
- [ ] No debug prints, commented-out code, or stray TODOs
- [ ] Build and tests pass on this exact tree
- [ ] Subject and footers pass `lint-commit.py`, prose passes `lint-prose.py`
