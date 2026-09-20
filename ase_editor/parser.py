from __future__ import annotations

from dataclasses import asdict
import math
from pathlib import Path

from .models import Aircraft, FlightPlan, Hold, Scenario, SourceRecord, Threshold
from .records import aircraft_values


def parse_scenario_file(path: str | Path) -> Scenario:
    source_path = Path(path)
    return parse_scenario_text(source_path.read_text(encoding="utf-8-sig"), source_path)


def parse_scenario_text(text: str, source_path: str | Path | None = None) -> Scenario:
    scenario = Scenario(source_path=Path(source_path) if source_path else None)
    current: Aircraft | None = None
    pending_pilots: list[SourceRecord] = []

    def global_pilots() -> None:
        for record in pending_pilots:
            record.index = len(scenario.pseudo_pilots)
            scenario.pseudo_pilots.append(record.text.strip().split(":", 1)[1])
        pending_pilots.clear()

    for raw_line in text.splitlines():
        line = raw_line.strip()
        record = SourceRecord("unknown", raw_line)
        scenario.source_records.append(record)
        if not line:
            record.kind = "blank"
            continue

        if line.startswith("@"):
            current = _parse_aircraft_position(line)
            for pilot in pending_pilots:
                pilot.owner = current
                current.source_records.append(pilot)
                current.pseudo_pilot = pilot.text.strip().split(":", 1)[1]
            pending_pilots.clear()
            scenario.aircraft.append(current)
            record.kind = "position"
        elif line.startswith("PSEUDOPILOT:"):
            # A pilot directive starts a possible prefix for the NEXT aircraft.
            # Keep every occurrence even if no aircraft follows it.
            current = None
            record.kind = "pseudo"
            record.values = {"pseudo_pilot": line.split(":", 1)[1]}
            pending_pilots.append(record)
            continue
        elif line.startswith(("AIRPORT_ALT:", "METAR:", "ILS", "HOLDING:")):
            global_pilots()
            current = None
            if line.startswith("AIRPORT_ALT:"):
                record.kind = "airport"
                scenario.airport_altitude = _float_or_none(line.split(":", 1)[1])
                record.values = {"airport_altitude": scenario.airport_altitude}
            elif line.startswith("METAR:"):
                record.kind = "metar"
                scenario.metar = line.split(":", 1)[1]
                record.values = {"metar": scenario.metar}
            elif line.startswith("ILS"):
                record.item = _parse_threshold(line)
                if record.item is not None:
                    record.kind = "threshold"
                    scenario.thresholds.append(record.item)
            else:
                record.item = _parse_hold(line)
                if record.item is not None:
                    record.kind = "hold"
                    scenario.holds.append(record.item)
            if record.item is not None:
                record.values = asdict(record.item)
        elif current is not None:
            if line.startswith("$FP"):
                record.kind = "fp"
                current.flight_plan = _parse_flight_plan(line)
            elif line.startswith("SIMDATA:"):
                record.kind = "sim"
                current.sim_data = line
            elif line.startswith("$ROUTE:"):
                record.kind = "route"
                current.editor_route = line.split(":", 1)[1].strip()
            elif line.startswith("DELAY:"):
                record.kind = "delay"
                _apply_delay(current, line)

        if current is not None:
            record.owner = current
            current.source_records.append(record)
            current.raw_lines.append(raw_line)
            record.values = aircraft_values(current)
        if record.kind == "unknown":
            unknown = current.unknown_lines if current is not None else scenario.unknown_lines
            record.index = len(unknown)
            unknown.append(raw_line)

    global_pilots()
    for aircraft in scenario.aircraft:
        aircraft.original_values = aircraft_values(aircraft)
    scenario.original_values = {
        "airport_altitude": scenario.airport_altitude, "metar": scenario.metar,
    }
    return scenario


def _parse_aircraft_position(line: str) -> Aircraft:
    parts = line.split(":")
    symbol = parts[0][1:] or "N"
    callsign = _part(parts, 1)
    aircraft = Aircraft(
        symbol=symbol,
        callsign=callsign,
        squawk=_part(parts, 2),
        mode_c=_part(parts, 3),
        latitude=_float_or_default(_part(parts, 4), 0.0),
        longitude=_float_or_default(_part(parts, 5), 0.0),
        altitude=_int_or_default(_part(parts, 6), 0),
        ground_speed=_int_or_default(_part(parts, 7), 0),
        heading_raw=_int_or_default(_part(parts, 8), 0),
        trailing_flag=_part(parts, 9),
    )
    return aircraft


def _parse_flight_plan(line: str) -> FlightPlan:
    head, sep, tail = line.partition(":/v/:")
    fields = head.split(":")
    route_text = tail.strip() if sep else ""
    raw_callsign = fields[0][3:] if fields else ""
    return FlightPlan(
        callsign=raw_callsign,
        raw_fields=fields,
        flight_type=_part(fields, 2),
        aircraft_type=_part(fields, 3),
        cruise_speed=_part(fields, 4),
        departure=_part(fields, 5),
        departure_time=_part(fields, 6),
        enroute_time=_part(fields, 7),
        cruise_altitude=_part(fields, 8),
        arrival=_part(fields, 9),
        alternate=_part(fields, 14),
        remarks=_part(fields, 15),
        route_text=route_text,
    )


def _parse_threshold(line: str) -> Threshold | None:
    parts = line.split(":")
    if len(parts) < 5:
        return None
    try:
        coordinates = [float(part) for part in parts[1:5]]
        if not all(math.isfinite(value) for value in coordinates):
            return None
        return Threshold(parts[0], *coordinates)
    except ValueError:
        return None


def _parse_hold(line: str) -> Hold | None:
    parts = line.split(":")
    if len(parts) < 4:
        return None
    try:
        return Hold(parts[1], int(parts[2]), int(parts[3]))
    except ValueError:
        return None


def _apply_delay(aircraft: Aircraft, line: str) -> None:
    parts = line.split(":")
    aircraft.delay_min = None
    aircraft.delay_max = None
    if len(parts) >= 2:
        aircraft.delay_min = _int_or_default(parts[1], 0)
    if len(parts) >= 3:
        aircraft.delay_max = _int_or_default(parts[2], 0)


def _part(parts: list[str], index: int) -> str:
    return parts[index].strip() if index < len(parts) else ""


def _int_or_default(value: str, default: int) -> int:
    try:
        return int(float(value.strip()))
    except (TypeError, ValueError, OverflowError):
        return default


def _float_or_default(value: str, default: float) -> float:
    result = _float_or_none(value)
    return default if result is None else result


def _float_or_none(value: str) -> float | None:
    try:
        result = float(value.strip())
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None
