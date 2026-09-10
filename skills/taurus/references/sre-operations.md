> Load when: Defining or reviewing service reliability, SLI and SLO policy, alerts, telemetry, capacity, on-call readiness, incident response, disaster recovery, or a production rollout. Separates user-visible reliability from component uptime and turns operational claims into measurable evidence.

# SRE operations

Reliability is a product behavior observed over time. Start with the user journey and
the failure they experience, then choose telemetry and controls that measure or protect
that behavior.

## Service expectations

Define each SLI as a numerator, denominator, data source, exclusions, and aggregation
window. Availability alone is rarely enough; consider latency, correctness, freshness,
durability, and coverage for the user journeys that matter. State the SLO target and
window, why users need it, and what happens when the service spends its error budget.

An error-budget policy names the release or remediation action before the budget is
exhausted. Do not invent five-nines from a component dashboard. Dependencies, maintenance
windows, low traffic, partial responses, and delayed data all change how an SLI behaves.

## Observability and alerts

- Emit traces, metrics, and structured logs with consistent service, operation, error,
  and deployment attributes. Correlate the signals with trace and request identifiers.
- Measure user symptoms at the service boundary. CPU and queue depth explain an incident;
  they do not replace success rate, latency, freshness, or correctness indicators.
- Keep metric labels bounded. User IDs, request IDs, raw URLs, and unbounded error text
  create cardinality incidents and may expose sensitive data.
- Alert on actionable symptoms or fast error-budget burn. Every page has an owner,
  urgency, tested notification path, dashboard, and runbook with a first safe action.
- Detect missing telemetry explicitly. No data is not evidence that a service is healthy.

Use OpenTelemetry semantic conventions where they fit so signals correlate across
languages and services. Record deliberate deviations; dashboards silently depending on
private attribute names become a migration trap.

## Capacity and failure readiness

Name the constrained resource and the workload unit that consumes it. Track saturation,
queueing, dependency quotas, connection pools, storage growth, and regional or zonal
headroom. Capacity claims need a load test, production trend, provider quota, or a stated
unknown with a measurement plan.

Bound concurrency, queues, retries, and work admitted during overload. Preserve capacity
for health checks and recovery traffic. Test startup, graceful shutdown, rolling deploy,
dependency timeout, retry amplification, poison messages, and loss of a zone or critical
dependency when those failures are credible.

Set RPO and RTO for durable systems. Backups count only after a restore or replay exercise
proves the data, credentials, tooling, and operator procedure still work. Record the last
exercise and the gap between its conditions and production.

## Change and incident practice

A production change names the canary population, success signals, observation window,
abort threshold, rollback owner, and the point after which rollback becomes a forward fix.
Feature flags need an owner and removal date; a disabled path that cannot be exercised is
not a tested rollback.

During an incident, establish command, preserve a timestamped decision log, stop the
impact, and change one variable at a time. Preserve volatile evidence before restarting.
The postmortem explains the mechanism and missing guardrail, quantifies impact, and assigns
action items with owners and verification. “Be more careful” is not a control.

## Review evidence

For an operational review, report:

```text
SERVICE: <user journey and owner>
SLO: <indicator, target, window, current budget state>
CAPACITY: <constraint, headroom, evidence>
ROLLOUT: <canary, success signal, abort threshold>
RECOVERY: <rollback or forward-fix, RPO/RTO, last exercise>
ALERTS: <pages, runbooks, notification test>
UNKNOWNS: <fact and cheapest way to measure it>
```

## Primary sources

- Google SRE service-level objectives: https://sre.google/workbook/implementing-slos/
- Google SRE error-budget policy: https://sre.google/workbook/error-budget-policy/
- Google SRE monitoring: https://sre.google/workbook/monitoring/
- OpenTelemetry observability concepts: https://opentelemetry.io/docs/concepts/observability-primer/
- OpenTelemetry semantic conventions: https://opentelemetry.io/docs/concepts/semantic-conventions/
- Kubernetes production environment: https://kubernetes.io/docs/setup/production-environment/
- Kubernetes probes: https://kubernetes.io/docs/concepts/workloads/pods/probes/
