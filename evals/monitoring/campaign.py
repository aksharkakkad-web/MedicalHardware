"""Small-to-large orchestration for monitoring intelligence evaluation."""

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
import platform
from typing import Callable, Iterable

from backend.app.ai.client import LLMClient
from evals.monitoring.artifacts import ArtifactRun
from evals.monitoring.generation import GeneratedCase, canonical_cases, generated_cases
from evals.monitoring.grading import CaseGrade, grade_case, summarize_grades
from evals.monitoring.scenarios import ScenarioExecution, run_scenario
from evals.monitoring.taxonomy import REQUIRED_CLUSTER_IDS
from evals.monitoring.transforms import transform_frames


_MODES = {"smoke", "pr", "mass", "gemini", "compare", "release"}
_LIVE_SCENARIOS = (
    "sustained_movement_change",
    "repetitive_movement",
    "inactivity",
    "unknown_anomaly",
)


@dataclass(frozen=True)
class CampaignConfig:
    mode: str
    case_count: int | None = None
    passes: int = 1
    master_seed: int = 20260901
    chunk_size: int = 100
    workers: int = 1
    live_concurrency: int = 1
    stop_on_hard_gate: bool = True

    def validate(self) -> "CampaignConfig":
        if self.mode not in _MODES:
            raise ValueError("campaign mode is invalid")
        if self.mode in {"mass", "gemini"} and (
            self.case_count is None or self.case_count < 1
        ):
            raise ValueError(f"{self.mode} mode requires a positive case_count")
        if self.case_count is not None and self.case_count < 1:
            raise ValueError("case_count must be positive")
        if not 1 <= self.passes <= 100:
            raise ValueError("passes must be between 1 and 100")
        if not 1 <= self.chunk_size <= 10_000:
            raise ValueError("chunk_size must be between 1 and 10000")
        if not 1 <= self.workers <= 64:
            raise ValueError("workers must be between 1 and 64")
        if not 1 <= self.live_concurrency <= 4:
            raise ValueError("live_concurrency must be between 1 and 4")
        if self.mode == "gemini" and self.workers != 1:
            raise ValueError("gemini mode uses explicit live_concurrency, not workers")
        return self


@dataclass(frozen=True)
class CampaignResult:
    run_id: str
    artifact_path: Path
    attempted: int
    completed: int
    failed: int
    passed: bool
    stopped_on_hard_gate: bool


ScenarioRunner = Callable[..., ScenarioExecution]


def _smoke_cases() -> tuple[GeneratedCase, ...]:
    references = [case for case in canonical_cases() if case.perturbation_kind == "reference"]
    return tuple(next(case for case in references if case.cluster_id == cluster) for cluster in REQUIRED_CLUSTER_IDS)


def _live_cases(case_count: int, master_seed: int) -> tuple[GeneratedCase, ...]:
    references = {
        case.base_scenario_id: case
        for case in canonical_cases()
        if case.perturbation_kind == "reference"
    }
    cases: list[GeneratedCase] = []
    for index in range(case_count):
        scenario_id = _LIVE_SCENARIOS[index % len(_LIVE_SCENARIOS)]
        base = references[scenario_id]
        seed = master_seed + index
        cases.append(
            replace(
                base,
                case_id=f"gemini_{index:08d}_{scenario_id}_{seed}",
                title=f"{base.title} — live interpretation {index + 1}",
                rationale="Fixed, saved live-provider interpretation case.",
                seed=seed,
                perturbation_pass=index // len(_LIVE_SCENARIOS),
            )
        )
    return tuple(cases)


def _cases(config: CampaignConfig) -> Iterable[GeneratedCase]:
    if config.mode == "smoke":
        return _smoke_cases()
    if config.mode == "pr":
        return canonical_cases()
    if config.mode == "mass":
        return generated_cases(
            case_count=config.case_count or 1,
            passes=config.passes,
            master_seed=config.master_seed,
        )
    if config.mode == "gemini":
        return _live_cases(config.case_count or 1, config.master_seed)
    raise ValueError(f"mode {config.mode} is handled by the comparison/release workflow")


def _case_record(case: GeneratedCase, execution: ScenarioExecution, grade: CaseGrade) -> dict[str, object]:
    return {
        "case_id": case.case_id,
        "case": asdict(case),
        "record": execution.record,
        "grade": asdict(grade),
    }


def _response_records(case: GeneratedCase, execution: ScenarioExecution) -> list[dict[str, object]]:
    return [
        {
            "case_id": case.case_id,
            "exchange_index": index,
            "request": asdict(request),
            "result": asdict(result),
        }
        for index, (request, result) in enumerate(
            zip(
                execution.interpretation_requests,
                execution.interpretation_results,
                strict=True,
            )
        )
    ]


