---
name: taurus-deliver
description: Deliver a change under the risk-tiered Taurus workflow, from repository inspection through current verification evidence.
---

Run the native OMP Taurus deliver workflow for the supplied scope.

1. Read `.omp/taurus/rules/omp-delta.md`.
2. Read `.omp/taurus/commands/deliver.md` and follow its workflow.
3. The input supplied with `/skill:taurus-deliver` is the complete workflow scope. Treat the canonical command's argument placeholder as that input. Resolve canonical `~/.claude/taurus` paths as `.omp/taurus` and canonical `~/.claude/skills` paths as `.omp/skills`.
4. Do not automatically invoke any personal `pr-gate`. Only prepare, commit, push, open a PR, deploy, or mutate an external system when the user explicitly requested that action.
