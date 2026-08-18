"""Immutable registered historical trials and the closed robustness battery."""

import json
import sys
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from tradinglab.adapter import (
    ENGINE_NAME,
    ENGINE_VERSION,
    AdapterResult,
    BacktestingPyAdapter,
)
from tradinglab.constants import (
    ANNUALIZATION_SESSIONS,
    ASSETS,
    INITIAL_CASH,
    NORMALIZATION_VERSION,
    PRICE_BASIS_ID,
    RISK_FREE_RATE,
    TEMPORAL_SPLITS,
    TemporalSplit,
)
from tradinglab.data import SnapshotStore
from tradinglab.hashing import canonical_json_bytes, sha256_bytes
from tradinglab.metrics import benchmark_deltas, canonical_metrics
from tradinglab.registry import TrialRegistry, code_provenance, utc_now
from tradinglab.reports import aggregate_report, plot_equity, render_trial_report
from tradinglab.specs import StrategySpec, load_spec, specification_hash
from tradinglab.strategies import primary_parameters

Purpose = Literal[
    "primary", "parameter_sensitivity", "friction_sensitivity", "debug", "synthetic"
]
ALLOWED_PURPOSES = {
    "primary",
    "parameter_sensitivity",
    "friction_sensitivity",
    "debug",
    "synthetic",
}


@dataclass(frozen=True)
class TrialRequest:
    spec_path: Path
    dataset_id: str
    asset: str
    split_key: str
    parameters: dict[str, float | int]
    friction_bps: int
    purpose: Purpose
    experiment_id: str
    benchmark_metrics: dict[str, Any] | None = None


@dataclass(frozen=True)
class TrialOutcome:
    trial_id: str
    experiment_id: str
    artifact_dir: Path
    metrics: dict[str, Any]
    manifest: dict[str, Any]


def new_experiment_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"exp_{stamp}_{uuid.uuid4().hex[:10]}"


def new_trial_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    return f"trial_{stamp}_{uuid.uuid4().hex[:10]}"


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(
        index=False,
        lineterminator="\n",
        float_format="%.17g",
        na_rep="",
    ).encode()


