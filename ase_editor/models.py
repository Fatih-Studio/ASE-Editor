from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


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
    raw_lines: list[str] = field(default_factory=list)
    unknown_lines: list[str] = field(default_factory=list)

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


@dataclass(slots=True)
class Hold:
    fix: str
    inbound_heading: int
    turn: int


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

    def all_geo_points(self) -> list[tuple[float, float]]:
        points: list[tuple[float, float]] = []
        for threshold in self.thresholds:
            points.append((threshold.latitude1, threshold.longitude1))
            points.append((threshold.latitude2, threshold.longitude2))
        for aircraft in self.aircraft:
            points.append((aircraft.latitude, aircraft.longitude))
        return points
