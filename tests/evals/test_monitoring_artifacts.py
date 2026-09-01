import gzip
import json
from pathlib import Path

import pytest

from evals.monitoring.artifacts import ArtifactRun, open_artifact_run


def test_artifact_run_writes_redacted_atomic_chunks_and_checksums(tmp_path: Path) -> None:
    run = ArtifactRun.create(
        tmp_path,
        run_id="run_001",
        manifest={"mode": "smoke", "api_key": "must-never-appear"},
    )
    run.append_chunk(
        "cases",
        0,
        [{"case_id": "case_1", "authorization": "Bearer secret", "result": "pass"}],
    )
    run.write_checkpoint({"completed_case_ids": ["case_1"], "completed": 1})
    run.finalize(metrics={"passed": 1}, hard_gates={"all_passed": True}, report="# Passed\n")

    chunk = next((tmp_path / "run_001" / "cases").glob("*.jsonl.gz"))
    content = gzip.decompress(chunk.read_bytes()).decode()
    assert "must-never-appear" not in content
    assert "Bearer secret" not in content
    assert "[REDACTED]" in content
    assert (tmp_path / "run_001" / "checksums.sha256").is_file()
    assert not list((tmp_path / "run_001").rglob("*.tmp"))


def test_artifact_run_resumes_only_after_checksum_validation(tmp_path: Path) -> None:
    run = ArtifactRun.create(tmp_path, run_id="run_002", manifest={"mode": "mass"})
    run.append_chunk("cases", 0, [{"case_id": "case_1"}])
    run.write_checkpoint({"completed_case_ids": ["case_1"], "completed": 1})
    run.finalize(metrics={"passed": 1}, hard_gates={"all_passed": True}, report="done")

    resumed = open_artifact_run(tmp_path / "run_002")
    assert resumed.completed_case_ids == {"case_1"}

    chunk = next((tmp_path / "run_002" / "cases").glob("*.jsonl.gz"))
    chunk.write_bytes(chunk.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="checksum"):
        open_artifact_run(tmp_path / "run_002")


def test_duplicate_case_completion_is_rejected(tmp_path: Path) -> None:
    run = ArtifactRun.create(tmp_path, run_id="run_003", manifest={"mode": "smoke"})
    run.append_chunk("cases", 0, [{"case_id": "case_1"}])

    with pytest.raises(ValueError, match="duplicate case_id"):
        run.append_chunk("cases", 1, [{"case_id": "case_1"}])


def test_manifest_is_valid_json_and_contains_schema_version(tmp_path: Path) -> None:
    ArtifactRun.create(tmp_path, run_id="run_004", manifest={"mode": "pr"})
    manifest = json.loads((tmp_path / "run_004" / "manifest.json").read_text())

    assert manifest["schema_version"] == "1.0"
    assert manifest["run_id"] == "run_004"
