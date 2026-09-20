from copy import deepcopy
from itertools import product
from pathlib import Path

import pytest

from ase_editor.exporter import serialize_scenario
from ase_editor.models import Aircraft, FlightPlan, Hold, Scenario, Threshold
from ase_editor.parser import parse_scenario_file, parse_scenario_text


FIXTURES = Path(__file__).parent / "fixtures"
POSITION = "@N:ONE:1234:1:-1:2:3000:220:900:0"
FP = "$FPONE:*A:I:A320:420:WIHH:0000:0000:30000:WIII:00:00:0:0:ALT:remarks:EXTRA:/v/:ONE DCT TWO"


def nonblank(text):
    return [line for line in text.splitlines() if line.strip()]


def semantic_values(scenario):
    return (
        scenario.airport_altitude, scenario.metar, scenario.pseudo_pilots,
        scenario.thresholds, scenario.holds, scenario.unknown_lines,
        [(a.callsign, a.latitude, a.longitude, a.altitude, a.heading_raw,
          a.flight_plan, a.sim_data, a.editor_route, a.pseudo_pilot,
          a.delay_min, a.delay_max, a.unknown_lines) for a in scenario.aircraft],
    )


@pytest.mark.parametrize("fixture", sorted(FIXTURES.glob("round_trip_*.txt")), ids=lambda path: path.stem)
def test_fixture_round_trip_preserves_records_and_meaning(fixture):
    text = fixture.read_text(encoding="utf-8")
    parsed = parse_scenario_text(text)
    exported = serialize_scenario(parsed)
    reparsed = parse_scenario_text(exported)

    assert nonblank(exported) == nonblank(text)
    assert semantic_values(reparsed) == semantic_values(parsed)
    assert serialize_scenario(reparsed) == exported


def test_pilot_and_unknown_ownership_between_sections():
    scenario = parse_scenario_file(FIXTURES / "round_trip_uncommon.txt")
    assert scenario.pseudo_pilots == ["GLOBAL_A", "GLOBAL_B", "TRAILING_A", "TRAILING_B"]
    assert [a.pseudo_pilot for a in scenario.aircraft] == ["LOCAL_B", "LOCAL_C"]
    assert scenario.unknown_lines == [
        "GLOBAL:BEFORE_ILS", "GLOBAL:BEFORE_HOLD", "GLOBAL:BEFORE_WEATHER", "GLOBAL:BETWEEN_AIRCRAFT",
    ]
    assert scenario.aircraft[0].unknown_lines == ["  ODD:ONE:keep spaces  "]
    assert scenario.aircraft[1].unknown_lines == ["ODD:TWO"]


@pytest.mark.parametrize("presence", list(product((False, True), repeat=3)))
def test_optional_record_presence_survives_rename(presence):
    optional = [FP, "SIMDATA:ONE:*:*", "$ROUTE:"]
    text = "\n".join([POSITION] + [line for present, line in zip(presence, optional) if present]) + "\n"
    scenario = parse_scenario_text(text)
    scenario.aircraft[0].callsign = "NEW"
    exported = serialize_scenario(scenario)
    reparsed = parse_scenario_text(exported)
    assert [(prefix in exported) for prefix in ("$FP", "SIMDATA:", "$ROUTE:")] == list(presence)
    assert "DELAY:" not in exported
    assert reparsed.aircraft[0].callsign == "NEW"
    assert serialize_scenario(reparsed) == exported


def test_delay_shapes_and_duplicate_effective_value():
    scenario = parse_scenario_file(FIXTURES / "round_trip_optional.txt")
    assert [(a.delay_min, a.delay_max) for a in scenario.aircraft] == [(None, None), (0, None), (5, 5), (4, None)]
    scenario.aircraft[-1].delay_min = 6
    exported = serialize_scenario(scenario)
    assert "DELAY:2:8\nDELAY:6\n" in exported
    assert parse_scenario_text(exported).aircraft[-1].delay_max is None


def test_rename_only_matching_references_in_all_occurrences():
    text = "\n".join([
        POSITION + ":EXTRA", FP, FP.replace("$FPONE", "$FPONE1"), FP,
        "SIMDATA:ONE:ONE:EXTRA", "SIMDATA:ONE1:ONE:EXTRA", "SIMDATA:OTHER:ONE:EXTRA",
        "UNKNOWN:ONE", "$ROUTE:ONE DCT TWO", "DELAY:3:7:EXTRA",
    ]) + "\n"
    scenario = parse_scenario_text(text)
    aircraft = scenario.aircraft[0]
    aircraft.callsign = "NEW"
    aircraft.flight_plan.aircraft_type = "B738"
    aircraft.delay_min = 4
    exported = serialize_scenario(scenario)
    assert exported.count("$FPNEW:") == 2
    assert "$FPNEW:*A:I:A320:" in exported  # Earlier duplicate retains its payload.
    assert "$FPNEW:*A:I:B738:" in exported
    assert "$FPONE1:*A:I:A320:" in exported
    assert "SIMDATA:NEW:ONE:EXTRA" in exported
    assert "SIMDATA:ONE1:ONE:EXTRA" in exported
    assert "SIMDATA:OTHER:ONE:EXTRA" in exported
    assert "UNKNOWN:ONE\n$ROUTE:ONE DCT TWO\nDELAY:4:7:EXTRA" in exported
    assert "remarks:EXTRA:/v/:ONE DCT TWO" in exported
    assert exported.startswith(POSITION.replace(":ONE:", ":NEW:") + ":EXTRA\n")
    assert serialize_scenario(scenario) == exported
    aircraft.callsign = "FINAL"
    assert "SIMDATA:FINAL:ONE:EXTRA" in serialize_scenario(scenario)
    reloaded = parse_scenario_text(serialize_scenario(scenario))
    reloaded.aircraft[0].callsign = "AGAIN"
    assert "SIMDATA:AGAIN:ONE:EXTRA" in serialize_scenario(reloaded)
    assert "SIMDATA:OTHER:ONE:EXTRA" in serialize_scenario(reloaded)


