from __future__ import annotations

import csv
import io
import xml.etree.ElementTree as ET

import pytest

from mouse_pressure.ui.stroke_export import (
    injected_samples,
    stroke_to_csv,
    stroke_to_svg,
)


@pytest.fixture()
def stroke() -> dict:
    return {
        "schema_version": 2,
        "metadata": {"button": "left"},
        "events": [
            {"kind": "motion", "x": 10, "y": 20},
            {"kind": "inject", "seq": 1, "t_ms": 0, "x": 10, "y": 20,
             "pressure": 250, "rotation": 180, "ok": True},
            {"kind": "inject", "seq": 2, "t_ms": 4, "x": 20, "y": 30,
             "pressure": 700, "rotation": 190, "ok": True},
            {"kind": "inject", "seq": 3, "t_ms": 7, "x": 30, "y": 45,
             "pressure": 1024, "rotation": 200, "ok": True},
            {"kind": "inject", "seq": 4, "t_ms": 10, "x": 30, "y": 45,
             "pressure": 0, "ok": True},
        ],
    }


def test_csv_exports_pen_samples_with_pressure_and_rotation(stroke: dict) -> None:
    rows = list(csv.DictReader(io.StringIO(stroke_to_csv(stroke))))
    assert len(rows) == 4
    assert [row["pressure"] for row in rows] == ["250", "700", "1024", "0"]
    assert rows[1]["rotation"] == "190"


def test_svg_is_vector_geometry_with_pressure_width(stroke: dict) -> None:
    text = stroke_to_svg(stroke, max_width=24, minimum_size=0.7)
    root = ET.fromstring(text)
    assert root.tag.endswith("svg")
    ns = {"svg": "http://www.w3.org/2000/svg"}
    segments = root.findall(".//svg:path", ns)
    circles = root.findall(".//svg:circle", ns)
    assert len(segments) == 2
    assert len(circles) == 3
    assert float(segments[0].attrib["stroke-width"]) < 24
    assert float(segments[-1].attrib["stroke-width"]) > float(
        segments[0].attrib["stroke-width"]
    )
    assert float(root.attrib["width"]) > 20
    assert float(root.attrib["height"]) > 25


def test_single_stationary_pressure_dab_exports_circle() -> None:
    trace = {"events": [{
        "kind": "inject", "x": 100, "y": 50, "pressure": 512, "ok": True,
    }]}
    svg = stroke_to_svg(trace)
    assert "<circle" in svg
    assert "<path" not in svg


def test_unfinished_and_failed_injections_are_not_exported(stroke: dict) -> None:
    stroke["events"].append({
        "kind": "inject", "x": 999, "y": 888, "pressure": 400, "ok": False,
    })
    assert len(injected_samples(stroke)) == 4
    assert '999.000' not in stroke_to_svg(stroke)


@pytest.mark.parametrize("bad", [
    {"events": []},
    {"events": [{"kind": "motion", "x": 1, "y": 1}]},
    {"events": "not an array"},
    {"events": [{"kind": "inject", "x": 1, "y": 1, "pressure": 0}]},
])
def test_invalid_or_empty_strokes_fail_cleanly(bad: dict) -> None:
    with pytest.raises(ValueError):
        stroke_to_svg(bad)


def test_svg_diameter_and_minimum_size_are_bounded(stroke: dict) -> None:
    for max_width, minimum_size in ((0, 0.5), (500, 0.5), (16, -0.1), (16, 1.2)):
        with pytest.raises(ValueError):
            stroke_to_svg(stroke, max_width=max_width, minimum_size=minimum_size)
