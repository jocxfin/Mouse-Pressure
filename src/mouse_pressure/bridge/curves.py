"""Pressure calibration and curve mapping."""

from dataclasses import dataclass

from mouse_pressure.bridge.config import ChannelConfig

_CURVE_ALIASES = {
    "linear": "linear",
    "soft": "ease_in",
    "hard": "ease_out",
    "scurve": "s_curve",
    "custom": "custom",
    "ease_in": "ease_in",
    "ease_out": "ease_out",
    "s_curve": "s_curve",
}


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


@dataclass
class PressureConfig:
    raw_min: int = 320
    raw_max: int = 680
    out_min: int = 0
    out_max: int = 1023
    deadzone_low: float = 0.05
    deadzone_high: float = 0.95
    curve: str = "s_curve"
    curve_strength: float = 2.0
    custom_curve_points: tuple[int, int, int, int, int] = (0, 25, 50, 75, 100)
    full_output_at_pct: int = 95


def pressure_config_for_channel(channel: ChannelConfig) -> PressureConfig:
    return PressureConfig(
        raw_min=channel.raw_min,
        raw_max=channel.raw_max,
        out_min=0,
        out_max=1023,
        deadzone_low=channel.deadzone_low / 100.0,
        deadzone_high=1.0 - channel.deadzone_high / 100.0,
        curve=normalize_curve_name(channel.curve),
        curve_strength=channel.curve_strength,
        custom_curve_points=channel.custom_curve_points,
        full_output_at_pct=channel.full_output_at_pct,
    )


def normalize_curve_name(name: str) -> str:
    normalized = _CURVE_ALIASES.get(str(name).lower())
    if normalized is None:
        raise ValueError(f"Unknown curve name: {name!r}")
    return normalized


def monotone_curve(t: float, percentages: tuple[int, ...]) -> float:
    """Interpolate five fixed-X knots without overshoot or pressure reversals."""
    t = _clamp01(t)
    values = [float(value) / 100.0 for value in percentages]
    if t <= 0.0:
        return values[0]
    if t >= 1.0:
        return values[-1]

    delta = [4.0 * (b - a) for a, b in zip(values, values[1:])]
    tangent = [0.0] * 5
    tangent[0] = max(0.0, min(3.0 * delta[0], 1.5 * delta[0] - 0.5 * delta[1]))
    tangent[-1] = max(0.0, min(3.0 * delta[-1], 1.5 * delta[-1] - 0.5 * delta[-2]))
    for index in (1, 2, 3):
        a, b = delta[index - 1], delta[index]
        tangent[index] = 2.0 * a * b / (a + b) if a > 0.0 and b > 0.0 else 0.0

    segment = min(3, int(t * 4.0))
    u = t * 4.0 - segment
    u2, u3 = u * u, u * u * u
    result = (
        (2 * u3 - 3 * u2 + 1) * values[segment]
        + (u3 - 2 * u2 + u) * tangent[segment] / 4.0
        + (-2 * u3 + 3 * u2) * values[segment + 1]
        + (u3 - u2) * tangent[segment + 1] / 4.0
    )
    return max(values[segment], min(values[segment + 1], result))


def apply_curve(normalized: float, config: PressureConfig) -> float:
    t = _clamp01(normalized)
    if t == 0.0 or t == 1.0:
        return t
    gamma = config.curve_strength
    curve = normalize_curve_name(config.curve)

    if curve == "linear":
        return t
    if curve == "ease_in":
        return t**gamma
    if curve == "ease_out":
        return 1.0 - (1.0 - t) ** gamma
    if curve == "s_curve":
        if t < 0.5:
            return 0.5 * (2.0 * t) ** gamma
        return 1.0 - 0.5 * (2.0 * (1.0 - t)) ** gamma
    if curve == "custom":
        return monotone_curve(t, config.custom_curve_points)
    return t


def map_normalized_pressure(normalized: float, config: PressureConfig) -> int:
    t = _clamp01(normalized)
    if t <= config.deadzone_low:
        return config.out_min
    if t >= config.deadzone_high:
        return config.out_max

    active_range = config.deadzone_high - config.deadzone_low
    if active_range <= 0.0:
        return config.out_min

    t = _clamp01((t - config.deadzone_low) / active_range)
    full_scale = config.full_output_at_pct / 100.0
    t = _clamp01(t / full_scale)
    if t >= 1.0:
        return config.out_max

    result = config.out_min + apply_curve(t, config) * (
        config.out_max - config.out_min
    )
    return max(config.out_min, min(config.out_max, round(result)))


def map_pressure(raw_value: int, config: PressureConfig) -> int:
    raw_range = config.raw_max - config.raw_min
    if raw_range <= 0:
        return config.out_min
    return map_normalized_pressure(
        (raw_value - config.raw_min) / raw_range,
        config,
    )
