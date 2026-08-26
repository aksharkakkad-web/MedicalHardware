# MedicalHardware review rules

- Reject changes that invent clinical thresholds, diagnoses, treatment advice, or unsupported medical claims.
- Reject real PHI, credentials, browser-session data, private keys, or secrets in code, fixtures, logs, screenshots, prompts, tests, or documentation.
- Keep deterministic event and warning creation outside the LLM. The LLM may interpret existing evidence but must never suppress deterministic warnings.
- Represent missing or low-quality sensor data as unavailable or low confidence; never fabricate precision.
- Keep firmware/edge preprocessing, cloud fusion, baselines, anomaly detection, events, LLM interpretation, and presentation boundaries aligned with `docs/ARCHITECTURE.md`.
- Any shared schema, API, or domain change must update `docs/DATA_CONTRACT.md`, backend/frontend types, fixtures, and relevant tests together.
- Simulator and real hardware must emit the same versioned edge-telemetry contract.
- Require the smallest useful deterministic tests for every behavior change and reject silent fallbacks.
- Flag changes that cross the ownership boundaries in `docs/TEAM_OWNERSHIP.md` without an explicit coordinated handoff.
- A merge-ready review requires 5/5 confidence and zero unresolved actionable comments.
