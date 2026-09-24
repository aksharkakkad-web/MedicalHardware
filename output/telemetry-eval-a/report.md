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
- Median case latency: 201.572 ms
- P95 case latency: 296.949 ms

## Interpretation

The replay proves the software contract, durability, assignment gate, source normalization, fusion, synthetic anomaly path, event idempotency, and restart behavior with controlled data. It does not prove real-sensor accuracy, production calibration thresholds, clinical meaning, or deployment readiness.
