"""Static per-trial and aggregate research reports."""

from pathlib import Path
from typing import Any

import matplotlib
import pandas as pd

from tradinglab.hashing import canonical_json_bytes, sha256_bytes

matplotlib.use("Agg")
from matplotlib import pyplot as plt

RESEARCH_WARNING = (
    "Historical performance is research evidence only and does not prove future "
    "profitability, paper-trading readiness, or live-trading suitability."
)


def _json_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    normalized = frame.astype(object).where(pd.notna(frame), None)
    return [
        {str(key): value for key, value in record.items()}
        for record in normalized.to_dict(orient="records")
    ]


def _markdown_table(frame: pd.DataFrame) -> str:
    columns = [str(column) for column in frame.columns]
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    rows = []
    for record in _json_records(frame):
        rows.append(
            "| "
            + " | ".join(
                "" if record[column] is None else str(record[column])
                for column in columns
            )
            + " |"
        )
    return "\n".join([header, separator, *rows])


def render_trial_report(
    manifest: dict[str, Any], metrics: dict[str, Any], report_path: Path
) -> None:
    """Write one inspectable Markdown report bound to its complete manifest."""

    deltas = manifest.get("benchmark_deltas", {})
    warning = (
        "\n> Warning: very small trade count; interpret comparisons cautiously.\n"
        if int(metrics["number_of_trades"]) < 5
        else ""
    )
    metric_lines = [f"| {name} | {value} |" for name, value in metrics.items()]
    delta_lines = [f"| {name} | {value} |" for name, value in deltas.items()]
    limitations = [
        "Normalized adjusted opens are a research proxy, not actual broker fills.",
        "Daily historical simulation cannot establish future or execution validity.",
        "Volume is preserved for provenance and not used by the strategy.",
    ]
    git_line = (
        f"- Git: `{manifest['git_commit']}` on `{manifest['git_branch']}`; "
        f"dirty = `{manifest['dirty_worktree']}`"
    )
    period_line = (
        f"- Asset and split: `{manifest['asset']}` / "
        f"`{manifest['temporal_split']}` ({manifest['effective_start']} through "
        f"{manifest['effective_end']})"
    )
    price_line = (
        f"- Price basis: `{manifest['price_basis']}` / normalization "
        f"`{manifest['normalization_version']}`"
    )
    friction_line = (
        f"- Modeled all-in friction: `{manifest['friction_bps']}` bps per actual "
        "side, charged exactly once."
    )
    failure_modes = (
        "\n".join(f"- {item}" for item in manifest["expected_failure_modes"])
        or "- None for this control."
    )
    report = f"""# Trial {manifest["trial_id"]}

## Identity and provenance

- Experiment: `{manifest["experiment_id"]}`
- Strategy: `{manifest["strategy_id"]}` version `{manifest["strategy_version"]}`
- Specification hash: `{manifest["spec_hash"]}`
{git_line}
- Dataset: `{manifest["dataset_id"]}` / `{manifest["dataset_checksum"]}`
{period_line}
- Purpose: `{manifest["purpose"]}`
- Parameters: `{manifest["parameters"]}`

## Causal, price, and execution assumptions

{price_line}
- Decision: confirmed close t using information through t only.
- Fill: next valid XNYS regular-session normalized open.
{friction_line}
- Sizing: whole shares from available unleveraged cash; long/cash only.
- Terminal convention: `{manifest["terminal_convention"]}`
- Engine: `{manifest["engine_name"]}` `{manifest["engine_version"]}` behind the adapter.
{warning}
## Canonical metrics

| Metric | Value |
| --- | ---: |
{chr(10).join(metric_lines)}

## Matching Buy & Hold deltas

| Delta | Value |
| --- | ---: |
{chr(10).join(delta_lines) if delta_lines else "| unavailable | None |"}

## Expected failure modes

{failure_modes}

## Limitations

{chr(10).join(f"- {item}" for item in limitations)}

Native-engine reference extraction status: `{manifest["engine_reference"]}`.
Canonical analytical hash: `{manifest["canonical_analytical_hash"]}`.

> {RESEARCH_WARNING}
"""
    report_path.write_text(report, encoding="utf-8")


