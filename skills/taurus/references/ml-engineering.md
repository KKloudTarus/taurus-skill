> Load when: Building or reviewing a predictive machine-learning system, training or feature pipeline, dataset change, experiment, model evaluation, registry promotion, batch inference, online serving, drift monitor, or retraining workflow. Covers reproducibility, leakage, skew, rollout, and model risk beyond ordinary application testing.

# ML engineering

An offline score is one observation about a larger production system. The dataset,
feature code, training environment, serving path, decision policy, and feedback loop are
all part of the behavior under review.

## Frame the decision

Name the user or business outcome, the action driven by the prediction, the cost of each
error class, and the non-ML baseline. Choose metrics from that decision rather than from
model popularity. State where a human can review or override the result and what the
system does when the model or feature pipeline is unavailable.

Do not promote a model because one aggregate metric improved. Define acceptance thresholds
before comparing candidates, including important cohorts, calibration, latency, resource
cost, and safety constraints.

## Data and features

- Version or immutably identify training, validation, and test datasets. Record lineage,
  collection window, schema, licenses, consent, retention, and transformations.
- Split data along the boundary production will cross. Time-dependent systems need future
  holdouts; users, devices, patients, or documents that leak across splits inflate scores.
- Fit preprocessing only on training data. Audit target leakage, post-outcome fields,
  duplicates, label delay, missingness, imbalance, and sampling bias.
- Define feature ownership, freshness, default behavior, and validation. Training and
  serving should share transformations or compare logged serving features against training.
- Protect sensitive attributes and proxies throughout storage, training, artifacts,
  experiment tracking, logs, and feature access.

## Reproducible training and evaluation

Record the code revision, data identifier, feature definition, parameters, random seeds,
runtime and dependency versions, hardware where it changes numerics, and resulting artifact
digest. Reproduction means another run can explain material differences, not that every
floating-point bit must match on every accelerator.

Compare with the current production model and a simple baseline on the same untouched
evaluation data. Report confidence intervals or run-to-run variance when the sample or
training process makes a point estimate unstable. Inspect per-cohort performance and the
examples behind errors; aggregate accuracy can hide a failed minority path.

Tests should cover data contracts, transformations, invariants, determinism where promised,
training-serving parity, artifact loading, and end-to-end inference. Keep evaluation data
out of tuning loops and detect accidental reuse.

## Promotion and serving

Use a registry or equivalent immutable record for model version, provenance, evaluation,
approval, and stage. Deploy by artifact digest. Separate model promotion from code rollout
when either needs an independent rollback.

Validate the serving signature and feature freshness before traffic. Use shadow, canary, or
A/B rollout when the decision risk warrants it. Define success, guardrail, abort, and
rollback metrics in advance. Preserve the previous model and compatible feature path until
rollback is proven.

Bound batch size, concurrency, queue age, memory, accelerator use, timeout, and fallback.
Measure end-to-end decision latency and cost under representative inputs, not only bare
model inference.

## Monitoring and retraining

Monitor input schema and quality, feature drift, prediction distribution, serving errors,
latency, freshness, and eventual outcome metrics. Drift is a signal to investigate; it is
not proof that retraining helps. Labels may arrive late, so specify proxy signals and the
delay before true performance can be measured.

Detect feedback loops where model decisions change the data later used as labels. A
retraining trigger has minimum data, evaluation, approval, and rollback gates; calendar
frequency alone is not a safety argument. Retired artifacts, datasets, and features follow
documented retention and deletion policy.

## Review evidence

```text
DECISION: <prediction, downstream action, error costs>
BASELINE: <non-ML and current-production comparison>
DATA: <version, split boundary, lineage, leakage checks>
EVALUATION: <metrics, thresholds, cohorts, uncertainty>
ARTIFACT: <code, environment, model digest, registry stage>
ROLLOUT: <shadow/canary, guardrails, rollback>
MONITORING: <quality, skew, drift, outcome, owner>
```

High-impact decisions about health, employment, credit, access, safety, money, or autonomous
actions are tier 0 and require domain, security, and human-oversight review in addition to
model evaluation.

## Primary sources

- Google Rules of Machine Learning: https://developers.google.com/machine-learning/guides/rules-of-ml
- Google Cloud MLOps pipelines: https://cloud.google.com/architecture/mlops-continuous-delivery-and-automation-pipelines-in-machine-learning
- NIST AI Risk Management Framework: https://www.nist.gov/itl/ai-risk-management-framework
- NIST AI RMF Playbook and evaluation resources: https://airc.nist.gov/
