import os
import importlib.util
from pathlib import Path

import pytest


pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None,
    reason="PySide6 is not installed",
)


def test_main_window_loads_sample_and_updates_selected_aircraft() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from ase_editor.ui import AircraftEditorDialog, MainWindow

    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    assert [action.text() for action in window.menuBar().actions()] == ["Menu", "View", "Help"]
    assert len(window.scenario.aircraft) == 14
    assert len(window.strip_rows) == 14
    assert not hasattr(window, "target_dock")
    assert window.canvas.icons
    assert window.canvas.range_nm in {10, 20, 40, 80, 120}
    assert window.scenario.aircraft[0].target_kind == "vehicle"
    assert not hasattr(window, "load_sector_button")
    assert not hasattr(window, "spawn_aircraft_button")
    assert window.load_sector_action.text() == "Load Sector Files (.sct)"
    assert window.load_scenario_action.text() == "Load Scenario (.txt)"
    menu_actions = [action.text() for action in window.menuBar().actions()[0].menu().actions()]
    assert "Spawn Aircraft" not in menu_actions
    assert "New Aircraft" not in menu_actions
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
    assert window.diagrams_action.text() == "Diagrams"
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
    window.load_sector(Path("WIII_Demo.sct"))
    assert window.sector_path and window.sector_path.name == "WIII_Demo.sct"
    assert "WIII_Demo.sct" in window.sector_status.text()
    assert window.sector_points
    assert window.sector_lines
    assert window.traffic_dock.width() == 320
    window.toggle_left_sidebar()
    assert window.traffic_dock.width() == 44
    window.toggle_left_sidebar()
    assert window.traffic_dock.width() == 320

    aircraft = window.scenario.aircraft[2]
    window.select_aircraft(aircraft)
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
