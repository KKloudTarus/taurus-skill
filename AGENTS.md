# Repository Guidelines

## Project Structure & Module Organization

This repository packages the Taurus delivery standard for global Claude Code use. `skills/taurus/SKILL.md` is the single skill entry point; detailed guidance belongs in `skills/taurus/references/`. Always-loaded policy lives in `rules/always-on.md`. Reviewer definitions are under `agents/`, slash commands under `commands/`, Python enforcement tools under `hooks/`, and Git hook wrappers under `githooks/`. Tests live in `tests/`; `install.sh` manages global installation.

Keep `.taurus-skill-source` at the repository root. It permits this source repository to version local agent configuration while installed hooks block those files elsewhere.

## Build, Test, and Development Commands

- `./run-tests.sh`: run all seven suites and report every failure.
- `python3 tests/test_guard_git.py`: run one Python `unittest` suite.
- `python3 tests/test_repo_integrity.py TestSkills.test_the_skill_routes_to_every_reference`: run one test method.
- `bash tests/test_install.sh`: exercise installation against an isolated configuration directory.
- `./install.sh --dry-run`: preview symlinks, settings, Git hooks, and ignore changes.
- `python3 hooks/lint-prose.py README.md`: check Markdown against the shipped writing standard.

There is no compilation step. Run the full suite before each commit.

## Coding Style & Naming Conventions

Use four spaces in Python and conventional shell indentation in Bash. Shell entry points use `#!/usr/bin/env bash`, strict mode where suitable, quoted expansions, and descriptive uppercase globals. Name Python tests `test_<area>.py`; use lowercase kebab-case for agent, command, and reference filenames. Preserve YAML frontmatter contracts and begin every reference with `> Load when:`. Keep each policy in its owning tool: prose in `hooks/lint-prose.py`, commit grammar in `hooks/lint-commit.py`, and gate schema in `hooks/gate-report.py`. Callers must reuse those definitions.

## Testing Guidelines

Tests use Python's `unittest` plus a Bash installer suite. Add regression tests with every behavior change, especially for shell parsing, hook chaining, installer idempotency, and documentation cross-references. No numeric coverage threshold exists; repository integrity tests instead enforce the published structural contracts. Keep executable bits on scripts and hooks.

## Commit & Pull Request Guidelines

Use Conventional Commits with lowercase types and imperative subjects, for example `fix(guard): reject nested shell substitutions`. Keep subjects at 72 characters or fewer. Stage explicit paths after reviewing `git status --porcelain`, then inspect `git diff --cached`.

PR titles follow the same grammar. PR bodies should cover Problem, Approach, Alternatives rejected, Risk and rollback, and Verification. Link the relevant ticket, name tests run, include benchmark evidence for performance claims, and add screenshots only for visible UI changes.
