from __future__ import annotations

import os
import tempfile
from dataclasses import asdict
from pathlib import Path

from .models import Aircraft, FlightPlan, Scenario, SourceRecord
from .records import FLIGHT_PLAN_FIELDS, POSITION_FIELDS


def serialize_scenario(scenario: Scenario) -> str:
    """Patch source records in place; generate canonical records only for additions."""
    records = scenario.source_records
    active = {id(aircraft): aircraft for aircraft in scenario.aircraft}
    original_owners = {id(record.owner) for record in records if record.owner is not None}
    new_aircraft = [aircraft for aircraft in scenario.aircraft if id(aircraft) not in original_owners]
    last_owned = max((i for i, record in enumerate(records) if record.owner is not None), default=-1)
    # Keep standalone trailing pilot directives trailing when adding traffic.
    insertion = last_owned + 1 if last_owned >= 0 else len(records)
    if last_owned < 0:
        while insertion and records[insertion - 1].kind in {"pseudo", "blank"}:
            insertion -= 1

    lines = _new_global_lines(scenario)
    for index in range(len(records) + 1):
        if index == insertion:
            for aircraft in new_aircraft:
                lines.extend(_aircraft_lines(aircraft))
                _append_blank(lines)
        if index == len(records):
            break
        record = records[index]
        aircraft = record.owner
        if aircraft is None:
            line = _global_record(record, scenario)
            if line is not None:
                lines.append(line)
        elif id(aircraft) in active:
            if record.kind == "position" and not _has_kind(aircraft, "pseudo") and aircraft.pseudo_pilot:
                lines.append(f"PSEUDOPILOT:{aircraft.pseudo_pilot}")
            line = _aircraft_record(record, aircraft)
            if line is not None:
                lines.append(line)
            if record is aircraft.source_records[-1]:
                lines.extend(_new_aircraft_lines(aircraft))
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines) + "\n"


def write_scenario_file(scenario: Scenario, path: str | Path) -> None:
    output_path = Path(path)
    text = serialize_scenario(scenario)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=output_path.parent,
            prefix=f".{output_path.name}.", suffix=".tmp", delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(text)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, output_path)
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                # Cleanup must not obscure the original write/replace failure.
                pass


def _has_kind(aircraft: Aircraft, kind: str) -> bool:
    return any(record.kind == kind for record in aircraft.source_records)


def _effective(record: SourceRecord, records: list[SourceRecord]) -> bool:
    return record is next(item for item in reversed(records) if item.kind == record.kind)


def _patch_tokens(text: str, changes: dict[int, str]) -> str:
    if not changes:
        return text
    parts = text.strip().split(":")
    for index, value in changes.items():
        while len(parts) <= index:
            parts.append("")
        parts[index] = value
    return ":".join(parts)


def _renamed_reference(value: str, aircraft: Aircraft) -> str:
    original = aircraft.original_values.get("callsign", aircraft.callsign)
    if aircraft.callsign != original and value.strip() == original:
        return aircraft.callsign
    return value


def _aircraft_record(record: SourceRecord, aircraft: Aircraft) -> str | None:
    text = record.text
    original = aircraft.original_values
    effective = _effective(record, aircraft.source_records)
    if record.kind == "unknown":
        return _indexed_line(record, aircraft.unknown_lines)
    if record.kind == "position":
        generated = _serialize_aircraft_position(aircraft).split(":")
        changes = {i: generated[i] for i, name in enumerate(POSITION_FIELDS)
                   if getattr(aircraft, name) != original[name]}
        return _patch_tokens(text, changes)
    if record.kind == "fp":
        head, separator, route = text.partition(":/v/:")
        raw_callsign = head.strip().split(":", 1)[0][3:]
        callsign = _renamed_reference(raw_callsign, aircraft)
        changes = {0: f"$FP{callsign}"} if callsign != raw_callsign else {}
        if effective:
            old_plan = original["flight_plan"]
            plan = aircraft.flight_plan
            for name, index in FLIGHT_PLAN_FIELDS.items():
                value = getattr(plan, name)
                if value != old_plan[name]:
                    changes[index] = f"$FP{value}" if name == "callsign" else value
            if plan.route_text != old_plan["route_text"]:
                separator, route = ":/v/:", plan.route_text
        return _patch_tokens(head, changes) + separator + route
    if record.kind == "sim":
        if effective and aircraft.sim_data != original["sim_data"]:
            text = aircraft.sim_data
            if not text:
                return None
        parts = text.strip().split(":")
        if len(parts) >= 2 and parts[0] == "SIMDATA":
            callsign = _renamed_reference(parts[1], aircraft)
            if callsign != parts[1]:
                return _patch_tokens(text, {1: callsign})
        return text
    if not effective:
        return text
    if record.kind == "pseudo" and aircraft.pseudo_pilot != original["pseudo_pilot"]:
        return f"PSEUDOPILOT:{aircraft.pseudo_pilot}"
    if record.kind == "route" and aircraft.editor_route != original["editor_route"]:
        return f"$ROUTE:{aircraft.editor_route}"
    if record.kind == "delay":
        changes = {}
        for index, name in ((1, "delay_min"), (2, "delay_max")):
            value = getattr(aircraft, name)
            if value != original[name]:
                changes[index] = str(value or 0)
        if changes:
            if aircraft.delay_min is None and aircraft.delay_max is None:
                return None
            if aircraft.delay_max is None and original["delay_max"] is not None:
                parts = _patch_tokens(text, changes).split(":")
                del parts[2]
                return ":".join(parts)
            return _patch_tokens(text, changes)
    return text


