"""Materialize normalized local CSVs for the LEAN custom-data subscription."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from .contract import ASSETS


def prepare(snapshot_root: Path, output_root: Path) -> int:
    target = output_root / "v0_2_normalized"
    target.mkdir(parents=True, exist_ok=True)
    for asset in ASSETS:
        source = snapshot_root / asset / "normalized.csv"
        destination = target / f"{asset}.csv"
        with (
            source.open(newline="", encoding="utf-8") as source_handle,
            destination.open("w", newline="", encoding="utf-8") as destination_handle,
        ):
            reader = csv.DictReader(source_handle)
            writer = csv.DictWriter(
                destination_handle,
                fieldnames=("date", "open", "high", "low", "close", "volume"),
            )
            writer.writeheader()
            for row in reader:
                writer.writerow(
                    {
                        "date": row["Session"][:10],
                        "open": row["Open"],
                        "high": row["High"],
                        "low": row["Low"],
                        "close": row["Close"],
                        "volume": row["Volume"],
                    }
                )
    return len(ASSETS)


def main() -> int:
    parser = argparse.ArgumentParser(description="prepare local normalized LEAN data")
    parser.add_argument("--snapshot-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=Path("v0_2_lean/lean_data"))
    args = parser.parse_args()
    print(f"prepared={prepare(args.snapshot_root, args.output_root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
