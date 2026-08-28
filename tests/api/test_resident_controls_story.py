from pathlib import Path
import subprocess
import sys

from backend.app.checkpoints.preferences_memory import run_checkpoint


EXPECTED_LINES = [
    "PASS unconfigured preferences are shown honestly",
    "PASS delivery choices never hide high or critical dashboard events",
    "PASS staff can add resident context with honest provenance",
    "PASS correction preserves and links the superseded context",
    "PASS retirement preserves all resident-memory history",
    "PASS preferences and resident memory survive restart",
    "CHECKPOINT C READY",
]


def test_checkpoint_c_story_proves_resident_controls_flow() -> None:
    assert run_checkpoint() == EXPECTED_LINES


def test_founder_resident_controls_checkpoint_prints_plain_language_proof() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "backend.app.checkpoints.preferences_memory"],
        cwd=Path(__file__).parents[2],
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert completed.stdout.splitlines() == EXPECTED_LINES
