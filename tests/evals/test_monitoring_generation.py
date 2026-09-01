from itertools import islice

from evals.monitoring.generation import canonical_cases, generated_cases
from evals.monitoring.taxonomy import REQUIRED_CLUSTER_IDS


def test_canonical_set_has_five_reviewable_variants_per_original_scenario() -> None:
    cases = canonical_cases()

    assert len(cases) == 120
    assert len({case.case_id for case in cases}) == 120
    assert {case.cluster_id for case in cases} == set(REQUIRED_CLUSTER_IDS)
    assert all(case.title and case.rationale for case in cases)
    counts: dict[str, int] = {}
    for case in cases:
        counts[case.base_scenario_id] = counts.get(case.base_scenario_id, 0) + 1
    assert set(counts.values()) == {5}


def test_generated_cases_are_lazy_balanced_and_reproducible() -> None:
    first = tuple(islice(generated_cases(case_count=500, passes=10, master_seed=44), 500))
    second = tuple(islice(generated_cases(case_count=500, passes=10, master_seed=44), 500))

    assert first == second
    assert len({case.case_id for case in first}) == 500
    cluster_counts = {cluster: sum(case.cluster_id == cluster for case in first) for cluster in REQUIRED_CLUSTER_IDS}
    assert max(cluster_counts.values()) - min(cluster_counts.values()) <= 1
    assert {case.perturbation_kind for case in first} >= {
        "timing",
        "numeric_jitter",
        "quality_boundary",
        "source_dropout",
        "input_replay",
    }


def test_case_identity_changes_with_seed_or_pass() -> None:
    seed_a = next(generated_cases(case_count=1, passes=1, master_seed=1))
    seed_b = next(generated_cases(case_count=1, passes=1, master_seed=2))
    pass_b = tuple(generated_cases(case_count=1, passes=2, master_seed=1))[1]

    assert seed_a.case_id != seed_b.case_id
    assert seed_a.case_id != pass_b.case_id
