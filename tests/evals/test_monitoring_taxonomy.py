from evals.monitoring.scenarios import REQUIRED_SCENARIO_IDS
from evals.monitoring.taxonomy import (
    REQUIRED_CLUSTER_IDS,
    scenario_contracts,
    scenario_clusters,
)


def test_taxonomy_has_twelve_stable_product_clusters() -> None:
    clusters = scenario_clusters()

    assert tuple(cluster.cluster_id for cluster in clusters) == REQUIRED_CLUSTER_IDS
    assert len(clusters) == 12
    assert all(cluster.title and cluster.description for cluster in clusters)
    assert any(cluster.safety_critical for cluster in clusters)
    assert any(not cluster.safety_critical for cluster in clusters)


def test_every_existing_scenario_has_a_complete_expectation_contract() -> None:
    clusters = {cluster.cluster_id for cluster in scenario_clusters()}
    contracts = scenario_contracts()

    assert set(contracts) == set(REQUIRED_SCENARIO_IDS)
    assert {contract.cluster_id for contract in contracts.values()} == clusters
    for scenario_id, contract in contracts.items():
        assert contract.scenario_id == scenario_id
        assert contract.event_outcome
        assert contract.interpretation_outcome
        assert contract.feedback_outcome
        assert contract.forbidden_outcomes


def test_normal_variation_and_urgent_fall_have_explicit_opposite_boundaries() -> None:
    contracts = scenario_contracts()

    assert contracts["normal_variation"].event_outcome == "no_resident_work"
    assert "false_resident_alert" in contracts["normal_variation"].forbidden_outcomes
    assert contracts["fall_like"].event_outcome == "urgent_event_without_ai_wait"
    assert "urgent_event_suppressed" in contracts["fall_like"].forbidden_outcomes
