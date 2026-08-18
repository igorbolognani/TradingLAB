"""Immutable registered historical trials and the closed robustness battery."""

import json
import sys
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

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
from tradinglab.hashing import canonical_json_bytes, sha256_bytes, sha256_file
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
    benchmark_trial_id: str | None = None


@dataclass(frozen=True)
class TrialOutcome:
    trial_id: str
    experiment_id: str
    artifact_dir: Path
    metrics: dict[str, Any]
    manifest: dict[str, Any]


@dataclass(frozen=True)
class _HoldoutPermit:
    """Internal capability issued only after the closed battery readiness audit."""

    experiment_id: str
    dataset_id: str
    dataset_manifest_hash: str
    git_commit: str
    battery_fingerprint: str


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
        self._validated_datasets: dict[str, dict[str, Any]] = {}

    def run_trial(
        self,
        request: TrialRequest,
        *,
        _holdout_permit: _HoldoutPermit | None = None,
    ) -> TrialOutcome:
        spec = load_spec(request.spec_path)
        split = self._validate_trial_request(request, spec, _holdout_permit)
        dataset_manifest = self._validated_dataset_manifest(request.dataset_id)
        if request.asset not in dataset_manifest["symbols"]:
            raise ValueError("trial asset is not present in the dataset")
        provenance = code_provenance(self.project_root)
        if split.is_holdout:
            assert _holdout_permit is not None
            if (
                _holdout_permit.experiment_id != request.experiment_id
                or _holdout_permit.dataset_id != request.dataset_id
                or _holdout_permit.dataset_manifest_hash
                != dataset_manifest["manifest_hash"]
                or _holdout_permit.git_commit != provenance["git_commit"]
                or provenance["dirty_worktree"]
            ):
                raise ValueError(
                    "holdout permit does not match the immutable run state"
                )
        benchmark_metrics, benchmark_trial_id = self._benchmark_for(
            request, spec, dataset_manifest, provenance
        )
        trial_id = new_trial_id()
        artifact_dir = self.project_root / "artifacts" / "trials" / trial_id
        evidence_class, notes = _evidence_classification(request.purpose)
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
            "dataset_manifest_hash": dataset_manifest["manifest_hash"],
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
            "benchmark_trial_id": benchmark_trial_id,
            "configuration_id": _configuration_id(
                request.asset,
                request.split_key,
                spec.strategy_id,
                request.parameters,
                request.friction_bps,
                request.purpose,
            ),
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
            "evidence_class": evidence_class,
            "notes": notes,
        }
        if split.is_holdout:
            assert _holdout_permit is not None
            common["holdout_battery_fingerprint"] = _holdout_permit.battery_fingerprint
        self.registry.append(
            {
                **common,
                "event_type": "started",
                "created_at": utc_now(),
                "status": "started",
            }
        )
        try:
            artifact_dir.mkdir(parents=True, exist_ok=False)
            data = self.snapshots.load_normalized(request.dataset_id, request.asset)
            result = self.adapter.run(
                data=data,
                spec=spec,
                parameters=request.parameters,
                split=split,
                friction_bps=request.friction_bps,
            )
            metrics = canonical_metrics(result.equity_curve, result.trades)
            if benchmark_metrics is not None:
                deltas = benchmark_deltas(metrics, benchmark_metrics)
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
                "artifact_inventory_hash": sha256_file(
                    artifact_dir / "artifact_inventory.json"
                ),
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
            "artifact_inventory": str(
                (artifact_dir / "artifact_inventory.json").relative_to(
                    self.project_root
                )
            ),
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
            "historical_evidence_only": common["evidence_class"] == "market_history",
            "paper_or_live_readiness": False,
        }
        (artifact_dir / "manifest.json").write_bytes(canonical_json_bytes(manifest))
        render_trial_report(manifest, metrics, artifact_dir / "report.md")
        plot_equity(
            result.equity_curve,
            artifact_dir / "plots" / "equity_curve.png",
            f"{spec.strategy_id} {common['asset']} {split.label}",
        )
        inventory = {
            "version": "tradinglab/artifact-inventory/v1",
            "trial_id": common["trial_id"],
            "files": {
                name: sha256_file(artifact_dir / name)
                for name in (
                    "manifest.json",
                    "metrics.csv",
                    "trades.csv",
                    "equity_curve.csv",
                    "signals.csv",
                    "report.md",
                    "plots/equity_curve.png",
                )
            },
        }
        inventory_path = artifact_dir / "artifact_inventory.json"
        inventory_path.write_bytes(canonical_json_bytes(inventory))
        return manifest

    def _validated_dataset_manifest(self, dataset_id: str) -> dict[str, Any]:
        cached = self._validated_datasets.get(dataset_id)
        if cached is not None:
            if self.snapshots.load_manifest(dataset_id) != cached:
                raise ValueError("dataset manifest changed during this runner lifetime")
            return cached
        self.snapshots.validate_dataset(dataset_id)
        manifest = self.snapshots.load_manifest(dataset_id)
        self._validated_datasets[dataset_id] = manifest
        return manifest

    def _benchmark_for(
        self,
        request: TrialRequest,
        spec: StrategySpec,
        dataset_manifest: dict[str, Any],
        provenance: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, str | None]:
        if spec.strategy_id == "CASH_0_V1":
            if request.benchmark_trial_id is not None:
                raise ValueError("CASH trials do not accept a benchmark trial")
            return None, None
        if spec.strategy_id == "BUY_HOLD_V1":
            if request.benchmark_trial_id is not None:
                raise ValueError("Buy & Hold is its own benchmark")
            return None, None
        if spec.benchmark != "matching_asset_buy_hold":
            raise ValueError("unsupported benchmark contract")
        if request.benchmark_trial_id is None:
            raise ValueError("strategy requires a matching Buy & Hold trial id")
        if provenance["dirty_worktree"]:
            raise ValueError("matching benchmark trials require a clean worktree")
        manifest = self._load_completed_trial_manifest(request.benchmark_trial_id)
        integrity_reasons = self._artifact_integrity_reasons(
            request.benchmark_trial_id, manifest
        )
        if integrity_reasons:
            raise ValueError(
                "benchmark trial artifact integrity failed: "
                + "; ".join(integrity_reasons)
            )
        expected = {
            "strategy_id": "BUY_HOLD_V1",
            "spec_hash": specification_hash(
                load_spec(self.project_root / "strategy_specs" / "BUY_HOLD_V1.yaml")
            ),
            "experiment_id": request.experiment_id,
            "dataset_id": request.dataset_id,
            "dataset_manifest_hash": dataset_manifest["manifest_hash"],
            "asset": request.asset,
            "temporal_split": request.split_key,
            "friction_bps": request.friction_bps,
            "git_commit": provenance["git_commit"],
            "git_branch": provenance["git_branch"],
            "python_version": provenance["python_version"],
            "dependency_lock_hash": provenance["dependency_lock_hash"],
            "engine_name": ENGINE_NAME,
            "engine_version": ENGINE_VERSION,
        }
        mismatches = [
            key for key, value in expected.items() if manifest.get(key) != value
        ]
        if mismatches:
            raise ValueError(
                "benchmark trial does not match this trial: " + ", ".join(mismatches)
            )
        if manifest.get("dirty_worktree") != provenance["dirty_worktree"]:
            raise ValueError("benchmark and candidate dirty-worktree states differ")
        metrics = manifest.get("metrics")
        if not isinstance(metrics, dict):
            raise ValueError("benchmark trial has no canonical metrics")
        return metrics, request.benchmark_trial_id

    def _load_completed_trial_manifest(self, trial_id: str) -> dict[str, Any]:
        events = self.registry.events_for_trial(trial_id)
        completed = [
            event for event in events if event.get("event_type") == "completed"
        ]
        if len(completed) != 1:
            raise ValueError("benchmark trial must have exactly one completed event")
        path = self.project_root / "artifacts" / "trials" / trial_id / "manifest.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("trial_id") != trial_id or payload.get("status") != "completed":
            raise ValueError("completed trial manifest identity mismatch")
        return cast(dict[str, Any], payload)

    def _validate_trial_request(
        self,
        request: TrialRequest,
        spec: StrategySpec,
        holdout_permit: _HoldoutPermit | None,
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
        split = TEMPORAL_SPLITS[request.split_key]
        if split.is_holdout and holdout_permit is None:
            raise ValueError(
                "Project Holdout can only run through the controlled battery gate"
            )
        return split

    def reproduce(self, trial_id: str) -> dict[str, Any]:
        """Separate analytical equivalence from full provenance reproduction."""

        path = self.project_root / "artifacts" / "trials" / trial_id / "manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        reasons: list[str] = []
        provenance = code_provenance(self.project_root)
        for key in (
            "git_commit",
            "git_branch",
            "python_version",
            "dependency_lock_hash",
        ):
            if manifest.get(key) != provenance[key]:
                reasons.append(f"{key} differs from the recorded trial")
        if manifest.get("dirty_worktree") is not False:
            reasons.append("recorded trial was created from a dirty worktree")
        if provenance["dirty_worktree"]:
            reasons.append("current worktree is dirty")
        if manifest.get("engine_name") != ENGINE_NAME:
            reasons.append("engine name differs from the recorded trial")
        if manifest.get("engine_version") != ENGINE_VERSION:
            reasons.append("engine version differs from the recorded trial")
        spec_path = (
            self.project_root / "strategy_specs" / f"{manifest['strategy_id']}.yaml"
        )
        spec = load_spec(spec_path)
        if manifest.get("spec_hash") != specification_hash(spec):
            reasons.append("strategy specification hash differs")
        try:
            validation = self.snapshots.validate_dataset(manifest["dataset_id"])
        except (FileNotFoundError, KeyError, ValueError) as exc:
            reasons.append(f"dataset validation failed: {exc}")
        else:
            if validation["dataset_checksum"] != manifest.get("dataset_checksum"):
                reasons.append("dataset checksum differs")
            if validation["manifest_hash"] != manifest.get("dataset_manifest_hash"):
                reasons.append("dataset manifest hash differs")
        artifact_reasons = self._artifact_integrity_reasons(trial_id, manifest)
        reasons.extend(artifact_reasons)
        analytical_equivalence = False
        try:
            data = self.snapshots.load_normalized(
                manifest["dataset_id"], manifest["asset"]
            )
            result = self.adapter.run(
                data=data,
                spec=spec,
                parameters=manifest["parameters"],
                split=TEMPORAL_SPLITS[manifest["temporal_split"]],
                friction_bps=int(manifest["friction_bps"]),
            )
            metrics = canonical_metrics(result.equity_curve, result.trades)
            if spec.strategy_id == "BUY_HOLD_V1":
                deltas = benchmark_deltas(metrics, metrics)
            elif spec.strategy_id == "CASH_0_V1":
                deltas = {}
            elif manifest.get("benchmark_trial_id"):
                try:
                    benchmark_manifest = self._load_completed_trial_manifest(
                        str(manifest["benchmark_trial_id"])
                    )
                    reasons.extend(
                        self._artifact_integrity_reasons(
                            str(manifest["benchmark_trial_id"]), benchmark_manifest
                        )
                    )
                    benchmark_expected = {
                        "strategy_id": "BUY_HOLD_V1",
                        "experiment_id": manifest.get("experiment_id"),
                        "dataset_id": manifest.get("dataset_id"),
                        "dataset_manifest_hash": manifest.get("dataset_manifest_hash"),
                        "asset": manifest.get("asset"),
                        "temporal_split": manifest.get("temporal_split"),
                        "friction_bps": manifest.get("friction_bps"),
                        "git_commit": manifest.get("git_commit"),
                        "dependency_lock_hash": manifest.get("dependency_lock_hash"),
                        "engine_version": manifest.get("engine_version"),
                    }
                    benchmark_mismatches = [
                        key
                        for key, value in benchmark_expected.items()
                        if benchmark_manifest.get(key) != value
                    ]
                    if benchmark_mismatches:
                        reasons.append(
                            "benchmark provenance differs: "
                            + ", ".join(benchmark_mismatches)
                        )
                    deltas = benchmark_deltas(metrics, benchmark_manifest["metrics"])
                except (FileNotFoundError, KeyError, ValueError) as exc:
                    reasons.append(f"benchmark reproduction failed: {exc}")
                    deltas = manifest.get("benchmark_deltas", {})
            else:
                reasons.append("matching benchmark trial id is absent")
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
            analytical_equivalence = actual == str(
                manifest["canonical_analytical_hash"]
            )
        except Exception as exc:  # reproduction reports corruption; it does not hide it
            reasons.append(
                f"analytical recomputation failed: {type(exc).__name__}: {exc}"
            )
        if not analytical_equivalence and not any(
            reason.startswith("analytical recomputation failed:") for reason in reasons
        ):
            reasons.append("canonical analytical hash differs")
        unique_reasons = list(dict.fromkeys(reasons))
        provenance_match = not unique_reasons
        return {
            "trial_id": trial_id,
            "analytical_equivalence": analytical_equivalence,
            "provenance_match": provenance_match,
            "artifacts_intact": not artifact_reasons,
            "reproduced": analytical_equivalence and provenance_match,
            "reasons": unique_reasons,
        }

    def _artifact_integrity_reasons(
        self, trial_id: str, manifest: dict[str, Any]
    ) -> list[str]:
        reasons: list[str] = []
        completed = [
            event
            for event in self.registry.events_for_trial(trial_id)
            if event.get("event_type") == "completed"
        ]
        if len(completed) != 1:
            return ["trial does not have exactly one completed registry event"]
        inventory_relative = manifest.get("artifact_paths", {}).get(
            "artifact_inventory"
        )
        expected_inventory_hash = completed[0].get("artifact_inventory_hash")
        if not inventory_relative or not expected_inventory_hash:
            return ["artifact inventory provenance is absent"]
        inventory_path = self.project_root / str(inventory_relative)
        if not inventory_path.is_file():
            return ["artifact inventory file is absent"]
        if sha256_file(inventory_path) != expected_inventory_hash:
            reasons.append("artifact inventory hash differs from registry")
        try:
            inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return [*reasons, "artifact inventory is invalid JSON"]
        expected_names = {
            "manifest.json",
            "metrics.csv",
            "trades.csv",
            "equity_curve.csv",
            "signals.csv",
            "report.md",
            "plots/equity_curve.png",
        }
        files = inventory.get("files")
        if (
            inventory.get("version") != "tradinglab/artifact-inventory/v1"
            or inventory.get("trial_id") != trial_id
            or not isinstance(files, dict)
            or set(files) != expected_names
        ):
            return [*reasons, "artifact inventory contract differs"]
        artifact_dir = inventory_path.parent
        for name, expected_hash in files.items():
            artifact_path = artifact_dir / name
            if (
                not artifact_path.is_file()
                or sha256_file(artifact_path) != expected_hash
            ):
                reasons.append(f"artifact hash differs: {name}")
        return reasons


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


def _evidence_classification(purpose: Purpose) -> tuple[str, str]:
    if purpose in {"primary", "parameter_sensitivity", "friction_sensitivity"}:
        return "market_history", "historical single-asset research trial"
    if purpose == "debug":
        return "debug_non_evidence", "debug-only trial; not historical evidence"
    return "synthetic_non_market", "synthetic trial; not market-history evidence"


def _configuration_id(
    asset: str,
    split_key: str,
    strategy_id: str,
    parameters: dict[str, float | int],
    friction_bps: int,
    purpose: Purpose | str,
) -> str:
    return sha256_bytes(
        canonical_json_bytes(
            {
                "asset": asset,
                "temporal_split": split_key,
                "strategy_id": strategy_id,
                "parameters": parameters,
                "friction_bps": friction_bps,
                "purpose": purpose,
            }
        )
    )


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


def _expected_configuration_ids(split_key: str) -> set[str]:
    return {
        _configuration_id(asset, split_key, strategy, parameters, friction, purpose)
        for asset in ASSETS
        for strategy, parameters, friction, purpose in battery_configurations()
    }


def _battery_fingerprint(
    project_root: Path,
    dataset_manifest: dict[str, Any],
    provenance: dict[str, Any],
) -> str:
    spec_hashes = {
        strategy_id: specification_hash(
            load_spec(project_root / "strategy_specs" / f"{strategy_id}.yaml")
        )
        for strategy_id in (
            "CASH_0_V1",
            "BUY_HOLD_V1",
            "TREND_SMA200_V1",
            "MEANREV_Z20_V1",
        )
    }
    return sha256_bytes(
        canonical_json_bytes(
            {
                "version": "tradinglab/closed-battery/v1",
                "assets": ASSETS,
                "configurations": battery_configurations(),
                "dataset_id": dataset_manifest["dataset_id"],
                "dataset_manifest_hash": dataset_manifest["manifest_hash"],
                "git_commit": provenance["git_commit"],
                "dependency_lock_hash": provenance["dependency_lock_hash"],
                "engine_name": ENGINE_NAME,
                "engine_version": ENGINE_VERSION,
                "spec_hashes": spec_hashes,
            }
        )
    )


def _events_for_experiment(
    registry: TrialRegistry, experiment_id: str
) -> list[dict[str, Any]]:
    return [
        event
        for event in registry.events()
        if event.get("experiment_id") == experiment_id
    ]


def _validate_event_provenance(
    events: list[dict[str, Any]],
    *,
    dataset_manifest: dict[str, Any],
    provenance: dict[str, Any],
) -> None:
    expected = {
        "dataset_id": dataset_manifest["dataset_id"],
        "dataset_checksum": dataset_manifest["dataset_checksum"],
        "dataset_manifest_hash": dataset_manifest["manifest_hash"],
        "git_commit": provenance["git_commit"],
        "git_branch": provenance["git_branch"],
        "python_version": provenance["python_version"],
        "dependency_lock_hash": provenance["dependency_lock_hash"],
        "engine_name": ENGINE_NAME,
        "engine_version": ENGINE_VERSION,
    }
    for event in events:
        if event.get("event_type") == "holdout_seen":
            continue
        mismatches = [key for key, value in expected.items() if event.get(key) != value]
        if mismatches:
            raise ValueError(
                "experiment mixes incompatible immutable provenance: "
                + ", ".join(mismatches)
            )
        if event.get("dirty_worktree") is not False:
            raise ValueError("closed battery contains a dirty-worktree trial")
        strategy_id = event.get("strategy_id")
        if isinstance(strategy_id, str):
            current_spec_hash = specification_hash(
                load_spec(
                    Path(provenance["project_root"])
                    / "strategy_specs"
                    / f"{strategy_id}.yaml"
                )
            )
            if event.get("spec_hash") != current_spec_hash:
                raise ValueError("experiment mixes a changed strategy specification")


def _assert_split_complete(
    events: list[dict[str, Any]],
    split_key: str,
    *,
    allow_failed_retries: bool = False,
) -> None:
    expected = _expected_configuration_ids(split_key)
    started = [
        event
        for event in events
        if event.get("event_type") == "started"
        and event.get("temporal_split") == split_key
    ]
    completed = [
        event
        for event in events
        if event.get("event_type") == "completed"
        and event.get("temporal_split") == split_key
    ]
    failed = [
        event
        for event in events
        if event.get("event_type") == "failed"
        and event.get("temporal_split") == split_key
    ]
    started_ids = [str(event.get("configuration_id")) for event in started]
    completed_ids = [str(event.get("configuration_id")) for event in completed]
    if failed and not allow_failed_retries:
        raise ValueError(f"{split_key} contains failed trials")
    completed_is_exact = set(completed_ids) == expected and len(completed_ids) == len(
        expected
    )
    started_is_exact = set(started_ids) == expected and (
        allow_failed_retries or len(started_ids) == len(expected)
    )
    if not completed_is_exact or not started_is_exact:
        raise ValueError(
            f"{split_key} is not the exact complete closed battery "
            f"({len(completed_ids)}/{len(expected)} completed)"
        )
    terminal = [*completed, *failed]
    if Counter(event.get("trial_id") for event in started) != Counter(
        event.get("trial_id") for event in terminal
    ):
        raise ValueError(f"{split_key} started/completed trial identities differ")


def _close_orphaned_holdout_starts(registry: TrialRegistry, experiment_id: str) -> None:
    events = _events_for_experiment(registry, experiment_id)
    terminals = {
        event.get("trial_id")
        for event in events
        if event.get("event_type") in {"completed", "failed"}
    }
    for event in events:
        if (
            event.get("event_type") == "started"
            and event.get("temporal_split") == "project_holdout"
            and event.get("trial_id") not in terminals
        ):
            registry.append(
                {
                    **event,
                    "event_type": "failed",
                    "created_at": utc_now(),
                    "status": "failed",
                    "error_type": "InterruptedHoldoutTrial",
                    "error": (
                        "explicit holdout resume found a started trial without a "
                        "terminal registry event"
                    ),
                }
            )


def _assert_development_validation_readiness(
    events: list[dict[str, Any]],
) -> None:
    _assert_split_complete(events, "development")
    _assert_split_complete(events, "validation_oos")
    development_terminal_indexes = [
        index
        for index, event in enumerate(events)
        if event.get("temporal_split") == "development"
        and event.get("event_type") == "completed"
    ]
    validation_start_indexes = [
        index
        for index, event in enumerate(events)
        if event.get("temporal_split") == "validation_oos"
        and event.get("event_type") == "started"
    ]
    if not development_terminal_indexes or not validation_start_indexes:
        raise ValueError("development/validation event ordering cannot be established")
    if max(development_terminal_indexes) >= min(validation_start_indexes):
        raise ValueError("validation began before all Development trials completed")


def run_battery(
    project_root: Path,
    *,
    dataset_id: str,
    split_keys: tuple[str, ...],
    confirm_holdout: bool,
    experiment_id: str | None = None,
    resume_holdout: bool = False,
) -> tuple[str, list[TrialOutcome], Path]:
    """Execute the predeclared sequence with an irreversible holdout gate."""

    runner = ExperimentRunner(project_root)
    allowed_sequences = {
        ("development",),
        ("validation_oos",),
        ("development", "validation_oos"),
        ("project_holdout",),
    }
    if split_keys not in allowed_sequences:
        raise ValueError("battery splits must follow the closed staged sequence")
    for split_name in split_keys:
        if split_name not in TEMPORAL_SPLITS:
            raise ValueError(f"unknown split: {split_name}")
    supplied_experiment_id = experiment_id
    experiment_id = experiment_id or new_experiment_id()
    dataset_manifest = runner._validated_dataset_manifest(dataset_id)
    provenance = code_provenance(project_root)
    provenance["project_root"] = str(project_root)
    if provenance["dirty_worktree"]:
        raise ValueError("closed battery requires a clean committed worktree")
    fingerprint = _battery_fingerprint(project_root, dataset_manifest, provenance)
    existing = _events_for_experiment(runner.registry, experiment_id)
    _validate_event_provenance(
        existing, dataset_manifest=dataset_manifest, provenance=provenance
    )

    holdout_permit: _HoldoutPermit | None = None
    if split_keys == ("project_holdout",):
        if not confirm_holdout:
            raise ValueError("controlled holdout execution requires --confirm-holdout")
        if supplied_experiment_id is None:
            raise ValueError("controlled holdout requires an existing experiment id")
        _assert_development_validation_readiness(existing)
        holdout_events = [
            event
            for event in runner.registry.events()
            if event.get("event_type") == "holdout_seen"
        ]
        prior_holdout_trials = [
            event
            for event in runner.registry.events()
            if event.get("temporal_split") == "project_holdout"
            and event.get("event_type") in {"started", "completed", "failed"}
        ]
        if not holdout_events and prior_holdout_trials:
            raise ValueError("holdout trials exist without a governed access marker")
        if holdout_events:
            if not resume_holdout:
                raise ValueError(
                    "Project Holdout is already marked seen; "
                    "explicit resume is required"
                )
            if len(holdout_events) != 1:
                raise ValueError(
                    "multiple holdout access events violate V0.1 governance"
                )
            marker = holdout_events[0]
            if (
                marker.get("experiment_id") != experiment_id
                or marker.get("dataset_id") != dataset_id
                or marker.get("dataset_manifest_hash")
                != dataset_manifest["manifest_hash"]
                or marker.get("git_commit") != provenance["git_commit"]
                or marker.get("battery_fingerprint") != fingerprint
            ):
                raise ValueError("holdout resume state differs from its first access")
            _close_orphaned_holdout_starts(runner.registry, experiment_id)
            existing = _events_for_experiment(runner.registry, experiment_id)
        else:
            if resume_holdout:
                raise ValueError("cannot resume a holdout that has not been opened")
            runner.registry.append(
                {
                    "event_type": "holdout_seen",
                    "created_at": utc_now(),
                    "experiment_id": experiment_id,
                    "temporal_split": "project_holdout",
                    "status": "seen",
                    "dataset_id": dataset_id,
                    "dataset_manifest_hash": dataset_manifest["manifest_hash"],
                    "git_commit": provenance["git_commit"],
                    "dependency_lock_hash": provenance["dependency_lock_hash"],
                    "engine_version": ENGINE_VERSION,
                    "battery_fingerprint": fingerprint,
                    "notes": "controlled final V0.1 holdout battery began",
                }
            )
            existing = _events_for_experiment(runner.registry, experiment_id)
        holdout_permit = _HoldoutPermit(
            experiment_id=experiment_id,
            dataset_id=dataset_id,
            dataset_manifest_hash=dataset_manifest["manifest_hash"],
            git_commit=str(provenance["git_commit"]),
            battery_fingerprint=fingerprint,
        )
    else:
        if confirm_holdout or resume_holdout:
            raise ValueError("holdout flags are only valid for the holdout split")
        if any(event.get("temporal_split") == "project_holdout" for event in existing):
            raise ValueError(
                "Development/Validation cannot continue after holdout access"
            )
        if split_keys[0] == "development" and existing:
            raise ValueError("Development requires a fresh experiment identity")
        if split_keys == ("validation_oos",):
            _assert_split_complete(existing, "development")

    outcomes: list[TrialOutcome] = []
    configurations = battery_configurations()
    benchmarks: dict[tuple[str, str, int], str] = {}
    for event in existing:
        if (
            event.get("event_type") == "completed"
            and event.get("strategy_id") == "BUY_HOLD_V1"
        ):
            benchmarks[
                (
                    str(event["asset"]),
                    str(event["temporal_split"]),
                    int(event["friction_bps"]),
                )
            ] = str(event["trial_id"])
    for split_key in split_keys:
        completed_ids = {
            str(event.get("configuration_id"))
            for event in existing
            if event.get("event_type") == "completed"
            and event.get("temporal_split") == split_key
        }
        if completed_ids and split_key != "project_holdout":
            raise ValueError(f"{split_key} already contains completed configurations")
        if len(completed_ids) != len(
            [
                event
                for event in existing
                if event.get("event_type") == "completed"
                and event.get("temporal_split") == split_key
            ]
        ):
            raise ValueError(f"{split_key} contains duplicate completed configurations")
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
                configuration_id = _configuration_id(
                    asset,
                    split_key,
                    strategy_id,
                    parameters,
                    friction,
                    purpose,
                )
                if configuration_id in completed_ids:
                    continue
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
                        benchmark_trial_id=(
                            benchmark
                            if strategy_id not in {"CASH_0_V1", "BUY_HOLD_V1"}
                            else None
                        ),
                    ),
                    _holdout_permit=holdout_permit,
                )
                outcomes.append(outcome)
                if strategy_id == "BUY_HOLD_V1":
                    benchmarks[benchmark_key] = outcome.trial_id
        existing = _events_for_experiment(runner.registry, experiment_id)
        _assert_split_complete(
            existing,
            split_key,
            allow_failed_retries=split_key == "project_holdout",
        )
    rows = completed_experiment_rows(project_root, runner.registry, experiment_id)
    report_dir = aggregate_report(
        rows,
        project_root / "artifacts" / "reports",
        experiment_id,
        runner.registry.events(),
    )
    return experiment_id, outcomes, report_dir


