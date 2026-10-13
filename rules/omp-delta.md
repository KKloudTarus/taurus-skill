# OMP project session

Apply these runtime adaptations when Taurus runs in OMP. The shared engineering
criteria and verdict schemas remain authoritative; this section replaces client-
specific paths, invocation syntax, tool names, and execution assumptions.

## Project scope and paths

- Start OMP from the project directory passed to the installer. The pack root is
  `.omp/taurus`, and the skill root is `.omp/skills/taurus`. Resolve these paths
  against that project root, including when assigning subagents.
- In shared documents, replace `~/.claude/taurus` with the pack root and
  `~/.claude/skills/taurus` with the skill root. Never execute an example using
  another client's home directory. Use the available Python interpreter; quote
  paths and use a platform-appropriate temporary directory, not a literal `/tmp`
  on Windows. `TAURUS_PYTHON` selects the extension's Python executable.
- Installation is opt-in per project. It does not modify global OMP settings,
  model roles, credentials, Git ignore files, or `core.hooksPath`. Native project
  settings and extensions depend on the launch directory; do not assume a launch
  in an arbitrary child directory loads this pack.

## Workflows and roles

- Load the router with `/skill:taurus`, or use `/skill:taurus-deliver`,
  `/skill:taurus-verify`, `/skill:taurus-panel`, `/skill:taurus-ship`, and
  `/skill:taurus-style` followed by the task or scope. These are skills, not the
  built-in OMP `/verify` command or client-specific slash-command templates.
- The orchestrator coordinates: inspect scope, select the tier, delegate
  implementation to the user's executor agent (or OMP's generic task agent),
  schedule verification, and reconcile evidence. Executors make code changes.
  Do not silently replace the user's model or executor mapping.
- Dispatch named Taurus reviewers with OMP `task`, using shared `context` and
  `tasks[]` entries with `agent`, `task`, and `solutionSpace`. Describe uncertainty
  in `solutionSpace`, not the amount of work. Give each reviewer the revision,
  requirements, relevant files, and actual verification output. Wait for terminal
  completion; a task launch acknowledgment is not a completed review. Do not put
  built-in tool names in the optional task `tools` field; it accepts registered
  eval-defined tools. Reviewer tools come from their agent files.
- Follow OMP's concurrency and delegation constraints. Independent reviewers can
  run together, but a single integration owner runs shared build/lint/tests once
  after edits settle. Do not run competing checks in reviewer branches.
- Taurus reviewer adapters expose only `read`, `grep`, and `glob` plus OMP's
  automatic result tool. They inspect evidence; they cannot execute checks,
  modify a fixture, install tools, or delegate. Ignore shared reviewer instructions
  to run commands or temporarily edit code. Request those checks from the
  orchestrator, who delegates them to an executor or verification owner.
- Preserve each reviewer's `VERDICT` contract. Missing required runtime evidence
  means `fail` with explicit unknowns, not a fabricated pass. The gate report's
  normal findings/disposition rules still apply. Load only the relevant references.
- The user's separate `pr-gate`, if present, is not a Taurus lifecycle reviewer.
  Invoke it only when the user explicitly requests its review/fix/recheck loop.
  In that loop, the orchestrator coordinates executor repairs, waits for evidence,
  then asks the gate to recheck; the orchestrator does not implement fixes.

## Enforcement boundaries

The project extension intercepts OMP's native `bash` tool and feeds the command and
working directory to the existing Git guard. Interpreter failures, guard failures,
and timeouts block the call. Fix the cause rather than routing around the guard.

This is not an OS sandbox: eval subprocesses, external terminals, other extensions,
and disabled extension loading are outside this interception boundary. The OMP
installer does not enable machine-wide Git hooks. Existing Git hooks continue to
apply independently. Do not claim all shell execution or Git writes are enforced.

Use native OMP tools rather than another client's tool names. Do not add AI
attribution, commit local `.omp/` state, or infer authorization for publishing,
merging, deployment, dependency installation, or other external actions.
