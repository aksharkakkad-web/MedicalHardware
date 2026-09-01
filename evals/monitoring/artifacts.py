"""Append-only, redacted, checksummed monitoring campaign artifacts."""

from dataclasses import dataclass, field
import gzip
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Iterable, Mapping


_SAFE_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
_SENSITIVE_KEYS = ("api_key", "authorization", "credential", "secret", "access_token")
_SECRET_PATTERNS = (
    re.compile(r"Bearer\s+[^\s\"']+", re.IGNORECASE),
    re.compile(r"AIza[A-Za-z0-9_-]{20,}"),
    re.compile(r"AQ\.[A-Za-z0-9_-]{16,}"),
)


def _redact_text(value: str) -> str:
    redacted = value
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def _redact(value: object, *, field_name: str = "") -> object:
    if any(marker in field_name.casefold() for marker in _SENSITIVE_KEYS):
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {str(key): _redact(item, field_name=str(key)) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    return value


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(_redact(value), sort_keys=True, separators=(",", ":"), default=str)
        + "\n"
    ).encode("utf-8")


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"artifact must contain an object: {path.name}")
    return value


@dataclass
class ArtifactRun:
    path: Path
    run_id: str
    completed_case_ids: set[str] = field(default_factory=set)

    @classmethod
    def create(
        cls,
        root: Path,
        *,
        run_id: str,
        manifest: Mapping[str, object],
    ) -> "ArtifactRun":
        if _SAFE_RUN_ID.fullmatch(run_id) is None:
            raise ValueError("run_id contains unsafe characters")
        path = Path(root).resolve() / run_id
        if path.exists() and any(path.iterdir()):
            raise ValueError(f"artifact run already exists: {run_id}")
        path.mkdir(parents=True, exist_ok=True)
        for directory in ("cases", "responses"):
            (path / directory).mkdir(exist_ok=True)
        run = cls(path=path, run_id=run_id)
        run.write_json(
            "manifest.json",
            {"schema_version": "1.0", "run_id": run_id, **dict(manifest)},
        )
        return run

    def write_json(self, relative_path: str, value: Mapping[str, object]) -> None:
        target = self.path / relative_path
        if not target.resolve().is_relative_to(self.path.resolve()):
            raise ValueError("artifact path escapes run directory")
        _atomic_write(target, _json_bytes(value))

    def append_chunk(
        self,
        kind: str,
        chunk_index: int,
        records: Iterable[Mapping[str, object]],
    ) -> Path:
        if kind not in {"cases", "responses", "failures"}:
            raise ValueError("artifact chunk kind is invalid")
        if chunk_index < 0:
            raise ValueError("chunk_index must not be negative")
        material = [dict(record) for record in records]
        if not material:
            raise ValueError("artifact chunk must contain records")
        if kind == "cases":
            ids = [record.get("case_id") for record in material]
            if any(not isinstance(case_id, str) or not case_id for case_id in ids):
                raise ValueError("case records require case_id")
            duplicate = set(ids) & self.completed_case_ids
            if len(ids) != len(set(ids)) or duplicate:
                raise ValueError("duplicate case_id completion")
            self.completed_case_ids.update(ids)
        directory = self.path / kind if kind != "failures" else self.path
        filename = (
            f"{chunk_index:08d}.jsonl.gz"
            if kind != "failures"
            else "failures.jsonl.gz"
        )
        target = directory / filename
        if target.exists():
            raise ValueError(f"artifact chunk already exists: {filename}")
        jsonl = b"".join(_json_bytes(record) for record in material)
        _atomic_write(target, gzip.compress(jsonl, compresslevel=6, mtime=0))
        return target

    def write_checkpoint(self, checkpoint: Mapping[str, object]) -> None:
        self.write_json("checkpoint.json", dict(checkpoint))

    def finalize(
        self,
        *,
        metrics: Mapping[str, object],
        hard_gates: Mapping[str, object],
        report: str,
        comparison: Mapping[str, object] | None = None,
    ) -> None:
        self.write_json("metrics.json", dict(metrics))
        self.write_json("hard-gates.json", dict(hard_gates))
        self.write_json("comparison.json", dict(comparison or {}))
        _atomic_write(self.path / "report.md", (_redact_text(report).rstrip() + "\n").encode())
        lines = []
        for file in sorted(path for path in self.path.rglob("*") if path.is_file() and path.name != "checksums.sha256"):
            digest = sha256(file.read_bytes()).hexdigest()
            lines.append(f"{digest}  {file.relative_to(self.path).as_posix()}")
        _atomic_write(self.path / "checksums.sha256", ("\n".join(lines) + "\n").encode())


def _validate_checksums(path: Path) -> None:
    checksum_path = path / "checksums.sha256"
    if not checksum_path.is_file():
        raise ValueError("artifact checksum file is missing")
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        file = path / relative
        if not file.is_file() or sha256(file.read_bytes()).hexdigest() != digest:
            raise ValueError(f"artifact checksum mismatch: {relative}")


def open_artifact_run(path: Path) -> ArtifactRun:
    path = Path(path).resolve()
    _validate_checksums(path)
    manifest = _read_json(path / "manifest.json")
    run_id = manifest.get("run_id")
    if not isinstance(run_id, str) or _SAFE_RUN_ID.fullmatch(run_id) is None:
        raise ValueError("artifact manifest run_id is invalid")
    checkpoint = _read_json(path / "checkpoint.json")
    completed = checkpoint.get("completed_case_ids", [])
    if not isinstance(completed, list) or any(not isinstance(item, str) for item in completed):
        raise ValueError("artifact checkpoint completed_case_ids is invalid")
    return ArtifactRun(path=path, run_id=run_id, completed_case_ids=set(completed))


__all__ = ["ArtifactRun", "open_artifact_run"]
