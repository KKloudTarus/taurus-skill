# Taurus delivery standard

A global Claude Code skill pack. Install once per machine, and every project on that
machine gets the same writing standard, engineering standard, verification gates,
and multi-agent review protocol.

## Install

```bash
git clone https://github.com/KKloudTarus/taurus-skill.git ~/src/taurus-skill
cd ~/src/taurus-skill
./install.sh
```

Start a new Claude Code session afterwards. Update with `git pull` in the clone;
the install uses symlinks, so no reinstall is needed.

```bash
./install.sh --dry-run        # show what would change
./install.sh --no-gitignore   # skip the global gitignore entries
./install.sh --uninstall      # remove everything the installer created
```

What it touches, all idempotently:

| Target | Change |
|---|---|
| `~/.claude/taurus` | symlink to this repo |
| `~/.claude/skills/taurus` | symlink to the one skill |
| `~/.claude/agents/*.md` | symlink per agent |
| `~/.claude/commands/*.md` | symlink per command |
| `~/.claude/settings.json` | adds one `PreToolUse` Bash hook, preserving existing hooks |
| `~/.claude/CLAUDE.md` | replaces the block between the `taurus:begin` and `taurus:end` markers |
| global gitignore | adds `.claude/`, `CLAUDE.md`, `AGENTS.md`, `.mcp.json` |
| global `core.hooksPath` | points at `githooks/`, skipped when it is already set elsewhere |
| | `githooks/` chains back to each repo's own `.git/hooks/<name>`, so nothing stops running |

Existing files are never overwritten. A path that already exists and is not a
symlink is skipped with a message. Reinstalling prunes symlinks into the repo that
no longer resolve, so a rename or a consolidation leaves nothing stale behind.

## Commands

| Command | Does |
|---|---|
| `/deliver <task>` | Full pipeline: interrogate, design, test, implement, verify, review |
| `/verify [scope]` | Three-agent gate: QA, security, performance, in parallel |
| `/panel <question>` | 2 to 3 independent agents on a decision, then an unbiased synthesis |
| `/ship [subject]` | Pre-commit audit, atomic commits, PR body |
| `/style [files]` | Lint prose against the writing standard and rewrite the findings |

## The skill

One skill, `taurus`, so the picker shows one entry. Its `SKILL.md` carries the rules
that apply to every task and routes to the reference that carries the depth.

| Reference | Covers |
|---|---|
| `engineering-baseline.md` | Interrogation questions, rigor tiers, work sequence, definition of done |
| `writing-voice.md` | The banned LLM constructions, the rewrite recipes, the linter |
| `git-discipline.md` | Branching, commits, PRs, no AI attribution, no local agent config in any repo |
| `conventional-commits.md` | The full Conventional Commits 1.0.0 grammar, allowed types, footers, breaking changes |
| `clean-architecture.md` | Layering, dependency direction, ports, per-language layouts |
| `test-discipline.md` | What to test, doubles, layers, correctness-critical extras |
| `algorithm-rigor.md` | Complexity against a stated N, query plans, concurrency, pattern selection |
| `system-design.md` | Boundaries, data, async, resilience, API contracts, caching, observability |
| `verification-gate.md` | The three checks that run before anything is called done |
| `review-panel.md` | The 2 to 3 agent protocol and the synthesis that trusts none of them |
| `rewrites.md` | Before and after examples for every banned construction |
| `checklists.md` | Reviewing a PR, debugging, refactoring, dependencies, migrations, incidents |

## Agents

All six are read-only. None can edit the code they review.

`qa-verifier` · `security-auditor` · `performance-auditor` · `architecture-critic` ·
`algorithm-verifier` · `decision-analyst`

Each returns a structured report with a verdict, a confidence level, findings
anchored to `file:line`, and its unknowns. The caller verifies every finding against
the code before acting on it.

## Enforcement

Three mechanisms run outside the model's judgment.

**Git guard** (`hooks/guard-git.py`, wired as a `PreToolUse` hook on Bash). Blocks:

- a commit message carrying AI attribution, a `Co-Authored-By` trailer, or a robot emoji
- a commit message that breaks the writing standard
- a commit message that breaks Conventional Commits 1.0.0
- staging, committing, or pushing `.claude/`, `CLAUDE.md`, `AGENTS.md`, `.mcp.json`
- a broad `git add` that would sweep any of those in

It fails closed. bash and git each parse a command line by their own rules, so where
the guard cannot read one with confidence it blocks and says why: a message on stdin,
command substitution, a nested shell, an unresolvable alias, a global flag it does not
know, or a message file that does not exist yet. Two spellings always work: one `-m`
per paragraph, or a message file written in its own command and passed with `-F`.

The guard is the fast layer, not the control of record. That is `githooks/`, wired
into every repo through `core.hooksPath`.

This repo carries a `.taurus-skill-source` marker, which exempts it from the path
rules so it can version its own configuration. The attribution rules apply everywhere.

**Prose linter** (`hooks/lint-prose.py`). Standalone, usable in CI and in a
pre-commit hook.

```bash
python3 hooks/lint-prose.py docs/*.md
python3 hooks/lint-prose.py --severity warn --format json README.md
echo "$MSG" | python3 hooks/lint-prose.py --stdin --profile commit
```

Exit 0 clean, 1 findings, 2 usage error. Suppress with
`<!-- prose-lint-disable -->` and `<!-- prose-lint-enable -->`, or
`prose-lint-disable-line` on a single line. Code fences, inline code, and URLs are
skipped automatically.

**Commit linter** (`hooks/lint-commit.py`). Validates a message against Conventional
Commits 1.0.0: type prefix, scope shape, subject length, the blank line before the
body, footer tokens, and both breaking-change forms.

```bash
python3 hooks/lint-commit.py .git/COMMIT_EDITMSG
echo "$MSG" | python3 hooks/lint-commit.py --stdin
python3 hooks/lint-commit.py --stdin --pr-title <<< "$PR_TITLE"
```

Same exit codes. Messages git generates itself are skipped: `Merge ...`, `Revert "..."`,
`fixup!`, `squash!`.

## Using it in a project's CI

```yaml
- run: python3 ~/.claude/taurus/hooks/lint-prose.py $(git diff --name-only origin/main -- '*.md')
- run: python3 ~/.claude/taurus/hooks/lint-commit.py --stdin --pr-title <<< "$PR_TITLE"
```

The installer already wires the same checks into every repo through
`core.hooksPath`, so nothing per-repo is needed.

## Tests

```bash
./run-tests.sh
```

Six suites: the prose linter, the commit linter, the git guard, the git hooks
against real repositories, the installer against an isolated config directory, and
the pack's own structure. The structure
suite lints every markdown file in the pack against the standard it ships, replays
every commit in this repo's history through the commit linter, and validates every
commit example the documentation prints, so the pack cannot violate its own rules.

## Layout

```
rules/always-on.md      merged into ~/.claude/CLAUDE.md, applies to every session
skills/taurus/SKILL.md  the one model-invoked skill, a router plus the core rules
skills/taurus/references/  the depth, read on demand, invisible to the picker
agents/<name>.md        specialist subagents
commands/<name>.md      slash commands
hooks/                  guard-git.py, lint-prose.py, lint-commit.py, shellscan.py
githooks/               commit-msg, pre-commit, pre-push, wired via core.hooksPath
tests/                  the six suites
install.sh              installer, updater, uninstaller
```
