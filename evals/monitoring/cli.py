"""Command-line entry point for monitoring evaluation campaigns."""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

from backend.app.ai.gemini import GeminiLLMClient, GeminiStructuredAnalysisClient
from evals.monitoring.campaign import CampaignConfig, run_campaign
from evals.monitoring.multi_agent_campaign import run_multi_agent_campaign


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="monitoring-intelligence-lab")
    parser.add_argument("mode", choices=("smoke", "pr", "mass", "gemini", "compare", "release", "multi-agent-mass", "multi-agent-gemini"))
    parser.add_argument("--cases", type=int)
    parser.add_argument("--passes", type=int, default=1)
    parser.add_argument("--seed", type=int, default=20260901)
    parser.add_argument("--chunk-size", type=int, default=100)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--live-concurrency", type=int, default=1)
    parser.add_argument("--continue-on-failure", action="store_true")
    parser.add_argument("--output-root", type=Path, default=Path("eval-results/monitoring"))
    parser.add_argument("--run-id")
    return parser


def _local_key() -> str | None:
    path = Path(".env.local")
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("GEMINI_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    try:
        args = parser.parse_args(argv)
        if args.mode in {"multi-agent-mass", "multi-agent-gemini"}:
            case_count = args.cases or (120 if args.mode == "multi-agent-mass" else 1)
            provider = (
                GeminiStructuredAnalysisClient(api_key=_local_key())
                if args.mode == "multi-agent-gemini"
                else None
            )
            run_id = args.run_id or (
                args.mode.replace("-", "_")
                + "_"
                + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            )
            multi_result = run_multi_agent_campaign(
                case_count=case_count,
                output_root=args.output_root,
                run_id=run_id,
                client=provider,
            )
            print(
                f"{run_id}: attempted={multi_result.attempted} "
                f"completed={multi_result.completed} failed={multi_result.failed}"
            )
            print(multi_result.path)
            return 0 if multi_result.passed else 1
        config = CampaignConfig(
            mode=args.mode,
            case_count=args.cases,
            passes=args.passes,
            master_seed=args.seed,
            chunk_size=args.chunk_size,
            workers=args.workers,
            live_concurrency=args.live_concurrency,
            stop_on_hard_gate=not args.continue_on_failure,
        )
        provider = GeminiLLMClient(api_key=_local_key()) if args.mode == "gemini" else None
        result = run_campaign(
            config,
            output_root=args.output_root,
            run_id=args.run_id,
            provider=provider,
        )
    except (ValueError, OSError) as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2
    print(f"{result.run_id}: attempted={result.attempted} completed={result.completed} failed={result.failed}")
    print(result.artifact_path)
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
