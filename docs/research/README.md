# Monitoring Intelligence Research

**Archived:** August 28, 2026  
**Status:** Research input for Phase 5 design; not yet the normative product
specification.

This directory preserves the two completed Deep Research reports that inform
the contactless-monitoring intelligence architecture.

## Reports

1. [`2026-08-28-contactless-monitoring-v1-research.md`](2026-08-28-contactless-monitoring-v1-research.md)
   establishes the broad sensor, quality, fusion, baseline, event, validation,
   and hardware strategy.
2. [`2026-08-28-anomaly-filter-llm-replication-research.md`](2026-08-28-anomaly-filter-llm-replication-research.md)
   investigates reproducible anomaly approaches and proposes the detailed
   filter, evidence-packet, LLM-skill, deterministic-policy, and evaluation
   design.

## How to use these reports

- Treat cited findings as evidence and explicitly labeled numerical proposals
  as testable engineering hypotheses.
- Verify original source links and licenses before copying code, redistributing
  data, or using a dataset commercially.
- Convert accepted recommendations into the Phase 5 design and the normative
  product documents before implementation.
- If a report conflicts with `PRD.md`, `ARCHITECTURE.md`, `DATA_CONTRACT.md`, or
  another approved source-of-truth document, the approved source remains in
  force until the team intentionally updates it.

The preserved report text includes citation markers produced inside the
original Deep Research session. Those internal markers may not resolve outside
that session. The broad V1 report was exported without a durable bibliography,
so its claims must be independently verified before they are treated as
evidence. The later anomaly-filter/LLM report includes a direct primary-source
link section that covers the main overlapping systems and should be the
starting point for that verification; it is not a substitute for checking each
original source and license.

## Immediate next artifact

Create and approve the Phase 5 monitoring-intelligence design. It should turn
the research into explicit product decisions for:

- normalized features and per-purpose quality;
- baseline eligibility, maturity, freezing, recalibration, and adoption of a
  legitimate new normal;
- anomaly persistence, recovery, recurrence, and the boundary between anomaly
  episodes and caregiver events;
- the rich anomaly evidence packet;
- LLM skills, retrieval, structured output, validation, and outage fallback;
- deterministic urgent-safety behavior; and
- simulator scenarios, operational metrics, and acceptance gates.