def completed_experiment_rows(
    project_root: Path, registry: TrialRegistry, experiment_id: str
) -> pd.DataFrame:
    """Load all immutable completed trial manifests for one experiment."""

    rows: list[dict[str, Any]] = []
    verifier = ExperimentRunner(project_root)
    for event in registry.completed_for_experiment(experiment_id):
        manifest_path = project_root / event["artifact_paths"]["manifest"]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("trial_id") != event.get("trial_id"):
            raise ValueError("completed registry event and manifest identity differ")
        integrity_reasons = verifier._artifact_integrity_reasons(
            str(event["trial_id"]), manifest
        )
        if integrity_reasons:
            raise ValueError(
                "completed trial artifact integrity failed: "
                + "; ".join(integrity_reasons)
            )
        rows.append(
            {
                "trial_id": manifest["trial_id"],
                "artifact_dir": manifest["artifact_paths"]["directory"],
                "asset": manifest["asset"],
                "temporal_split": manifest["temporal_split"],
                "strategy_id": manifest["strategy_id"],
                "purpose": manifest["purpose"],
                "evidence_class": manifest["evidence_class"],
                "parameters": json.dumps(manifest["parameters"], sort_keys=True),
                "friction_bps": manifest["friction_bps"],
                "engine_reconciled": manifest["engine_reference"][
                    "reconciles_within_one_microdollar"
                ],
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
