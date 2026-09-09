from __future__ import annotations

from pathlib import Path

from .models import Aircraft, FlightPlan, Hold, Scenario, Threshold


def parse_scenario_file(path: str | Path) -> Scenario:
    source_path = Path(path)
    return parse_scenario_text(source_path.read_text(encoding="utf-8-sig"), source_path)


def parse_scenario_text(text: str, source_path: str | Path | None = None) -> Scenario:
    scenario = Scenario(source_path=Path(source_path) if source_path else None)
    current: Aircraft | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("@"):
            current = _parse_aircraft_position(line)
            current.raw_lines.append(raw_line)
            scenario.aircraft.append(current)
            continue

        if line.startswith("PSEUDOPILOT:"):
            scenario.pseudo_pilots.append(line.split(":", 1)[1])
            if current is not None:
                current.raw_lines.append(raw_line)
            continue

        if line.startswith("AIRPORT_ALT:"):
            scenario.airport_altitude = _float_or_none(line.split(":", 1)[1])
            continue

        if line.startswith("METAR:"):
            scenario.metar = line.split(":", 1)[1]
            continue

        if line.startswith("ILS"):
            threshold = _parse_threshold(line)
            if threshold:
                scenario.thresholds.append(threshold)
            else:
                scenario.unknown_lines.append(raw_line)
            continue

        if line.startswith("HOLDING:"):
            hold = _parse_hold(line)
            if hold:
                scenario.holds.append(hold)
            else:
                scenario.unknown_lines.append(raw_line)
            continue

        if line.startswith("$FP"):
            if current is None:
                scenario.unknown_lines.append(raw_line)
                continue
            current.flight_plan = _parse_flight_plan(line)
            current.raw_lines.append(raw_line)
            continue

        if line.startswith("SIMDATA:"):
            if current is None:
                scenario.unknown_lines.append(raw_line)
                continue
            current.sim_data = line
            current.raw_lines.append(raw_line)
            continue

        if line.startswith("$ROUTE:"):
            if current is None:
                scenario.unknown_lines.append(raw_line)
                continue
            current.editor_route = line.split(":", 1)[1].strip()
            current.raw_lines.append(raw_line)
            continue

        if line.startswith("DELAY:"):
            if current is None:
                scenario.unknown_lines.append(raw_line)
                continue
            _apply_delay(current, line)
            current.raw_lines.append(raw_line)
            continue

        if current is None:
            scenario.unknown_lines.append(raw_line)
        else:
            current.unknown_lines.append(raw_line)
            current.raw_lines.append(raw_line)

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
        return Threshold(
            name=parts[0],
            latitude1=float(parts[1]),
            longitude1=float(parts[2]),
            latitude2=float(parts[3]),
            longitude2=float(parts[4]),
        )
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
    if len(parts) >= 2:
        aircraft.delay_min = _int_or_default(parts[1], 0)
    if len(parts) >= 3:
        aircraft.delay_max = _int_or_default(parts[2], 0)


def _part(parts: list[str], index: int) -> str:
    return parts[index].strip() if index < len(parts) else ""


def _int_or_default(value: str, default: int) -> int:
    try:
        return int(float(value.strip()))
    except (TypeError, ValueError):
        return default


def _float_or_default(value: str, default: float) -> float:
    result = _float_or_none(value)
    return default if result is None else result


def _float_or_none(value: str) -> float | None:
    try:
        return float(value.strip())
    except (TypeError, ValueError):
        return None
