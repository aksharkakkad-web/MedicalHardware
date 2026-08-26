# AGENTS.md

This file is the navigation map for coding agents. Keep it short. Detailed product and architecture knowledge lives in `docs/`.

## Read before coding

Read the relevant source-of-truth documents before making changes:

1. `docs/PRD.md` — product requirements and scope
2. `docs/ARCHITECTURE.md` — system boundaries and responsibilities
3. `docs/DATA_CONTRACT.md` — schemas, domain objects, API semantics
4. `docs/BUILD_PLAN.md` — implementation sequence and acceptance criteria
5. `docs/TEAM_OWNERSHIP.md` — human ownership, parallel-development boundaries, and handoff rules

If code and docs disagree, do not silently choose one. Determine whether the code is stale or the documented decision intentionally changed, then update them together.

## Shared skills and tool routing

- Before implementing or planning a feature, use `check-before-build` to inspect the current repository, Git history, and active remote issues/pull requests for reusable or overlapping work.
- For ordinary frontend or backend implementation, infer the owner's lane after the reuse report and run `scripts/start-work.sh <backend|frontend> "<short-task-name>"` before editing. Do not ask the founder to create a branch or supply Git commands; the helper creates the correct owned branch from clean `main`. Stop for dirty worktrees, an existing work branch, or a shared-contract boundary.
- Use Agent Browser for public pages, headless testing, and general browser automation.
- Use Ego Browser when the task requires the user's authenticated local browser session, or when the user explicitly requests Ego Browser.
- Keep credentials and browser-session data local. Never commit them to this repository.
- Graphify is installed, but do not generate its knowledge graph until source code exists.

## Pull request and auto-merge policy

- After repository bootstrap, make changes on short-lived branches and merge through pull requests; do not push feature work directly to `main`.
- Run `greploop` until Greptile reports 5/5 confidence with zero unresolved actionable comments, up to its five-iteration safety limit.
- GitHub auto-merge may be enabled only when the `repository-policy` and Greptile status checks are required on `main` and the repository variable `AUTO_MERGE_ENABLED` is `true`.
- Greptile reviews every new PR commit. A pushed fix invalidates the prior review and must receive a fresh result.
- Sensitive paths excluded by `.greptile/config.json` require human approval even when the review is 5/5.
- Use squash merge and delete the source branch after merge.


## Human ownership boundaries

The three-owner product/engineering team has stable ownership defined in `docs/TEAM_OWNERSHIP.md`:

- **Akshar:** backend, database, ingestion, fusion, baselines, anomaly/event logic, room/resident assignment, LLM/context, feedback-learning backend, backend evals.
- **Rishit:** clinic/home frontends, user-facing product flows, design system, frontend data clients, contract-valid mocks, scenario simulator, frontend/E2E tests.
- **Hardware/Firmware Engineer:** sensor bring-up, firmware, edge preprocessing, device transport/health, and hardware validation.
- **Shared:** contracts and source-of-truth docs; only one person/agent edits a shared contract at a time.

Agents should stay inside the requesting founder's owned areas unless the task explicitly authorizes crossing a boundary. Prefer handoffs through contracts over editing the other owner's subsystem.

## Product invariants

- Core hardware is 60 GHz radar + thermal + ESP32-S3 Wi-Fi CSI.
- V1 supports one assigned resident per monitored room and does not attempt to identify or separate multiple people.
- The embedded device performs lightweight per-sensor edge preprocessing: raw-to-usable conversion, obvious-junk filtering, downsampling/compression, timestamps/sequence metadata, packaging, and buffering/retry.
- Cross-sensor fusion, resident baselines, anomaly detection, confidence/event logic, LLM interpretation, and feedback learning live in the cloud.
- Data collection is continuous while the device is operating.
- Sensor fusion is preferred over adding redundant core sensors.
- Edge firmware handles lightweight per-sensor decoding/filtering/feature reduction. Cloud Python handles telemetry validation, cross-sensor fusion, baselines, anomaly detection, confidence, device health, and deterministic warnings.
- The LLM interprets already-created events; it does not monitor sensor telemetry streams.
- The LLM cannot suppress deterministic events/warnings.
- Low-quality data must be shown as low-confidence/unavailable, not as fake precision.
- Resident-away and possible-multi-person periods pause resident-specific baseline learning.
- Material room/device/sensor setup changes create a new setup version and recalibrate affected baseline dimensions without deleting resident history or semantic memory.
- Resolved events remain immutable; recurrences create new linked events rather than reopening history.
- Watch items may auto-close into history, but high/critical events never silently expire.
- Resident memory and numerical baseline are separate concepts.
- Feedback can update resident context quickly; baseline updates are controlled; global behavior changes are evaluated/versioned.
- Clinic dashboard and home app are separate product experiences sharing the core engine.
- The first commercial market is intentionally not hard-coded into the architecture.
- The event system must remain general/extensible; do not reduce the product to only fall detection.
- Known objective event families are allowed, but the system must support `unknown_anomaly` instead of forcing every anomaly into a preset cause.
- Frontends are built UI/UX-first as production code against contract-valid mock clients, then switched to real APIs behind the same interface.
- UI components consume a typed frontend client/provider boundary; they must not directly depend on fixture files or backend/database internals.

