from __future__ import annotations

import argparse
import json
from pathlib import Path

from mythings.engine import ClaudeCLIEngine, Engine, NoopEngine
from mythings.ledger import Ledger

from mysignalprocessor.tool import SignalProcessor

_ENGINE_NAMES = ("noop", "claude-cli")


def build_engine(name: str, *, model: str | None = None) -> Engine:
    if name == "claude-cli":
        return ClaudeCLIEngine(model=model)
    return NoopEngine()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mysignalprocessor",
        description="Compute an FFT/statistics read on a local CSV signal and narrate it.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    analyze = sub.add_parser("analyze", help="analyze one CSV signal file")
    analyze.add_argument("--file", required=True)
    analyze.add_argument("--sample-rate", type=float, default=1.0)
    analyze.add_argument("--repo", help="GitHub slug owner/name, needed for --comment")
    analyze.add_argument("--issue", type=int, help="issue to comment on with --comment")
    analyze.add_argument(
        "--comment", action="store_true", help="also post the analysis to the issue"
    )
    analyze.add_argument("--json", action="store_true")
    analyze.add_argument("--ledger", type=Path, default=Path(".mythings/ledger.jsonl"))
    analyze.add_argument("--engine", choices=sorted(_ENGINE_NAMES), default="noop")
    analyze.add_argument("--engine-model", help="model for --engine claude-cli")

    args = parser.parse_args(argv)
    engine = build_engine(args.engine, model=args.engine_model)

    processor = SignalProcessor(
        ledger=Ledger(args.ledger),
        repo=args.repo,
        engine=engine,
    )
    result = processor.analyze(
        args.file,
        sample_rate=args.sample_rate,
        issue=args.issue,
        comment=args.comment,
    )

    if args.json:
        print(
            json.dumps(
                {
                    "outcome": result.outcome,
                    "file": result.file,
                    "n_samples": result.n_samples,
                    "sample_rate": result.sample_rate,
                    "dominant_freq_hz": result.dominant_freq_hz,
                    "mean": result.mean,
                    "std": result.std,
                    "peak": result.peak,
                    "narrative": result.narrative,
                    "suggested_action": result.suggested_action,
                    "detail": result.detail,
                    "comment_url": result.comment_url,
                }
            )
        )
    else:
        print(result.narrative or result.detail)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
