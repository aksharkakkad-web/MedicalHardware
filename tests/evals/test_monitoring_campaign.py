import gzip
import json
from pathlib import Path

import pytest

from evals.monitoring.campaign import CampaignConfig, run_campaign


def test_smoke_campaign_runs_one_reference_case_per_cluster_and_saves_evidence(tmp_path: Path) -> None:
    result = run_campaign(
        CampaignConfig(mode="smoke", chunk_size=4, master_seed=7),
        output_root=tmp_path,
        run_id="smoke_test",
    )

    assert result.attempted == 12
    assert result.completed == 12
    assert result.passed is True
    assert (result.artifact_path / "report.md").is_file()
    metrics = json.loads((result.artifact_path / "metrics.json").read_text())
    assert metrics["case_count"] == 12


def test_mass_campaign_honors_case_count_times_passes(tmp_path: Path) -> None:
    result = run_campaign(
        CampaignConfig(mode="mass", case_count=6, passes=2, chunk_size=5, stop_on_hard_gate=False),
        output_root=tmp_path,
        run_id="mass_test",
    )

    assert result.attempted == 12
    assert result.completed + result.failed == 12
    checkpoint = json.loads((result.artifact_path / "checkpoint.json").read_text())
    assert checkpoint["next_index"] == 12


def test_balanced_mass_campaign_uses_only_compatible_perturbations(tmp_path: Path) -> None:
    result = run_campaign(
        CampaignConfig(mode="mass", case_count=250, passes=2, chunk_size=100),
        output_root=tmp_path,
        run_id="mass_compatible",
    )

    assert result.attempted == 500
    assert result.completed == 500
    assert result.failed == 0
    assert result.passed is True


@pytest.mark.parametrize(
    "config",
    [
        CampaignConfig(mode="not-real"),
        CampaignConfig(mode="mass", case_count=0),
        CampaignConfig(mode="smoke", chunk_size=0),
        CampaignConfig(mode="gemini", case_count=1, live_concurrency=9),
    ],
)
def test_campaign_rejects_unsafe_or_unbounded_configuration(config: CampaignConfig) -> None:
    with pytest.raises(ValueError):
        config.validate()


def test_gemini_mode_requires_an_explicit_provider(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="provider"):
        run_campaign(
            CampaignConfig(mode="gemini", case_count=1),
            output_root=tmp_path,
            run_id="gemini_missing",
        )


def test_gemini_campaign_records_provider_failure_as_failure_not_fallback_pass(tmp_path: Path) -> None:
    class FailingProvider:
        def interpret(self, request):
            raise RuntimeError("sanitized live failure")

    result = run_campaign(
        CampaignConfig(mode="gemini", case_count=1),
        output_root=tmp_path,
        run_id="gemini_failure",
        provider=FailingProvider(),
    )

    assert result.completed == 0
    assert result.failed == 1
    assert result.passed is False
    failure_text = gzip.decompress(
        (result.artifact_path / "failures.jsonl.gz").read_bytes()
    ).decode()
    assert "sanitized live failure" in failure_text


def test_full_canonical_review_set_completes_without_hard_failures(tmp_path: Path) -> None:
    result = run_campaign(
        CampaignConfig(mode="pr", chunk_size=30),
        output_root=tmp_path,
        run_id="canonical_complete",
    )

    assert result.attempted == 120
    assert result.completed == 120
    assert result.failed == 0
    assert result.passed is True
