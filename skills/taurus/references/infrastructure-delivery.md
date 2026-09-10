> Load when: Creating or reviewing infrastructure as code, cloud resources, Kubernetes manifests, CI/CD deployment paths, environment topology, or an infrastructure plan. Covers Terraform, OpenTofu, Pulumi, state and stack safety, policy checks, rollout evidence, and the authorization boundary around apply operations.

# Infrastructure delivery

Infrastructure code changes production through a control plane. Review the rendered
plan or preview against live state; a source diff alone cannot show resource
replacement, provider defaults, drift, or a delete caused by an address change.

## Establish the operating context

Before changing code, identify:

- the selected tool and exact CLI/provider versions;
- the root module, Pulumi project, workspace, or stack in scope;
- state backend, lock or concurrency mechanism, encryption, backup, and recovery owner;
- cloud accounts, subscriptions, regions, clusters, and environments the change can reach;
- the deployment identity and its permissions;
- the expected creates, updates, replacements, deletes, and monthly cost direction.

Do not run `apply`, `up`, `destroy`, state mutation, import, refresh that writes state,
or a production policy override without explicit user authorization. A request to edit
or review IaC authorizes validation and preview only when those operations are read-only
for the configured tool and backend.

Plan and preview are not automatically harmless: providers read live APIs, Terraform data
sources can execute external programs, and a Pulumi program is general-purpose code. Inspect
the configuration first, use scoped read credentials, and sandbox untrusted pull requests.

## Shared invariants

- Keep state remote for team-managed infrastructure, with locking or serialized runs,
  encryption, access logging, version history, and a tested recovery path. Treat state
  and saved plans as secrets even when terminal output marks values sensitive.
- Use short-lived workload identity in CI. Do not store long-lived cloud keys in source,
  plan artifacts, stack configuration, logs, or generic CI variables.
- Pin the CLI, providers, plugins, and reusable modules. Commit the dependency lock file.
  Upgrade deliberately and review provider release notes and schema changes.
- Split state or stacks by blast radius, ownership, permissions, and change cadence.
  Do not create one state per resource or one global state for unrelated systems.
- Build modules and components around an operational capability. A thin wrapper over one
  resource adds an API without adding safety or reuse.
- Prefer stable logical identities. Use migration declarations such as `moved` blocks or
  aliases when refactoring; never accept replacement until the reviewer understands why.
- Protect critical data with provider controls, backups, retention, and deletion
  protection. Lifecycle flags are guardrails, not substitutes for recovery.
- Detect drift on a schedule and assign an owner. Do not silently make an emergency
  console edit the new source of truth.

## Terraform and OpenTofu

Follow the repository's chosen CLI; do not switch between `terraform` and `tofu` against
the same state as a convenience. Confirm provider and language compatibility first.

For an HCL root module, these checks avoid the configured backend and provider APIs:

```bash
terraform fmt -check -recursive
terraform init -backend=false
terraform validate

tofu fmt -check -recursive
tofu init -backend=false
tofu validate
```

Inspect test files before running `terraform test` or `tofu test`: test runs may use
`apply`, create real resources, and destroy them afterwards unless providers are mocked.

Run the matching `plan` against the intended workspace only when credentials and backend
access are in scope. Capture machine-readable output where supported, review every
replacement and deletion, and record whether drift contributed to the plan. Saved plan
files may contain cleartext secrets; keep them in a trusted runner with short retention.

Keep module trees shallow and pass dependencies into modules from the root. Expose typed,
documented inputs and only the outputs consumers need. Avoid routine `-target`, blanket
`ignore_changes`, provisioners, and direct state-file editing; each bypasses part of the
declarative dependency model. Use the CLI state commands for an approved recovery or
migration procedure.

OpenTofu can encrypt state and plans at the language layer. Key loss makes encrypted state
unrecoverable, so test key rotation and fallback before enabling it in production.
Encryption does not replace backend versioning or protect against replaying old state.

## Pulumi

A Pulumi stack is a deployment, configuration, permission, and concurrency boundary.
Start with one project and a small number of environment stacks; split when blast radius,
ownership, permissions, or preview time justifies the coordination cost.

Run language formatting, lint, type checking, and tests before `pulumi preview`. Preview
every pull request and rerun it after rebasing because state or the target branch may have
changed. Apply the reviewed commit through CI; do not substitute an unreviewed local `up`.
Inspect program initialization, dynamic providers, and command resources before preview so
ordinary language code cannot hide a network or filesystem side effect.

Use `Config.requireSecret` or the language equivalent and preserve Pulumi's secret-marked
`Output` values. An `apply` callback receives plaintext and can still leak it through logs
or files. Build Component Resources for concepts with a stable interface, not to conceal
ordinary provider resources. Use Stack References sparingly across independently owned
stacks and treat their outputs as versioned contracts.

Pulumi tests serve different purposes: unit tests inspect program logic, policy tests
enforce resource invariants, and integration tests deploy disposable infrastructure and
assert real behavior. A mocked unit test does not prove that the cloud accepts the plan.

## Delivery and production review

A safe pipeline produces a plan or preview for each pull request, attaches it to the exact
commit and target environment, checks policy, requires the appropriate owner, and applies
through a serialized protected job. Recompute when code, state, provider versions, or the
target environment changes.

Review Kubernetes workloads for requests and limits, readiness/startup/liveness semantics,
disruption behavior, rollout strategy, service accounts, network policy, secret delivery,
and zone failure. A green manifest validator does not prove that a rollout preserves
capacity or that a probe represents user-visible health.

Record an abort signal, rollback or forward-fix procedure, state recovery steps, and the
telemetry that confirms success. Destructive production plans, IAM boundary changes,
state migrations, and changes that can remove recovery data are tier 0.

## Primary sources

- Terraform configuration and workflow guidance: https://developer.hashicorp.com/terraform/language/style
- Terraform sensitive data: https://developer.hashicorp.com/terraform/language/manage-sensitive-data
- OpenTofu module design: https://opentofu.org/docs/language/modules/develop/
- OpenTofu state and plan encryption: https://opentofu.org/docs/language/state/encryption/
- OpenTofu testing: https://opentofu.org/docs/cli/commands/test/
- Pulumi project and stack organization: https://www.pulumi.com/docs/iac/guides/basics/organizing-projects-stacks/
- Pulumi continuous delivery: https://www.pulumi.com/docs/iac/guides/continuous-delivery/
- Pulumi secrets: https://www.pulumi.com/docs/iac/concepts/secrets/
- Pulumi testing: https://www.pulumi.com/docs/iac/guides/testing/
- Kubernetes production considerations: https://kubernetes.io/docs/setup/production-environment/
- SLSA supply-chain specification: https://slsa.dev/spec/v1.2/
