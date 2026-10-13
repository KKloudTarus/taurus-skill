---
name: taurus-panel
description: Convene a two- or three-agent Taurus review panel on a decision or review and synthesize the result.
---

Run the native OMP Taurus review-panel workflow for the supplied scope.

1. Read `.omp/taurus/rules/omp-delta.md`.
2. Read `.omp/taurus/commands/panel.md` and follow its workflow.
3. The input supplied with `/skill:taurus-panel` is the complete workflow scope. Treat the canonical command's argument placeholder as that input. Resolve canonical `~/.claude/taurus` paths as `.omp/taurus` and canonical `~/.claude/skills` paths as `.omp/skills`.
4. Do not automatically invoke any personal `pr-gate`.
