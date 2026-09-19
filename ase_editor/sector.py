from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re


@dataclass(frozen=True, slots=True)
class SectorColor:
    name: str
    value: int

    @property
    def red(self) -> int:
        return self.value & 0xFF

    @property
    def green(self) -> int:
        return (self.value >> 8) & 0xFF

    @property
    def blue(self) -> int:
        return (self.value >> 16) & 0xFF


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
    color_name: str = ""
    min_latitude: float = field(init=False)
    max_latitude: float = field(init=False)
    min_longitude: float = field(init=False)
    max_longitude: float = field(init=False)
    render_key: int = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "min_latitude", min(self.latitude1, self.latitude2))
        object.__setattr__(self, "max_latitude", max(self.latitude1, self.latitude2))
        object.__setattr__(self, "min_longitude", min(self.longitude1, self.longitude2))
        object.__setattr__(self, "max_longitude", max(self.longitude1, self.longitude2))
        render_key = (
            int(abs(self.latitude1) * 100_000)
            ^ (int(abs(self.longitude1) * 100_000) << 1)
            ^ (int(abs(self.latitude2) * 100_000) << 2)
            ^ (int(abs(self.longitude2) * 100_000) << 3)
        )
        object.__setattr__(self, "render_key", render_key)


@dataclass(frozen=True, slots=True)
class SectorTextLabel:
    text: str
    latitude: float
    longitude: float
    source: str = "LABELS"
    color_name: str = ""


@dataclass(frozen=True, slots=True)
class SectorRegion:
    name: str
    color_name: str
    points: tuple[tuple[float, float], ...]
    source: str = "REGIONS"
    min_latitude: float = field(init=False)
    max_latitude: float = field(init=False)
    min_longitude: float = field(init=False)
    max_longitude: float = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "min_latitude", min(point[0] for point in self.points))
        object.__setattr__(self, "max_latitude", max(point[0] for point in self.points))
        object.__setattr__(self, "min_longitude", min(point[1] for point in self.points))
        object.__setattr__(self, "max_longitude", max(point[1] for point in self.points))


@dataclass(frozen=True, slots=True)
class SectorInfo:
    raw_lines: tuple[str, ...] = ()
    title: str = ""
    default_callsign: str = ""
    default_airport: str = ""
    center_latitude: float | None = None
    center_longitude: float | None = None
    nm_per_degree_latitude: float | None = None
    nm_per_degree_longitude: float | None = None
    magnetic_variation: float | None = None
    scale_factor: float | None = None


@dataclass(frozen=True, slots=True)
class SectorData:
    points: dict[str, SectorPoint]
    lines: list[SectorLine]
    regions: list[SectorRegion]
    labels: list[SectorTextLabel]
    colors: dict[str, SectorColor]
    info: SectorInfo = field(default_factory=SectorInfo)


COORD_RE = re.compile(r"^([NSWE])(\d{3}|\d{2})\.(\d{2})\.(\d{2}(?:\.\d+)?)$")
COLOR_DEFINE_RE = re.compile(r"^#define\s+(\S+)\s+(-?\d+)", re.IGNORECASE)


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


def load_sector_lines(path: str | Path, max_lines: int | None = 5000, balanced: bool = False) -> list[SectorLine]:
    return load_sector_data(path, max_lines=max_lines, balanced=balanced).lines


