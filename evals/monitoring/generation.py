"""Lazy, deterministic generation of balanced monitoring evaluation cases."""

from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json
from random import Random
from typing import Iterator

from evals.monitoring.scenarios import scenario_definitions
from evals.monitoring.taxonomy import (
    REQUIRED_CLUSTER_IDS,
    ScenarioExpectation,
    scenario_contracts,
)
from evals.monitoring.transforms import FrameTransformSpec


@dataclass(frozen=True)
class GeneratedCase:
    case_id: str
    title: str
    rationale: str
    base_scenario_id: str
    canonical_id: str
    cluster_id: str
    seed: int
    perturbation_pass: int
    perturbation_kind: str
    transform_spec: FrameTransformSpec
    expectation: ScenarioExpectation

    def identity_payload(self) -> dict[str, object]:
        return {
            "base_scenario_id": self.base_scenario_id,
            "canonical_id": self.canonical_id,
            "cluster_id": self.cluster_id,
            "seed": self.seed,
            "perturbation_pass": self.perturbation_pass,
            "perturbation_kind": self.perturbation_kind,
            "transform_spec": asdict(self.transform_spec),
        }


_CANONICAL_VARIANTS = (
    ("reference", "Reference behavior", "The original founder-approved behavior with no perturbation."),
    ("earlier", "Earlier in the day", "The same behavior at a different time to avoid rigid schedule assumptions."),
    ("later", "Later in the day", "The same behavior later to cover ordinary day-to-day timing variance."),
    ("light_jitter", "Light measurement variation", "Small deterministic numeric variation within the same product story."),
    ("stronger_jitter", "Stronger measurement variation", "A wider but still bounded variation near the expected behavior."),
)


def _canonical_transform(
    variant: str,
    seed: int,
    *,
    cluster_id: str,
) -> FrameTransformSpec:
    if variant == "earlier":
        return FrameTransformSpec(seed=seed, time_shift_seconds=-3_600)
    if variant == "later":
        return FrameTransformSpec(seed=seed, time_shift_seconds=5_400)
    if variant == "light_jitter":
        if cluster_id in {"fall_like", "event_lifecycle", "ai_provider_failure"}:
            return FrameTransformSpec(seed=seed, time_shift_seconds=300)
        return FrameTransformSpec(seed=seed, numeric_jitter=0.01)
    if variant == "stronger_jitter":
        if cluster_id in {"fall_like", "event_lifecycle", "ai_provider_failure"}:
            return FrameTransformSpec(seed=seed, time_shift_seconds=600)
        return FrameTransformSpec(seed=seed, numeric_jitter=0.03)
    return FrameTransformSpec(seed=seed)


def canonical_cases() -> tuple[GeneratedCase, ...]:
    contracts = scenario_contracts()
    cases: list[GeneratedCase] = []
    for scenario_index, definition in enumerate(scenario_definitions()):
        contract = contracts[definition.scenario_id]
        for variant_index, (variant, title, rationale) in enumerate(_CANONICAL_VARIANTS):
            seed = scenario_index * len(_CANONICAL_VARIANTS) + variant_index
            canonical_id = f"{definition.scenario_id}__{variant}"
            expectation = contract
            if (
                variant in {"light_jitter", "stronger_jitter"}
                and contract.event_outcome in {"caregiver_event", "deterministic_fallback_event"}
                and contract.cluster_id not in {"ai_provider_failure"}
            ):
                expectation = replace(
                    contract,
                    event_outcome="boundary_behavior_recorded",
                    interpretation_outcome="boundary_may_abstain",
                )
            cases.append(
                GeneratedCase(
                    case_id=canonical_id,
                    title=f"{definition.intent}: {title}",
                    rationale=rationale,
                    base_scenario_id=definition.scenario_id,
                    canonical_id=canonical_id,
                    cluster_id=contract.cluster_id,
                    seed=seed,
                    perturbation_pass=0,
                    perturbation_kind=variant,
                    transform_spec=_canonical_transform(
                        variant,
                        seed,
                        cluster_id=contract.cluster_id,
                    ),
                    expectation=expectation,
                )
            )
    return tuple(cases)


