from __future__ import annotations

import math

import pytest

from mouse_pressure.bridge.config import ChannelConfig, RuntimeConfig
from mouse_pressure.bridge.curves import (
    apply_curve,
    map_normalized_pressure,
    map_pressure,
    monotone_curve,
    pressure_config_for_channel,
)
from mouse_pressure.runtime.config_store import (
    runtime_config_from_dict,
    runtime_config_to_dict,
)
from mouse_pressure.runtime.models import validate_channel_config


@pytest.mark.parametrize("curve", ["linear", "soft", "hard", "scurve", "custom"])
@pytest.mark.parametrize("gamma", [1.1, 2.0, 4.0])
def test_every_curve_reaches_the_exact_endpoints(curve: str, gamma: float) -> None:
    config = pressure_config_for_channel(
        ChannelConfig(curve=curve, curve_strength=gamma, full_output_at_pct=95)
    )
    assert map_pressure(config.raw_min, config) == 0
    assert map_pressure(config.raw_max, config) == 1023
    assert map_normalized_pressure(0.95, config) == 1023
    assert map_normalized_pressure(1, config) == 1023
    assert map_normalized_pressure(0.949, config) <= 1023


@pytest.mark.parametrize("curve", ["linear", "soft", "hard", "scurve", "custom"])
def test_curve_output_never_falls_as_pressure_rises(curve: str) -> None:
    config = pressure_config_for_channel(ChannelConfig(curve=curve))
    mapped = [map_normalized_pressure(i / 1024, config) for i in range(1025)]
    assert mapped == sorted(mapped)
    assert all(0 <= value <= 1023 for value in mapped)


def test_custom_monotone_spline_has_no_overshoot_or_kinks() -> None:
    presets = (
        (0, 25, 50, 75, 100),
        (0, 0, 0, 90, 100),
        (0, 70, 88, 96, 100),
        (0, 3, 17, 42, 100),
    )
    for points in presets:
        values = [monotone_curve(i / 1000, points) for i in range(1001)]
        assert values == sorted(values)
        assert values[0] == 0
        assert values[-1] == 1
        for index, knot in enumerate(points):
            assert math.isclose(monotone_curve(index / 4, points), knot / 100)


def test_full_output_knob_reaches_max_below_calibrated_peak() -> None:
    for full_at in (70, 80, 90, 95, 100):
        channel = ChannelConfig(
            raw_min=300,
            raw_max=700,
            curve="soft",
            curve_strength=4.0,
            full_output_at_pct=full_at,
        )
        cfg = pressure_config_for_channel(channel)
        raw = 300 + math.ceil((700 - 300) * full_at / 100)
        assert map_pressure(raw, cfg) == 1023
        assert map_pressure(700, cfg) == 1023


def test_raw_mapping_and_normalized_mapping_share_one_scale() -> None:
    cfg = pressure_config_for_channel(
        ChannelConfig(curve="soft", curve_strength=3.2, deadzone_low=4, deadzone_high=4)
    )
    for raw in range(200, 900):
        normalized = (raw - cfg.raw_min) / (cfg.raw_max - cfg.raw_min)
        assert map_pressure(raw, cfg) == map_normalized_pressure(normalized, cfg)


def test_legacy_settings_load_as_schema_two() -> None:
    original = RuntimeConfig()
    raw = runtime_config_to_dict(original)
    raw["schema_version"] = 1
    raw["left"].pop("custom_curve_points")
    raw["left"].pop("full_output_at_pct")
    raw["right"].pop("custom_curve_points")
    raw["right"].pop("full_output_at_pct")
    parsed = runtime_config_from_dict(raw)
    assert parsed.schema_version == 2
    assert parsed.left.full_output_at_pct == 95
    assert parsed.left.custom_curve_points == (0, 25, 50, 75, 100)


@pytest.mark.parametrize("points", [
    (0, 50, 35, 90, 100),
    (0, 20, 40, 60, 90),
    (0, 20, 40, 60),
    (-1, 20, 40, 60, 100),
    (0, 20, 40, 60, True),
])
def test_invalid_control_points_rejected(points: tuple[int, ...]) -> None:
    channel = ChannelConfig(custom_curve_points=points)
    errors = validate_channel_config(vars(channel))
    assert any("custom_curve_points" in error for error in errors)


def test_custom_curve_is_distinct_from_power_curve() -> None:
    custom = pressure_config_for_channel(
        ChannelConfig(curve="custom", custom_curve_points=(0, 2, 15, 65, 100))
    )
    exponential = pressure_config_for_channel(
        ChannelConfig(curve="soft", curve_strength=3.0)
    )
    assert apply_curve(0.5, custom) > apply_curve(0.5, exponential)
