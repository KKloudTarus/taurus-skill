---
name: taurus-ship
description: Pre-commit audit, then commit and optionally open a PR under Taurus git discipline.
---

Run the native OMP Taurus ship workflow for the supplied scope.

1. Read `.omp/taurus/rules/omp-delta.md`.
2. Read `.omp/taurus/commands/ship.md` and follow its workflow.
3. The input supplied with `/skill:taurus-ship` is the complete workflow scope. Treat the canonical command's argument placeholder or default as that input. Resolve canonical `~/.claude/taurus` paths as `.omp/taurus` and canonical `~/.claude/skills` paths as `.omp/skills`.
4. Do not automatically invoke any personal `pr-gate`. The canonical workflow's `/verify` refers only to `/skill:taurus-verify`; invoke it only under the command's stated conditions. Never commit, push, or open a PR unless the user explicitly requested the corresponding action.
