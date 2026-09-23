---
name: taurus-ship
description: Pre-commit audit, then commit and optionally open a PR under git-discipline
---

Run the Taurus ship workflow. The text the user attached to this skill is the argument string.

Read `commands/ship.md` in the pack root and follow it.

The pack root is the `taurus` symlink in Codex home (`~/.codex/taurus`, or `$CODEX_HOME/taurus` when `CODEX_HOME` is set). Skill files live under `~/.agents/skills`. In the command file, `~/.claude/taurus` means the pack root and `~/.claude/skills` means `~/.agents/skills`. `$ARGUMENTS` and `${ARGUMENTS...}` mean the argument string.
