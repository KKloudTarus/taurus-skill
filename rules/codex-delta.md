# Codex session

Path and invocation only. The rules above are unchanged.

- The pack root is the `taurus` symlink in Codex home (`~/.codex/taurus`, or
  `$CODEX_HOME/taurus` when `CODEX_HOME` is set). The skill is
  `~/.agents/skills/taurus`. A Taurus document that says `~/.claude/taurus` means
  the pack root. One that says `~/.claude/skills` means `~/.agents/skills`.
- `.codex/` is local agent config, the same as `.claude/`. Do not commit it.
- Workflows Claude runs as `/deliver`, `/panel`, `/ship`, `/style`, and `/verify`
  are the skills `$taurus-deliver`, `$taurus-panel`, `$taurus-ship`,
  `$taurus-style`, and `$taurus-verify`.
- Reviewers are the named subagents in Codex home under `agents/`. They are
  read-only. Spawn them together when the harness can run them in parallel.
- A `PreToolUse` hook runs `guard-git.py` for shell git commands. If it blocks,
  fix the cause. Do not bypass it. The hook does nothing until you trust it in
  `/hooks`. Git hooks installed with `--githooks` remain the control of record.
