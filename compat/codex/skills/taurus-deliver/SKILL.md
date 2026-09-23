---
name: taurus-deliver
description: Deliver a change under a risk-tiered Taurus workflow, from repository inspection through current verification evidence
---

Run the Taurus deliver workflow. The text the user attached to this skill is the argument string.

Read `commands/deliver.md` in the pack root and follow it.

The pack root is the `taurus` symlink in Codex home (`~/.codex/taurus`, or `$CODEX_HOME/taurus` when `CODEX_HOME` is set). Skill files live under `~/.agents/skills`. In the command file, `~/.claude/taurus` means the pack root and `~/.claude/skills` means `~/.agents/skills`. `$ARGUMENTS` and `${ARGUMENTS...}` mean the argument string.