def _indexed_line(record: SourceRecord, values: list[str]) -> str | None:
    if record.index is not None and record.index < len(values):
        return values[record.index]
    return None


def _global_record(record: SourceRecord, scenario: Scenario) -> str | None:
    if record.kind == "unknown":
        return _indexed_line(record, scenario.unknown_lines)
    if record.kind == "pseudo":
        value = _indexed_line(record, scenario.pseudo_pilots)
        if value is None:
            return None
        return record.text if value == record.text.strip().split(":", 1)[1] else f"PSEUDOPILOT:{value}"
    if record.kind in {"airport", "metar"} and _effective(record, scenario.source_records):
        name = "airport_altitude" if record.kind == "airport" else "metar"
        value = getattr(scenario, name)
        if value != scenario.original_values[name]:
            if value is None:
                return None
            return f"AIRPORT_ALT:{_format_float(value)}" if name == "airport_altitude" else f"METAR:{value}"
    if record.item is not None:
        items = scenario.thresholds if record.kind == "threshold" else scenario.holds
        if not any(item is record.item for item in items):
            return None
        values = asdict(record.item)
        offset = 0 if record.kind == "threshold" else 1
        changes = {}
        for index, (name, value) in enumerate(values.items(), offset):
            if value != record.values[name]:
                changes[index] = _format_coordinate(value) if name.startswith("latitude") or name.startswith("longitude") else str(value)
        return _patch_tokens(record.text, changes)
    return record.text


def _new_global_lines(scenario: Scenario) -> list[str]:
    records = scenario.source_records
    kinds = {record.kind for record in records if record.owner is None}
    lines: list[str] = []
    pilot_count = sum(record.kind == "pseudo" and record.owner is None for record in records)
    lines.extend(f"PSEUDOPILOT:{pilot}" for pilot in scenario.pseudo_pilots[pilot_count:])
    if "airport" not in kinds and scenario.airport_altitude is not None:
        lines.append(f"AIRPORT_ALT:{_format_float(scenario.airport_altitude)}")
    existing_items = {id(record.item) for record in records if record.item is not None}
    for threshold in scenario.thresholds:
        if id(threshold) not in existing_items:
            lines.append(":".join([threshold.name] + [_format_coordinate(value) for value in (
                threshold.latitude1, threshold.longitude1, threshold.latitude2, threshold.longitude2,
            )]))
    for hold in scenario.holds:
        if id(hold) not in existing_items:
            lines.append(f"HOLDING:{hold.fix}:{hold.inbound_heading}:{hold.turn}")
    if "metar" not in kinds and scenario.metar:
        lines.append(f"METAR:{scenario.metar}")
    unknown_count = sum(record.kind == "unknown" and record.owner is None for record in records)
    lines.extend(scenario.unknown_lines[unknown_count:])
    _append_blank(lines)
    return lines


def _new_aircraft_lines(aircraft: Aircraft) -> list[str]:
    kinds = {record.kind for record in aircraft.source_records}
    lines = []
    plan = asdict(aircraft.flight_plan)
    old_plan = aircraft.original_values.get("flight_plan", asdict(FlightPlan()))
    # A rename alone must not manufacture a missing flight plan.
    if "fp" not in kinds and any(plan[name] != old_plan[name] for name in plan if name != "callsign"):
        lines.append(_serialize_flight_plan(aircraft))
    if "sim" not in kinds and aircraft.sim_data:
        lines.append(_serialize_sim_data(aircraft))
    if "route" not in kinds and aircraft.editor_route:
        lines.append(f"$ROUTE:{aircraft.editor_route}")
    if "delay" not in kinds and (aircraft.delay_min is not None or aircraft.delay_max is not None):
        lines.append(_serialize_delay(aircraft))
    unknown_count = sum(record.kind == "unknown" for record in aircraft.source_records)
    lines.extend(aircraft.unknown_lines[unknown_count:])
    return lines


def _aircraft_lines(aircraft: Aircraft) -> list[str]:
    lines = []
    if aircraft.pseudo_pilot and not _has_kind(aircraft, "pseudo"):
        lines.append(f"PSEUDOPILOT:{aircraft.pseudo_pilot}")
    if aircraft.source_records:
        for record in aircraft.source_records:
            line = _aircraft_record(record, aircraft)
            if line is not None:
                lines.append(line)
    else:
        lines.append(_serialize_aircraft_position(aircraft))
    lines.extend(_new_aircraft_lines(aircraft))
    return lines


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
    fields[0] = f"$FP{_renamed_reference(plan.callsign, aircraft) or aircraft.callsign}"
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
        parts[1] = _renamed_reference(parts[1], aircraft)
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
