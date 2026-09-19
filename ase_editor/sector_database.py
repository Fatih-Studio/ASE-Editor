from __future__ import annotations

from pathlib import Path
import sqlite3

from .sector import (
    SectorColor,
    SectorData,
    SectorInfo,
    SectorLine,
    SectorPoint,
    SectorRegion,
    SectorTextLabel,
    load_sector_data,
    parse_sector_info_lines,
)


SCHEMA_VERSION = "1"


def build_sector_database(
    source_path: str | Path,
    database_path: str | Path,
    database_name: str = "Indonesia",
) -> SectorData:
    source = Path(source_path)
    destination = Path(database_path)
    sector_data = load_sector_data(source)
    destination.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(destination) as connection:
        _create_schema(connection)
        _write_sector_data(connection, sector_data, database_name, source)

    return sector_data


def load_sector_database(database_path: str | Path) -> SectorData:
    source = Path(database_path)
    with sqlite3.connect(source) as connection:
        connection.row_factory = sqlite3.Row
        metadata = _read_metadata(connection)
        info = _sector_info_from_metadata(metadata)
        colors = {
            row["name"]: SectorColor(row["name"], int(row["value"]))
            for row in connection.execute("SELECT name, value FROM colors")
        }
        points = {
            row["identifier"]: SectorPoint(
                row["identifier"],
                float(row["latitude"]),
                float(row["longitude"]),
                row["source"],
            )
            for row in connection.execute(
                "SELECT identifier, latitude, longitude, source FROM points"
            )
        }
        lines = [
            SectorLine(
                float(row["latitude1"]),
                float(row["longitude1"]),
                float(row["latitude2"]),
                float(row["longitude2"]),
                row["source"],
                row["label"] or "",
                row["color_name"] or "",
            )
            for row in connection.execute(
                """
                SELECT latitude1, longitude1, latitude2, longitude2, source, label, color_name
                FROM lines
                ORDER BY id
                """
            )
        ]
        labels = [
            SectorTextLabel(
                row["text"],
                float(row["latitude"]),
                float(row["longitude"]),
                row["source"],
                row["color_name"] or "",
            )
            for row in connection.execute(
                "SELECT text, latitude, longitude, source, color_name FROM labels ORDER BY id"
            )
        ]
        region_points: dict[int, list[tuple[float, float]]] = {}
        for row in connection.execute(
            "SELECT region_id, latitude, longitude FROM region_points ORDER BY region_id, sequence"
        ):
            region_points.setdefault(int(row["region_id"]), []).append(
                (float(row["latitude"]), float(row["longitude"]))
            )

        regions = [
            SectorRegion(
                row["name"] or "",
                row["color_name"] or "",
                tuple(region_points.get(int(row["id"]), [])),
                row["source"],
            )
            for row in connection.execute(
                "SELECT id, name, color_name, source FROM regions ORDER BY id"
            )
            if len(region_points.get(int(row["id"]), [])) >= 3
        ]

    return SectorData(points, lines, regions, labels, colors, info)


def save_sector_info(database_path: str | Path, lines: list[str] | tuple[str, ...]) -> SectorInfo:
    info = parse_sector_info_lines(tuple(lines))
    metadata = {
        "title": info.title,
        "default_callsign": info.default_callsign,
        "default_airport": info.default_airport,
        "center_latitude": _metadata_float(info.center_latitude),
        "center_longitude": _metadata_float(info.center_longitude),
        "nm_per_degree_latitude": _metadata_float(info.nm_per_degree_latitude),
        "nm_per_degree_longitude": _metadata_float(info.nm_per_degree_longitude),
        "magnetic_variation": _metadata_float(info.magnetic_variation),
        "scale_factor": _metadata_float(info.scale_factor),
    }
    for index, line in enumerate(info.raw_lines):
        metadata[f"info_line_{index}"] = line

    with sqlite3.connect(database_path) as connection:
        connection.execute("DELETE FROM metadata WHERE key LIKE 'info_line_%'")
        connection.executemany(
            """
            INSERT INTO metadata (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            sorted(metadata.items()),
        )

    return info


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        DROP TABLE IF EXISTS metadata;
        DROP TABLE IF EXISTS colors;
        DROP TABLE IF EXISTS points;
        DROP TABLE IF EXISTS lines;
        DROP TABLE IF EXISTS regions;
        DROP TABLE IF EXISTS region_points;
        DROP TABLE IF EXISTS labels;

        CREATE TABLE metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE colors (
            name TEXT PRIMARY KEY,
            value INTEGER NOT NULL
        );

        CREATE TABLE points (
            identifier TEXT PRIMARY KEY,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            source TEXT NOT NULL
        );

        CREATE TABLE lines (
            id INTEGER PRIMARY KEY,
            latitude1 REAL NOT NULL,
            longitude1 REAL NOT NULL,
            latitude2 REAL NOT NULL,
            longitude2 REAL NOT NULL,
            source TEXT NOT NULL,
            label TEXT NOT NULL,
            color_name TEXT NOT NULL,
            min_latitude REAL NOT NULL,
            max_latitude REAL NOT NULL,
            min_longitude REAL NOT NULL,
            max_longitude REAL NOT NULL,
            render_key INTEGER NOT NULL
        );

        CREATE TABLE regions (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            color_name TEXT NOT NULL,
            source TEXT NOT NULL,
            min_latitude REAL NOT NULL,
            max_latitude REAL NOT NULL,
            min_longitude REAL NOT NULL,
            max_longitude REAL NOT NULL
        );

        CREATE TABLE region_points (
            region_id INTEGER NOT NULL,
            sequence INTEGER NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            PRIMARY KEY (region_id, sequence)
        );

        CREATE TABLE labels (
            id INTEGER PRIMARY KEY,
            text TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            source TEXT NOT NULL,
            color_name TEXT NOT NULL
        );

        CREATE INDEX idx_lines_bounds ON lines (min_latitude, max_latitude, min_longitude, max_longitude);
        CREATE INDEX idx_regions_bounds ON regions (min_latitude, max_latitude, min_longitude, max_longitude);
        CREATE INDEX idx_region_points_region ON region_points (region_id);
        """
    )


