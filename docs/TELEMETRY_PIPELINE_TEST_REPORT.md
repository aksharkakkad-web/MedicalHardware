# Telemetry Pipeline Test Report

## Decision summary

The backend software bridge passed 48 of 48 deterministic, device-shaped replay cases in two independent runs. Stable result content matched across both runs after excluding measured runtime fields.

This is strong evidence that the software plumbing behaves as designed with controlled data. It is not evidence that the real sensors are accurate, that the synthetic thresholds are clinically meaningful, or that production deployment is ready.

## Quantified result

| Measure | Result |
|---|---:|
| Scenarios | 48 |
| Passed | 48 |
| Failed | 0 |
| Accepted sensor packets | 385 |
| Exact retry packets safely ignored | 3 |
| Expected conflicts detected | 2 / 2 |
| Expected assignment blocks detected | 2 / 2 |
| Required feature mappings missed | 0 |
| Supported synthetic anomaly recall | 100% |
| Normal/away false-event rate | 0% |
| Replay idempotency failures | 0 |
| Median isolated-case runtime, first recorded run | 201.572 ms |
| P95 isolated-case runtime, first recorded run | 296.949 ms |

Runtime numbers are local development measurements and are not production service-level claims.

## Coverage by scenario family

| Family | Cases | Anomaly detected | Caregiver event | Main proof |
|---|---:|---:|---:|---|
| Normal human variation | 6 | 0 | 0 | Ordinary variation did not create false events |
| Away/return context | 4 | 0 | 0 | High movement while marked away did not become a resident anomaly |
| Bathroom-like absence context | 4 | 0 | 0 | Expected absence context suppressed resident inference |
| Unusual movement | 6 | 6 | 6 | Persistent supported movement changes reached anomaly/event flow |
| Inactivity | 4 | 4 | 4 | Persistent low movement relative to a synthetic baseline was detected |
| Physiological deviation | 4 | 4 | 4 | Heart-rate-shaped deviations reached the non-diagnostic anomaly flow |
| Optional posture/fall-like evidence | 4 | 4 | 4 | Height/posture fields survived translation and synthetic detection |
| Missing sensor/source ablation | 4 | 0 | 0 | Missing sources stayed explicit in fused frames |
| Degraded signal quality | 4 | 0 | 0 | Low quality remained visible without fabricated replacement values |
| Retry/conflict/stream behavior | 4 | 0 | 0 | Retry, changed identity, stale sequence, gap, and new stream rules held |
| Assignment failure | 2 | 0 | 0 | Raw packets survived while resident frames/events were blocked |
| Recovery/recurrence | 2 | 2 | 2 | Recovery and later recurrence completed without replay duplication |

## What was exercised

Every scenario used the production Pydantic envelope, authenticated HTTP endpoint, durable packet store, assignment resolver, source normalizers, fusion layer, processing coordinator, baseline gate, and relevant anomaly/event persistence. Expected truth stayed outside production envelopes.

The suite covered:

- Mahin-shaped radar, MLX90640 thermal, and ESP32 CSI envelopes;
- exact retries, changed duplicate conflicts, stale sequences, sequence gaps, and stream restart;
- missing sources, low signal quality, normal variation, away context, and assignment failure;
- numerical movement, inactivity, heart-rate-shaped, and posture-shaped deviations;
- durable restart/event idempotency through the integration suite;
- deterministic artifacts in `output/telemetry-eval-a` and `output/telemetry-eval-b` when run locally.

## Still unproven

- Real hardware accuracy and long-duration stability.
- Real room noise, visitors, bedding, multipath, placement changes, and sensor failure distributions.
- Production calibration values and acceptable false-alert/recall tradeoffs.
- Clinical interpretation or diagnostic validity; the system intentionally makes neither claim.
- Live Gemini/Sol/Terra quality gates in this telemetry campaign.
- Production credentials, deployment, monitoring, and frontend real-client wiring.

## Reproduce

```bash
python3 -m evals.telemetry.cli --output output/telemetry-eval-a
python3 -m evals.telemetry.cli --output output/telemetry-eval-b
python3 -m pytest tests/evals/test_edge_telemetry_replay.py -q
```

The two JSON outputs should match after excluding `latency_ms`, `median_case_latency_ms`, and `p95_case_latency_ms`.
