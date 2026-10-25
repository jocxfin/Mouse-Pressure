from __future__ import annotations

import json
from dataclasses import replace

import pytest

from mouse_pressure.bridge.config import ChannelConfig, RuntimeConfig
from mouse_pressure.runtime.config_store import (
    runtime_config_from_dict,
    runtime_config_to_dict,
)
from mouse_pressure.runtime.profiles import (
    ProfileLibrary,
    application_names,
    validated_mapping,
)


def test_create_select_reload_and_application_matching(tmp_path) -> None:
    baseline = RuntimeConfig()
    library = ProfileLibrary(tmp_path)
    library.load(baseline)
    assert library.get("default").name == "Default"

    drawing = replace(
        baseline,
        left=replace(
            baseline.left,
            curve="custom",
            custom_curve_points=(0, 12, 38, 75, 100),
        ),
        right=replace(baseline.right, output_target="rotation"),
    )
    profile = library.create("Ink & rotation", drawing)
    library.assign(profile.id, "Photoshop.EXE, Krita.exe, Photoshop.exe")
    library.auto_switch = True
    library.save()

    restored = ProfileLibrary(tmp_path)
    restored.load(baseline)
    assert restored.auto_switch
    assert restored.selected_id == profile.id
    assert restored.match("PHOTOSHOP.exe") == profile.id
    assert restored.match("krita.exe") == profile.id
    assert restored.match("notepad.exe") is None
    assert restored.get(profile.id).mapping["left"]["custom_curve_points"] == (
        0, 12, 38, 75, 100
    )


def test_profiles_never_override_device_settings(tmp_path) -> None:
    config = RuntimeConfig(
        session_dpi=1600,
        session_haptic_left=4,
        session_report_rate_hz=2000,
        remap_hold_hotkey="Mouse 4",
        left=ChannelConfig(actuation_level=9, curve="soft"),
    )
    library = ProfileLibrary(tmp_path)
    library.load(config)
    mapping = library.get("default").mapping
    assert "session_dpi" not in mapping
    assert "activation_hotkey" not in mapping
    assert "remap_hold_hotkey" not in mapping
    assert "actuation_level" not in mapping["left"]
    existing = runtime_config_to_dict(config)
    for name, value in mapping.items():
        if isinstance(value, dict):
            existing[name].update(value)
        else:
            existing[name] = value
    applied = runtime_config_from_dict(existing)
    assert applied.session_dpi == 1600
    assert applied.left.actuation_level == 9
    assert applied.remap_hold_hotkey == "Mouse 4"


def test_duplicate_application_assignment_is_rejected(tmp_path) -> None:
    library = ProfileLibrary(tmp_path)
    library.load(RuntimeConfig())
    a = library.create("Photoshop", RuntimeConfig())
    b = library.create("Krita", RuntimeConfig())
    library.assign(a.id, "photoshop.exe")
    with pytest.raises(ValueError, match="assigned"):
        library.assign(b.id, "PHOTOSHOP.EXE")


def test_import_export_roundtrip_preserves_curve_but_not_rules(tmp_path) -> None:
    config = RuntimeConfig(left=ChannelConfig(
        curve="custom", custom_curve_points=(0, 10, 26, 55, 100)
    ))
    library = ProfileLibrary(tmp_path)
    library.load(config)
    profile = library.create("Detailed Ink", config)
    library.assign(profile.id, "Photoshop.exe")
    export = tmp_path / "ink.json"
    library.export_profile(profile.id, export)
    content = json.loads(export.read_text("utf8"))
    assert content["kind"] == "mouse-pressure-profile"
    assert content["applications"] == ["photoshop.exe"]

    imported = library.import_profile(export)
    assert imported.id != profile.id
    assert imported.name == "Detailed Ink (2)"
    assert imported.applications == ()
    assert imported.mapping["left"]["custom_curve_points"] == (0, 10, 26, 55, 100)


def test_update_rename_delete_are_persistent(tmp_path) -> None:
    library = ProfileLibrary(tmp_path)
    library.load(RuntimeConfig())
    profile = library.create("Airbrush", RuntimeConfig())
    library.rename(profile.id, "Soft Shading")
    library.update(profile.id, RuntimeConfig(
        left=ChannelConfig(curve="hard", pressure_floor=4)
    ))
    library.remove(profile.id)
    assert library.selected_id == "default"
    with pytest.raises(ValueError, match="one profile"):
        library.remove("default")
    loaded = ProfileLibrary(tmp_path)
    loaded.load(RuntimeConfig())
    assert [entry.name for entry in loaded.profiles] == ["Default"]


@pytest.mark.parametrize("exe", [
    r"C:\Windows\photoshop.exe",
    "../krita.exe",
    "Photoshop",
    "c:\\",
])
def test_executable_names_cannot_include_paths(exe: str) -> None:
    with pytest.raises(ValueError):
        application_names(exe)


@pytest.mark.parametrize("invalid", [
    {"left": {}, "right": {}, "session_dpi": 900},
    {"right": {}},
    {"left": {}, "right": {}, "left_enabled": "true"},
])
def test_profile_mapping_rejects_unrelated_or_invalid_data(invalid: dict) -> None:
    with pytest.raises((ValueError, TypeError)):
        validated_mapping(invalid)


def test_library_version_validation_preserves_file(tmp_path) -> None:
    library = ProfileLibrary(tmp_path)
    library.path.write_text('{"version":77,"profiles":[]}', "utf8")
    with pytest.raises(ValueError, match="version"):
        library.load(RuntimeConfig())
    assert '"version":77' in library.path.read_text("utf8")
