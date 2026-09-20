from __future__ import annotations

from pathlib import Path

from .models import Aircraft, FlightPlan, Scenario


def serialize_scenario(scenario: Scenario) -> str:
    lines: list[str] = []

    for pseudo_pilot in scenario.pseudo_pilots:
        lines.append(f"PSEUDOPILOT:{pseudo_pilot}")
    _append_blank(lines)

    if scenario.airport_altitude is not None:
        lines.append(f"AIRPORT_ALT:{_format_float(scenario.airport_altitude)}")
        _append_blank(lines)

    for threshold in scenario.thresholds:
        lines.append(
            ":".join(
                [
                    threshold.name,
                    _format_coordinate(threshold.latitude1),
                    _format_coordinate(threshold.longitude1),
                    _format_coordinate(threshold.latitude2),
                    _format_coordinate(threshold.longitude2),
                ]
            )
        )
    _append_blank(lines)

    for hold in scenario.holds:
        lines.append(f"HOLDING:{hold.fix}:{hold.inbound_heading}:{hold.turn}")
    _append_blank(lines)

    if scenario.metar:
        lines.append(f"METAR:{scenario.metar}")
        _append_blank(lines)

    lines.extend(scenario.unknown_lines)
    _append_blank(lines)

    for aircraft in scenario.aircraft:
        if aircraft.pseudo_pilot:
            lines.append(f"PSEUDOPILOT:{aircraft.pseudo_pilot}")
        lines.append(_serialize_aircraft_position(aircraft))
        lines.append(_serialize_flight_plan(aircraft))
        if aircraft.sim_data:
            lines.append(_serialize_sim_data(aircraft))
        if aircraft.editor_route:
            lines.append(f"$ROUTE:{aircraft.editor_route}")
        if aircraft.delay_min is not None or aircraft.delay_max is not None:
            lines.append(_serialize_delay(aircraft))
        lines.extend(aircraft.unknown_lines)
        _append_blank(lines)

    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + "\n"


def write_scenario_file(scenario: Scenario, path: str | Path) -> None:
    output_path = Path(path)
    output_path.write_text(serialize_scenario(scenario), encoding="utf-8")


def _serialize_aircraft_position(aircraft: Aircraft) -> str:
    return ":".join(
        [
            f"@{aircraft.symbol or 'N'}",
            aircraft.callsign,
            aircraft.squawk,
            aircraft.mode_c,
            _format_coordinate(aircraft.latitude),
            _format_coordinate(aircraft.longitude),
            str(aircraft.altitude),
            str(aircraft.ground_speed),
            str(aircraft.heading_raw),
            aircraft.trailing_flag,
        ]
    )


def _serialize_flight_plan(aircraft: Aircraft) -> str:
    plan = aircraft.flight_plan
    fields = _flight_plan_fields(plan)
    fields[0] = f"$FP{aircraft.callsign}"
    fields[2] = plan.flight_type
    fields[3] = plan.aircraft_type
    fields[4] = plan.cruise_speed
    fields[5] = plan.departure
    fields[6] = plan.departure_time
    fields[7] = plan.enroute_time
    fields[8] = plan.cruise_altitude
    fields[9] = plan.arrival
    fields[14] = plan.alternate
    fields[15] = plan.remarks
    return f"{':'.join(fields)}:/v/:{plan.route_text}"


def _flight_plan_fields(plan: FlightPlan) -> list[str]:
    fields = list(plan.raw_fields)
    if not fields:
        fields = ["$FP", "*A", "", "", "", "", "", "", "", "", "00", "00", "0", "0", "", ""]
    while len(fields) < 16:
        fields.append("")
    return fields


def _serialize_sim_data(aircraft: Aircraft) -> str:
    parts = aircraft.sim_data.split(":")
    if len(parts) >= 2 and parts[0] == "SIMDATA":
        parts[1] = aircraft.callsign
        return ":".join(parts)
    return aircraft.sim_data


def _serialize_delay(aircraft: Aircraft) -> str:
    if aircraft.delay_max is None:
        return f"DELAY:{aircraft.delay_min or 0}"
    return f"DELAY:{aircraft.delay_min or 0}:{aircraft.delay_max}"


def _append_blank(lines: list[str]) -> None:
    if lines and lines[-1] != "":
        lines.append("")


def _format_coordinate(value: float) -> str:
    return f"{value:.7f}"


def _format_float(value: float) -> str:
    value = float(value)
    if value.is_integer():
        return f"{value:.1f}"
    return str(value)
