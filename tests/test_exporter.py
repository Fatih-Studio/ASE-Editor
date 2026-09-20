from pathlib import Path

from ase_editor.exporter import serialize_scenario, write_scenario_file
from ase_editor.parser import parse_scenario_file, parse_scenario_text


ROOT = Path(__file__).resolve().parents[1]


def test_serialize_wihh_sample_contains_expected_records() -> None:
    scenario = parse_scenario_file(ROOT / "WIHH_example.txt")

    text = serialize_scenario(scenario)

    assert text.startswith("PSEUDOPILOT:ALL\n\nAIRPORT_ALT:84.0")
    assert text.count("\n@") == 14
    assert text.count("\n$FP") == 14
    assert text.count("\nSIMDATA:") == 14
    assert text.count("\n$ROUTE:") == 12
    assert text.count("\nDELAY:") == 12
    assert text.count("PSEUDOPILOT:ALL") == 15
    assert "ILS06:-6.2722343:106.8787898:-6.2609290:106.9036165" in text
    assert "HOLDING:ELNIR:270:-1" in text
    assert "METAR:WIHH 010400Z" in text


def test_parse_edit_export_round_trips_changed_aircraft_fields() -> None:
    scenario = parse_scenario_file(ROOT / "WIHH_example.txt")
    aircraft = next(item for item in scenario.aircraft if item.callsign == "CTV761")

    aircraft.callsign = "TST123"
    aircraft.squawk = "7001"
    aircraft.latitude = -6.1234567
    aircraft.longitude = 106.7654321
    aircraft.altitude = 12300
    aircraft.ground_speed = 321
    aircraft.heading_raw = 180
    aircraft.flight_plan.aircraft_type = "B738"
    aircraft.flight_plan.departure = "WIII"
    aircraft.flight_plan.arrival = "WARR"
    aircraft.flight_plan.route_text = "WIII DCT WARR"
    aircraft.editor_route = "ELNIR DCT ILS24"

    text = serialize_scenario(scenario)
    reparsed = parse_scenario_text(text)
    edited = next(item for item in reparsed.aircraft if item.callsign == "TST123")

    assert "@N:TST123:7001:1:-6.1234567:106.7654321:12300:321:180:0" in text
    assert "$FPTST123:*A:I:B738:420:WIII:0000:0000:30000:WARR" in text
    assert "SIMDATA:TST123:*:*:25:1:0.010:0.0" in text
    assert "$ROUTE:ELNIR DCT ILS24" in text
    assert len(reparsed.aircraft) == 14
    assert edited.flight_plan.aircraft_type == "B738"
    assert edited.flight_plan.departure == "WIII"
    assert edited.flight_plan.arrival == "WARR"
    assert edited.flight_plan.route_text == "WIII DCT WARR"
    assert edited.editor_route == "ELNIR DCT ILS24"


def test_serialize_preserves_global_and_aircraft_unknown_lines() -> None:
    scenario = parse_scenario_text(
        "\n".join(
            [
                "PSEUDOPILOT:GLOBAL",
                "AIRPORT_ALT:84",
                "UNKNOWN:GLOBAL",
                "PSEUDOPILOT:LOCAL",
                "@N:TST001:1234:1:-1:2:3000:220:900:0",
                "$FPTST001:*A:I:A320:420:WIHH:0000:0000:30000:WIII:00:00:0:0::/v/:WIHH WIII",
                "ODD:AIRCRAFT",
            ]
        )
    )

    text = serialize_scenario(scenario)
    reparsed = parse_scenario_text(text)

    assert "UNKNOWN:GLOBAL" in text
    assert "ODD:AIRCRAFT" in text
    assert "PSEUDOPILOT:LOCAL\n@N:TST001" in text
    assert reparsed.unknown_lines == ["UNKNOWN:GLOBAL"]
    assert reparsed.aircraft[0].unknown_lines == ["ODD:AIRCRAFT"]
    assert reparsed.aircraft[0].pseudo_pilot == "LOCAL"


def test_write_scenario_file_updates_disk(tmp_path: Path) -> None:
    scenario = parse_scenario_file(ROOT / "WIHH_example.txt")
    output_path = tmp_path / "saved.txt"

    write_scenario_file(scenario, output_path)

    assert output_path.read_text(encoding="utf-8").startswith("PSEUDOPILOT:ALL")
