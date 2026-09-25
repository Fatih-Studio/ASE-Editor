import importlib.util

import pytest

from ase_editor.exporter import serialize_scenario
from ase_editor.models import Aircraft, Scenario
from ase_editor.parser import parse_scenario_file, parse_scenario_text


pytestmark = pytest.mark.skipif(importlib.util.find_spec("PySide6") is None, reason="PySide6 is not installed")


@pytest.fixture
def app(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("ASE_EDITOR_SETTINGS_PATH", str(tmp_path / "settings.ini"))
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance() or QApplication([])
    yield application
    application.processEvents()


@pytest.fixture
def window(app, monkeypatch):
    from ase_editor.ui import MainWindow

    monkeypatch.setattr(MainWindow, "_load_startup_data", lambda self: None)
    window = MainWindow()
    window.show()
    app.processEvents()
    yield window
    if window.threshold_dialog is not None:
        window.threshold_dialog.reject()
    for dialog in list(window.editor_dialogs):
        dialog.close()
    window.close()


def fill_dialog(dialog, name="ILS06"):
    values = dict(name=name, latitude1="-6.2722343", longitude1="106.8787898",
                  latitude2="-6.2609290", longitude2="106.9036165")
    for name, value in values.items():
        dialog.fields[name].setText(value)


def test_toolbar_create_cancel_validation_and_selection(window, app):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    window.new_aircraft_action.trigger()
    window.ils_threshold_action.trigger()
    dialog = window.threshold_dialog
    assert dialog.isModal()
    assert not window.pending_new_aircraft
    assert all(edit.text() == "" for edit in dialog.fields.values())
    assert all(edit.isReadOnly() for edit in dialog.fields.values())
    assert dialog.save_button.isHidden() and dialog.cancel_button.isHidden()
    QTest.mouseClick(dialog.add_threshold_button, Qt.LeftButton)
    assert dialog.add_threshold_button.isChecked()
    assert not dialog.threshold_list.isEnabled()
    assert all(not edit.isReadOnly() for edit in dialog.fields.values())
    QTest.mouseClick(dialog.save_button, Qt.LeftButton)
    assert all(not label.isHidden() for label in dialog.errors.values())
    assert window.scenario.thresholds == []
    fill_dialog(dialog)
    QTest.mouseClick(dialog.cancel_button, Qt.LeftButton)
    assert window.threshold_dialog is dialog
    assert dialog.mode == "view"
    assert all(edit.isReadOnly() for edit in dialog.fields.values())
    assert window.scenario.thresholds == []
    dialog.add_threshold_button.click()
    fill_dialog(dialog, " ils06 ")
    view = (window.canvas.center_lat, window.canvas.center_lon, window.canvas.range_nm)
    QTest.mouseClick(dialog.save_button, Qt.LeftButton)
    threshold = window.scenario.thresholds[0]
    assert threshold.name == "ILS06"
    assert window.threshold_dialog is dialog
    assert window.selected_threshold is window.canvas.selected_threshold is threshold
    assert window.selected is window.canvas.selected is None
    assert dialog.threshold_list.currentItem().data(Qt.UserRole) is threshold
    assert dialog.edit_threshold_button.isEnabled()
    assert all(edit.isReadOnly() for edit in dialog.fields.values())
    assert not dialog.add_threshold_button.isChecked()
    assert view == (window.canvas.center_lat, window.canvas.center_lon, window.canvas.range_nm)


@pytest.mark.parametrize("record", [
    "ILS06:1.123456789:2.000:3:4:EXTRA\n",
    "ILS_LEGACY:1.123456789:2:3:4:EXTRA\n",
    "ILS06:91:2:91:2:EXTRA\n",
    "ILS06:1:2:3:4\nILS06:1:2:3:4\n",
])
def test_noop_and_cancel_preserve_records(app, record):
    from ase_editor.ui import ThresholdEditorDialog

    scenario = parse_scenario_text(record)
    threshold = scenario.thresholds[0]
    dialog = ThresholdEditorDialog(scenario, threshold)
    dialog.edit_threshold_button.click()
    dialog._save()
    assert serialize_scenario(scenario) == record
    dialog.edit_threshold_button.click()
    dialog.fields["latitude1"].setText("10")
    dialog.cancel_button.click()
    assert dialog.fields["latitude1"].text() == str(threshold.latitude1)
    assert serialize_scenario(scenario) == record
    dialog.reject()


def test_edit_save_reload_delete_export(window, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "information", lambda *args: None)
    source = "GLOBAL:BEFORE\nILS06:1.123456789:2:3:4:EXTRA\nILS24:1:2:240\nODD:AFTER\n"
    window.scenario = parse_scenario_text(source)
    window._refresh_all()
    threshold = window.scenario.thresholds[0]
    window.select_threshold(threshold)
    view = (window.canvas.center_lat, window.canvas.center_lon, window.canvas.range_nm)
    window.open_threshold_editor()
    dialog = window.threshold_dialog
    assert dialog.save_button.text() == ""
    dialog.edit_threshold_button.click()
    assert dialog.edit_threshold_button.isChecked()
    dialog.fields["name"].setText("ILS07L")
    dialog.fields["longitude2"].setText("5.123456789")
    dialog.save_button.click()
    assert window.scenario.thresholds[0] is threshold
    assert threshold.latitude1 == 1.123456789
    assert threshold.longitude2 == 5.1234568
    assert dialog.threshold_list.item(0).text().splitlines()[0] == "ILS07L"
    assert view == (window.canvas.center_lat, window.canvas.center_lon, window.canvas.range_nm)
    dialog.reject()
    path = tmp_path / "saved.txt"
    window.save_scenario_to_path(path)
    first = path.read_bytes()
    window.save_scenario()
    assert path.read_bytes() == first
    window.load_scenario(path)
    assert window.selected_threshold is window.canvas.selected_threshold is None
    window.select_threshold(window.scenario.thresholds[0])
    window.open_threshold_editor()
    dialog = window.threshold_dialog
    dialog.delete_threshold_button.click()
    window.save_scenario()
    assert parse_scenario_file(path).thresholds == []
    assert path.read_text() == "GLOBAL:BEFORE\nILS24:1:2:240\nODD:AFTER\n"
    assert dialog.threshold_list.count() == 0
    assert not dialog.delete_threshold_button.isEnabled()


def test_dialog_invalid_edit_is_atomic(window):
    first = window.scenario.create_threshold("ILS06", 1, 2, 3, 4)
    window.scenario.create_threshold("ILS24", 1, 2, 3, 4)
    window._refresh_all()
    window.open_threshold_editor(first)
    dialog = window.threshold_dialog
    dialog.edit_threshold_button.click()
    dialog.fields["name"].setText("ILS24")
    dialog.fields["latitude1"].setText("5")
    dialog.save_button.click()
    assert not dialog.errors["name"].isHidden()
    assert first.name == "ILS06" and first.latitude1 == 1
    assert window.threshold_dialog is dialog


def test_list_lives_in_popup_selection_double_click_and_add(window, app):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    first = window.scenario.create_threshold("ILS06", 1, 2, 3, 4)
    second = window.scenario.create_threshold("ILS24", 2, 3, 4, 5)
    window._refresh_all()
    assert not hasattr(window, "threshold_panel")
    assert not hasattr(window, "threshold_list")
    window.ils_threshold_action.trigger()
    dialog = window.threshold_dialog
    app.processEvents()
    dialog.threshold_search.setText("24")
    assert dialog.threshold_list.item(0).isHidden()
    assert not dialog.threshold_list.item(1).isHidden()
    dialog.threshold_search.setText("missing")
    assert not dialog.empty_list_label.isHidden()
    dialog.threshold_search.clear()
    item = dialog.threshold_list.item(1)
    pos = dialog.threshold_list.visualItemRect(item).center()
    QTest.mouseClick(dialog.threshold_list.viewport(), Qt.LeftButton, pos=pos)
    assert window.selected_threshold is second
    assert (window.canvas.center_lat, window.canvas.center_lon) == (3, 4)
    assert dialog.fields["name"].text() == "ILS24"
    dialog.threshold_search.setText("06")
    assert not dialog.delete_threshold_button.isEnabled()
    dialog.delete_selected()
    assert window.scenario.thresholds == [first, second]
    dialog.threshold_search.clear()
    QTest.mouseClick(dialog.threshold_list.viewport(), Qt.LeftButton, pos=pos)
    QTest.mouseDClick(dialog.threshold_list.viewport(), Qt.LeftButton, pos=pos)
    assert window.threshold_dialog.threshold is second
    assert all(field.isReadOnly() for field in dialog.fields.values())
    dialog.add_threshold_button.click()
    assert all(field.text() == "" for field in dialog.fields.values())
    assert dialog.threshold is None
    assert window.selected_threshold is None
    assert not dialog.edit_threshold_button.isEnabled()
    assert not dialog.delete_threshold_button.isEnabled()
    fill_dialog(dialog, "ILS07L")
    dialog.save_button.click()
    assert dialog.threshold_list.count() == 3
    assert dialog.save_button.isHidden()
    dialog.save_button.click()
    assert dialog.threshold_list.count() == 3  # Repeated Save does not create another item.
    dialog.delete_threshold_button.click()
    assert dialog.threshold_list.count() == 2
    assert window.scenario.thresholds == [first, second]


def test_canvas_selection_edit_hidden_layer_and_aircraft_priority(window, app):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    threshold = window.scenario.create_threshold("ILS06", 0, -0.01, 0, 0.01)
    window._refresh_all()
    window.canvas.center_lat = window.canvas.center_lon = 0
    app.processEvents()
    center = window.canvas.geo_to_screen(0, 0).toPoint()
    QTest.mouseClick(window.canvas, Qt.LeftButton, pos=center)
    assert window.selected_threshold is window.canvas.selected_threshold is threshold
    QTest.mouseDClick(window.canvas, Qt.LeftButton, pos=center)
    assert window.threshold_dialog.threshold is threshold
    window.threshold_dialog.reject()
    window.view_layer_actions["Thresholds"].setChecked(False)
    QTest.mouseClick(window.canvas, Qt.LeftButton, pos=center)
    assert window.selected_threshold is None
    window.select_threshold(threshold)
    assert window.selected_threshold is threshold  # List management works while hidden.
    window.view_layer_actions["Thresholds"].setChecked(True)
    aircraft = Aircraft("TEST", latitude=0, longitude=0)
    window.scenario.aircraft.append(aircraft)
    QTest.mouseClick(window.canvas, Qt.LeftButton, pos=center)
    assert window.selected is window.canvas.selected is aircraft
    assert window.selected_threshold is window.canvas.selected_threshold is None
    QTest.mouseClick(window.canvas, Qt.LeftButton, pos=QPoint(10, 10))
    assert window.selected is window.selected_threshold is None


def test_canvas_threshold_tolerance_nearest_and_identity_tie(app):
    from PySide6.QtCore import QPointF
    from ase_editor.ui import RadarCanvas

    canvas = RadarCanvas()
    canvas.resize(600, 600)
    canvas.center_lat = canvas.center_lon = 0
    first = canvas.scenario.create_threshold("ILS06", 0, -0.01, 0, 0.01)
    second = canvas.scenario.create_threshold("ILS24", 0.01, -0.01, 0.01, 0.01)
    center = canvas.geo_to_screen(0, 0)
    assert canvas._threshold_at(center + QPointF(0, 8)) is first
    assert canvas._threshold_at(center + QPointF(0, 8.01)) is None
    assert canvas._threshold_at(canvas.geo_to_screen(0.01, 0)) is second
    second.latitude1 = second.latitude2 = 0
    assert canvas._threshold_at(center) is first
    canvas.close()


def test_shortcuts_route_selection_and_do_not_intercept_dialog_text(window, app):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    aircraft = Aircraft("TEST")
    window.scenario.aircraft.append(aircraft)
    threshold = window.scenario.create_threshold("ILS06", 1, 2, 3, 4)
    window._refresh_all()
    window.select_threshold(threshold)
    window.activateWindow()
    window.canvas.setFocus()
    app.processEvents()
    QTest.keyClick(window.canvas, Qt.Key_I)
    assert window.threshold_dialog.threshold is threshold
    dialog = window.threshold_dialog
    field = dialog.fields["name"]
    field.setFocus()
    field.selectAll()
    QTest.keyClicks(field, "blocked")
    assert field.text() == "ILS06"
    dialog.edit_threshold_button.click()
    field.setFocus()
    field.selectAll()
    QTest.keyClick(field, Qt.Key_I)
    assert field.text() == "i"
    field.selectAll()
    QTest.keyClick(field, Qt.Key_Delete)
    assert field.text() == ""
    assert window.scenario.thresholds == [threshold]
    dialog.reject()
    window.activateWindow()
    window.canvas.setFocus()
    app.processEvents()
    QTest.keyClick(window.canvas, Qt.Key_Delete)
    assert window.scenario.thresholds == []
    assert window.scenario.aircraft == [aircraft]
    window.select_aircraft(aircraft)
    window.canvas.setFocus()
    QTest.keyClick(window.canvas, Qt.Key_I)
    assert window.editor_dialogs[-1].aircraft is aircraft


def test_loading_scenario_closes_stale_dialog(window, tmp_path):
    old = window.scenario.create_threshold("ILS06", 1, 2, 3, 4)
    window._refresh_all()
    window.select_threshold(old)
    window.open_threshold_editor()
    path = tmp_path / "replacement.txt"
    path.write_text("ILS24:5:6:7:8\n")
    window.load_scenario(path)
    assert window.threshold_dialog is None
    assert window.selected_threshold is window.canvas.selected_threshold is None
    window.ils_threshold_action.trigger()
    assert window.threshold_dialog.threshold_list.item(0).text().splitlines()[0] == "ILS24"


def test_icon_edit_cancel_restore_and_escape(window, app):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    threshold = window.scenario.create_threshold("ILS06", 1, 2, 3, 4)
    window._refresh_all()
    window.open_threshold_editor(threshold)
    dialog = window.threshold_dialog
    for button in (dialog.add_threshold_button, dialog.edit_threshold_button,
                   dialog.delete_threshold_button, dialog.save_button, dialog.cancel_button):
        assert button.text() == ""
        assert not button.icon().isNull()
        assert button.toolTip() and button.accessibleName()
    # Even a programmatic save cannot commit from view mode.
    dialog.fields["name"].setText("ILS24")
    dialog._save()
    assert threshold.name == "ILS06"
    dialog.edit_threshold_button.click()
    assert dialog.fields["name"].text() == "ILS06"
    assert dialog.edit_threshold_button.isChecked()
    assert not dialog.delete_threshold_button.isEnabled()
    assert not dialog.add_threshold_button.isEnabled()
    dialog.fields["latitude1"].setText("10")
    dialog.delete_selected()
    assert window.scenario.thresholds == [threshold]
    dialog.cancel_button.click()
    assert dialog.fields["latitude1"].text() == "1.0"
    assert not dialog.edit_threshold_button.isChecked()
    assert all(field.isReadOnly() for field in dialog.fields.values())
    dialog.add_threshold_button.click()
    fill_dialog(dialog, "ILS24")
    QTest.keyClick(dialog.fields["name"], Qt.Key_Escape)
    assert window.threshold_dialog is dialog
    assert dialog.threshold is window.selected_threshold is threshold
    assert dialog.fields["name"].text() == "ILS06"
    assert window.scenario.thresholds == [threshold]


@pytest.mark.parametrize("suffix", ["1", "2"])
@pytest.mark.parametrize("create", [False, True])
def test_map_pick_fills_only_requested_pair_and_saves_on_check(window, app, suffix, create):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    threshold = window.scenario.create_threshold("ILS06", -6.1, 106.1, -6.2, 106.2)
    aircraft = Aircraft("TEST", latitude=-6, longitude=106)
    window.scenario.aircraft.append(aircraft)
    window._refresh_all()
    window.open_threshold_editor(threshold)
    dialog = window.threshold_dialog
    assert all(not button.isEnabled() for button in dialog.map_pick_buttons.values())
    dialog.request_coordinate_pick(suffix)
    assert window._threshold_map_pick is None
    if create:
        dialog.add_threshold_button.click()
        fill_dialog(dialog, "ILS24")
    else:
        dialog.edit_threshold_button.click()
    before = {name: field.text() for name, field in dialog.fields.items()}
    original = serialize_scenario(window.scenario)
    window.canvas.center_lat, window.canvas.center_lon = -6, 106
    dialog.map_pick_buttons[suffix].click()
    app.processEvents()
    assert dialog.isHidden()
    assert window.threshold_dialog is dialog
    assert window.canvas.cursor().shape() == Qt.CrossCursor
    assert not window.pending_new_aircraft
    assert not window.new_aircraft_action.isEnabled()
    point = window.canvas.geo_to_screen(-6, 106).toPoint()
    latitude, longitude = window.canvas.screen_to_geo(point)
    QTest.mouseClick(window.canvas, Qt.LeftButton, pos=point)
    app.processEvents()
    assert dialog.isVisible() and dialog.isModal()
    assert window._threshold_map_pick is None
    assert window.canvas.coordinate_pick_label is None
    assert window.new_aircraft_action.isEnabled()
    assert not dialog.map_pick_buttons[suffix].isChecked()
    assert dialog.fields[f"latitude{suffix}"].text() == f"{latitude:.7f}"
    assert dialog.fields[f"longitude{suffix}"].text() == f"{longitude:.7f}"
    for name, value in before.items():
        if name not in (f"latitude{suffix}", f"longitude{suffix}"):
            assert dialog.fields[name].text() == value
    assert serialize_scenario(window.scenario) == original
    assert window.scenario.aircraft == [aircraft]
    dialog.save_button.click()
    saved = window.scenario.thresholds[-1] if create else threshold
    assert getattr(saved, f"latitude{suffix}") == round(latitude, 7)
    assert getattr(saved, f"longitude{suffix}") == round(longitude, 7)
    assert dialog.mode == "view"


def test_map_pick_escape_preserves_draft_and_allows_another_pick(window, app):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    window.ils_threshold_action.trigger()
    dialog = window.threshold_dialog
    dialog.add_threshold_button.click()
    fill_dialog(dialog)
    before = {name: field.text() for name, field in dialog.fields.items()}
    # Preserve an action that was disabled before entering pick mode.
    window.save_scenario_action.setEnabled(False)
    dialog.map_pick_buttons["1"].click()
    app.processEvents()
    QTest.keyClick(window.canvas, Qt.Key_Escape)
    app.processEvents()
    assert dialog.isVisible() and dialog.mode == "create"
    assert not window.save_scenario_action.isEnabled()
    assert window.new_aircraft_action.isEnabled()
    assert {name: field.text() for name, field in dialog.fields.items()} == before
    assert window.scenario.thresholds == []
    dialog.map_pick_buttons["2"].click()
    app.processEvents()
    QTest.mouseClick(window.canvas, Qt.LeftButton, pos=window.canvas.rect().center())
    app.processEvents()
    assert dialog.isVisible()
    assert dialog.fields["latitude1"].text() == before["latitude1"]
    dialog.cancel_button.click()
    assert window.scenario.thresholds == []


@pytest.mark.parametrize("finish", ["replace", "close"])
def test_map_pick_cleans_up_on_scenario_replacement_or_window_close(window, app, tmp_path, finish):
    window.ils_threshold_action.trigger()
    dialog = window.threshold_dialog
    dialog.add_threshold_button.click()
    dialog.map_pick_buttons["1"].click()
    app.processEvents()
    if finish == "replace":
        path = tmp_path / "new.txt"
        path.write_text("ILS24:1:2:3:4\n")
        window.load_scenario(path)
        assert window.scenario.thresholds[0].name == "ILS24"
    else:
        window.close()
    assert window.threshold_dialog is None
    assert window._threshold_map_pick is None
    assert window.canvas.coordinate_pick_label is None
    assert window._map_pick_controls == []
