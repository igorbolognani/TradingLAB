"""Command-line validation runner for the V0.2 independent implementation."""

from __future__ import annotations

import argparse
from pathlib import Path

from .compare import compare_primary, write_comparison_report


def main() -> int:
    parser = argparse.ArgumentParser(description="validate the independent V0.2 replay")
    parser.add_argument("--snapshot-root", type=Path, required=True)
    parser.add_argument("--report-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("v0_2_lean/output"))
    args = parser.parse_args()
    comparison = compare_primary(
        snapshot_root=args.snapshot_root,
        report_csv=args.report_csv,
        artifact_root=args.output_dir,
        output_csv=args.output_dir / "primary_comparison.csv",
    )
    write_comparison_report(comparison, args.output_dir / "comparison_report.json")
    print(
        f"checked={comparison.checked} passed={comparison.passed} "
        f"failed={len(comparison.failures)}"
    )
    for failure in comparison.failures:
        print(failure)
    return 0 if not comparison.failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
