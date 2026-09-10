# taurus-skill

This repo is the source of the Taurus delivery standard, installed globally into
`~/.claude` by `./install.sh`. Everything here ends up applying to every project on
the machine, so a change here is a change to how every session behaves.

## Commands

```bash
./run-tests.sh              # all seven suites, run before every commit
./install.sh --dry-run      # show what an install would change
python3 hooks/lint-prose.py <files>
```

One suite, or one class inside it, since each Python suite passes argv to
`unittest.main`:

```bash
python3 tests/test_guard_git.py
python3 tests/test_repo_integrity.py TestSkills.test_the_skill_routes_to_every_reference
bash tests/test_install.sh
```

`run-tests.sh` runs every suite even after one fails, then reports which ones did.

## Rules specific to this repo

- This is the one repo that may commit `.claude/` and `CLAUDE.md`. The
  `.taurus-skill-source` marker at the root is what grants that. The guard, the
  prose linter, and the `pre-commit` and `pre-push` git hooks all read it. Do not
  delete it. The exemption covers the path rules only: the attribution and message
  rules still apply here, and the prose linter never takes the exemption on the
  `commit` profile.
- `hooks/lint-prose.py` owns the prose pattern definitions and
  `hooks/lint-commit.py` owns the Conventional Commits grammar. The verification
  schema belongs to `hooks/gate-report.py`. `hooks/guard-git.py` shells out to both
  linters for commit messages. Add each rule in its owning tool only.
- `hooks/guard-git.py` never guesses at shell quoting. `hooks/shellscan.py` is the
  lexer; ask it whether a span is code or data. Regex-over-raw-text produced both
  false blocks and real bypasses, twice.
- The guard is the fast layer. `githooks/` is the control of record, wired into every
  repo by `install.sh` through `core.hooksPath`. A rule that must actually hold goes
  in a git hook, not only in the guard.
- `core.hooksPath` replaces a repo's whole hook directory, so `githooks/` carries a
  stub for every hook name git defines. Fifteen of the eighteen enforce nothing and
  exist only to `exec` the repo's own `.git/hooks/<name>`. Adding a hook name means
  adding its stub, or that hook stops running in every repo on the machine.
  `pre-push` reads refs on stdin, so it buffers them and replays them to the chained
  hook instead of exec'ing.
- `githooks/commit-msg` finds the linters through `TAURUS_ROOT`, default
  `~/.claude/taurus`. Editing a linter in the working copy does not change what the
  hook runs unless `TAURUS_ROOT` points here, which is what `tests/test_git_hooks.py`
  sets.
- Anything in `install.sh` that writes global git config needs an opt-out flag, and
  `tests/test_install.sh` must pass it. `CLAUDE_CONFIG_DIR` does not isolate git.
- Every markdown file in the pack is linted by `tests/test_repo_integrity.py`
  against the standard the pack ships. Wrap examples that intentionally trigger a rule in
  `<!-- prose-lint-disable -->` and `<!-- prose-lint-enable -->` rather than
  weakening a rule.
- The pack ships exactly one skill, `skills/taurus`, because every directory under
  `skills/` becomes its own entry in the picker. Depth goes in
  `skills/taurus/references/`, which the picker does not see. A test enforces the
  count, and another fails on a reference that `SKILL.md` does not route to.
- `tests/test_repo_integrity.py` also enforces the frontmatter contract: skill name
  matches its directory, agent name matches its filename, agents declare no editing
  tools, agents state a `VERDICT` contract, every reference opens with a
  `> Load when:` line, and cross-references between the skill, references, agents,
  and commands resolve.
- The installer must stay idempotent and must never overwrite a real file. The
  installer suite runs against an isolated `CLAUDE_CONFIG_DIR`, so it is safe to run.

## Layout

`rules/always-on.md` is merged into the user's `~/.claude/CLAUDE.md` between the
`taurus:begin` and `taurus:end` markers. It is the only always-loaded piece.
Everything in `skills/` is model-invoked on demand.