def load_sector_data(path: str | Path, max_lines: int | None = None, balanced: bool = False) -> SectorData:
    source_path = Path(path)
    if not source_path.exists():
        return SectorData({}, [], [], [], {})

    point_sections = {"VOR", "NDB", "FIXES", "AIRPORT"}
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
    points: dict[str, SectorPoint] = {}
    lines: list[SectorLine] = []
    regions: list[SectorRegion] = []
    labels: list[SectorTextLabel] = []
    colors: dict[str, SectorColor] = {}
    info_lines: list[str] = []
    section_counts: dict[str, int] = {}
    current_labels: dict[str, str] = {}
    diagram_sections = {"SID", "STAR", "GEO"}
    section_labels: dict[str, set[str]] = {}
    label_segment_counts: dict[tuple[str, str], int] = {}
    accepted_current_label: dict[str, bool] = {}
    section_limit = max(1, max_lines // len(useful_sections)) if balanced and max_lines is not None else max_lines
    label_limit = 160
    label_segment_limit = 80
    active_region_name = ""
    active_region_color = ""
    active_region_points: list[tuple[float, float]] = []

    def flush_region() -> None:
        nonlocal active_region_points
        if len(active_region_points) >= 3:
            regions.append(
                SectorRegion(
                    active_region_name,
                    active_region_color,
                    tuple(active_region_points),
                )
            )
        active_region_points = []

    with source_path.open("r", encoding="utf-8-sig", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith(";"):
                continue
            color = _parse_color_define(line)
            if color:
                colors[color.name] = color
                continue
            if line.startswith("[") and line.endswith("]"):
                if current_section == "REGIONS":
                    flush_region()
                current_section = line.strip("[]").upper()
                continue
            if current_section in point_sections:
                parsed_point = _parse_point_line(line, current_section)
                if parsed_point and parsed_point.identifier not in points:
                    points[parsed_point.identifier] = parsed_point
                continue
            if current_section == "INFO":
                info_lines.append(line)
                continue
            if current_section == "REGIONS":
                if line.upper().startswith("REGIONNAME"):
                    flush_region()
                    active_region_name = line.split(maxsplit=1)[1] if len(line.split(maxsplit=1)) > 1 else ""
                    active_region_color = ""
                    continue
                region_color = _line_color_name(line)
                region_coords = _coord_pairs(line)
                if region_color:
                    flush_region()
                    active_region_color = region_color
                if region_coords:
                    active_region_points.extend(region_coords)
                continue

            if current_section == "LABELS":
                label = _parse_text_label(line)
                if label:
                    labels.append(label)
                continue

            if current_section not in useful_sections:
                continue
            if max_lines is not None:
                is_diagram_section = current_section in diagram_sections
                if balanced and not is_diagram_section and section_counts.get(current_section, 0) >= section_limit:
                    continue

            parsed = _parse_line_primitive(line, current_section, current_labels.get(current_section, ""))
            if not parsed:
                continue

            if max_lines is not None:
                has_explicit_label = bool(_line_label(line))
                if has_explicit_label and parsed.label:
                    current_labels[current_section] = parsed.label
                    if balanced and parsed.source in diagram_sections:
                        source_labels = section_labels.setdefault(current_section, set())
                        if parsed.label not in source_labels and len(source_labels) >= label_limit:
                            accepted_current_label[current_section] = False
                            continue
                        source_labels.add(parsed.label)
                        accepted_current_label[current_section] = True

                if balanced and parsed.source in diagram_sections:
                    if not accepted_current_label.get(current_section, True):
                        continue
                    label_key = (current_section, parsed.label)
                    if label_segment_counts.get(label_key, 0) >= label_segment_limit:
                        continue
                    label_segment_counts[label_key] = label_segment_counts.get(label_key, 0) + 1

            lines.append(parsed)
            section_counts[current_section] = section_counts.get(current_section, 0) + 1
            if max_lines is not None and not balanced and len(lines) >= max_lines:
                break

    if current_section == "REGIONS":
        flush_region()

    return SectorData(points, lines, regions, labels, colors, _parse_info_lines(info_lines))


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


def parse_sector_info_lines(lines: list[str] | tuple[str, ...]) -> SectorInfo:
    center_latitude = _parse_sector_coord(lines[3]) if len(lines) > 3 else None
    center_longitude = _parse_sector_coord(lines[4]) if len(lines) > 4 else None
    return SectorInfo(
        raw_lines=tuple(lines),
        title=lines[0] if len(lines) > 0 else "",
        default_callsign=lines[1] if len(lines) > 1 else "",
        default_airport=lines[2] if len(lines) > 2 else "",
        center_latitude=center_latitude,
        center_longitude=center_longitude,
        nm_per_degree_latitude=_float_or_none(lines[5]) if len(lines) > 5 else None,
        nm_per_degree_longitude=_float_or_none(lines[6]) if len(lines) > 6 else None,
        magnetic_variation=_float_or_none(lines[7]) if len(lines) > 7 else None,
        scale_factor=_float_or_none(lines[8]) if len(lines) > 8 else None,
    )


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
    return SectorLine(lat1, lon1, lat2, lon2, section, label, _line_color_name(line))


def _parse_text_label(line: str) -> SectorTextLabel | None:
    coord_indexes = [index for index, part in enumerate(line.split()) if COORD_RE.match(part.upper())]
    if len(coord_indexes) < 2:
        return None

    parts = line.split()
    latitude = _parse_sector_coord(parts[coord_indexes[0]])
    longitude = _parse_sector_coord(parts[coord_indexes[1]])
    if latitude is None or longitude is None:
        return None

    text_part = " ".join(parts[: coord_indexes[0]]).strip()
    if text_part.startswith('"') and text_part.endswith('"'):
        text_part = text_part[1:-1]
    color_name = _line_color_name(line)
    return SectorTextLabel(text_part, latitude, longitude, color_name=color_name)


def _parse_info_lines(lines: list[str]) -> SectorInfo:
    return parse_sector_info_lines(lines)


def _line_label(line: str) -> str:
    parts = line.split()
    coord_indexes = [index for index, part in enumerate(parts) if COORD_RE.match(part.upper())]
    if not coord_indexes:
        return ""
    return " ".join(parts[: coord_indexes[0]][:4])


def _parse_color_define(line: str) -> SectorColor | None:
    match = COLOR_DEFINE_RE.match(line)
    if not match:
        return None
    name, value = match.groups()
    try:
        return SectorColor(name, int(value))
    except ValueError:
        return None


def _line_color_name(line: str) -> str:
    for part in line.split():
        if part.upper().startswith("COLOR_"):
            return part
    return ""


def _float_or_none(value: str) -> float | None:
    try:
        return float(value.strip())
    except (TypeError, ValueError):
        return None


def _coord_pairs(line: str) -> list[tuple[float, float]]:
    parts = line.split()
    coords = [part for part in parts if COORD_RE.match(part.upper())]
    pairs: list[tuple[float, float]] = []
    for index in range(0, len(coords) - 1, 2):
        latitude = _parse_sector_coord(coords[index])
        longitude = _parse_sector_coord(coords[index + 1])
        if latitude is not None and longitude is not None:
            pairs.append((latitude, longitude))
    return pairs


def _parse_sector_coord(value: str) -> float | None:
    match = COORD_RE.match(value.upper())
    if not match:
        return None
    hemisphere, degrees, minutes, seconds = match.groups()
    decimal = float(degrees) + float(minutes) / 60.0 + float(seconds) / 3600.0
    if hemisphere in {"S", "W"}:
        decimal *= -1.0
    return decimal
