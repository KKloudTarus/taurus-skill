---
name: taurus-style
description: Review text for a natural technical voice with Taurus writing guidance and prose-linter evidence.
---

Run the native OMP Taurus writing-style workflow for the supplied scope.

1. Read `.omp/taurus/rules/omp-delta.md`.
2. Read `.omp/taurus/commands/style.md` and follow its workflow.
3. The input supplied with `/skill:taurus-style` is the complete workflow scope. Treat the canonical command's argument placeholder or default as that input. Resolve canonical `~/.claude/taurus` paths as `.omp/taurus` and canonical `~/.claude/skills` paths as `.omp/skills`.
4. Do not automatically invoke any personal `pr-gate`.
