from pathlib import Path

import pytest

from tradinglab.experiments import battery_configurations
from tradinglab.specs import load_spec, specification_hash


def test_all_canonical_specs_validate_and_hash_deterministically(
    spec_dir: Path,
) -> None:
    paths = sorted(spec_dir.glob("*.yaml"))
    first = [
        (load_spec(path).strategy_id, specification_hash(load_spec(path)))
        for path in paths
    ]
    second = [
        (load_spec(path).strategy_id, specification_hash(load_spec(path)))
        for path in paths
    ]
    assert first == second
    assert len(first) == 4
    assert len({digest for _, digest in first}) == 4


def test_executable_yaml_tag_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "unsafe.yaml"
    path.write_text(
        "!!python/object/apply:os.system ['echo forbidden']\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="unsafe or invalid YAML"):
        load_spec(path)


def test_extra_or_drifted_specification_fields_are_rejected(
    spec_dir: Path, tmp_path: Path
) -> None:
    source = (spec_dir / "TREND_SMA200_V1.yaml").read_text(encoding="utf-8")
    path = tmp_path / "drift.yaml"
    path.write_text(
        source.replace("warmup_bars: 200", "warmup_bars: 199"), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="closed behavior"):
        load_spec(path)


def test_battery_is_predeclared_deduplicated_and_non_cartesian() -> None:
    configurations = battery_configurations()
    canonical = {
        (strategy, str(parameters), friction, purpose)
        for strategy, parameters, friction, purpose in configurations
    }
    assert len(configurations) == len(canonical) == 21
    parameter = [item for item in configurations if item[3] == "parameter_sensitivity"]
    friction = [item for item in configurations if item[3] == "friction_sensitivity"]
    assert len(parameter) == 8
    assert len(friction) == 9
    assert all(item[2] == 5 for item in parameter)
    assert all(
        item[1]
        in (
            {"sma": 200},
            {"lookback": 20, "entry_z": -2.0, "exit_z": 0.0, "max_hold": 10},
        )
        for item in friction
        if item[0] != "BUY_HOLD_V1"
    )