def _report(
    *,
    config: CampaignConfig,
    attempted: int,
    completed: int,
    failures: list[dict[str, object]],
    summary: dict[str, object],
    stopped: bool,
) -> str:
    result = "PASS" if not failures and bool(summary.get("passed")) else "NOT READY"
    return f"""# Monitoring intelligence campaign

Result: **{result}**

- Mode: `{config.mode}`
- Attempted: {attempted}
- Completed and graded: {completed}
- Execution failures: {len(failures)}
- Hard safety failures: {summary.get('hard_failure_count', 0)}
- Stopped early on a hard gate: {str(stopped).lower()}

This is synthetic/software evaluation evidence. It is not clinical validation and does not prove real-hardware performance.
"""


def run_campaign(
    config: CampaignConfig,
    *,
    output_root: Path,
    run_id: str | None = None,
    provider: LLMClient | None = None,
    scenario_runner: ScenarioRunner = run_scenario,
) -> CampaignResult:
    config.validate()
    if config.mode == "gemini" and provider is None:
        raise ValueError("gemini mode requires an explicit provider")
    if config.mode != "gemini" and provider is not None:
        raise ValueError("a live provider is only allowed in gemini mode")
    run_id = run_id or datetime.now(timezone.utc).strftime(f"{config.mode}_%Y%m%dT%H%M%SZ")
    artifact = ArtifactRun.create(
        Path(output_root),
        run_id=run_id,
        manifest={
            "mode": config.mode,
            "config": asdict(config),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "python_version": platform.python_version(),
            "synthetic_only": True,
            "clinical_authority": False,
        },
    )
    attempted = 0
    grades: list[CaseGrade] = []
    failures: list[dict[str, object]] = []
    case_buffer: list[dict[str, object]] = []
    response_buffer: list[dict[str, object]] = []
    chunk_index = 0
    stopped = False

    def flush() -> None:
        nonlocal chunk_index
        if not case_buffer:
            return
        artifact.append_chunk("cases", chunk_index, tuple(case_buffer))
        if response_buffer:
            artifact.append_chunk("responses", chunk_index, tuple(response_buffer))
        case_buffer.clear()
        response_buffer.clear()
        chunk_index += 1
        artifact.write_checkpoint(
            {
                "attempted": attempted,
                "completed": len(grades),
                "failed": len(failures),
                "next_index": attempted,
                "next_chunk_index": chunk_index,
            }
        )

    for case in _cases(config):
        attempted += 1
        transform = lambda frames, spec=case.transform_spec: transform_frames(frames, spec)
        try:
            execution = scenario_runner(
                case.base_scenario_id,
                llm_client=provider,
                frame_transform=transform,
            )
            grade = grade_case(case, execution)
            grades.append(grade)
            case_buffer.append(_case_record(case, execution, grade))
            response_buffer.extend(_response_records(case, execution))
            if grade.hard_failures and config.stop_on_hard_gate:
                stopped = True
        except Exception as exc:  # campaign evidence must preserve isolated case failures
            failures.append(
                {
                    "case_id": case.case_id,
                    "base_scenario_id": case.base_scenario_id,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
            if config.stop_on_hard_gate:
                stopped = True
        if len(case_buffer) >= config.chunk_size or stopped:
            flush()
        if stopped:
            break
    flush()
    if not (artifact.path / "checkpoint.json").exists():
        artifact.write_checkpoint(
            {
                "attempted": attempted,
                "completed": len(grades),
                "failed": len(failures),
                "next_index": attempted,
                "next_chunk_index": chunk_index,
            }
        )
    if failures:
        artifact.append_chunk("failures", 0, failures)
    summary = summarize_grades(tuple(grades)) if grades else {
        "passed": False,
        "case_count": 0,
        "passed_case_count": 0,
        "hard_failure_count": 0,
        "hard_failures": {},
        "scores": {},
        "clusters": {},
    }
    passed = not failures and bool(summary["passed"]) and not stopped
    artifact.finalize(
        metrics={
            **summary,
            "attempted": attempted,
            "completed": len(grades),
            "execution_failure_count": len(failures),
        },
        hard_gates={
            "all_passed": passed,
            "stopped_on_hard_gate": stopped,
            "hard_failures": summary["hard_failures"],
        },
        report=_report(
            config=config,
            attempted=attempted,
            completed=len(grades),
            failures=failures,
            summary=summary,
            stopped=stopped,
        ),
    )
    return CampaignResult(
        run_id=run_id,
        artifact_path=artifact.path,
        attempted=attempted,
        completed=len(grades),
        failed=len(failures),
        passed=passed,
        stopped_on_hard_gate=stopped,
    )


__all__ = ["CampaignConfig", "CampaignResult", "run_campaign"]
