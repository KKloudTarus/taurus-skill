---
name: taurus-verify
description: Run the Taurus verification required by a change's rigor tier and write its worktree-bound report.
---

Run the native OMP Taurus verification workflow for the supplied scope.

1. Read `.omp/taurus/rules/omp-delta.md`.
2. Read `.omp/taurus/commands/verify.md` and follow its workflow.
3. The input supplied with `/skill:taurus-verify` is the complete workflow scope. Treat the canonical command's argument placeholder or default as that input. Resolve canonical `~/.claude/taurus` paths as `.omp/taurus` and canonical `~/.claude/skills` paths as `.omp/skills`.
4. Do not automatically invoke any personal `pr-gate`.
