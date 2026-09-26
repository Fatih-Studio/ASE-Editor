"""Pure route formatting and position-based checkpoint suggestions."""
from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True, slots=True)
class RouteNode:
    ident: str
    latitude: float
    longitude: float
    via_ident: str | None = None
    via_type: str | None = None


def compact_route(nodes: tuple[RouteNode, ...]) -> str:
    if not nodes:
        return ""
    tokens = [nodes[0].ident]
    index = 1
    while index < len(nodes):
        node = nodes[index]
        airway = node.via_ident if node.via_type in {"AWY-HI", "AWY-LO"} else None
        if airway:
            end = index
            while (end + 1 < len(nodes)
                   and nodes[end + 1].via_ident == airway
                   and nodes[end + 1].via_type == node.via_type):
                end += 1
            tokens.extend((airway, nodes[end].ident))
            index = end + 1
        else:
            # Keep every fix for tracks/procedures; do not invent a procedure.
            tokens.extend(("DCT", node.ident))
            index += 1
    return " ".join(tokens)


def checkpoint_text(nodes: tuple[RouteNode, ...], start: int) -> str:
    if not 0 <= start < len(nodes):
        raise ValueError("Choose a starting checkpoint.")
    return " ".join(node.ident for node in nodes[start:])


def _arc_and_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> tuple[float, float]:
    a, b = math.radians(lat1), math.radians(lat2)
    delta = math.radians(lon2 - lon1)
    hav = math.sin((b - a) / 2) ** 2 + math.cos(a) * math.cos(b) * math.sin(delta / 2) ** 2
    arc = 2 * math.asin(math.sqrt(max(0.0, min(1.0, hav))))
    bearing = math.atan2(math.sin(delta) * math.cos(b),
                         math.cos(a) * math.sin(b) - math.sin(a) * math.cos(b) * math.cos(delta))
    return arc, bearing


def suggest_checkpoint(nodes: tuple[RouteNode, ...], latitude: float,
                       longitude: float, heading: float) -> tuple[int, float]:
    """Return a downstream node index and distance to its segment in NM.

    Distances use clamped great-circle segments, including across the dateline.
    Heading breaks near-distance ties; the user must review the suggestion.
    """
    if len(nodes) < 2:
        raise ValueError("At least two route nodes are required.")
    candidates = []
    for index, (a, b) in enumerate(zip(nodes, nodes[1:])):
        length, direction = _arc_and_bearing(a.latitude, a.longitude, b.latitude, b.longitude)
        distance, bearing = _arc_and_bearing(a.latitude, a.longitude, latitude, longitude)
        along = math.atan2(math.sin(distance) * math.cos(bearing - direction), math.cos(distance))
        if length < 1e-12 or along <= 0:
            separation = distance
        elif along >= length:
            separation = _arc_and_bearing(b.latitude, b.longitude, latitude, longitude)[0]
        else:
            separation = abs(math.asin(max(-1.0, min(1.0, math.sin(distance) * math.sin(bearing - direction)))))
        mismatch = abs((math.degrees(direction) - heading + 180) % 360 - 180)
        candidates.append((separation * 3440.065, mismatch, index + 1))
    nearest = min(item[0] for item in candidates)
    chosen = min((item for item in candidates if item[0] <= nearest + 1.0),
                 key=lambda item: (item[1], item[0], item[2]))
    return chosen[2], chosen[0]
