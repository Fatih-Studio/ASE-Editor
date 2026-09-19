from pathlib import Path

from ase_editor.parser import parse_scenario_file, parse_scenario_text
from ase_editor.sector import load_sector_data, load_sector_lines, load_sector_points
from ase_editor.sector_database import load_sector_database


ROOT = Path(__file__).resolve().parents[1]


def test_parse_wihh_sample_globals_and_aircraft() -> None:
    scenario = parse_scenario_file(ROOT / "WIHH_example.txt")

    assert scenario.airport_altitude == 84.0
    assert scenario.metar.startswith("WIHH 010400Z")
    assert len(scenario.thresholds) == 4
    assert scenario.thresholds[0].name == "ILS06"
    assert len(scenario.holds) == 1
    assert scenario.holds[0].fix == "ELNIR"
    assert len(scenario.aircraft) == 14


def test_parse_aircraft_block_fields() -> None:
    scenario = parse_scenario_file(ROOT / "WIHH_example.txt")
    aircraft = next(item for item in scenario.aircraft if item.callsign == "CTV761")

    assert aircraft.squawk == "4105"
    assert aircraft.latitude == -6.1975900
    assert aircraft.longitude == 107.3490600
    assert aircraft.altitude == 1600
    assert aircraft.flight_plan.aircraft_type == "A320"
    assert aircraft.flight_plan.departure == "WARR"
    assert aircraft.flight_plan.arrival == "WIHH"
    assert aircraft.editor_route == "ELNIR KOMIT ILS24"
    assert aircraft.delay_min == 3
    assert aircraft.delay_max == 7


def test_parser_preserves_unknown_lines() -> None:
    scenario = parse_scenario_text(
        "AIRPORT_ALT:84\nUNKNOWN:GLOBAL\n@N:TST001:1234:1:-1:2:3000:220:900:0\nODD:AIRCRAFT\n"
    )

    assert scenario.unknown_lines == ["UNKNOWN:GLOBAL"]
    assert scenario.aircraft[0].unknown_lines == ["ODD:AIRCRAFT"]


def test_load_sector_points_resolves_known_fixes_when_sector_exists() -> None:
    sector_path = ROOT / "WIII_Demo.sct"
    if not sector_path.exists():
        return

    points = load_sector_points(sector_path)

    assert "ELNIR" in points
    assert "KOMIT" in points
    assert points["ELNIR"].latitude < 0
    assert points["ELNIR"].longitude > 0


def test_load_sector_lines_reads_basic_primitives_when_sector_exists() -> None:
    sector_path = ROOT / "WIII_Demo.sct"
    if not sector_path.exists():
        return

    lines = load_sector_lines(sector_path, max_lines=50)

    assert lines
    assert all(line.source in {"RUNWAY", "SID", "STAR", "ARTCC", "ARTCC HIGH", "ARTCC LOW", "GEO"} for line in lines)


def test_load_sector_data_reads_full_sct_structures_when_sector_exists() -> None:
    sector_path = ROOT / "WIII_Demo.sct"
    if not sector_path.exists():
        return

    data = load_sector_data(sector_path)

    assert len(data.points) > 10_000
    assert len(data.lines) > 250_000
    assert len(data.regions) > 2_000
    assert len(data.labels) >= 10
    assert "COLOR_RunwayBorder" in data.colors
    assert any(region.name.startswith("WIII") for region in data.regions)
    assert any(label.text == "Singapore Radar" for label in data.labels)
    assert any(line.color_name for line in data.lines if line.source == "GEO")
    assert data.info.title == "ATC Simulator Indonesia v1.0"
    assert data.info.default_airport == "WIII"


def test_packaged_indonesia_database_loads_when_present() -> None:
    database = ROOT / "data" / "sector" / "indonesia.sqlite3"
    if not database.exists():
        return

    data = load_sector_database(database)

    assert data.info.title == "ATC Simulator Indonesia v1.0"
    assert data.info.default_airport == "WIII"
    assert len(data.points) > 10_000
    assert len(data.lines) > 250_000
    assert len(data.regions) > 2_000
