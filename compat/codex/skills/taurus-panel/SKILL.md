---
name: taurus-panel
description: Convene a 2-3 agent review panel on a decision or a review, then synthesize without deferring to any agent
---

Run the Taurus panel workflow. The text the user attached to this skill is the argument string.

Read `commands/panel.md` in the pack root and follow it.

The pack root is the `taurus` symlink in Codex home (`~/.codex/taurus`, or `$CODEX_HOME/taurus` when `CODEX_HOME` is set). Skill files live under `~/.agents/skills`. In the command file, `~/.claude/taurus` means the pack root and `~/.claude/skills` means `~/.agents/skills`. `$ARGUMENTS` and `${ARGUMENTS...}` mean the argument string.
