from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True, slots=True)
class SectorPoint:
    identifier: str
    latitude: float
    longitude: float
    source: str


@dataclass(frozen=True, slots=True)
class SectorLine:
    latitude1: float
    longitude1: float
    latitude2: float
    longitude2: float
    source: str
    label: str = ""


COORD_RE = re.compile(r"^([NSWE])(\d{3}|\d{2})\.(\d{2})\.(\d{2}(?:\.\d+)?)$")


def load_sector_points(path: str | Path) -> dict[str, SectorPoint]:
    source_path = Path(path)
    if not source_path.exists():
        return {}

    useful_sections = {"VOR", "NDB", "FIXES", "AIRPORT"}
    current_section = ""
    points: dict[str, SectorPoint] = {}

    with source_path.open("r", encoding="utf-8-sig", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith(";"):
                continue
            if line.startswith("[") and line.endswith("]"):
                current_section = line.strip("[]").upper()
                continue
            if current_section not in useful_sections:
                continue

            parsed = _parse_point_line(line, current_section)
            if parsed and parsed.identifier not in points:
                points[parsed.identifier] = parsed

    return points


def load_sector_lines(path: str | Path, max_lines: int = 5000, balanced: bool = False) -> list[SectorLine]:
    source_path = Path(path)
    if not source_path.exists():
        return []

    useful_sections = {
        "RUNWAY",
        "SID",
        "STAR",
        "ARTCC",
        "ARTCC HIGH",
        "ARTCC LOW",
        "GEO",
        "REGIONS",
        "LABELS",
        "HIGH AIRWAY",
        "LOW AIRWAY",
        "DIAGRAMS",
    }
    current_section = ""
    lines: list[SectorLine] = []
    section_counts: dict[str, int] = {}
    current_labels: dict[str, str] = {}
    diagram_sections = {"SID", "STAR", "GEO"}
    section_labels: dict[str, set[str]] = {}
    label_segment_counts: dict[tuple[str, str], int] = {}
    accepted_current_label: dict[str, bool] = {}
    section_limit = max(1, max_lines // len(useful_sections)) if balanced else max_lines
    label_limit = 160
    label_segment_limit = 80

    with source_path.open("r", encoding="utf-8-sig", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith(";"):
                continue
            if line.startswith("[") and line.endswith("]"):
                current_section = line.strip("[]").upper()
                continue
            if current_section not in useful_sections:
                continue
            is_diagram_section = current_section in diagram_sections
            if balanced and not is_diagram_section and section_counts.get(current_section, 0) >= section_limit:
                continue

            parsed = _parse_line_primitive(line, current_section, current_labels.get(current_section, ""))
            if parsed:
                has_explicit_label = bool(_line_label(line))
                if has_explicit_label and parsed.label:
                    current_labels[current_section] = parsed.label
                    if balanced and is_diagram_section:
                        labels = section_labels.setdefault(current_section, set())
                        if parsed.label not in labels and len(labels) >= label_limit:
                            accepted_current_label[current_section] = False
                            continue
                        labels.add(parsed.label)
                        accepted_current_label[current_section] = True

                if balanced and is_diagram_section:
                    if not accepted_current_label.get(current_section, True):
                        continue
                    label_key = (current_section, parsed.label)
                    if label_segment_counts.get(label_key, 0) >= label_segment_limit:
                        continue
                    label_segment_counts[label_key] = label_segment_counts.get(label_key, 0) + 1

                lines.append(parsed)
                section_counts[current_section] = section_counts.get(current_section, 0) + 1
                if not balanced and len(lines) >= max_lines:
                    break

    return lines


def resolve_route_tokens(
    tokens: list[str], sector_points: dict[str, SectorPoint]
) -> list[SectorPoint]:
    resolved: list[SectorPoint] = []
    for token in tokens:
        identifier = token.split("/", 1)[0].upper()
        point = sector_points.get(identifier)
        if point:
            resolved.append(point)
    return resolved


def _parse_point_line(line: str, section: str) -> SectorPoint | None:
    parts = line.split()
    if not parts:
        return None
    identifier = parts[0].upper()
    coords = [part for part in parts[1:] if COORD_RE.match(part.upper())]
    if len(coords) < 2:
        return None
    latitude = _parse_sector_coord(coords[0])
    longitude = _parse_sector_coord(coords[1])
    if latitude is None or longitude is None:
        return None
    return SectorPoint(identifier, latitude, longitude, section)


def _parse_line_primitive(line: str, section: str, fallback_label: str = "") -> SectorLine | None:
    parts = line.split()
    coord_indexes = [index for index, part in enumerate(parts) if COORD_RE.match(part.upper())]
    if len(coord_indexes) < 4:
        return None

    coords = [parts[index] for index in coord_indexes[:4]]
    lat1 = _parse_sector_coord(coords[0])
    lon1 = _parse_sector_coord(coords[1])
    lat2 = _parse_sector_coord(coords[2])
    lon2 = _parse_sector_coord(coords[3])
    if None in {lat1, lon1, lat2, lon2}:
        return None

    label_parts = parts[: coord_indexes[0]]
    label = " ".join(label_parts[:4]) or fallback_label
    return SectorLine(lat1, lon1, lat2, lon2, section, label)


def _line_label(line: str) -> str:
    parts = line.split()
    coord_indexes = [index for index, part in enumerate(parts) if COORD_RE.match(part.upper())]
    if not coord_indexes:
        return ""
    return " ".join(parts[: coord_indexes[0]][:4])


def _parse_sector_coord(value: str) -> float | None:
    match = COORD_RE.match(value.upper())
    if not match:
        return None
    hemisphere, degrees, minutes, seconds = match.groups()
    decimal = float(degrees) + float(minutes) / 60.0 + float(seconds) / 3600.0
    if hemisphere in {"S", "W"}:
        decimal *= -1.0
    return decimal
