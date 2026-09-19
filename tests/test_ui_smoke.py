import os
import importlib.util
from pathlib import Path

import pytest


pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None,
    reason="PySide6 is not installed",
)


def test_main_window_loads_sample_and_updates_selected_aircraft(tmp_path, monkeypatch) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("ASE_EDITOR_SETTINGS_PATH", str(tmp_path / "settings.ini"))

    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from ase_editor.ui import AircraftEditorDialog, MainWindow, RANGE_PRESETS_NM

    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    assert [action.text() for action in window.menuBar().actions()] == ["Menu", "View", "Theme", "Help"]
    assert len(window.scenario.aircraft) == 14
    assert len(window.strip_rows) == 14
    assert not hasattr(window, "target_dock")
    assert window.canvas.icons
    assert window.canvas.range_nm in RANGE_PRESETS_NM
    assert window.scenario.aircraft[0].target_kind == "vehicle"
    assert set(window.strip_category_rows) == {"Ground Vehicle", "Aircraft"}
    assert window.strip_category_rows["Ground Vehicle"][0].label.text().startswith("GROUND VEHICLE")
    assert window.strip_category_rows["Aircraft"][0].label.text().startswith("AIRCRAFT")
    window._toggle_strip_category("Ground Vehicle")
    assert window.strip_category_rows["Ground Vehicle"][0].collapsed
    assert all(row.isHidden() for row in window.strip_category_rows["Ground Vehicle"][1])
    window._toggle_strip_category("Ground Vehicle")
    assert not hasattr(window, "load_sector_button")
    assert not hasattr(window, "spawn_aircraft_button")
    assert not hasattr(window, "load_sector_action")
    assert window.load_database_menu.title() == "Load Database"
    assert window.load_database_actions["Indonesia"].text() == "Indonesia"
    assert window.load_scenario_action.text() == "Load Scenario (.txt)"
    menu_actions = [action.text() for action in window.menuBar().actions()[0].menu().actions()]
    assert "Load Database" in menu_actions
    assert "Load Sector Files (.sct)" not in menu_actions
    assert "Spawn Aircraft" not in menu_actions
    assert "New Aircraft" not in menu_actions
    theme_menu = window.menuBar().actions()[2].menu()
    assert theme_menu is not None
    assert [action.text() for action in theme_menu.actions()] == ["Presets", "Edit Colors..."]
    preset_menu = theme_menu.actions()[0].menu()
    assert preset_menu is not None
    assert "vACC Indonesia" in [action.text() for action in preset_menu.actions()]
    assert "UK 2026/09" in [action.text() for action in preset_menu.actions()]
    assert [action.text() for action in window.scenario_toolbar.actions()] == ["New Aircraft", "ILS Threshold"]
    assert window.scenario_toolbar.iconSize().width() == 12
    assert window.scenario_toolbar.iconSize().height() == 12
    aircraft_count = len(window.scenario.aircraft)
    spawn_lat = window.canvas.center_lat
    spawn_lon = window.canvas.center_lon
    window.new_aircraft_action.trigger()
    assert window.pending_new_aircraft
    assert len(window.scenario.aircraft) == aircraft_count
    QTest.mouseClick(window.canvas, Qt.LeftButton, pos=QPoint(window.canvas.width() // 2, window.canvas.height() // 2))
    assert not window.pending_new_aircraft
    assert len(window.scenario.aircraft) == aircraft_count + 1
    assert window.selected is window.scenario.aircraft[-1]
    assert window.selected.latitude == pytest.approx(spawn_lat)
    assert window.selected.longitude == pytest.approx(spawn_lon)
    window.delete_selected_aircraft()
    assert len(window.scenario.aircraft) == aircraft_count
    view_menu = window.menuBar().actions()[1].menu()
    assert view_menu is not None
    assert "Mouse Location" not in [action.text() for action in view_menu.actions()]
    assert "Geography" in window.view_layer_actions
    assert "Diagrams" not in window.view_layer_actions
    assert window.info_sector_action.text() == "Info Sector"
    assert window.diagrams_action.text() == "Diagrams"
    window.open_info_sector_dialog()
    assert window.info_sector_dialog is not None
    assert window.info_sector_dialog.field_edits["name"].text() == "ATC Simulator Indonesia v1.0"
    assert window.info_sector_dialog.field_edits["wx_station"].text() == "WIII"
    window.info_sector_dialog.close()
    window.view_layer_actions["Fixes"].setChecked(False)
    assert not window.canvas.view_layers["Fixes"]
    window.view_layer_actions["Fixes"].setChecked(True)
    assert window.canvas.view_layers["Fixes"]
    window.open_diagrams_dialog()
    assert window.diagram_dialog is not None
    assert window.diagram_dialog.lists["SID"].count() > 0
    first_sid = window.diagram_dialog.lists["SID"].item(0)
    first_sid.setCheckState(Qt.Unchecked)
    assert first_sid.text() in window.canvas.hidden_diagram_labels["SID"]
    window.diagram_dialog.close()
    window.load_database("Indonesia")
    assert window.sector_path and window.sector_path.name == "indonesia.sqlite3"
    assert "DB: Indonesia" in window.sector_status.text()
    assert window.sector_points
    assert window.sector_lines
    assert window.traffic_dock.width() == 320
    window.toggle_left_sidebar()
    assert window.traffic_dock.width() == 44
    window.toggle_left_sidebar()
    assert window.traffic_dock.width() == 320

    aircraft = window.scenario.aircraft[2]
    window.select_aircraft(aircraft)
    assert window.canvas.center_lat == pytest.approx(aircraft.latitude)
    assert window.canvas.center_lon == pytest.approx(aircraft.longitude)
    editor = AircraftEditorDialog(aircraft, window)
    editor.aircraft_saved.connect(window._aircraft_changed)
    editor.resize(655, 623)
    app.processEvents()
    assert editor.position_grid.itemAtPosition(0, 2) is None
    assert editor.latitude.minimumHeight() >= 30
    editor.callsign.setText("TST123")
    editor._save()
    assert aircraft.callsign == "TST123"
    assert any("TST123" in row.property("searchText") for row in window.strip_rows)
    assert window.canvas.selected is aircraft
    assert window.stack_count.text() == "14 ACFT"
    window.open_aircraft_editor(aircraft)
    assert window.editor_dialogs
    for dialog in list(window.editor_dialogs):
        dialog.close()

    window.close()
    app.processEvents()


def test_view_and_geo_diagram_visibility_persist_between_windows(tmp_path, monkeypatch) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("ASE_EDITOR_SETTINGS_PATH", str(tmp_path / "settings.ini"))

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from ase_editor.ui import MainWindow

    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    window.view_layer_actions["Geography"].setChecked(False)
    assert not window.canvas.view_layers["Geography"]

    window.open_diagrams_dialog()
    assert window.diagram_dialog is not None
    geo_list = window.diagram_dialog.lists["GEO"]
    if geo_list.count() == 0 or not geo_list.item(0).flags() & Qt.ItemFlag.ItemIsUserCheckable:
        pytest.skip("Sample sector has no GEO diagram labels")
    window.diagram_dialog.show_all_checks["GEO"].setChecked(False)
    hidden_geo = set(window.canvas.hidden_diagram_labels["GEO"])
    assert hidden_geo
    window.canvas.center_lat = -7.25
    window.canvas.center_lon = 107.5
    window.canvas.set_range_nm(0.5)
    window.close()

    restored = MainWindow()
    assert not restored.view_layer_actions["Geography"].isChecked()
    assert not restored.canvas.view_layers["Geography"]
    assert restored.canvas.hidden_diagram_labels["GEO"] == hidden_geo
    assert restored.canvas.center_lat == pytest.approx(-7.25)
    assert restored.canvas.center_lon == pytest.approx(107.5)
    assert restored.canvas.range_nm == 0.5

    restored.open_diagrams_dialog()
    assert restored.diagram_dialog is not None
    assert not restored.diagram_dialog.show_all_checks["GEO"].isChecked()
    restored.close()
    app.processEvents()