def _write_sector_data(
    connection: sqlite3.Connection,
    sector_data: SectorData,
    database_name: str,
    source_path: Path,
) -> None:
    info = sector_data.info
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "database_name": database_name,
        "source_file": source_path.name,
        "title": info.title,
        "default_callsign": info.default_callsign,
        "default_airport": info.default_airport,
        "center_latitude": _metadata_float(info.center_latitude),
        "center_longitude": _metadata_float(info.center_longitude),
        "nm_per_degree_latitude": _metadata_float(info.nm_per_degree_latitude),
        "nm_per_degree_longitude": _metadata_float(info.nm_per_degree_longitude),
        "magnetic_variation": _metadata_float(info.magnetic_variation),
        "scale_factor": _metadata_float(info.scale_factor),
    }
    for index, line in enumerate(info.raw_lines):
        metadata[f"info_line_{index}"] = line

    connection.executemany(
        "INSERT INTO metadata (key, value) VALUES (?, ?)",
        sorted(metadata.items()),
    )
    connection.executemany(
        "INSERT INTO colors (name, value) VALUES (?, ?)",
        ((color.name, color.value) for color in sector_data.colors.values()),
    )
    connection.executemany(
        "INSERT INTO points (identifier, latitude, longitude, source) VALUES (?, ?, ?, ?)",
        (
            (point.identifier, point.latitude, point.longitude, point.source)
            for point in sector_data.points.values()
        ),
    )
    connection.executemany(
        """
        INSERT INTO lines (
            id, latitude1, longitude1, latitude2, longitude2, source, label, color_name,
            min_latitude, max_latitude, min_longitude, max_longitude, render_key
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                index,
                line.latitude1,
                line.longitude1,
                line.latitude2,
                line.longitude2,
                line.source,
                line.label,
                line.color_name,
                line.min_latitude,
                line.max_latitude,
                line.min_longitude,
                line.max_longitude,
                line.render_key,
            )
            for index, line in enumerate(sector_data.lines, start=1)
        ),
    )
    connection.executemany(
        """
        INSERT INTO regions (
            id, name, color_name, source, min_latitude, max_latitude, min_longitude, max_longitude
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                index,
                region.name,
                region.color_name,
                region.source,
                region.min_latitude,
                region.max_latitude,
                region.min_longitude,
                region.max_longitude,
            )
            for index, region in enumerate(sector_data.regions, start=1)
        ),
    )
    connection.executemany(
        """
        INSERT INTO region_points (region_id, sequence, latitude, longitude)
        VALUES (?, ?, ?, ?)
        """,
        (
            (region_id, sequence, latitude, longitude)
            for region_id, region in enumerate(sector_data.regions, start=1)
            for sequence, (latitude, longitude) in enumerate(region.points)
        ),
    )
    connection.executemany(
        """
        INSERT INTO labels (id, text, latitude, longitude, source, color_name)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            (
                index,
                label.text,
                label.latitude,
                label.longitude,
                label.source,
                label.color_name,
            )
            for index, label in enumerate(sector_data.labels, start=1)
        ),
    )


def _read_metadata(connection: sqlite3.Connection) -> dict[str, str]:
    return {
        row["key"]: row["value"]
        for row in connection.execute("SELECT key, value FROM metadata")
    }


def _sector_info_from_metadata(metadata: dict[str, str]) -> SectorInfo:
    raw_lines: list[str] = []
    index = 0
    while f"info_line_{index}" in metadata:
        raw_lines.append(metadata[f"info_line_{index}"])
        index += 1

    return SectorInfo(
        raw_lines=tuple(raw_lines),
        title=metadata.get("title", ""),
        default_callsign=metadata.get("default_callsign", ""),
        default_airport=metadata.get("default_airport", ""),
        center_latitude=_metadata_to_float(metadata.get("center_latitude", "")),
        center_longitude=_metadata_to_float(metadata.get("center_longitude", "")),
        nm_per_degree_latitude=_metadata_to_float(metadata.get("nm_per_degree_latitude", "")),
        nm_per_degree_longitude=_metadata_to_float(metadata.get("nm_per_degree_longitude", "")),
        magnetic_variation=_metadata_to_float(metadata.get("magnetic_variation", "")),
        scale_factor=_metadata_to_float(metadata.get("scale_factor", "")),
    )


def _metadata_float(value: float | None) -> str:
    return "" if value is None else repr(value)


def _metadata_to_float(value: str) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None