def test_sample_mismatched_references_survive_export_and_rename():
    scenario = parse_scenario_file(FIXTURES.parents[1] / "WIHH_example.txt")
    vehicle = scenario.aircraft[0]
    assert vehicle.callsign == "FIR001"
    assert vehicle.flight_plan.callsign == "FIF001"
    for callsign in ("FIR001", "VEHICLE"):
        vehicle.callsign = callsign
        text = serialize_scenario(scenario)
        assert "$FPFIF001:" in text
        assert "SIMDATA:FIF001:" in text
        assert f"@S:{callsign}:" in text


def test_untouched_callsign_whitespace_survives_and_renames_only_reference_field():
    text = POSITION + "\n  $FPONE :custom  \n  SIMDATA: ONE :keep spaces  \n"
    scenario = parse_scenario_text(text)
    assert serialize_scenario(scenario) == text
    scenario.aircraft[0].callsign = "NEW"
    exported = serialize_scenario(scenario)
    assert "$FPNEW:custom" in exported
    assert "SIMDATA:NEW:keep spaces" in exported


def test_nonfinite_numeric_records_survive_without_poisoning_model_values():
    text = (
        "AIRPORT_ALT:NaN\nILS06:NaN:2:3:4\n"
        "@N:ONE:1234:1:NaN:Infinity:Infinity:NaN:Infinity:0\nDELAY:Infinity\n"
    )
    scenario = parse_scenario_text(text)
    assert scenario.airport_altitude is None
    assert scenario.thresholds == []
    assert scenario.aircraft[0].latitude == 0
    assert scenario.aircraft[0].altitude == 0
    assert serialize_scenario(scenario) == text


def test_authored_optional_fields_are_added_once():
    scenario = parse_scenario_text(POSITION + "\nODD:KEEP\n")
    aircraft = scenario.aircraft[0]
    aircraft.flight_plan.aircraft_type = "B738"
    aircraft.sim_data = "SIMDATA:ONE:*:*"
    aircraft.editor_route = "DCT TEST"
    aircraft.delay_min = 0
    text = serialize_scenario(scenario)
    for prefix in ("$FP", "SIMDATA:", "$ROUTE:", "DELAY:"):
        assert text.count(prefix) == 1
    assert text.index("$FP") < text.index("SIMDATA:") < text.index("$ROUTE:") < text.index("DELAY:")
    assert serialize_scenario(parse_scenario_text(text)) == text


def test_copy_delete_and_new_aircraft_preserve_global_records():
    scenario = parse_scenario_file(FIXTURES / "round_trip_uncommon.txt")
    source = scenario.aircraft[0]
    copied = deepcopy(source)
    copied.callsign = "COPY"
    assert all(record.owner is copied for record in copied.source_records)
    copied.unknown_lines.append("COPY_ONLY:VALUE")
    scenario.aircraft.append(copied)
    scenario.aircraft.remove(source)
    scenario.aircraft.append(Aircraft(callsign="NEW", flight_plan=FlightPlan(aircraft_type="A320")))
    text = serialize_scenario(scenario)
    reparsed = parse_scenario_text(text)
    assert [a.callsign for a in reparsed.aircraft] == ["TWO", "COPY", "NEW"]
    assert "GLOBAL:BETWEEN_AIRCRAFT" in reparsed.unknown_lines
    assert reparsed.pseudo_pilots == scenario.pseudo_pilots
    assert text.count("PSEUDOPILOT:LOCAL_A") == 1
    assert "SIMDATA:COPY:" in text
    assert "COPY_ONLY:VALUE" not in source.unknown_lines
    assert serialize_scenario(reparsed) == text


def test_global_edits_preserve_duplicate_records_and_extra_fields():
    scenario = parse_scenario_text("AIRPORT_ALT:10\nAIRPORT_ALT:20\nILS06:1:2:3:4:EXTRA\nHOLDING:X:90:1:EXTRA\nMETAR:A\nMETAR:B\n")
    scenario.airport_altitude = 30
    scenario.metar = "C"
    scenario.thresholds[0].latitude1 = 5
    scenario.holds[0].inbound_heading = 180
    assert serialize_scenario(scenario) == (
        "AIRPORT_ALT:10\nAIRPORT_ALT:30.0\nILS06:5.0000000:2:3:4:EXTRA\n"
        "HOLDING:X:180:1:EXTRA\nMETAR:A\nMETAR:C\n"
    )


def test_new_scenario_generates_canonical_records():
    scenario = Scenario(
        airport_altitude=84, metar="WIHH TEST", pseudo_pilots=["GLOBAL"],
        thresholds=[Threshold("ILS06", 1, 2, 3, 4)], holds=[Hold("FIX", 90, 1)],
        aircraft=[Aircraft(callsign="NEW", flight_plan=FlightPlan(aircraft_type="A320"), pseudo_pilot="LOCAL")],
    )
    text = serialize_scenario(scenario)
    parsed = parse_scenario_text(text)
    assert parsed.pseudo_pilots == ["GLOBAL"]
    assert parsed.aircraft[0].pseudo_pilot == "LOCAL"
    assert parsed.aircraft[0].flight_plan.aircraft_type == "A320"
    assert serialize_scenario(parsed) == text
