"""Small explicit command interface for data, trials, reports, and registry."""

import argparse
import json
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from tradinglab.constants import ASSETS, TEMPORAL_SPLITS
from tradinglab.dashboard_server import portfolio_payload
from tradinglab.data import (
    SnapshotStore,
    inspect_canonical_candles,
    load_candle_csv,
)
from tradinglab.data_source import RetrievalRequest
from tradinglab.experiments import (
    ExperimentRunner,
    TrialRequest,
    completed_experiment_rows,
    new_experiment_id,
    run_battery,
)
from tradinglab.registry import TrialRegistry
from tradinglab.reports import aggregate_report


def _project_root(value: str) -> Path:
    path = Path(value).resolve()
    if not (path / ".git").is_dir() or not (path / "pyproject.toml").is_file():
        raise argparse.ArgumentTypeError("project root must be the TradingLAB checkout")
    return path


def _parameters(value: str) -> dict[str, float | int]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError("parameters must be a JSON object") from exc
    if not isinstance(payload, dict) or any(
        not isinstance(item, (int, float)) or isinstance(item, bool)
        for item in payload.values()
    ):
        raise argparse.ArgumentTypeError("parameters must map names to numbers")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tradinglab", description="TradingLAB V0.1 local research interface"
    )
    parser.add_argument(
        "--project-root",
        type=_project_root,
        default=Path.cwd(),
        help="canonical repository root (default: current directory)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch = subparsers.add_parser("fetch", help="fetch an immutable yfinance dataset")
    fetch.add_argument("--symbols", nargs="+", choices=ASSETS, required=True)
    fetch.add_argument("--start", type=date.fromisoformat, required=True)
    fetch.add_argument("--end-exclusive", type=date.fromisoformat, required=True)

    validate = subparsers.add_parser("validate-dataset", help="validate a snapshot")
    validate.add_argument("--dataset-id", required=True)

    validate_candles = subparsers.add_parser(
        "validate-candle-file",
        help="validate a provider-neutral OHLCV CSV without network access",
    )
    validate_candles.add_argument("--path", type=Path, required=True)
    validate_candles.add_argument("--symbol", default=None)

    run = subparsers.add_parser("run", help="run one explicit registered trial")
    run.add_argument("--spec", type=Path, required=True)
    run.add_argument("--dataset-id", required=True)
    run.add_argument("--asset", choices=ASSETS, required=True)
    run.add_argument("--split", choices=tuple(TEMPORAL_SPLITS), required=True)
    run.add_argument("--parameters-json", type=_parameters, required=True)
    run.add_argument("--friction-bps", type=int, choices=(0, 5, 10, 25), required=True)
    run.add_argument(
        "--purpose",
        choices=(
            "primary",
            "parameter_sensitivity",
            "friction_sensitivity",
            "debug",
            "synthetic",
        ),
        required=True,
    )
    run.add_argument("--experiment-id", default=None)
    run.add_argument(
        "--benchmark-trial-id",
        default=None,
        help="matching completed Buy & Hold trial required by non-control strategies",
    )

    battery = subparsers.add_parser(
        "run-battery", help="run the closed cross-asset robustness battery"
    )
    battery.add_argument("--dataset-id", required=True)
    battery.add_argument(
        "--splits", nargs="+", choices=tuple(TEMPORAL_SPLITS), required=True
    )
    battery.add_argument("--confirm-holdout", action="store_true")
    battery.add_argument(
        "--resume-holdout",
        action="store_true",
        help="resume only missing trials after an interrupted authorized holdout",
    )
    battery.add_argument(
        "--experiment-id",
        default=None,
        help="explicit existing experiment identity for staged continuation",
    )

    report = subparsers.add_parser("report", help="generate a new aggregate report")
    report.add_argument("--experiment-id", required=True)

    registry = subparsers.add_parser("registry", help="inspect append-only events")
    registry.add_argument("--limit", type=int, default=20)

    reproduce = subparsers.add_parser(
        "reproduce", help="verify canonical analytical reproduction"
    )
    reproduce.add_argument("--trial-id", required=True)

    portfolio = subparsers.add_parser(
        "run-portfolio", help="run the broker-neutral V0.6 reference portfolio"
    )
    portfolio.add_argument("--dataset-id", required=True)
    portfolio.add_argument(
        "--split", choices=("development", "validation_oos"), required=True
    )
    portfolio.add_argument(
        "--allocation-method",
        choices=("equal_weight", "inverse_vol"),
        default="equal_weight",
    )
    portfolio.add_argument(
        "--friction-bps", type=int, choices=(0, 5, 10, 25), default=5
    )
    portfolio.add_argument(
        "--output",
        type=Path,
        default=None,
        help="optional local JSON path for importing the result into the site",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    project_root = Path(args.project_root).resolve()
    snapshots = SnapshotStore(project_root / "data" / "snapshots")
    registry = TrialRegistry(project_root / "registry" / "events.jsonl")
    if args.command == "fetch":
        manifest = snapshots.fetch_dataset(
            RetrievalRequest(
                symbols=tuple(args.symbols),
                start=args.start,
                end_exclusive=args.end_exclusive,
            )
        )
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return 0
    if args.command == "validate-dataset":
        print(
            json.dumps(
                snapshots.validate_dataset(args.dataset_id), indent=2, sort_keys=True
            )
        )
        return 0
    if args.command == "validate-candle-file":
        candle_rows = load_candle_csv(args.path.resolve(), symbol=args.symbol)
        print(
            json.dumps(
                {
                    "path": str(args.path.resolve()),
                    "symbol": args.symbol,
                    "quality": inspect_canonical_candles(candle_rows),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.command == "run":
        runner = ExperimentRunner(project_root)
        outcome = runner.run_trial(
            TrialRequest(
                spec_path=args.spec.resolve(),
                dataset_id=args.dataset_id,
                asset=args.asset,
                split_key=args.split,
                parameters=args.parameters_json,
                friction_bps=args.friction_bps,
                purpose=args.purpose,
                experiment_id=args.experiment_id or new_experiment_id(),
                benchmark_trial_id=args.benchmark_trial_id,
            )
        )
        print(json.dumps(outcome.manifest, indent=2, sort_keys=True))
        return 0
    if args.command == "run-battery":
        experiment_id, outcomes, report_dir = run_battery(
            project_root,
            dataset_id=args.dataset_id,
            split_keys=tuple(args.splits),
            confirm_holdout=bool(args.confirm_holdout),
            experiment_id=args.experiment_id,
            resume_holdout=bool(args.resume_holdout),
        )
        print(
            json.dumps(
                {
                    "experiment_id": experiment_id,
                    "trial_count": len(outcomes),
                    "report_dir": str(report_dir),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.command == "report":
        rows = completed_experiment_rows(project_root, registry, args.experiment_id)
        output = aggregate_report(
            rows,
            project_root / "artifacts" / "reports",
            args.experiment_id,
            registry.events(),
        )
        print(output)
        return 0
    if args.command == "registry":
        events = registry.events()
        print(json.dumps(events[-args.limit :], indent=2, sort_keys=True))
        return 0
    if args.command == "reproduce":
        result = ExperimentRunner(project_root).reproduce(args.trial_id)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["reproduced"] else 1
    if args.command == "run-portfolio":
        result = portfolio_payload(
            project_root,
            dataset_id=args.dataset_id,
            split_key=args.split,
            allocation_method=args.allocation_method,
            friction_bps=args.friction_bps,
        )
        serialized = json.dumps(result, indent=2, sort_keys=True)
        if args.output is not None:
            output_path = args.output.resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(serialized + "\n", encoding="utf-8")
        print(serialized)
        return 0
    raise AssertionError("unreachable command")


if __name__ == "__main__":
    raise SystemExit(main())
