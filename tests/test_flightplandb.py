from copy import deepcopy
from threading import Event

import pytest
import requests

from ase_editor.flightplandb import FlightPlanDBClient, FlightPlanDBError, generation_inputs


class Response:
    def __init__(self, data, status=200, headers=None):
        self.data, self.status_code, self.headers = data, status, headers or {}
        self.closed = False

    def json(self):
        if isinstance(self.data, Exception):
            raise self.data
        return self.data

    def close(self):
        self.closed = True


class Session:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.calls = []

    def request(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv("FLIGHTPLANDB_API_KEY", " test-key ")
    def forbidden(*args, **kwargs):
        raise AssertionError("Live network forbidden")
    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)


@pytest.fixture
def plan():
    return {"distance": 500.5, "route": {"nodes": [
        {"ident": "WIII", "lat": -6, "lon": 106, "via": None},
        {"ident": "KASAL", "lat": -6, "lon": 107, "via": None},
        {"ident": "MID", "lat": -7, "lon": 110, "via": {"ident": "G461", "type": "AWY-HI"}},
        {"ident": "SBR", "lat": -7, "lon": 112, "via": {"ident": "G461", "type": "AWY-HI"}},
        {"ident": "RABOL", "lat": -8, "lon": 114, "via": {"ident": "W33", "type": "AWY-LO"}},
        {"ident": "WADD", "lat": -8, "lon": 115, "via": None},
    ]}}


def test_generate_fetch_and_compact(plan):
    created = Response({"id": 42})
    fetched = Response(plan, headers={"X-Limit-Used": "2", "X-Limit-Cap": "100"})
    session = Session(created, fetched)
    result = FlightPlanDBClient(session=session).generate_route(" wiii ", "wadd", cruise_altitude_ft=35000, cruise_speed_kt=420)
    assert result.plan_id == 42
    assert len(result.nodes) == 6
    assert result.route_text == "WIII DCT KASAL G461 SBR W33 RABOL DCT WADD"
    assert result.quota == (2, 100)
    assert result.distance_nm == 500.5
    args, kwargs = session.calls[0]
    assert args == ("POST", "https://api.flightplandatabase.com/auto/generate")
    assert kwargs["auth"] == ("test-key", "")
    assert kwargs["json"] == {"fromICAO": "WIII", "toICAO": "WADD", "cruiseAlt": 35000, "cruiseSpeed": 420}
    assert kwargs["headers"]["X-Units"] == "AVIATION"
    assert kwargs["timeout"] == (10, 30)
    assert kwargs["allow_redirects"] is False
    assert session.calls[1][0] == ("GET", "https://api.flightplandatabase.com/plan/42")
    assert created.closed and fetched.closed


def test_blank_options_omitted(plan):
    session = Session(Response({"id": 1}), Response(plan))
    FlightPlanDBClient(session=session).generate_route("WIII", "WADD")
    assert session.calls[0][1]["json"] == {"fromICAO": "WIII", "toICAO": "WADD"}


@pytest.mark.parametrize("altitude,speed,feet,knots", [("FL350", "N0420", 35000, 420), ("F300", "420", 30000, 420), ("30000", "250.5", 30000, 250.5)])
def test_cruise_formats(altitude, speed, feet, knots):
    assert generation_inputs("wiii", "wadd", altitude, speed) == {
        "departure": "WIII", "arrival": "WADD", "cruise_altitude_ft": feet, "cruise_speed_kt": knots}


@pytest.mark.parametrize("args", [("", "WADD"), ("WII", "WADD"), ("WIII", "WIII"),
                                  ("WIII", "WADD", "S1100"), ("WIII", "WADD", "0"),
                                  ("WIII", "WADD", "", "M082"), ("WIII", "WADD", "nan"),
                                  ("WIII", "WADD", "", "-10")])
def test_invalid_inputs(args):
    with pytest.raises(FlightPlanDBError) as error:
        generation_inputs(*args)
    assert error.value.kind == "input"


def test_missing_key_never_calls_api(monkeypatch):
    monkeypatch.delenv("FLIGHTPLANDB_API_KEY")
    session = Session()
    with pytest.raises(FlightPlanDBError, match="FLIGHTPLANDB_API_KEY"):
        FlightPlanDBClient(session=session).generate_route("WIII", "WADD")
    assert not session.calls


@pytest.mark.parametrize("status,kind", [(401, "auth"), (403, "auth"), (429, "limit"), (400, "api"), (500, "api"), (302, "api")])
@pytest.mark.parametrize("during_fetch", [False, True])
def test_http_failure_no_retry_or_secret_exposure(status, kind, during_fetch):
    response = Response({"errors": ["test-key"]}, status, {"X-Limit-Used": "100", "X-Limit-Cap": "100"})
    session = Session(*([Response({"id": 42})] if during_fetch else []), response)
    with pytest.raises(FlightPlanDBError) as error:
        FlightPlanDBClient(session=session).generate_route("WIII", "WADD")
    assert error.value.kind == kind
    assert "test-key" not in str(error.value)
    assert error.value.quota == (100, 100)
    assert len(session.calls) == (2 if during_fetch else 1)
    assert response.closed


@pytest.mark.parametrize("failure,kind", [(requests.Timeout("test-key"), "timeout"),
                                         (requests.ConnectionError("test-key"), "network")])
@pytest.mark.parametrize("during_fetch", [False, True])
def test_transport_failure(failure, kind, during_fetch):
    session = Session(*([Response({"id": 42})] if during_fetch else []), failure)
    with pytest.raises(FlightPlanDBError) as error:
        FlightPlanDBClient(session=session).generate_route("WIII", "WADD")
    assert error.value.kind == kind
    assert "test-key" not in str(error.value)
    assert len(session.calls) == (2 if during_fetch else 1)


@pytest.mark.parametrize("response", [{}, {"id": True}, {"id": "42"}, [], ValueError("test-key")])
def test_bad_generate_response(response):
    with pytest.raises(FlightPlanDBError) as error:
        FlightPlanDBClient(session=Session(Response(response))).generate_route("WIII", "WADD")
    assert error.value.kind == "response"
    assert "test-key" not in str(error.value)


@pytest.mark.parametrize("change", ["missing", "empty", "ident", "coordinate", "mismatch", "via", "type"])
def test_bad_nodes_preserve_failure(plan, change):
    plan = deepcopy(plan)
    if change == "missing":
        del plan["route"]
    elif change == "empty":
        plan["route"]["nodes"] = []
    else:
        node = plan["route"]["nodes"][0]
        if change == "ident":
            node["ident"] = "WIII\n$ROUTE:BAD"
        elif change == "coordinate":
            node["lat"] = float("nan")
        elif change == "mismatch":
            node["ident"] = "WIHH"
        elif change == "via":
            node["via"] = "G461"
        elif change == "type":
            node["via"] = {"ident": "G461", "type": []}
    with pytest.raises(FlightPlanDBError) as error:
        FlightPlanDBClient(session=Session(Response({"id": 42}), Response(plan))).generate_route("WIII", "WADD")
    assert error.value.kind == "response"


def test_cancellation_before_request():
    cancel = Event()
    cancel.set()
    session = Session()
    with pytest.raises(FlightPlanDBError) as error:
        FlightPlanDBClient(session=session, cancel=cancel).generate_route("WIII", "WADD")
    assert error.value.kind == "cancelled"
    assert not session.calls
