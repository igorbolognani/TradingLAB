"""Compare independent V0.2 replay outputs with V0.1 analytical artifacts."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from .contract import ASSETS, METRIC_TOLERANCES, PRIMARY_PARAMETERS, SPLITS, STRATEGIES
from .core import load_normalized_csv, replay


@dataclass(frozen=True)
class Comparison:
    checked: int
    passed: int
    failures: tuple[str, ...]


def _number(value: str) -> float | None:
    return None if value == "" else float(value)


def _compare_events(
    result, artifact_dir: Path, failures: list[str], label: str
) -> None:
    with (artifact_dir / "signals.csv").open(newline="", encoding="utf-8") as handle:
        expected_signals = list(csv.DictReader(handle))
    if len(expected_signals) != len(result.signals):
        failures.append(
            f"{label}/signals: {len(result.signals)} != {len(expected_signals)}"
        )
    for index, (actual, expected) in enumerate(
        zip(result.signals, expected_signals, strict=False)
    ):
        fields = (
            ("decision_session", actual.decision_session.isoformat()),
            ("order_eligibility_session", actual.order_eligibility_session.isoformat()),
            ("action", actual.action),
            ("reason", actual.reason),
        )
        for field, value in fields:
            if expected[field] != value:
                failures.append(
                    f"{label}/signals[{index}]/{field}: {value} != {expected[field]}"
                )
        expected_indicator = _number(expected["indicator_value"])
        if actual.indicator_value is None or expected_indicator is None:
            if actual.indicator_value != expected_indicator:
                failures.append(f"{label}/signals[{index}]/indicator: null mismatch")
        elif abs(actual.indicator_value - expected_indicator) > 1e-9:
            failures.append(f"{label}/signals[{index}]/indicator: value mismatch")

    with (artifact_dir / "trades.csv").open(newline="", encoding="utf-8") as handle:
        expected_fills = list(csv.DictReader(handle))
    if len(expected_fills) != len(result.fills):
        failures.append(f"{label}/fills: {len(result.fills)} != {len(expected_fills)}")
    for index, (actual, expected) in enumerate(
        zip(result.fills, expected_fills, strict=False)
    ):
        expected_side = {"entry": "buy", "exit": "sell"}[actual.side]
        checks = (
            ("fill_session", actual.session.isoformat()),
            ("side", expected_side),
            ("quantity", str(actual.quantity)),
        )
        for field, value in checks:
            if expected[field] != value:
                failures.append(
                    f"{label}/fills[{index}]/{field}: {value} != {expected[field]}"
                )
        expected_price = float(expected["normalized_fill_price"])
        expected_cost = float(expected["modeled_friction"])
        if abs(actual.price - expected_price) > 1e-10:
            failures.append(f"{label}/fills[{index}]/price: value mismatch")
        if abs(actual.cost - expected_cost) > 1e-8:
            failures.append(f"{label}/fills[{index}]/cost: value mismatch")


def compare_primary(
    *,
    snapshot_root: Path,
    report_csv: Path,
    artifact_root: Path,
    output_csv: Path | None = None,
) -> Comparison:
    """Compare all 60 primary V0.1 rows, preserving explicit tolerances."""

    with report_csv.open(newline="", encoding="utf-8") as handle:
        source_rows = list(csv.DictReader(handle))
    source_rows = [row for row in source_rows if row["purpose"] == "primary"]
    expected = {
        (row["asset"], row["temporal_split"], row["strategy_id"]): row
        for row in source_rows
    }
    if set(expected) != {
        (asset, split, strategy)
        for asset in ASSETS
        for split in SPLITS
        for strategy in STRATEGIES
    }:
        raise ValueError("V0.1 report does not contain the complete primary battery")

    output_rows: list[dict[str, str]] = []
    failures: list[str] = []
    metrics = tuple(METRIC_TOLERANCES)
    for asset in ASSETS:
        bars = load_normalized_csv(snapshot_root / asset / "normalized.csv")
        for split in SPLITS:
            for strategy in STRATEGIES:
                result = replay(
                    bars,
                    asset=asset,
                    split=split,
                    strategy_id=strategy,
                    friction_bps=5,
                    parameters=PRIMARY_PARAMETERS[strategy],
                )
                source = expected[(asset, split, strategy)]
                _compare_events(
                    result,
                    Path(source["artifact_dir"]),
                    failures,
                    f"{asset}/{split}/{strategy}",
                )
                row = {
                    "asset": asset,
                    "split": split,
                    "strategy_id": strategy,
                    "friction_bps": "5",
                }
                for metric in metrics:
                    actual = result.metrics[metric]
                    expected_value = _number(
                        source[metric if metric != "CAGR" else "CAGR"]
                    )
                    row[f"v0_2_{metric}"] = "" if actual is None else str(actual)
                    row[f"v0_1_{metric}"] = (
                        "" if expected_value is None else str(expected_value)
                    )
                    if actual is None or expected_value is None:
                        if actual != expected_value:
                            failures.append(
                                f"{asset}/{split}/{strategy}/{metric}: null mismatch"
                            )
                    elif (
                        abs(float(actual) - expected_value) > METRIC_TOLERANCES[metric]
                    ):
                        failures.append(
                            f"{asset}/{split}/{strategy}/{metric}: "
                            f"{actual} != {expected_value} "
                            f"(tol {METRIC_TOLERANCES[metric]})"
                        )
                output_rows.append(row)

    if output_csv is not None:
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        with output_csv.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(output_rows[0]))
            writer.writeheader()
            writer.writerows(output_rows)
    return Comparison(
        len(output_rows), len(output_rows) - len(failures), tuple(failures)
    )


def write_comparison_report(comparison: Comparison, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "contract": "tradinglab/v0.2-independent-reproduction/v1",
        "checked": comparison.checked,
        "passed": comparison.passed,
        "failed": len(comparison.failures),
        "metric_tolerances": METRIC_TOLERANCES,
        "failures": comparison.failures,
    }
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
