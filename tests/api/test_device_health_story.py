from pathlib import Path
import subprocess
import sys

from backend.app.checkpoints.device_health import run_checkpoint


EXPECTED_LINES = [
    "PASS device is assigned to the resident room",
    "PASS online device allows current monitoring",
    "PASS buffering and offline states stop current monitoring",
    "PASS source limitations remain visible",
    "PASS online recovery restores current monitoring",
    "PASS assignment and health history survive restart",
    "CHECKPOINT B READY",
]


def test_checkpoint_b_story_proves_complete_device_health_flow() -> None:
    assert run_checkpoint() == EXPECTED_LINES


def test_founder_device_checkpoint_prints_plain_language_proof() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "backend.app.checkpoints.device_health"],
        cwd=Path(__file__).parents[2],
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert completed.stdout.splitlines() == EXPECTED_LINES
