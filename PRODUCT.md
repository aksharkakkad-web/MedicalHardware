# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Care-facility staff who monitor several assigned residents and need to understand what requires attention quickly. This is inferred from the repository source-of-truth documents because the user asked for unattended execution.

## Product Purpose

Adaptive Care gives staff a privacy-preserving view of resident monitoring, explains why an event was raised, makes uncertainty visible, and supports a short acknowledge, check, resolve, and feedback workflow.

## Positioning

The product combines passive non-camera sensing, personal baselines, selective AI interpretation, and caregiver feedback. The interface must present this as monitoring support, not diagnosis or a replacement for staff judgment.

## Operating Context

Staff use the clinic dashboard as an operational console across multiple rooms. They begin with the most urgent unresolved work, open a resident or event, review evidence and data quality, take the next staff action, and preserve the outcome for later review.

## Capabilities and Constraints

- Clinic and home experiences are separate products.
- V1 supports one assigned resident per monitored room.
- Low-quality or ambiguous data must appear limited or unavailable, never precise.
- AI explains already-created events and cannot suppress deterministic warnings.
- Event history is permanent; recurrences become linked events.
- Current UI data is synthetic and must remain clearly labeled.
- The frontend uses the typed `MonitoringClient` boundary so mock and real APIs remain interchangeable.
- No clinical diagnosis, invented threshold, real resident data, or unsupported performance claim may appear.

## Brand Commitments

The product name is Adaptive Care. The requested direction is exceptionally clean, calm, professional, and Apple-like: clarity, restraint, native-feeling controls, careful typography, and color reserved for meaning.

## Evidence on Hand

Repository requirements, architecture, data contracts, backend handoff documents, contract-valid mock fixtures, and the current clinic dashboard implementation. There are no approved customer logos, testimonials, clinical claims, or real resident records.

## Product Principles

- Put the next caregiver decision before secondary detail.
- Make confidence, ambiguity, and device failure impossible to miss.
- Keep normal rooms quiet and attention states specific.
- Reveal detail progressively instead of presenting every field at once.
- Make every action fast, reversible where possible, and visibly recorded.

## Accessibility & Inclusion

The interface must remain understandable without color alone, support keyboard navigation and zoomed text, provide clear focus states, respect reduced motion, and keep interactive targets comfortably sized.
