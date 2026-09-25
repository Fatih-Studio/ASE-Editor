from copy import deepcopy

import pytest

from ase_editor.exporter import serialize_scenario, write_scenario_file
from ase_editor.models import Scenario, Threshold, ThresholdValidationError
from ase_editor.parser import parse_scenario_file, parse_scenario_text


@pytest.mark.parametrize("name", ["ILS01", "ILS36", "ILS07L", "ILS24C", "ILS06R", " ils06 "])
def test_create_valid_name_and_normalize_coordinates(name):
    scenario = Scenario()
    threshold = scenario.create_threshold(name, "-6.123456789", 106, -6, 107)
    assert threshold.name == name.strip().upper()
    assert threshold.latitude1 == -6.1234568
    assert scenario.thresholds[0] is threshold


@pytest.mark.parametrize("name", ["", "ILS", "ILS00", "ILS37", "ILS6", "ILS06X", "ILS06_TEST", "ILS06:EXTRA"])
def test_reject_invalid_names_without_mutation(name):
    scenario = Scenario()
    with pytest.raises(ThresholdValidationError) as error:
        scenario.create_threshold(name, 1, 2, 3, 4)
    assert "name" in error.value.errors
    assert scenario.thresholds == []


@pytest.mark.parametrize("field,value", [
    ("latitude1", ""), ("latitude1", "bad"), ("latitude1", 90.00000001),
    ("latitude2", -90.00000001), ("longitude1", 180.00000001),
    ("longitude2", -180.00000001), ("latitude1", "NaN"),
    ("longitude1", "inf"), ("longitude2", "-inf"), ("latitude2", None),
])
def test_reject_invalid_coordinates_atomically(field, value):
    scenario = Scenario()
    threshold = scenario.create_threshold("ILS06", 1, 2, 3, 4)
    original = deepcopy(threshold)
    with pytest.raises(ThresholdValidationError) as error:
        scenario.update_threshold(threshold, name="ILS24", **{field: value})
    assert field in error.value.errors
    assert threshold == original


def test_boundaries_and_coincident_endpoints_after_rounding():
    scenario = Scenario()
    scenario.create_threshold("ILS06", -90, -180, 90, 180)
    for end in (1, 1.00000001):
        with pytest.raises(ThresholdValidationError, match="different positions"):
            scenario.create_threshold("ILS24", 1, 2, end, 2)


def test_duplicate_names_and_self_edit():
    scenario = Scenario(thresholds=[Threshold("ils06", 1, 2, 3, 4)])
    with pytest.raises(ThresholdValidationError, match="already exists"):
        scenario.create_threshold(" ILS06 ", 5, 6, 7, 8)
    threshold = scenario.thresholds[0]
    scenario.update_threshold(threshold, name="ILS06", latitude1=5)
    assert threshold.name == "ILS06"
    second = scenario.create_threshold("ILS24", 1, 2, 3, 4)
    with pytest.raises(ThresholdValidationError):
        scenario.update_threshold(second, name="ils06")
    assert second.name == "ILS24"


def test_identity_edit_delete_and_noop_legacy_records():
    text = "ILS_LEGACY:1.123456789:2:3:4:EXTRA\nILS_LEGACY:1.123456789:2:3:4:EXTRA\n"
    scenario = parse_scenario_text(text)
    first, second = scenario.thresholds
    scenario.update_threshold(first)
    assert serialize_scenario(scenario) == text
    with pytest.raises(ThresholdValidationError):
        scenario.update_threshold(first, longitude1=5)
    scenario.delete_threshold(second)
    scenario.update_threshold(first, longitude1=5)
    assert scenario.thresholds[0] is first
    assert first.latitude1 == 1.123456789
    assert serialize_scenario(scenario) == "ILS_LEGACY:1.123456789:5.0000000:3:4:EXTRA\n"
    with pytest.raises(ValueError, match="no longer belongs"):
        scenario.update_threshold(second, name="ILS24")


def test_create_edit_delete_round_trip_preserves_source(tmp_path):
    original = (
        "GLOBAL:BEFORE\nILS06:-6.1:106.1:-6.2:106.2:EXTRA\n"
        "ILS24:-6.2:106.2:240\nILS_BROKEN:bad:coordinates\nGLOBAL:AFTER\n"
    )
    scenario = parse_scenario_text(original)
    loaded = scenario.thresholds[0]
    created = scenario.create_threshold("ILS07L", -6.3, 106.3, -6.4, 106.4)
    scenario.update_threshold(loaded, name="ILS06R", latitude1=-6.15)
    text = serialize_scenario(scenario)
    assert "GLOBAL:BEFORE\nILS06R:-6.1500000:106.1:-6.2:106.2:EXTRA\n" in text
    assert "ILS24:-6.2:106.2:240\nILS_BROKEN:bad:coordinates\nGLOBAL:AFTER\n" in text
    path = tmp_path / "thresholds.txt"
    write_scenario_file(scenario, path)
    parsed = parse_scenario_file(path)
    assert [item.name for item in parsed.thresholds] == [created.name, loaded.name]
    assert serialize_scenario(parsed) == text == serialize_scenario(scenario)
    scenario.delete_threshold(loaded)
    scenario.delete_threshold(created)
    text = serialize_scenario(scenario)
    assert parse_scenario_text(text).thresholds == []
    assert text == original.replace("ILS06:-6.1:106.1:-6.2:106.2:EXTRA\n", "")


def test_empty_scenario_round_trip():
    scenario = Scenario()
    threshold = scenario.create_threshold("ILS06", 1, 2, 3, 4)
    text = serialize_scenario(scenario)
    assert parse_scenario_text(text).thresholds == [threshold]
    assert serialize_scenario(parse_scenario_text(text)) == text
