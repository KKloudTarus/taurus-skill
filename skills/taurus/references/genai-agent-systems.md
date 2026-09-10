> Load when: Building or reviewing an LLM feature, prompt, retrieval-augmented generation pipeline, model gateway, structured-output flow, memory system, tool-using agent, autonomous workflow, or generative-AI evaluation. Covers task-specific evals, untrusted model behavior, retrieval permissions, tool authorization, cost, and safe rollout.

# Generative AI and agent systems

Model output is nondeterministic, fallible, and untrusted. Design the surrounding system
so a plausible but wrong response cannot silently become an unauthorized data access,
external action, security decision, or irreversible state change.

## Define behavior with evals

Write the task, allowed behavior, refusal boundary, and failure taxonomy before tuning the
prompt or changing models. Build an eval set from representative production cases, known
failures, boundary inputs, adversarial inputs, and important languages or user segments.
Keep a held-out set for the final decision.

Use deterministic checks for structure, citations, policy, tool arguments, and exact facts
where possible. Human or model graders need a rubric with anchored examples; calibrate
automated graders against blinded human review and inspect disagreement. Report per-class
results, variance, latency, and cost, not one blended score.

Version the model and provider, parameters, system and user prompt templates, tools and
schemas, retrieval configuration, corpus snapshot, safety policy, grader, and eval data.
A model alias without a resolved version cannot support a reproducible release.

## Retrieval and grounding

- Enforce document and tenant permissions before retrieval and again before returning
  content. The model must not decide access from prompt text.
- Evaluate retrieval separately from generation: relevant-item coverage, ranking, filters,
  freshness, empty retrieval, conflicting sources, and poisoned documents.
- Treat retrieved text as untrusted instructions. Preserve provenance through chunking and
  return citations that identify the actual supporting source.
- A citation proves where text came from, not that the claim is correct. Test answer support
  and abstention when evidence is absent or contradictory.
- Keep ingestion idempotent and versioned. Deletion and permission changes must reach every
  index, cache, embedding store, and evaluation copy within a stated window.

## Tools, agents, and memory

Expose narrow typed tools with server-side authentication and authorization. Validate model
arguments exactly as untrusted API input. Use least-privilege credentials scoped to the
user, tenant, action, and lifetime; never give a model a broad credential and rely on its
prompt to respect policy.

Separate proposing an action from authorizing and executing it. Require human confirmation
at the moment of a consequential or irreversible action, showing the resolved target and
effect. Apply idempotency keys, transaction boundaries, rate and spend limits, timeouts,
bounded retries, maximum steps, and an auditable stop reason.

Assume direct and indirect prompt injection. Model output sent to a shell, browser, SQL
engine, template, URL fetcher, or another model stays untrusted and passes through a typed
policy boundary. Sandbox code and file access, restrict network destinations, and protect
against SSRF, path traversal, data exfiltration, and confused-deputy behavior.

Memory has an owner, purpose, retention period, size bound, and deletion path. Do not turn
arbitrary model summaries into durable facts without provenance and correction. Keep secret,
private, cross-tenant, and untrusted instructions out of shared memory.

## Reliability and production operation

Validate structured output against a schema and handle refusal, truncation, malformed data,
tool failure, provider timeout, quota exhaustion, and context overflow explicitly. Fallbacks
must preserve the product's safety boundary; a cheaper model or no-retrieval path may not be
safe for the same action.

Trace model calls, retrieval, tool proposals, approvals, execution, retries, token use,
latency, resolved versions, and policy decisions with sensitive content redacted. Bound log
retention and sampling. Prompts and responses often contain credentials, personal data, and
copyrighted material.

Roll out prompts, models, retrievers, and tool policies through versioned canaries or shadow
traffic when possible. Compare them on the frozen eval and live guardrails, define rollback
before exposure, and preserve the previous compatible configuration. Provider changes need
an exit plan for model behavior, data retention, rate limits, and regional processing.

## Review evidence

```text
TASK: <allowed behavior, refusal boundary, affected users>
VERSIONS: <model, prompts, tools, corpus, policy, grader>
EVALS: <dataset, metrics, thresholds, segments, variance>
RETRIEVAL: <permissions, freshness, support, deletion>
ACTIONS: <tool scopes, approvals, idempotency, limits>
THREATS: <prompt injection, output sinks, exfiltration controls>
ROLLOUT: <canary, live guardrails, cost ceiling, rollback>
```

An agent that can spend money, modify infrastructure, publish externally, access sensitive
data, or make a high-impact decision is tier 0 even when the code change is small.

## Primary sources

- NIST Generative AI Profile: https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf
- NIST AI Risk Management Framework: https://www.nist.gov/itl/ai-risk-management-framework
- OWASP GenAI Security Project: https://genai.owasp.org/
- OWASP Top 10 for LLM applications: https://owasp.org/www-project-top-10-for-large-language-model-applications/
- OpenTelemetry semantic conventions: https://opentelemetry.io/docs/specs/semconv/
