# Monitoring Intelligence Lab

**Owner:** Akshar — backend intelligence and product logic  
**Purpose:** Prove the monitoring flow repeatedly before real sensors and production-model spending.

## The whole product flow, in plain English

The system follows one controlled path:

```text
signals → aligned evidence → anomaly filter → deterministic event →
AI explanation → dashboard action → feedback → guarded resident memory
```

The filter does the numerical work. It asks whether a change is strong enough, persistent enough, supported by usable sensors, and meaningfully different from that resident's flexible baseline. Ordinary variation, a bathroom trip, a visitor, or poor sensor quality should not be turned into a confident resident warning.

The AI receives a bounded JSON evidence packet only after a meaningful non-urgent anomaly exists. It can classify likely patterns, explain uncertainty, and recommend how to present the situation. It cannot invent measurements, identify a person, diagnose a condition, suppress an urgent event, or directly change memory. A corroborated urgent fall-like signal creates provisional caregiver work without waiting for AI.

Acknowledgment quiets repeated attention but does not erase the anomaly. Explicit operator feedback is separate. Feedback may create a small, reversible resident-memory proposal—such as a flexible habit or temporary behavior—but one observation does not become a permanent normal.

## What the lab exercises

The original 24 founder-approved scenarios remain the source behavior. They are organized into 12 product clusters: normal human variation, temporary absence, flexible routines, multi-person ambiguity, movement change, inactivity, fall-like motion, respiration concern, sensor degradation, new-behavior learning, event lifecycle, and AI failure.

The lab adds:

- 120 named, founder-reviewable canonical timelines;
- deterministic timing, numeric, quality, source-loss, and replay perturbations;
- strict grading and zero-tolerance safety gates;
- redacted, compressed, checksummed run evidence;
- a pinned Gemini 3.7 Flash development adapter with low thinking and structured JSON;
- exact paired-run comparison for later model or prompt changes; and
- a separately approved production gate of 5,000 Terra cases and 1,000 Sol critical/fallback cases.

## The test ladder

Run each level only after the earlier level is clean.

### 1. Fast cross-cluster smoke check

```bash
python3 -m evals.monitoring.cli smoke
```

This runs one reference story from every product cluster. Use it after a focused code change.

### 2. Full 120-case review set

```bash
python3 -m evals.monitoring.cli pr
```

This is the normal review checkpoint before merging intelligence changes.

### 3. Offline mass software campaign

```bash
python3 -m evals.monitoring.cli mass --cases 100000 --passes 10 --chunk-size 1000
```

This targets 100,000 distinct synthetic timelines with 10 deterministic passes, or 1,000,000 complete backend executions. It uses no external AI and therefore has no API cost. Start with a measured 10,000-execution run before committing machine time to the full campaign.

### 4. Live Gemini development campaign

```bash
python3 -m evals.monitoring.cli gemini --cases 100
python3 -m evals.monitoring.cli gemini --cases 1000
python3 -m evals.monitoring.cli gemini --cases 25000
```

The command reads the locally ignored `GEMINI_API_KEY` from `.env.local`. The target is 25,000 saved live interpretations over time, subject to the Google account's actual free quota. A quota-limited run must report only the calls it really completed and remain resumable; it must never label unattempted calls as passes.

### 5. Later production-model gate

Terra and Sol are not dispatched by the free-development command. Before any paid run, record explicit cost approval. The later gate requires the same fixed cases, zero hard safety failures, 5,000 completed Terra interpretations, and 1,000 completed Sol critical/fallback interpretations.

## What automatically stops a campaign

A run is not ready if it suppresses urgent work, accepts invented measurements or evidence, guesses resident attribution, contaminates a baseline, creates duplicate open events, trusts invalid AI, lets AI failure block the deterministic path, teaches memory without explicit feedback, or treats acknowledgment as anomaly resolution.

The run saves its completed chunks and failure evidence before reporting the stop.

## Where results are saved

Every run writes an ignored local directory beneath:

```text
eval-results/monitoring/<run-id>/
```

It contains a manifest, compressed case and response records, failures, metrics, hard gates, a plain-English report, a checkpoint, and SHA-256 checksums. Credentials and authorization values are redacted before serialization. These generated files are evidence for local review and are not committed to Git.

## What passing means—and does not mean

Passing proves that the implemented software contracts behave consistently on the saved synthetic inputs and, for live runs, that the selected model obeyed the bounded output contract on those inputs.

It is not clinical validation. It does not prove real hardware detection quality, real-world alert rates, medical usefulness, or pilot readiness. Those require real hardware, representative environments and residents, clinical/product review, privacy and security review, and frontend convergence. Rishit can continue the frontend independently against the existing contracts while Akshar runs this backend lab.