def plot_equity(equity_curve: pd.DataFrame, path: Path, title: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(9, 4.5))
    x = pd.to_datetime(equity_curve["session"])
    axis.plot(x, equity_curve["net_equity"], label="Net equity", linewidth=1.4)
    axis.plot(
        x,
        equity_curve["gross_equity"],
        label="Gross equity",
        linewidth=1.0,
        alpha=0.65,
    )
    axis.set_title(title)
    axis.set_xlabel("Session")
    axis.set_ylabel("USD")
    axis.grid(alpha=0.2)
    axis.legend()
    figure.tight_layout()
    figure.savefig(path, dpi=120, metadata={"Software": "TradingLAB V0.1"})
    plt.close(figure)


def aggregate_report(rows: pd.DataFrame, output_root: Path, experiment_id: str) -> Path:
    """Create a new immutable cross-asset/temporal/sensitivity report directory."""

    if rows.empty:
        raise ValueError(f"no completed trials for experiment {experiment_id}")
    analytical_columns = sorted(
        column for column in rows.columns if column not in {"trial_id", "artifact_dir"}
    )
    report_hash = sha256_bytes(
        canonical_json_bytes(
            _json_records(
                rows.loc[:, analytical_columns].sort_values(
                    analytical_columns, kind="stable"
                )
            )
        )
    )
    report_id = f"report_{experiment_id}_{report_hash[:12]}"
    directory = output_root / report_id
    if directory.exists():
        expected = directory / "all_trials.csv"
        if not expected.is_file():
            raise FileExistsError(f"incomplete immutable report directory: {directory}")
        return directory
    directory.mkdir(parents=True, exist_ok=False)
    rows.sort_values(
        ["temporal_split", "asset", "strategy_id", "purpose", "friction_bps"],
        kind="stable",
    ).to_csv(directory / "all_trials.csv", index=False, lineterminator="\n")

    primary = rows[rows["purpose"] == "primary"]
    summary = (
        primary.groupby(["strategy_id", "temporal_split"], dropna=False)
        .agg(
            median_CAGR=("CAGR", "median"),
            worst_CAGR=("CAGR", "min"),
            median_Sharpe=("Sharpe", "median"),
            worst_max_drawdown=("max_drawdown", "min"),
            assets=("asset", "nunique"),
        )
        .reset_index()
    )
    summary.to_csv(
        directory / "cross_asset_summary.csv", index=False, lineterminator="\n"
    )
    sensitivity = rows[
        rows["purpose"].isin(["parameter_sensitivity", "friction_sensitivity"])
    ]
    sensitivity.to_csv(
        directory / "sensitivities.csv", index=False, lineterminator="\n"
    )

    sections: list[str] = []
    for split in ("development", "validation_oos", "project_holdout"):
        subset = primary[primary["temporal_split"] == split]
        if subset.empty:
            continue
        columns = [
            "asset",
            "strategy_id",
            "CAGR",
            "Sharpe",
            "max_drawdown",
            "number_of_trades",
            "delta_CAGR_vs_buy_hold",
            "delta_Sharpe_vs_buy_hold",
            "delta_max_drawdown_vs_buy_hold",
        ]
        sections.append(f"## {split}\n\n{_markdown_table(subset[columns])}")
    small_count = int((rows["number_of_trades"] < 5).sum())
    markdown = f"""# TradingLAB V0.1 robustness report

Experiment: `{experiment_id}`  
Analytical report hash: `{report_hash}`

This report preserves every asset and split separately. Median and worst
cross-asset summaries are descriptive and never replace individual results.
Primary configurations remain frozen; sensitivity results do not promote a
winner. Small-trade-count warnings: {small_count} trials below five lifecycles.

{chr(10).join(sections)}

## Sensitivity contract

Parameter trials vary exactly one predeclared dimension at 5 bps. Friction
trials use only frozen primary parameters at 0/5/10/25 bps. There is no
Cartesian search, automatic optimization, or automatic promotion.

The detailed tables are `all_trials.csv`, `cross_asset_summary.csv`, and
`sensitivities.csv`. Poor and unattractive outcomes remain present.

> {RESEARCH_WARNING}
"""
    (directory / "report.md").write_text(markdown, encoding="utf-8")
    return directory
