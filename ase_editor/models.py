from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import math
import re


@dataclass(slots=True)
class RouteWaypoint:
    identifier: str
    latitude: float | None = None
    longitude: float | None = None

    @property
    def is_resolved(self) -> bool:
        return self.latitude is not None and self.longitude is not None


@dataclass(slots=True)
class FlightPlan:
    callsign: str = ""
    flight_type: str = ""
    aircraft_type: str = ""
    departure: str = ""
    arrival: str = ""
    alternate: str = ""
    departure_time: str = ""
    enroute_time: str = ""
    cruise_speed: str = ""
    cruise_altitude: str = ""
    route_text: str = ""
    remarks: str = ""
    raw_fields: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Aircraft:
    callsign: str
    squawk: str = ""
    mode_c: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    altitude: int = 0
    ground_speed: int = 0
    heading_raw: int = 0
    trailing_flag: str = ""
    symbol: str = "N"
    flight_plan: FlightPlan = field(default_factory=FlightPlan)
    sim_data: str = ""
    editor_route: str = ""
    delay_min: int | None = None
    delay_max: int | None = None
    cleared_flight_level: int | None = None
    ias_variation: int = 0
    dummy_controller: str = ""
    perf_profile: str = ""
    wake_category: str = ""
    target_kind: str = "aircraft"
    pseudo_pilot: str = ""
    raw_lines: list[str] = field(default_factory=list)
    unknown_lines: list[str] = field(default_factory=list)
    source_records: list[SourceRecord] = field(default_factory=list, repr=False, compare=False)
    original_values: dict[str, object] = field(default_factory=dict, repr=False, compare=False)

    @property
    def display_speed(self) -> str:
        if self.ground_speed:
            return str(self.ground_speed)
        return self.flight_plan.cruise_speed or ""

    @property
    def route_source(self) -> str:
        return self.editor_route or self.flight_plan.route_text

    @property
    def route_tokens(self) -> list[str]:
        return [token for token in self.route_source.replace("\n", " ").split(" ") if token]

    @property
    def heading_degrees(self) -> float:
        if self.heading_raw > 360:
            return (self.heading_raw / 4096.0) * 360.0
        return float(self.heading_raw)

    @property
    def actual_flight_level(self) -> int:
        return int(round(self.altitude / 100.0))

    @property
    def cleared_level_text(self) -> str:
        if self.cleared_flight_level is None:
            return f"FL{self.actual_flight_level:03d}"
        return f"FL{self.cleared_flight_level:03d}"

    @property
    def transponder_mode_text(self) -> str:
        return "C" if self.mode_c == "1" else "A"

    @property
    def delay_text(self) -> str:
        if self.delay_min is None and self.delay_max is None:
            return ""
        if self.delay_max is None:
            return str(self.delay_min)
        return f"{self.delay_min}:{self.delay_max}"


@dataclass(slots=True)
class Threshold:
    name: str
    latitude1: float
    longitude1: float
    latitude2: float
    longitude2: float


class ThresholdValidationError(ValueError):
    def __init__(self, errors: dict[str, str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors.values()))


def validate_threshold(
    values: dict[str, object], thresholds: list[Threshold], existing: Threshold | None = None,
) -> dict[str, object]:
    """Validate a creation or partial edit without changing the source object."""
    fields = ("name", "latitude1", "longitude1", "latitude2", "longitude2")
    if values.keys() - set(fields):
        raise ValueError("Unknown threshold field")
    result = {name: getattr(existing, name) if existing is not None else None for name in fields}
    changes = {name: value for name, value in values.items() if value != result[name]}
    if existing is not None and not changes:
        return result
    result.update(changes)
    errors = {}
    if existing is None or "name" in changes:
        name = str(result["name"] or "").strip().upper()
        result["name"] = name
        if not re.fullmatch(r"ILS(?:0[1-9]|[12][0-9]|3[0-6])[LCR]?", name):
            errors["name"] = "Use ILS01–ILS36, optionally followed by L, C, or R."
    if any(item is not existing and item.name.strip().casefold() == str(result["name"]).casefold()
           for item in thresholds):
        errors["name"] = "A threshold with this name already exists."
    for name in fields[1:]:
        limit = 90 if name.startswith("latitude") else 180
        try:
            value = float(result[name])
            if not math.isfinite(value) or not -limit <= value <= limit:
                raise ValueError
            if existing is None or name in changes:
                result[name] = round(value, 7)
        except (ValueError, TypeError, OverflowError):
            errors[name] = f"Enter a finite decimal number between −{limit} and {limit}."
    if not any(name in errors for name in fields[1:]):
        if (round(result["latitude1"], 7), round(result["longitude1"], 7)) == (
            round(result["latitude2"], 7), round(result["longitude2"], 7)
        ):
            errors["latitude2"] = "Threshold and far end must be different positions."
    if errors:
        raise ThresholdValidationError(errors)
    return result


@dataclass(slots=True)
class Hold:
    fix: str
    inbound_heading: int
    turn: int


@dataclass(slots=True)
class SourceRecord:
    """An ordered input record, independently of its editable model projection."""

    kind: str
    text: str
    owner: Aircraft | None = field(default=None, repr=False, compare=False)
    values: dict[str, object] = field(default_factory=dict)
    item: Threshold | Hold | None = None
    index: int | None = None


@dataclass(slots=True)
class Scenario:
    source_path: Path | None = None
    airport_altitude: float | None = None
    metar: str = ""
    pseudo_pilots: list[str] = field(default_factory=list)
    aircraft: list[Aircraft] = field(default_factory=list)
    thresholds: list[Threshold] = field(default_factory=list)
    holds: list[Hold] = field(default_factory=list)
    unknown_lines: list[str] = field(default_factory=list)
    source_records: list[SourceRecord] = field(default_factory=list, repr=False, compare=False)
    original_values: dict[str, object] = field(default_factory=dict, repr=False, compare=False)

    def create_threshold(self, name: str, latitude1: object, longitude1: object,
                         latitude2: object, longitude2: object) -> Threshold:
        values = validate_threshold(dict(name=name, latitude1=latitude1, longitude1=longitude1,
                                         latitude2=latitude2, longitude2=longitude2), self.thresholds)
        threshold = Threshold(**values)
        self.thresholds.append(threshold)
        return threshold

    def update_threshold(self, threshold: Threshold, **changes: object) -> Threshold:
        if not any(item is threshold for item in self.thresholds):
            raise ValueError("Threshold no longer belongs to this scenario")
        values = validate_threshold(changes, self.thresholds, threshold)
        for name, value in values.items():
            if value != getattr(threshold, name):
                setattr(threshold, name, value)
        return threshold

    def delete_threshold(self, threshold: Threshold) -> None:
        self.thresholds[:] = [item for item in self.thresholds if item is not threshold]

    def all_geo_points(self) -> list[tuple[float, float]]:
        points: list[tuple[float, float]] = []
        for threshold in self.thresholds:
            points.append((threshold.latitude1, threshold.longitude1))
            points.append((threshold.latitude2, threshold.longitude2))
        for aircraft in self.aircraft:
            points.append((aircraft.latitude, aircraft.longitude))
        return points
