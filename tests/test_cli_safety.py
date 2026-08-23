import re
from pathlib import Path

from tradinglab.cli import build_parser


def test_cli_exposes_only_declared_local_research_operations() -> None:
    help_text = build_parser().format_help()
    for command in (
        "fetch",
        "validate-dataset",
        "validate-candle-file",
        "run",
        "run-battery",
        "report",
        "registry",
        "reproduce",
    ):
        assert command in help_text
    assert "submit" not in help_text.lower()


def test_battery_accepts_explicit_experiment_continuation() -> None:
    args = build_parser().parse_args(
        [
            "run-battery",
            "--dataset-id",
            "dataset",
            "--splits",
            "development",
            "--experiment-id",
            "experiment",
        ]
    )
    assert args.experiment_id == "experiment"


def test_no_broker_dependency_client_credentials_or_submission_path(
    project_root: Path,
) -> None:
    pyproject = (project_root / "pyproject.toml").read_text(encoding="utf-8").lower()
    for forbidden_dependency in ("alpaca", "ib_insync", "ccxt", "metatrader", "lean"):
        assert forbidden_dependency not in pyproject
    sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (project_root / "src" / "tradinglab").rglob("*.py")
    )
    for forbidden_symbol in (
        r"\bsubmit_order\b",
        r"\bplace_order\b",
        r"\bbroker_client\b",
        r"\bapi_key\b",
        r"\bsecret_key\b",
        r"Backtest\.optimize",
    ):
        assert re.search(forbidden_symbol, sources, flags=re.IGNORECASE) is None
    network_imports = [
        path
        for path in (project_root / "src" / "tradinglab").rglob("*.py")
        if re.search(
            r"^(?:import|from)\s+(requests|httpx|aiohttp|socket)\b",
            path.read_text(encoding="utf-8"),
            flags=re.MULTILINE,
        )
    ]
    assert network_imports == []
    assert "yfinance" in (
        project_root / "src" / "tradinglab" / "data_source" / "yfinance_source.py"
    ).read_text(encoding="utf-8")