class ExperimentRunner:
    """Bind specifications, code, data, assumptions, ledgers, and reports."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.snapshots = SnapshotStore(project_root / "data" / "snapshots")
        self.registry = TrialRegistry(project_root / "registry" / "events.jsonl")
        self.adapter = BacktestingPyAdapter()

    def run_trial(self, request: TrialRequest) -> TrialOutcome:
        spec = load_spec(request.spec_path)
        split = self._validate_trial_request(request, spec)
        dataset_manifest = self.snapshots.load_manifest(request.dataset_id)
        if request.asset not in dataset_manifest["symbols"]:
            raise ValueError("trial asset is not present in the dataset")
        provenance = code_provenance(self.project_root)
        trial_id = new_trial_id()
        artifact_dir = self.project_root / "artifacts" / "trials" / trial_id
        common = {
            "trial_id": trial_id,
            "experiment_id": request.experiment_id,
            "purpose": request.purpose,
            "strategy_id": spec.strategy_id,
            "strategy_version": spec.strategy_version,
            "spec_hash": specification_hash(spec),
            **provenance,
            "engine_name": ENGINE_NAME,
            "engine_version": ENGINE_VERSION,
            "dataset_id": request.dataset_id,
            "dataset_checksum": dataset_manifest["dataset_checksum"],
            "asset_dataset_checksum": dataset_manifest["checksums"][request.asset][
                "normalized"
            ],
            "asset": request.asset,
            "evaluation_period": {
                "start": split.start.isoformat(),
                "end": split.end.isoformat(),
            },
            "temporal_split": split.key,
            "parameters": request.parameters,
            "friction_scenario": f"{request.friction_bps}_bps_per_side",
            "friction_bps": request.friction_bps,
            "price_basis": PRICE_BASIS_ID,
            "execution_assumptions": {
                "decision": "confirmed close t with information through t",
                "fill": "next valid XNYS normalized open",
                "integer_shares": True,
                "long_only": True,
                "leverage": 1,
                "cash_interest": 0,
                "initial_cash_usd": INITIAL_CASH,
            },
            "terminal_convention": (
                "open positions marked to final normalized Close; no forced exit or "
                "fictional exit friction"
            ),
            "artifact_paths": {
                "directory": str(artifact_dir.relative_to(self.project_root))
            },
            "notes": "historical single-asset research trial",
        }
        self.registry.append(
            {
                **common,
                "event_type": "started",
                "created_at": utc_now(),
                "status": "started",
            }
        )
        artifact_dir.mkdir(parents=True, exist_ok=False)
        try:
            data = self.snapshots.load_normalized(request.dataset_id, request.asset)
            result = self.adapter.run(
                data=data,
                spec=spec,
                parameters=request.parameters,
                split=split,
                friction_bps=request.friction_bps,
            )
            metrics = canonical_metrics(result.equity_curve, result.trades)
            if request.benchmark_metrics is not None:
                deltas = benchmark_deltas(metrics, request.benchmark_metrics)
            elif spec.strategy_id == "BUY_HOLD_V1":
                deltas = benchmark_deltas(metrics, metrics)
            else:
                deltas = {}
            manifest = self._write_completed_artifacts(
                artifact_dir=artifact_dir,
                common=common,
                spec=spec,
                dataset_manifest=dataset_manifest,
                result=result,
                metrics=metrics,
                deltas=deltas,
                split=split,
            )
            completed = {
                **common,
                "event_type": "completed",
                "created_at": utc_now(),
                "status": "completed",
                "artifact_paths": manifest["artifact_paths"],
                "canonical_analytical_hash": manifest["canonical_analytical_hash"],
            }
            self.registry.append(completed)
            return TrialOutcome(
                trial_id=trial_id,
                experiment_id=request.experiment_id,
                artifact_dir=artifact_dir,
                metrics=metrics,
                manifest=manifest,
            )
        except Exception as exc:
            failed_manifest = {
                **common,
                "status": "failed",
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            (artifact_dir / "manifest.json").write_bytes(
                canonical_json_bytes(failed_manifest)
            )
            (artifact_dir / "report.md").write_text(
                f"# Failed trial {trial_id}\n\n`{type(exc).__name__}: {exc}`\n",
                encoding="utf-8",
            )
            self.registry.append(
                {
                    **common,
                    "event_type": "failed",
                    "created_at": utc_now(),
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
            raise

    def _write_completed_artifacts(
        self,
        *,
        artifact_dir: Path,
        common: dict[str, Any],
        spec: StrategySpec,
        dataset_manifest: dict[str, Any],
        result: AdapterResult,
        metrics: dict[str, Any],
        deltas: dict[str, Any],
        split: TemporalSplit,
    ) -> dict[str, Any]:
        metric_frame = pd.DataFrame([{**metrics, **deltas}])
        artifact_content = {
            "metrics.csv": _csv_bytes(metric_frame),
            "trades.csv": _csv_bytes(result.trades),
            "equity_curve.csv": _csv_bytes(result.equity_curve),
            "signals.csv": _csv_bytes(result.signals),
        }
        for name, content in artifact_content.items():
            (artifact_dir / name).write_bytes(content)
        canonical_hash = sha256_bytes(
            canonical_json_bytes(
                {
                    name: sha256_bytes(content)
                    for name, content in artifact_content.items()
                }
            )
        )
        native_final_equity = float(result.engine_equity_curve["Equity"].iloc[-1])
        canonical_final_equity = float(result.equity_curve["net_equity"].iloc[-1])
        native_delta = native_final_equity - canonical_final_equity
        canonical_completed = (
            int((result.trades["side"] == "sell").sum())
            if not result.trades.empty
            else 0
        )
        paths = {
            "directory": str(artifact_dir.relative_to(self.project_root)),
            **{
                name.removesuffix(".csv"): str(
                    (artifact_dir / name).relative_to(self.project_root)
                )
                for name in artifact_content
            },
            "manifest": str(
                (artifact_dir / "manifest.json").relative_to(self.project_root)
            ),
            "report": str((artifact_dir / "report.md").relative_to(self.project_root)),
            "plots": str((artifact_dir / "plots").relative_to(self.project_root)),
        }
        manifest = {
            **common,
            "status": "completed",
            "effective_start": str(result.equity_curve["session"].iloc[0]),
            "effective_end": str(result.equity_curve["session"].iloc[-1]),
            "dataset_requested_start": dataset_manifest["requested_start"],
            "dataset_requested_end_exclusive": dataset_manifest[
                "requested_end_exclusive"
            ],
            "normalization_version": NORMALIZATION_VERSION,
            "exchange_calendar": dataset_manifest["exchange_calendar"],
            "normalized_timezone": dataset_manifest["normalized_timezone"],
            "annualization_sessions": ANNUALIZATION_SESSIONS,
            "risk_free_rate": RISK_FREE_RATE,
            "engine_configuration": result.engine_configuration,
            "engine_reference": {
                "closed_trade_rows": len(result.engine_trades),
                "equity_rows": len(result.engine_equity_curve),
                "canonical_completed_lifecycles": canonical_completed,
                "native_final_equity": native_final_equity,
                "canonical_final_equity": canonical_final_equity,
                "final_equity_delta_usd": native_delta,
                "reconciles_within_one_microdollar": (
                    len(result.engine_trades) == canonical_completed
                    and abs(native_delta) <= 0.000001
                ),
                "authoritative": False,
            },
            "terminal_position_open": result.terminal_position_open,
            "terminal_position_quantity": result.terminal_position_quantity,
            "metrics": metrics,
            "benchmark_deltas": deltas,
            "expected_failure_modes": list(spec.expected_failure_modes),
            "canonical_analytical_hash": canonical_hash,
            "canonical_artifact_hashes": {
                name: sha256_bytes(content)
                for name, content in artifact_content.items()
            },
            "artifact_paths": paths,
            "holdout_seen": split.is_holdout,
            "historical_evidence_only": True,
            "paper_or_live_readiness": False,
        }
        (artifact_dir / "manifest.json").write_bytes(canonical_json_bytes(manifest))
        render_trial_report(manifest, metrics, artifact_dir / "report.md")
        plot_equity(
            result.equity_curve,
            artifact_dir / "plots" / "equity_curve.png",
            f"{spec.strategy_id} {common['asset']} {split.label}",
        )
        return manifest

    def _validate_trial_request(
        self, request: TrialRequest, spec: StrategySpec
    ) -> TemporalSplit:
        if request.asset not in ASSETS:
            raise ValueError("asset must belong to the closed V0.1 universe")
        if request.split_key not in TEMPORAL_SPLITS:
            raise ValueError("unknown temporal split")
        if request.purpose not in ALLOWED_PURPOSES:
            raise ValueError("unknown trial purpose")
        if request.friction_bps not in {0, 5, 10, 25}:
            raise ValueError("friction scenario is not predeclared")
        _validate_parameter_policy(
            spec.strategy_id, request.parameters, request.purpose
        )
        return TEMPORAL_SPLITS[request.split_key]

    def reproduce(self, trial_id: str) -> bool:
        """Recompute analytical CSVs in memory and compare their canonical hash."""

        path = self.project_root / "artifacts" / "trials" / trial_id / "manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        spec_path = (
            self.project_root / "strategy_specs" / f"{manifest['strategy_id']}.yaml"
        )
        spec = load_spec(spec_path)
        data = self.snapshots.load_normalized(manifest["dataset_id"], manifest["asset"])
        result = self.adapter.run(
            data=data,
            spec=spec,
            parameters=manifest["parameters"],
            split=TEMPORAL_SPLITS[manifest["temporal_split"]],
            friction_bps=int(manifest["friction_bps"]),
        )
        metrics = canonical_metrics(result.equity_curve, result.trades)
        deltas = manifest.get("benchmark_deltas", {})
        content = {
            "metrics.csv": _csv_bytes(pd.DataFrame([{**metrics, **deltas}])),
            "trades.csv": _csv_bytes(result.trades),
            "equity_curve.csv": _csv_bytes(result.equity_curve),
            "signals.csv": _csv_bytes(result.signals),
        }
        actual = sha256_bytes(
            canonical_json_bytes(
                {name: sha256_bytes(value) for name, value in content.items()}
            )
        )
        return actual == str(manifest["canonical_analytical_hash"])


def _validate_parameter_policy(
    strategy_id: str, parameters: dict[str, float | int], purpose: str
) -> None:
    primary = primary_parameters(strategy_id)
    if purpose in {"primary", "friction_sensitivity"} and parameters != primary:
        raise ValueError("primary/friction trials require frozen primary parameters")
    if purpose != "parameter_sensitivity":
        return
    allowed: list[dict[str, float | int]] = []
    if strategy_id == "TREND_SMA200_V1":
        allowed = [{"sma": value} for value in (150, 200, 250)]
    elif strategy_id == "MEANREV_Z20_V1":
        for lookback in (15, 20, 25):
            allowed.append({**primary, "lookback": lookback})
        for entry_z in (-1.5, -2.0, -2.5):
            allowed.append({**primary, "entry_z": entry_z})
        for max_hold in (5, 10, 15):
            allowed.append({**primary, "max_hold": max_hold})
    if parameters not in allowed:
        raise ValueError("parameters are not a predeclared one-at-a-time sensitivity")


def battery_configurations() -> list[tuple[str, dict[str, float | int], int, Purpose]]:
    """Return the deduplicated, non-Cartesian closed validation battery."""

    configurations: list[tuple[str, dict[str, float | int], int, Purpose]] = []
    for strategy_id in (
        "CASH_0_V1",
        "BUY_HOLD_V1",
        "TREND_SMA200_V1",
        "MEANREV_Z20_V1",
    ):
        configurations.append(
            (strategy_id, primary_parameters(strategy_id), 5, "primary")
        )
    for sma in (150, 250):
        configurations.append(
            ("TREND_SMA200_V1", {"sma": sma}, 5, "parameter_sensitivity")
        )
    mean_primary = primary_parameters("MEANREV_Z20_V1")
    for key, values in (
        ("lookback", (15, 25)),
        ("entry_z", (-1.5, -2.5)),
        ("max_hold", (5, 15)),
    ):
        for value in values:
            configurations.append(
                (
                    "MEANREV_Z20_V1",
                    {**mean_primary, key: value},
                    5,
                    "parameter_sensitivity",
                )
            )
    for friction in (0, 10, 25):
        for strategy_id in (
            "BUY_HOLD_V1",
            "TREND_SMA200_V1",
            "MEANREV_Z20_V1",
        ):
            configurations.append(
                (
                    strategy_id,
                    primary_parameters(strategy_id),
                    friction,
                    "friction_sensitivity",
                )
            )
    return configurations


def run_battery(
    project_root: Path,
    *,
    dataset_id: str,
    split_keys: tuple[str, ...],
    confirm_holdout: bool,
    experiment_id: str | None = None,
) -> tuple[str, list[TrialOutcome], Path]:
    """Execute the predeclared sequence, keeping matching benchmarks visible."""

    runner = ExperimentRunner(project_root)
    for split_name in split_keys:
        if split_name not in TEMPORAL_SPLITS:
            raise ValueError(f"unknown split: {split_name}")
    if "project_holdout" in split_keys:
        if not confirm_holdout:
            raise ValueError("controlled holdout execution requires --confirm-holdout")
        if runner.registry.holdout_seen():
            raise ValueError(
                "Project Holdout is already marked seen; do not rerun informally"
            )
    experiment_id = experiment_id or new_experiment_id()
    outcomes: list[TrialOutcome] = []
    configurations = battery_configurations()
    benchmarks: dict[tuple[str, str, int], dict[str, Any]] = {}
    for split_key in split_keys:
        if split_key == "project_holdout":
            runner.registry.append(
                {
                    "event_type": "holdout_seen",
                    "created_at": utc_now(),
                    "experiment_id": experiment_id,
                    "temporal_split": split_key,
                    "status": "seen",
                    "notes": "controlled final V0.1 holdout battery began",
                }
            )
        for asset in ASSETS:
            ordered = sorted(
                configurations,
                key=lambda item: (
                    item[2],
                    0 if item[0] == "BUY_HOLD_V1" else 1,
                    item[0],
                    str(item[1]),
                ),
            )
            for strategy_id, parameters, friction, purpose in ordered:
                benchmark_key = (asset, split_key, friction)
                benchmark = benchmarks.get(benchmark_key)
                outcome = runner.run_trial(
                    TrialRequest(
                        spec_path=project_root
                        / "strategy_specs"
                        / f"{strategy_id}.yaml",
                        dataset_id=dataset_id,
                        asset=asset,
                        split_key=split_key,
                        parameters=parameters,
                        friction_bps=friction,
                        purpose=purpose,
                        experiment_id=experiment_id,
                        benchmark_metrics=benchmark
                        if strategy_id not in {"CASH_0_V1", "BUY_HOLD_V1"}
                        else (benchmark if strategy_id == "BUY_HOLD_V1" else None),
                    )
                )
                outcomes.append(outcome)
                if strategy_id == "BUY_HOLD_V1":
                    benchmarks[benchmark_key] = outcome.metrics
    rows = completed_experiment_rows(project_root, runner.registry, experiment_id)
    report_dir = aggregate_report(
        rows, project_root / "artifacts" / "reports", experiment_id
    )
    return experiment_id, outcomes, report_dir


def completed_experiment_rows(
    project_root: Path, registry: TrialRegistry, experiment_id: str
) -> pd.DataFrame:
    """Load all immutable completed trial manifests for one experiment."""

    rows: list[dict[str, Any]] = []
    for event in registry.completed_for_experiment(experiment_id):
        manifest_path = project_root / event["artifact_paths"]["manifest"]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        rows.append(
            {
                "trial_id": manifest["trial_id"],
                "artifact_dir": manifest["artifact_paths"]["directory"],
                "asset": manifest["asset"],
                "temporal_split": manifest["temporal_split"],
                "strategy_id": manifest["strategy_id"],
                "purpose": manifest["purpose"],
                "parameters": json.dumps(manifest["parameters"], sort_keys=True),
                "friction_bps": manifest["friction_bps"],
                **manifest["metrics"],
                **manifest["benchmark_deltas"],
            }
        )
    return pd.DataFrame(rows)


def trial_metrics_from_path(path: Path) -> dict[str, Any]:
    frame = pd.read_csv(path)
    payload = frame.iloc[0].where(pd.notna(frame.iloc[0]), None).to_dict()
    return {str(key): value for key, value in payload.items()}


def current_python() -> str:
    return sys.executable
