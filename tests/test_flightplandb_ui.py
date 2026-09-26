from copy import deepcopy
from threading import Event, get_ident
import time

import pytest
import requests

from ase_editor.exporter import serialize_scenario
from ase_editor.flightplandb import FlightPlanDBError, GeneratedRoute
from ase_editor.parser import parse_scenario_text
from ase_editor.route_tools import RouteNode


SOURCE = ("@N:ONE:1234:1:0:0.5:3000:220:1024:0\n"
          "$FPONE:*A:I:A320:420:WIII:0000:0000:30000:WADD:00:00:0:0::remarks:/v/:ORIGINAL\n"
          "$ROUTE:ELNIR KOMIT ILS24\nUNKNOWN:preserve\n")
NODES = (RouteNode("WIII", 0, 0), RouteNode("MID", 0, 1), RouteNode("WADD", 0, 2))
RESULT = GeneratedRoute(42, NODES, "WIII DCT MID DCT WADD", 120.5, (2, 100))


@pytest.fixture
def app(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("ASE_EDITOR_SETTINGS_PATH", str(tmp_path / "settings.ini"))
    monkeypatch.setenv("FLIGHTPLANDB_API_KEY", "test-key")
    def forbidden(*args, **kwargs):
        raise AssertionError("Live network forbidden")
    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)
    from PySide6.QtWidgets import QApplication
    application = QApplication.instance() or QApplication([])
    yield application
    application.processEvents()


def wait_until(app, condition):
    from PySide6.QtTest import QTest
    deadline = time.monotonic() + 5
    while not condition() and time.monotonic() < deadline:
        app.processEvents()
        QTest.qWait(5)
    assert condition(), "Timed out waiting for Qt worker"


@pytest.fixture
def dialog(app):
    from ase_editor.ui import AircraftEditorDialog
    scenario = parse_scenario_text(SOURCE)
    editor = AircraftEditorDialog(scenario.aircraft[0])
    editor.show()
    yield editor, scenario
    editor.close()
    app.processEvents()


def test_generation_uses_drafts_off_main_thread_then_save(app, dialog, monkeypatch):
    from ase_editor.ui import FlightPlanDBClient
    editor, scenario = dialog
    original = deepcopy(editor.aircraft)
    calls = []
    def generate(self, **kwargs):
        calls.append((get_ident(), kwargs))
        return RESULT
    monkeypatch.setattr(FlightPlanDBClient, "generate_route", generate)
    editor.departure.setText(" wiii ")
    editor.cruise_altitude.setText("FL350")
    editor.cruise_speed.setText("N0450")
    editor.flightplandb_button.click()
    wait_until(app, lambda: not editor._generation_busy)
    assert calls[0][0] != get_ident()
    assert calls[0][1] == {"departure": "WIII", "arrival": "WADD", "cruise_altitude_ft": 35000, "cruise_speed_kt": 450}
    assert editor.route_text.toPlainText() == RESULT.route_text
    assert editor.aircraft == original
    assert serialize_scenario(scenario) == SOURCE
    assert editor.checkpoints_text.toPlainText() == "ELNIR KOMIT ILS24"
    assert editor.suggest_checkpoints_button.isEnabled()
    assert "120.5 NM" in editor.flightplandb_status.text()
    editor.save_button.click()
    assert editor.aircraft.flight_plan.route_text == RESULT.route_text
    assert "$ROUTE:ELNIR KOMIT ILS24" in serialize_scenario(scenario)
    assert "UNKNOWN:preserve" in serialize_scenario(scenario)


@pytest.mark.parametrize("kind", ["auth", "limit", "timeout", "network", "api", "response"])
def test_error_preserves_drafts(app, dialog, monkeypatch, kind):
    from ase_editor.ui import FlightPlanDBClient
    editor, scenario = dialog
    def fail(self, **kwargs):
        raise FlightPlanDBError(kind, "Readable failure")
    monkeypatch.setattr(FlightPlanDBClient, "generate_route", fail)
    editor.flightplandb_button.click()
    wait_until(app, lambda: not editor._generation_busy)
    assert editor.flightplandb_status.text() == "Readable failure"
    assert editor.route_text.toPlainText() == "ORIGINAL"
    assert serialize_scenario(scenario) == SOURCE
    assert editor.save_button.isEnabled() and editor.flightplandb_button.isEnabled()


@pytest.mark.parametrize("invalid", ["key", "departure", "arrival", "altitude", "speed"])
def test_preflight_validation_does_not_start_worker(app, dialog, monkeypatch, invalid):
    editor, _ = dialog
    if invalid == "key":
        monkeypatch.delenv("FLIGHTPLANDB_API_KEY")
    elif invalid in {"departure", "arrival"}:
        getattr(editor, invalid).clear()
    elif invalid == "altitude":
        editor.cruise_altitude.setText("S1100")
    else:
        editor.cruise_speed.setText("M080")
    editor.flightplandb_button.click()
    assert editor._generation_worker is None
    assert editor.flightplandb_status.text()


