from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_intelligence_lab_doc_names_the_complete_product_flow_and_limits() -> None:
    content = (ROOT / "docs" / "MONITORING_INTELLIGENCE_LAB.md").read_text()

    assert "signals → aligned evidence → anomaly filter" in content
    assert "AI explanation → dashboard action → feedback → guarded resident memory" in content
    assert "not clinical validation" in content
    assert "real hardware" in content
    assert "frontend" in content


def test_documented_campaign_commands_use_real_modes() -> None:
    content = (ROOT / "docs" / "MONITORING_INTELLIGENCE_LAB.md").read_text()

    for mode in ("smoke", "pr", "mass", "gemini"):
        assert f"python3 -m evals.monitoring.cli {mode}" in content
    assert "--cases 100000 --passes 10" in content
    assert "--cases 25000" in content
