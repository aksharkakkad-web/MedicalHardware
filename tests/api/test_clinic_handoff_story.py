from pathlib import Path
import subprocess
import sys

from backend.app.checkpoints.clinic_handoff import run_checkpoint


EXPECTED_LINES = [
    "PASS clinic overview composes residents, monitoring, and device state",
    "PASS active events filter and page in caregiver attention order",
    "PASS lifecycle moves resolved events into preserved history",
    "PASS delivery preferences never hide urgent dashboard events",
    "PASS feedback and staff edits preserve resident context",
    "PASS awareness and selective calibration history stay available",
    "PASS generated OpenAPI represents the real Product API",
    "PASS the complete clinic API story survives restart",
    "CHECKPOINT D READY",
]


def test_checkpoint_d_story_proves_the_complete_clinic_api_handoff() -> None:
    assert run_checkpoint() == EXPECTED_LINES


def test_founder_clinic_handoff_command_prints_plain_language_proof() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "backend.app.checkpoints.clinic_handoff"],
        cwd=Path(__file__).parents[2],
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert completed.stdout.splitlines() == EXPECTED_LINES