@pytest.mark.parametrize("change", ["route", "input", "input_back"])
def test_pending_request_responsive_duplicate_safe_and_stale(app, dialog, monkeypatch, change):
    from ase_editor.ui import FlightPlanDBClient
    editor, scenario = dialog
    release, entered = Event(), Event()
    calls = []
    def generate(self, **kwargs):
        calls.append(kwargs)
        entered.set()
        release.wait(5)
        return RESULT
    monkeypatch.setattr(FlightPlanDBClient, "generate_route", generate)
    editor.flightplandb_button.click()
    try:
        wait_until(app, entered.is_set)
        assert not editor.save_button.isEnabled()
        editor._generate_flightplandb()
        editor._save()
        assert len(calls) == 1
        assert serialize_scenario(scenario) == SOURCE
        if change == "route":
            editor.route_text.setPlainText("NEW MANUAL ROUTE")
        else:
            editor.departure.setText("WIHH")
            if change == "input_back":
                editor.departure.setText("WIII")
    finally:
        release.set()
    wait_until(app, lambda: not editor._generation_busy)
    assert "discarded" in editor.flightplandb_status.text()
    assert editor.route_text.toPlainText() == ("NEW MANUAL ROUTE" if change == "route" else "ORIGINAL")
    assert not editor.suggest_checkpoints_button.isEnabled()


@pytest.mark.parametrize("destroy", [False, True])
def test_close_during_generation_discards_result_and_keeps_worker_alive(app, monkeypatch, destroy):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QSignalSpy
    from ase_editor.ui import AircraftEditorDialog, FlightPlanDBClient
    scenario = parse_scenario_text(SOURCE)
    editor = AircraftEditorDialog(scenario.aircraft[0])
    editor.setAttribute(Qt.WA_DeleteOnClose, destroy)
    editor.show()
    release, entered = Event(), Event()
    def generate(self, **kwargs):
        entered.set()
        release.wait(5)
        return RESULT
    monkeypatch.setattr(FlightPlanDBClient, "generate_route", generate)
    editor.flightplandb_button.click()
    worker = editor._generation_worker
    # The native spy records completion even if deleteLater removes the worker
    # before a queued Python callback would run.
    finished = QSignalSpy(worker.finished)
    try:
        wait_until(app, entered.is_set)
        editor.close()
        app.processEvents()
    finally:
        release.set()
    wait_until(app, lambda: finished.count() == 1)
    assert serialize_scenario(scenario) == SOURCE


def test_preview_start_selection_repeated_identifiers_and_editable_ending(app, dialog):
    from PySide6.QtWidgets import QDialog
    from ase_editor.ui import CheckpointPreviewDialog
    editor, _ = dialog
    nodes = NODES + (RouteNode("MID", 0, 3), RouteNode("WADD", 0, 4))
    result = GeneratedRoute(42, nodes, "", None)
    preview = CheckpointPreviewDialog(result, "ELNIR KOMIT ILS24", 0, 0.5, 90, editor)
    assert preview.start_checkpoint.currentIndex() == 1
    assert preview.route_text.toPlainText() == "MID WADD MID WADD"
    preview.start_checkpoint.setCurrentIndex(3)
    assert preview.route_text.toPlainText() == "MID WADD"
    preview.route_text.setPlainText("MID ELNIR KOMIT ILS24")
    assert preview.existing.toPlainText() == "ELNIR KOMIT ILS24"
    preview.apply_button.click()
    assert preview.result() == QDialog.DialogCode.Accepted
    preview.deleteLater()


@pytest.mark.parametrize("apply", [False, True])
def test_checkpoint_apply_cancel_and_save(app, dialog, monkeypatch, apply):
    from PySide6.QtWidgets import QDialog
    from ase_editor.ui import CheckpointPreviewDialog
    editor, scenario = dialog
    editor._generation_completed(RESULT)
    def preview_exec(self):
        self.route_text.setPlainText("mid elnir komit ils24")
        return QDialog.DialogCode.Accepted if apply else QDialog.DialogCode.Rejected
    monkeypatch.setattr(CheckpointPreviewDialog, "exec", preview_exec)
    editor.suggest_checkpoints_button.click()
    expected = "MID ELNIR KOMIT ILS24" if apply else "ELNIR KOMIT ILS24"
    assert editor.checkpoints_text.toPlainText() == expected
    assert serialize_scenario(scenario) == SOURCE
    editor._save()
    assert editor.aircraft.editor_route == expected
    assert f"$ROUTE:{expected}" in serialize_scenario(scenario)


def test_close_discards_generated_drafts_and_input_change_invalidates_preview(app, dialog):
    editor, scenario = dialog
    editor._generation_completed(RESULT)
    editor.checkpoints_text.setPlainText("MID WADD")
    editor.arrival.setText("WIHH")
    assert not editor.suggest_checkpoints_button.isEnabled()
    editor.close()
    assert serialize_scenario(scenario) == SOURCE


def test_missing_checkpoint_record_created_only_when_authored(app):
    from ase_editor.ui import AircraftEditorDialog
    source = SOURCE.replace("$ROUTE:ELNIR KOMIT ILS24\n", "")
    scenario = parse_scenario_text(source)
    editor = AircraftEditorDialog(scenario.aircraft[0])
    editor._generation_completed(RESULT)
    editor._save()
    assert "$ROUTE:" not in serialize_scenario(scenario)
    editor = AircraftEditorDialog(scenario.aircraft[0])
    editor.checkpoints_text.setPlainText("MID\nWADD")
    editor._save()
    exported = serialize_scenario(scenario)
    assert "$ROUTE:MID WADD" in exported
    assert parse_scenario_text(exported).aircraft[0].editor_route == "MID WADD"