## Safety / medical-development rules

- Do not invent real medical thresholds or clinical claims.
- Synthetic/demo warning rules must be labeled test-only.
- Do not claim that the system diagnoses heart attack, seizure, stroke, or another condition unless a separately validated requirement explicitly adds that capability.
- Specific-event patterns may be represented as research/possible interpretations.
- Do not use real PHI in fixtures, logs, screenshots, prompts, analytics, or tests.
- Never send unnecessary raw or identifying data to an LLM.

## Architecture boundaries

- Hardware/vendor parsing and raw-to-usable conversion belong in firmware/edge adapter modules.
- The cloud consumes versioned compact edge-telemetry contracts from `docs/DATA_CONTRACT.md`.
- Simulator and real hardware must use the same edge-telemetry ingestion boundary.
- Device-to-room and room-to-resident assignment happens in authorized backend/domain logic, not in UI code.
- Suspected multi-person presence must lower confidence or make resident-specific output unavailable; never guess attribution.
- Do not leak radar-vendor, MLX90640, or ESP32 CSI/RuView structures into product/UI/domain code.
- Continuous raw sensor uploads are not the primary production path. Raw/debug capture must be explicit, bounded, and separate.
- Keep sensor processors, fusion, baseline, anomaly, events, AI, feedback, and device-health logic modular.
- Do not add a trained event classifier until labeled data/evals justify it.
- Do not add another core sensor because it seems interesting; require a documented failure mode/new information need.

## Contract discipline

Before changing a shared schema/API/domain object:

1. inspect `docs/DATA_CONTRACT.md`;
2. update the contract in the same change;
3. version/migrate intentionally;
4. update backend models;
5. update frontend clients/types;
6. update simulator fixtures;
7. update tests/evals.

Only one agent should own shared schema changes at a time.

## Coding style

Prefer:

- small modules with explicit interfaces;
- typed models at boundaries;
- pure functions for signal/baseline/anomaly logic where practical;
- dependency injection/interfaces around LLM providers and external services;
- deterministic tests;
- idempotent ingestion and event operations;
- structured logging;
- migrations instead of manual DB edits;
- comments explaining why, not narrating obvious code.

Avoid:

- throwaway static mockups that are rebuilt from scratch later;
- fixture imports scattered directly across UI components;
- giant all-in-one monitoring files;
- hidden global state;
- magic thresholds embedded throughout code;
- coupling UI to database internals;
- LLM-generated facts that are not present in structured evidence;
- silent fallbacks that fabricate values.

## Expected repo areas

```text
apps/clinic-dashboard/
apps/home-app/
backend/
firmware/
simulator/
prompts/
evals/
docs/
```

Exact layout may evolve, but logical boundaries in `ARCHITECTURE.md` must remain clear.

## Testing expectations

Every feature change should include the smallest useful tests.

At minimum, verify relevant:

- contract/schema tests;
- backend unit/integration tests;
- frontend lint/typecheck/build;
- critical UI flow tests;
- simulator/replay tests;
- evaluation cases for signal/anomaly/AI behavior.

When the repo is bootstrapped, keep the exact canonical commands in this file up to date.

Current backend/domain verification:

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Never report a task complete without running the relevant available checks or clearly stating what could not be run.

## Codex task style

Treat tasks like GitHub issues:

- one primary objective;
- explicit scope;
- acceptance criteria;
- non-goals;
- verification commands;
- relevant file/doc pointers.

For large work, plan first. Split independent work into separate agents/worktrees. Do not parallelize agents that will fight over the same shared contract or files.

Suggested roles when useful:

- planner/architect;
- frontend;
- backend/data;
- simulator/signal;
- AI/prompt;
- reviewer/verifier.

Review and integrate each agent's diff; parallelism is not a substitute for integration testing.

## Documentation rule

The repository docs are the system of record. If an architectural, product, or contract decision changes, update the appropriate document in the same change.

Do not turn this file into a giant manual. Add detailed knowledge to the relevant `docs/` file and link it here if needed.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
