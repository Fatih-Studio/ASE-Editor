"""Shared field maps and snapshots for lossless record patches."""

from dataclasses import asdict

from .models import Aircraft


POSITION_FIELDS = (
    "symbol", "callsign", "squawk", "mode_c", "latitude", "longitude",
    "altitude", "ground_speed", "heading_raw", "trailing_flag",
)
FLIGHT_PLAN_FIELDS = {
    "callsign": 0, "flight_type": 2, "aircraft_type": 3, "cruise_speed": 4,
    "departure": 5, "departure_time": 6, "enroute_time": 7,
    "cruise_altitude": 8, "arrival": 9, "alternate": 14, "remarks": 15,
}


def aircraft_values(aircraft: Aircraft) -> dict[str, object]:
    values = {name: getattr(aircraft, name) for name in POSITION_FIELDS}
    values.update({name: getattr(aircraft, name) for name in (
        "sim_data", "editor_route", "delay_min", "delay_max", "pseudo_pilot",
    )})
    values["flight_plan"] = asdict(aircraft.flight_plan)
    return values