def _balanced_bases() -> tuple[GeneratedCase, ...]:
    by_cluster = {
        cluster_id: [case for case in canonical_cases() if case.cluster_id == cluster_id]
        for cluster_id in REQUIRED_CLUSTER_IDS
    }
    positions = {cluster_id: 0 for cluster_id in REQUIRED_CLUSTER_IDS}
    ordered: list[GeneratedCase] = []
    while any(positions[key] < len(by_cluster[key]) for key in REQUIRED_CLUSTER_IDS):
        for cluster_id in REQUIRED_CLUSTER_IDS:
            position = positions[cluster_id]
            cases = by_cluster[cluster_id]
            if position < len(cases):
                ordered.append(cases[position])
                positions[cluster_id] += 1
    return tuple(ordered)


def _stable_seed(master_seed: int, timeline_index: int, pass_index: int) -> int:
    digest = sha256(f"{master_seed}:{timeline_index}:{pass_index}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def _compatible_kind(kind: str, base: GeneratedCase) -> str:
    if base.cluster_id in {"ai_provider_failure", "event_lifecycle"} and kind in {
        "numeric_jitter",
        "quality_boundary",
        "input_replay",
    }:
        return "timing"
    if base.base_scenario_id in {
        "preentered_new_behavior",
        "post_event_new_behavior",
    } and kind == "input_replay":
        return "timing"
    return kind


def _mass_transform(kind: str, seed: int) -> FrameTransformSpec:
    random = Random(seed)
    if kind == "timing":
        return FrameTransformSpec(
            seed=seed,
            time_shift_seconds=random.choice((-900, -300, 300, 900)),
        )
    if kind == "numeric_jitter":
        return FrameTransformSpec(seed=seed, numeric_jitter=random.uniform(0.005, 0.05))
    if kind == "quality_boundary":
        return FrameTransformSpec(seed=seed, downgrade_quality=True)
    if kind == "source_dropout":
        return FrameTransformSpec(seed=seed, drop_sources=("csi",))
    return FrameTransformSpec(seed=seed, duplicate_last_frame=True)


def _case_id(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return f"generated_{sha256(canonical.encode()).hexdigest()[:24]}"


def generated_cases(
    *,
    case_count: int,
    passes: int,
    master_seed: int = 20260901,
) -> Iterator[GeneratedCase]:
    """Yield ``case_count × passes`` descriptors without retaining the campaign."""

    if case_count < 1:
        raise ValueError("case_count must be positive")
    if passes < 1:
        raise ValueError("passes must be positive")
    bases_by_cluster = {
        cluster_id: tuple(
            case for case in canonical_cases() if case.cluster_id == cluster_id
        )
        for cluster_id in REQUIRED_CLUSTER_IDS
    }
    kinds = ("timing", "numeric_jitter", "quality_boundary", "source_dropout", "input_replay")
    for pass_index in range(passes):
        for timeline_index in range(case_count):
            cluster_id = REQUIRED_CLUSTER_IDS[timeline_index % len(REQUIRED_CLUSTER_IDS)]
            cluster_cases = bases_by_cluster[cluster_id]
            cluster_position = timeline_index // len(REQUIRED_CLUSTER_IDS)
            base = cluster_cases[cluster_position % len(cluster_cases)]
            seed = _stable_seed(master_seed, timeline_index, pass_index)
            requested_kind = kinds[(timeline_index + pass_index) % len(kinds)]
            kind = _compatible_kind(requested_kind, base)
            transform = _mass_transform(kind, seed)
            expectation = base.expectation
            if (
                kind in {"numeric_jitter", "quality_boundary"}
                and expectation.event_outcome != "no_resident_work"
            ):
                expectation = replace(
                    expectation,
                    event_outcome="boundary_behavior_recorded",
                    interpretation_outcome="boundary_may_abstain",
                )
            identity = {
                "canonical_id": base.canonical_id,
                "master_seed": master_seed,
                "timeline_index": timeline_index,
                "pass_index": pass_index,
                "kind": kind,
                "seed": seed,
                "transform": asdict(transform),
            }
            yield GeneratedCase(
                case_id=_case_id(identity),
                title=f"{base.title} — generated {kind} pass {pass_index + 1}",
                rationale=f"Deterministic {kind.replace('_', ' ')} perturbation for mass evaluation.",
                base_scenario_id=base.base_scenario_id,
                canonical_id=base.canonical_id,
                cluster_id=base.cluster_id,
                seed=seed,
                perturbation_pass=pass_index,
                perturbation_kind=kind,
                transform_spec=transform,
                expectation=expectation,
            )


__all__ = ["GeneratedCase", "canonical_cases", "generated_cases"]
