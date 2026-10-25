from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import mouse_pressure.pyside_ui as ui_module  # noqa: E402
from mouse_pressure.bridge.config import LaunchConfig  # noqa: E402
from mouse_pressure.dev_ui import BridgeController  # noqa: E402
from mouse_pressure.pyside_ui import MainWindow  # noqa: E402
from mouse_pressure.runtime.config_store import ConfigStore  # noqa: E402
from mouse_pressure.runtime.log_bus import LogBus  # noqa: E402
from mouse_pressure.runtime.runtime_service import RuntimeService  # noqa: E402
from mouse_pressure.ui.qt_widgets import CustomCurveEditor  # noqa: E402


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_curve_editor_supports_dragging_and_keyboard_changes() -> None:
    _app()
    curve = CustomCurveEditor()
    curve.resize(380, 220)
    curve.show()
    changed = []
    curve.pointsChanged.connect(changed.append)
    curve.set_points((0, 18, 49, 80, 100))
    curve.set_point(2, 99)
    assert curve.points() == (0, 18, 80, 80, 100)
    curve.set_point(2, 30)
    QTest.keyClick(curve, Qt.Key.Key_Up)
    assert curve.points()[2] == 31
    assert changed
    curve.close()


def test_live_profile_switching_waits_until_pen_contact_ends(
    tmp_path: Path, monkeypatch
) -> None:
    _app()
    store = ConfigStore(tmp_path)
    log = LogBus(maxlen=100)
    service = RuntimeService(
        launch_config=LaunchConfig(config_dir=str(tmp_path)),
        config_store=store,
        log_bus=log,
    )
    controller = BridgeController(service)
    window = MainWindow(service, controller, log, store)
    window.profile_timer.stop()
    window.event_timer.stop()
    try:
        base = service.get_config()
        drawing = replace(
            base, left=replace(base.left, curve="soft", full_output_at_pct=85)
        )
        profile = window.profile_library.create("Photoshop", drawing)
        window.profile_library.assign(profile.id, "Photoshop.exe")
        window.profile_library.selected_id = "default"
        window.profile_library.auto_switch = True
        window.profile_library.save()
        monkeypatch.setattr(ui_module, "foreground_executable", lambda: "photoshop.exe")
        busy_button = True
        monkeypatch.setattr(ui_module, "mouse_buttons_down", lambda: busy_button)

        window._check_auto_profile()
        window._check_auto_profile()
        assert window._active_profile_id == "default"
        busy_button = False
        window._check_auto_profile()
        assert window._active_profile_id == profile.id
        assert service.get_config().left.curve == "soft"
        assert service.get_config().left.full_output_at_pct == 85

        monkeypatch.setattr(ui_module, "foreground_executable", lambda: "notepad.exe")
        window._check_auto_profile()
        window._check_auto_profile()
        assert window._active_profile_id == "default"
        assert service.get_config().left.curve == base.left.curve
        assert len(window.nav_buttons) == 5
    finally:
        window.hide()
        controller.close()
