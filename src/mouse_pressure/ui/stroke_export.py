"""Export recorded pen geometry without requiring a drawing application."""

from __future__ import annotations

import csv
import io
from typing import Any
from xml.sax.saxutils import escape

_EXPORT_FIELDS = (
    "seq", "t_ms", "x", "y", "pressure", "rotation",
    "tilt_x", "tilt_y", "flags", "ok",
)


def injected_samples(trace: dict[str, Any]) -> list[dict[str, Any]]:
    events = trace.get("events", [])
    if not isinstance(events, list):
        raise ValueError("Stroke events must be an array")
    selected = [
        item for item in events
        if isinstance(item, dict)
        and item.get("kind") == "inject"
        and item.get("ok", True)
        and all(key in item for key in ("x", "y", "pressure"))
    ]
    if not selected:
        raise ValueError("The stroke has no completed pen samples")
    return selected


def stroke_to_csv(trace: dict[str, Any]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=_EXPORT_FIELDS, lineterminator="\n")
    writer.writeheader()
    for event in injected_samples(trace):
        writer.writerow({key: event.get(key, "") for key in _EXPORT_FIELDS})
    return output.getvalue()


def stroke_to_svg(
    trace: dict[str, Any], *, max_width: float = 16.0, minimum_size: float = 0.7
) -> str:
    if not 0.25 <= max_width <= 300:
        raise ValueError("Brush diameter must be between 0.25 and 300 pixels")
    if not 0 <= minimum_size <= 1:
        raise ValueError("Minimum diameter must be between 0 and 100%")
    points: list[tuple[float, float, float]] = []
    for event in injected_samples(trace):
        pressure = max(0.0, min(1.0, float(event["pressure"]) / 1024.0))
        if pressure <= 0:
            continue
        point = (float(event["x"]), float(event["y"]), pressure)
        if points and points[-1][:2] == point[:2]:
            points[-1] = point
        else:
            points.append(point)
    if not points:
        raise ValueError("The stroke contains no pen contact")

    def diameter(pressure: float) -> float:
        return max_width * (minimum_size + (1 - minimum_size) * pressure)

    margin = max_width / 2 + 2
    minimum_x = min(x for x, _, _ in points) - margin
    minimum_y = min(y for _, y, _ in points) - margin
    maximum_x = max(x for x, _, _ in points) + margin
    maximum_y = max(y for _, y, _ in points) + margin
    viewbox = (
        f"{minimum_x:.3f} {minimum_y:.3f} "
        f"{maximum_x-minimum_x:.3f} {maximum_y-minimum_y:.3f}"
    )
    elements = []
    for previous, current in zip(points, points[1:]):
        x1, y1, p1 = previous
        x2, y2, p2 = current
        if (x1, y1) == (x2, y2):
            continue
        width = (diameter(p1) + diameter(p2)) / 2.0
        elements.append(
            f'<path d="M {x1:.3f} {y1:.3f} L {x2:.3f} {y2:.3f}" '
            f'stroke-width="{width:.3f}"/>'
        )
    for x, y, pressure in points:
        elements.append(
            f'<circle cx="{x:.3f}" cy="{y:.3f}" '
            f'r="{diameter(pressure)/2:.3f}"/>'
        )
    body = "\n  ".join(elements)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="{escape(viewbox)}" '
        f'width="{maximum_x-minimum_x:.1f}" '
        f'height="{maximum_y-minimum_y:.1f}">\n'
        '  <g fill="#202020" stroke="#202020" '
        'stroke-linecap="round" stroke-linejoin="round">\n'
        f'  {body}\n'
        '  </g>\n</svg>\n'
    )
