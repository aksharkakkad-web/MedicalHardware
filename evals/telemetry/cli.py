"""CLI for deterministic telemetry pipeline replay."""

from __future__ import annotations

import argparse
from pathlib import Path

from evals.telemetry.replay import run_replay
from evals.telemetry.scenarios import scenarios


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="telemetry-pipeline-replay")
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = run_replay(scenarios())
    result.write(args.output)
    print(
        f"telemetry replay: {result.summary.passed_cases}/"
        f"{result.summary.total_cases} passed"
    )
    print(args.output)
    return 0 if result.summary.failed_cases == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
