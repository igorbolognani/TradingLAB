"""Declarative strategy specification loading, validation, and hashing."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from tradinglab.constants import ASSETS, CANONICAL_STRATEGIES
from tradinglab.hashing import canonical_json_bytes, sha256_bytes

Asset = Literal["SPY", "IWM", "EFA", "TLT", "GLD"]
StrategyId = Literal["CASH_0_V1", "BUY_HOLD_V1", "TREND_SMA200_V1", "MEANREV_Z20_V1"]
StrategyFamily = Literal["cash_control", "buy_hold", "trend", "mean_reversion"]
EntryRule = Literal[
    "never",
    "first_eligible_open",
    "close_gt_sma",
    "flat_and_z_lte_entry",
]
ExitRule = Literal["never", "close_lte_sma", "z_gte_exit_or_max_hold"]


class StrictModel(BaseModel):
    """Base for declarative models: no unnoticed specification fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class IndicatorDefinition(StrictModel):
    name: Literal["none", "sma", "zscore"]
    source: Literal["normalized_close", "none"]
    lookback: int = Field(ge=0)
    min_periods: int = Field(ge=0)
    standard_deviation_ddof: Literal[0] | None = None


class PositionSizing(StrictModel):
    method: Literal["none", "all_available_cash_integer"]
    fractional_shares: Literal[False]


class RiskConstraints(StrictModel):
    long_only: Literal[True]
    shorting: Literal[False]
    leverage: Literal[1]
    pyramiding: Literal[False]
    cash_interest: Literal[0]


class StrategyParameters(StrictModel):
    sma: int | None = Field(default=None, ge=1)
    lookback: int | None = Field(default=None, ge=1)
    entry_z: float | None = None
    exit_z: float | None = None
    max_hold: int | None = Field(default=None, ge=1)


class ModeledExecutionFriction(StrictModel):
    concept: Literal["modeled_all_in_execution_friction"]
    base_bps_per_side: Literal[5]
    sensitivity_bps_per_side: tuple[Literal[0, 5, 10, 25], ...]


class StrategySpec(StrictModel):
    strategy_id: StrategyId
    strategy_version: Literal["1"]
    strategy_family: StrategyFamily
    hypothesis: str = Field(min_length=1)
    applicable_assets: tuple[Asset, ...]
    timeframe: Literal["1d_regular_session"]
    price_basis: Literal["yahoo_total_return_adjusted_ohlc_v1"]
    indicator_definitions: tuple[IndicatorDefinition, ...]
    warmup_bars: int = Field(ge=0)
    decision_time: Literal["after_confirmed_close_t"]
    execution_time: Literal["next_valid_regular_session_open"]
    entry_rule: EntryRule
    exit_rule: ExitRule
    position_sizing: PositionSizing
    risk_constraints: RiskConstraints
    parameters: StrategyParameters
    parameter_policy: Literal[
        "fixed_control", "fixed_benchmark", "frozen_primary_predeclared_ota_only"
    ]
    modeled_execution_friction: ModeledExecutionFriction
    benchmark: Literal["none", "matching_asset_buy_hold"]
    expected_failure_modes: tuple[str, ...]

    @model_validator(mode="after")
    def validate_closed_contract(self) -> "StrategySpec":
        """Reject specifications that drift from the four closed V0.1 contracts."""

        if tuple(self.applicable_assets) != ASSETS:
            raise ValueError(
                "applicable_assets must be the five canonical ETFs in order"
            )
        expected_common = {
            "CASH_0_V1": ("cash_control", 0, "never", "never"),
            "BUY_HOLD_V1": (
                "buy_hold",
                0,
                "first_eligible_open",
                "never",
            ),
            "TREND_SMA200_V1": ("trend", 200, "close_gt_sma", "close_lte_sma"),
            "MEANREV_Z20_V1": (
                "mean_reversion",
                20,
                "flat_and_z_lte_entry",
                "z_gte_exit_or_max_hold",
            ),
        }
        family, warmup, entry, exit_rule = expected_common[self.strategy_id]
        actual = (
            self.strategy_family,
            self.warmup_bars,
            self.entry_rule,
            self.exit_rule,
        )
        if actual != (family, warmup, entry, exit_rule):
            raise ValueError(f"{self.strategy_id} does not match its closed behavior")

        params = self.parameters
        if self.strategy_id == "TREND_SMA200_V1" and params != StrategyParameters(
            sma=200
        ):
            raise ValueError("Trend primary parameters must be SMA=200")
        if self.strategy_id == "MEANREV_Z20_V1" and params != StrategyParameters(
            lookback=20, entry_z=-2.0, exit_z=0.0, max_hold=10
        ):
            raise ValueError("Mean Reversion primary parameters are fixed")
        if (
            self.strategy_id in {"CASH_0_V1", "BUY_HOLD_V1"}
            and params != StrategyParameters()
        ):
            raise ValueError("Control and benchmark specifications take no parameters")
        return self


def load_spec(path: Path) -> StrategySpec:
    """Load declarative YAML safely and validate the closed strategy schema."""

    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"unsafe or invalid YAML in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("strategy specification root must be a mapping")
    spec = StrategySpec.model_validate(payload)
    if spec.strategy_id not in CANONICAL_STRATEGIES:
        raise ValueError("only canonical V0.1 strategies are accepted")
    return spec


def specification_hash(spec: StrategySpec) -> str:
    """Hash the validated, normalized declarative representation."""

    return sha256_bytes(canonical_json_bytes(spec.model_dump(mode="json")))
