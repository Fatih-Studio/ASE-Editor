import importlib.util
from copy import deepcopy

import pytest

from ase_editor.exporter import serialize_scenario
from ase_editor.parser import parse_scenario_file, parse_scenario_text


pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="PySide6 is not installed",
)
POSITION = "@N:ONE:1234:1:-1:2:3000:220:3816:0\n"


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
    yield window
    window.close()


@pytest.mark.parametrize("tail", [
    "", "DELAY:0\n", "DELAY:5\n", "DELAY:5:5\n",
    "$FP\nSIMDATA:\n$ROUTE:\n", "$FPOTHER:custom\nSIMDATA:OTHER:ONE\n",
    "$FPONE:*A:I:A320:420:WIHH:0000:0000:30000:WIII:00:00:0:0::remarks:/v/:lower case route\n",
])
def test_dialog_noop_preserves_all_model_values_and_records(app, tail):
    from ase_editor.ui import AircraftEditorDialog

    scenario = parse_scenario_text(POSITION + tail)
    aircraft = scenario.aircraft[0]
    original = deepcopy(aircraft)
    dialog = AircraftEditorDialog(aircraft)
    dialog._save()
    assert aircraft == original
    assert serialize_scenario(scenario) == POSITION + tail


def test_dialog_rename_does_not_create_fp_and_authored_field_does(app):
    from ase_editor.ui import AircraftEditorDialog

    scenario = parse_scenario_text(POSITION + "DELAY:5\n")
    aircraft = scenario.aircraft[0]
    dialog = AircraftEditorDialog(aircraft)
    dialog.callsign.setText("NEW")
    dialog.delay_min.setValue(6)
    dialog._save()
    assert "$FP" not in serialize_scenario(scenario)
    assert "DELAY:6\n" in serialize_scenario(scenario)
    assert aircraft.delay_max is None
    assert aircraft.heading_raw == 3816

    dialog = AircraftEditorDialog(aircraft)
    dialog.aircraft_type.setCurrentText("B738")
    dialog._save()
    text = serialize_scenario(scenario)
    reparsed = parse_scenario_text(text)
    assert text.count("$FP") == 1
    assert reparsed.aircraft[0].flight_plan.callsign == "NEW"
    assert reparsed.aircraft[0].flight_plan.aircraft_type == "B738"


def test_dialog_rename_preserves_mismatched_references(app):
    from ase_editor.ui import AircraftEditorDialog

    scenario = parse_scenario_text(POSITION + "$FPOTHER:custom\nSIMDATA:OTHER:ONE\n")
    for callsign in ("NEW", "FINAL"):
        dialog = AircraftEditorDialog(scenario.aircraft[0])
        dialog.callsign.setText(callsign)
        dialog._save()
        text = serialize_scenario(scenario)
        assert f"@N:{callsign}:" in text
        assert "$FPOTHER:custom\nSIMDATA:OTHER:ONE\n" in text


@pytest.mark.parametrize("save_as", [False, True])
@pytest.mark.parametrize("failure", ["serialize", "replace"])
def test_ui_failed_save_keeps_path_and_existing_bytes(window, tmp_path, monkeypatch, save_as, failure):
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    from ase_editor import exporter

    original_path = tmp_path / "original.txt"
    target = tmp_path / "save-as.txt" if save_as else original_path
    original_path.write_bytes(b"original contents")
    target.write_bytes(b"target contents")
    window.scenario = parse_scenario_text(POSITION, original_path)
    window.scenario.aircraft[0].callsign = "EDITED"
    errors, successes = [], []
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: errors.append(args[-1]))
    monkeypatch.setattr(QMessageBox, "information", lambda *args: successes.append(args[-1]))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(target), ""))

    def fail(*args):
        raise OSError("injected save failure")

    if failure == "serialize":
        monkeypatch.setattr(exporter, "serialize_scenario", fail)
    else:
        monkeypatch.setattr(exporter.os, "replace", fail)
    if save_as:
        window.save_scenario_as_action.trigger()
    else:
        window.save_scenario_action.trigger()

    assert window.scenario.source_path == original_path
    assert window.scenario.aircraft[0].callsign == "EDITED"
    assert target.read_bytes() == b"target contents"
    assert len(errors) == 1 and "injected save failure" in errors[0]
    assert successes == []
    assert not list(tmp_path.glob("*.tmp"))


def test_ui_copy_delete_create_and_repeated_save(window, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QInputDialog, QMessageBox

    window.scenario = parse_scenario_text(
        "PSEUDOPILOT:LOCAL\n" + POSITION + "$FPONE:custom\nSIMDATA:ONE:EXTRA\nODD:ONE\n"
        "METAR:WIHH TEST\nGLOBAL:KEEP\nPSEUDOPILOT:TRAILING\n"
    )
    original = window.scenario.aircraft[0]
    window.selected = original
    monkeypatch.setattr(QInputDialog, "getText", lambda *args, **kwargs: ("COPY", True))
    monkeypatch.setattr(QMessageBox, "information", lambda *args: None)
    window.copy_aircraft()
    copied = window.selected
    assert copied is not original
    assert all(record.owner is copied for record in copied.source_records)
    window.selected = original
    window.delete_selected_aircraft()
    window.new_aircraft()
    window._place_new_aircraft(-1, 2)
    target = tmp_path / "saved.txt"
    window.save_scenario_to_path(target)
    assert window.scenario.source_path == target
    first = target.read_bytes()
    window.save_scenario()
    assert target.read_bytes() == first
    reparsed = parse_scenario_file(target)
    assert [a.callsign for a in reparsed.aircraft] == ["COPY", "NEW001"]
    assert reparsed.aircraft[0].flight_plan.callsign == "COPY"
    assert reparsed.aircraft[0].sim_data == "SIMDATA:COPY:EXTRA"
    assert reparsed.aircraft[1].flight_plan.aircraft_type == "A320"
    assert reparsed.unknown_lines == ["GLOBAL:KEEP"]
    assert reparsed.pseudo_pilots == ["TRAILING"]
