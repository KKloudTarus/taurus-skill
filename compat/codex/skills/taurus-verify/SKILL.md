---
name: taurus-verify
description: Run the Taurus verification required by the change's rigor tier and write a worktree-bound JSON report
---

Run the Taurus verify workflow. The text the user attached to this skill is the argument string.

Read `commands/verify.md` in the pack root and follow it.

The pack root is the `taurus` symlink in Codex home (`~/.codex/taurus`, or `$CODEX_HOME/taurus` when `CODEX_HOME` is set). Skill files live under `~/.agents/skills`. In the command file, `~/.claude/taurus` means the pack root and `~/.claude/skills` means `~/.agents/skills`. `$ARGUMENTS` and `${ARGUMENTS...}` mean the argument string.
