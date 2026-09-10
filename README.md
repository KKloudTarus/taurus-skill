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
| `/deliver <task>` | Risk-tiered delivery from inspection through verification evidence |
| `/verify [scope]` | Tier-aware checks, reviewers, and a worktree-bound JSON report |
| `/panel <question>` | 2 to 3 independent agents on a decision, then an unbiased synthesis |
| `/ship [subject]` | Pre-commit audit, atomic commits, PR body |
| `/style [files]` | Review prose for natural voice and inspect linter signals |

## The skill

One skill, `taurus`, so the picker shows one entry. Its `SKILL.md` carries the rules
that apply to every task and routes to the reference that carries the depth.

Claude sees the skill name and description during selection. It loads the router only
when Taurus applies, then reads the engineering baseline and the smallest set of
references required by the actual risk. It does not preload the reference directory.
Engineering work reports that choice once:

```text
TAURUS ROUTE: tier=1; refs=engineering-baseline,infrastructure-delivery; review=agents
```

Review cost follows the same tier. Tier 0 uses the full panel, tier 1 uses the matched
reviewer and only necessary specialists, and tier 2 stays with focused checks and
self-review. An extra panel requires an explicit request, a hard-to-reverse decision,
or unresolved material evidence.

| Reference | Covers |
|---|---|
| `engineering-baseline.md` | Interrogation questions, rigor tiers, work sequence, definition of done |
| `writing-voice.md` | Natural technical voice, artifact-specific tone, and linter limits |
| `git-discipline.md` | Branching, commits, PRs, no AI attribution, no local agent config in any repo |
| `conventional-commits.md` | The full Conventional Commits 1.0.0 grammar, allowed types, footers, breaking changes |
| `clean-architecture.md` | Hexagonal boundaries, idiomatic Go packages, and feature-oriented frontend structure |
| `test-discipline.md` | What to test, doubles, layers, correctness-critical extras |
| `algorithm-rigor.md` | Complexity against a stated N, query plans, concurrency, pattern selection |
| `system-design.md` | Boundaries, data, async, resilience, API contracts, caching, observability |
| `infrastructure-delivery.md` | Terraform, OpenTofu, Pulumi, Kubernetes, CI/CD, state, plans, policy, rollout |
| `sre-operations.md` | SLI/SLO, error budgets, observability, capacity, incidents, recovery |
| `frontend-quality.md` | Accessibility, browser behavior, async UI states, contracts, Web Vitals |
| `ml-engineering.md` | Data lineage, leakage, reproducibility, evaluation, skew, drift, model rollout |
| `genai-agent-systems.md` | LLM and RAG evals, retrieval permissions, tool safety, memory, cost, rollout |
| `verification-gate.md` | Tier-aware checks and the machine-readable gate report |
| `review-panel.md` | The 2 to 3 agent protocol and the synthesis that trusts none of them |
| `rewrites.md` | Contextual rewrites for stiff, generic, or over-compressed prose |
| `checklists.md` | Reviewing a PR, debugging, refactoring, dependencies, migrations, incidents |

## Agents

All ten are read-only. None can edit the code they review.

`qa-verifier` · `security-auditor` · `performance-auditor` · `architecture-critic` ·
`algorithm-verifier` · `reliability-auditor` · `platform-auditor` ·
`frontend-quality-auditor` · `ai-ml-verifier` · `decision-analyst`

Each returns a structured report with a verdict, a confidence level, findings
anchored to `file:line`, and its unknowns. The caller verifies every finding against
the code before acting on it.

## Enforcement

Four mechanisms run outside the model's judgment.

**Git guard** (`hooks/guard-git.py`, wired as a `PreToolUse` hook on Bash). Blocks:

- a commit message carrying AI attribution, a `Co-Authored-By` trailer, or a robot emoji
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

Exit 0 means no finding reached the configured failure threshold; warnings may still
be printed. Exit 1 means the threshold was reached, and exit 2 is a usage error. Suppress with
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

**Gate report** (`hooks/gate-report.py`). Writes and validates a machine-readable
verification result bound to the current commit and worktree. The default report is
`.git/taurus/verification.json`, so it stays out of the project tree.

```bash
python3 hooks/gate-report.py write /tmp/taurus-gate-input.json
python3 hooks/gate-report.py validate
python3 hooks/gate-report.py fingerprint
```

A changed commit, tracked file, untracked file, or symlink makes the report stale.
The schema enforces tier-specific checks, domain evidence such as an infrastructure
plan or model evaluation, reviewers, and unresolved findings.

## Using it in a project's CI

```yaml
- run: python3 ~/.claude/taurus/hooks/lint-prose.py $(git diff --name-only origin/main -- '*.md')
- run: python3 ~/.claude/taurus/hooks/lint-commit.py --stdin --pr-title <<< "$PR_TITLE"
```

The installer already wires the Git-side checks into every repo through
`core.hooksPath`. The gate report is local evidence for the exact pre-ship worktree;
CI should still run its own build, test, lint, and type-check jobs.

## Tests

```bash
./run-tests.sh
```

Seven suites: the prose linter, commit linter, gate report, git guard, git hooks,
installer against an isolated config directory, and the pack's own structure. The structure
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
hooks/                  guards, linters, shell scanner, gate report writer
githooks/               commit-msg, pre-commit, pre-push, wired via core.hooksPath
tests/                  the seven suites
install.sh              installer, updater, uninstaller
```
