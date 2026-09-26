"""Flight Plan Database generation client (no UI or credential persistence)."""
from __future__ import annotations

from dataclasses import dataclass
import math
import os
import re
from threading import Event

import requests

from .route_tools import RouteNode, compact_route


class FlightPlanDBError(Exception):
    def __init__(self, kind: str, message: str, *, quota: tuple[int, int] | None = None):
        super().__init__(message)
        self.kind = kind
        self.quota = quota


@dataclass(frozen=True, slots=True)
class GeneratedRoute:
    plan_id: int
    nodes: tuple[RouteNode, ...]
    route_text: str
    distance_nm: float | None
    quota: tuple[int, int] | None = None  # used, cap


def generation_inputs(departure: str, arrival: str, altitude: str = "", speed: str = "") -> dict:
    departure, arrival = departure.strip().upper(), arrival.strip().upper()
    if not re.fullmatch(r"[A-Z]{4}", departure) or not re.fullmatch(r"[A-Z]{4}", arrival):
        raise FlightPlanDBError("input", "Enter departure and arrival as four-letter ICAO codes.")
    if departure == arrival:
        raise FlightPlanDBError("input", "Departure and arrival must be different airports.")
    result = {"departure": departure, "arrival": arrival}
    for raw, field, label in ((altitude, "cruise_altitude_ft", "altitude"), (speed, "cruise_speed_kt", "speed")):
        value = raw.strip().upper()
        if not value:
            continue
        multiplier = 1
        if label == "altitude" and re.fullmatch(r"FL?\d{3}", value):
            value = value.lstrip("FL")
            multiplier = 100
        elif label == "speed" and re.fullmatch(r"N\d{4}", value):
            value = value[1:]
        if not re.fullmatch(r"\d+(?:\.\d+)?", value) or not math.isfinite(float(value)) or float(value) <= 0:
            formats = "feet or FLxxx/Fxxx" if label == "altitude" else "knots or Nxxxx"
            raise FlightPlanDBError("input", f"Enter cruise {label} as positive {formats}, or leave it blank.")
        result[field] = float(value) * multiplier
    return result


def _identifier(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9./+-]*", value.strip()):
        raise ValueError("Invalid node identifier")
    return value.strip().upper()


def _coordinate(value: object, bound: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Invalid coordinate")
    number = float(value)
    if not math.isfinite(number) or abs(number) > bound:
        raise ValueError("Invalid coordinate")
    return number


class FlightPlanDBClient:
    BASE_URL = "https://api.flightplandatabase.com"
    TIMEOUT = (10, 30)

    def __init__(self, *, session=None, cancel: Event | None = None):
        self._session = session
        self.cancel = cancel or Event()

    def generate_route(self, departure: str, arrival: str, *, cruise_altitude_ft: float | None = None,
                       cruise_speed_kt: float | None = None) -> GeneratedRoute:
        key = os.environ.get("FLIGHTPLANDB_API_KEY", "").strip()
        if not key:
            raise FlightPlanDBError("credentials", "Set FLIGHTPLANDB_API_KEY in the project's .env file or your environment, then restart the app.")
        inputs = generation_inputs(departure, arrival,
                                   "" if cruise_altitude_ft is None else str(cruise_altitude_ft),
                                   "" if cruise_speed_kt is None else str(cruise_speed_kt))
        payload = {"fromICAO": inputs["departure"], "toICAO": inputs["arrival"]}
        for argument, parameter in (("cruise_altitude_ft", "cruiseAlt"), ("cruise_speed_kt", "cruiseSpeed")):
            if argument in inputs:
                payload[parameter] = inputs[argument]
        session = self._session or requests.Session()
        try:
            generated, quota = self._request(session, "POST", "/auto/generate", key, json=payload)
            plan_id = generated.get("id")
            if isinstance(plan_id, bool) or not isinstance(plan_id, int) or plan_id <= 0:
                raise ValueError("Missing plan ID")
            plan, fetched_quota = self._request(session, "GET", f"/plan/{plan_id}", key)
            raw_nodes = plan["route"]["nodes"]
            if not isinstance(raw_nodes, list) or len(raw_nodes) < 2:
                raise ValueError("Missing route nodes")
            nodes = []
            for raw in raw_nodes:
                via = raw.get("via")
                if via is not None and not isinstance(via, dict):
                    raise ValueError("Invalid via")
                nodes.append(RouteNode(_identifier(raw["ident"]), _coordinate(raw["lat"], 90),
                                       _coordinate(raw["lon"], 180),
                                       _identifier(via["ident"]) if via else None,
                                       via.get("type") if via else None))
                if nodes[-1].via_type is not None and not isinstance(nodes[-1].via_type, str):
                    raise ValueError("Invalid via type")
            if nodes[0].ident != inputs["departure"] or nodes[-1].ident != inputs["arrival"]:
                raise ValueError("Route airports do not match")
            distance = plan.get("distance")
            if isinstance(distance, bool) or not isinstance(distance, (int, float)) or not math.isfinite(distance) or distance < 0:
                distance = None
            return GeneratedRoute(plan_id, tuple(nodes), compact_route(tuple(nodes)), distance, fetched_quota or quota)
        except (KeyError, TypeError, ValueError, AttributeError):
            raise FlightPlanDBError("response", "FlightPlanDB returned an incomplete or invalid route. Your drafts were preserved.") from None
        finally:
            if self._session is None:
                session.close()

    def _request(self, session, method: str, path: str, key: str, **kwargs):
        if self.cancel.is_set():
            raise FlightPlanDBError("cancelled", "Route generation was cancelled.")
        try:
            response = session.request(method, self.BASE_URL + path, auth=(key, ""),
                                       headers={"Accept": "application/json", "X-Units": "AVIATION"},
                                       timeout=self.TIMEOUT, allow_redirects=False, **kwargs)
        except requests.Timeout:
            raise FlightPlanDBError("timeout", "FlightPlanDB timed out. Generation may have completed remotely; your local drafts were preserved.") from None
        except requests.RequestException:
            raise FlightPlanDBError("network", "Could not connect to FlightPlanDB. Check your connection and try again.") from None
        try:
            quota = None
            try:
                quota = (int(response.headers["X-Limit-Used"]), int(response.headers["X-Limit-Cap"]))
            except (KeyError, ValueError, TypeError):
                pass
            code = response.status_code
            if code in (401, 403):
                raise FlightPlanDBError("auth", "FlightPlanDB rejected the API key or account permissions.", quota=quota)
            if code == 429:
                message = "FlightPlanDB request limit reached. Try again when your quota is available."
                if quota:
                    message += f" Requests used: {quota[0]} / {quota[1]}."
                raise FlightPlanDBError("limit", message, quota=quota)
            if not 200 <= code < 300:
                raise FlightPlanDBError("api", f"FlightPlanDB request failed (HTTP {code}). Check the airports or try again later.", quota=quota)
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError("Invalid response")
            return data, quota
        finally:
            response.close()
