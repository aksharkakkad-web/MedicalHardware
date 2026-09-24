# Telemetry Pipeline Replay Report

This report exercises device-shaped radar, thermal, and Wi-Fi CSI payloads through the production ingestion and intelligence boundary. All thresholds and sensor inputs are synthetic engineering fixtures, not clinical validation.

## Results

- Cases: 48
- Passed: 48
- Failed: 0
- Accepted packets: 385
- Duplicate packets safely ignored: 3
- Expected conflicts detected: 2/2
- Assignment blocks detected: 2/2
- Supported anomaly recall: 100.0%
- Normal false-event rate: 0.0%
- Caregiver events without a trusted live AI result: 0
- Median case latency: 216.396 ms
- P95 case latency: 336.605 ms

## Interpretation

The replay proves the software contract, durability, assignment gate, source normalization, fusion, synthetic anomaly path, pending-safe AI boundary, and restart behavior with controlled data. Anomalies remain pending and create no caregiver event without a trusted AI result. A separate focused integration test proves that a validated staged analysis can create an idempotent caregiver event. This does not prove real-sensor accuracy, production calibration thresholds, clinical meaning, or deployment readiness.
