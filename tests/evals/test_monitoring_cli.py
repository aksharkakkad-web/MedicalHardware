from pathlib import Path

from evals.monitoring.cli import main


def test_cli_smoke_mode_returns_success_and_creates_run(tmp_path: Path) -> None:
    exit_code = main(["smoke", "--output-root", str(tmp_path), "--run-id", "cli_smoke"])

    assert exit_code == 0
    assert (tmp_path / "cli_smoke" / "report.md").is_file()


def test_cli_rejects_mass_mode_without_positive_case_count(tmp_path: Path) -> None:
    exit_code = main(["mass", "--output-root", str(tmp_path), "--cases", "0"])

    assert exit_code == 2
