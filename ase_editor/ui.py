from __future__ import annotations

from copy import deepcopy
import hashlib
import os
from pathlib import Path
import math
import re
import sys

from PySide6.QtCore import QLineF, QPoint, QPointF, QRegularExpression, QSettings, QSize, Qt, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QIcon,
    QKeySequence,
    QPainter,
    QPen,
    QPolygonF,
    QPixmap,
    QRegularExpressionValidator,
    QShortcut,
    QTransform,
    QFontDatabase,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .exporter import write_scenario_file
from .models import Aircraft, FlightPlan, Scenario
from .parser import parse_scenario_file
from .sector import (
    SectorColor,
    SectorInfo,
    SectorRegion,
    SectorLine,
    SectorPoint,
    SectorTextLabel,
    parse_sector_info_lines,
    resolve_route_tokens,
)
from .sector_database import load_sector_database, save_sector_info
from .theme import (
    ThemePreset,
    UK_2026_09_INDONESIA_THEME,
    VACCC_INDONESIA_PRESET_NAME,
    preset_from_sector_colors,
)


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_SCENARIO = ROOT / "WIHH_example.txt"
SECTOR_DATABASES = {"Indonesia": ROOT / "data" / "sector" / "indonesia.sqlite3"}
ASSET_DIR = ROOT / "asset"
RANGE_PRESETS_NM = (0.1, 0.5, 1, 2, 5, 10)
METERS_PER_NM = 1852.0
SETTINGS_ORGANIZATION = "ASEEditor"
SETTINGS_APPLICATION = "EuroScopeScenarioStudio"
SETTINGS_PATH_ENV = "ASE_EDITOR_SETTINGS_PATH"
DIAGRAM_SOURCES = ("SID", "STAR", "GEO")
MOVEMENT_SURFACE_COLORS = {
    "COLOR_APP",
    "COLOR_Taxiway",
}
MOVEMENT_SURFACE_SOURCES = {"SID", "STAR"}
MOVEMENT_SURFACE_LABEL_TOKENS = ("TAXIWAY",)
MOVEMENT_SURFACE_EXCLUDED_LABEL_TOKENS = ("APRON", "BORDER", "HARD", "PARKPOS", "STAND")
DEFAULT_AIRCRAFT_LENGTH_METERS = 39.5
DEFAULT_VEHICLE_LENGTH_METERS = 6.0
MIN_AIRCRAFT_ICON_PIXELS = 30.0
MIN_VEHICLE_ICON_PIXELS = 40.0
MAX_TARGET_ICON_PIXELS = 160.0
MAX_VELOCITY_LEADER_PIXELS = 140.0
RADAR_FONT_FILE = ASSET_DIR / "windows_command_prompt.ttf"
RADAR_FONT_FAMILY = "Consolas"
RADAR_TEXT_ENABLED = False
FIX_LABELS_ENABLED = True
_RADAR_FONT_LOAD_ATTEMPTED = False
RADAR_GLYPHS = {
    "0": ("111", "101", "101", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "010", "010", "111"),
    "2": ("111", "001", "001", "111", "100", "100", "111"),
    "3": ("111", "001", "001", "111", "001", "001", "111"),
    "4": ("101", "101", "101", "111", "001", "001", "001"),
    "5": ("111", "100", "100", "111", "001", "001", "111"),
    "6": ("111", "100", "100", "111", "101", "101", "111"),
    "7": ("111", "001", "001", "010", "010", "010", "010"),
    "8": ("111", "101", "101", "111", "101", "101", "111"),
    "9": ("111", "101", "101", "111", "001", "001", "111"),
    "A": ("010", "101", "101", "111", "101", "101", "101"),
    "B": ("110", "101", "101", "110", "101", "101", "110"),
    "C": ("111", "100", "100", "100", "100", "100", "111"),
    "D": ("110", "101", "101", "101", "101", "101", "110"),
    "E": ("111", "100", "100", "111", "100", "100", "111"),
    "F": ("111", "100", "100", "111", "100", "100", "100"),
    "G": ("111", "100", "100", "101", "101", "101", "111"),
    "H": ("101", "101", "101", "111", "101", "101", "101"),
    "I": ("111", "010", "010", "010", "010", "010", "111"),
    "J": ("001", "001", "001", "001", "101", "101", "111"),
    "K": ("101", "101", "110", "100", "110", "101", "101"),
    "L": ("100", "100", "100", "100", "100", "100", "111"),
    "M": ("101", "111", "111", "101", "101", "101", "101"),
    "N": ("101", "111", "111", "111", "101", "101", "101"),
    "O": ("111", "101", "101", "101", "101", "101", "111"),
    "P": ("111", "101", "101", "111", "100", "100", "100"),
    "Q": ("111", "101", "101", "101", "111", "001", "001"),
    "R": ("111", "101", "101", "111", "110", "101", "101"),
    "S": ("111", "100", "100", "111", "001", "001", "111"),
    "T": ("111", "010", "010", "010", "010", "010", "010"),
    "U": ("101", "101", "101", "101", "101", "101", "111"),
    "V": ("101", "101", "101", "101", "101", "101", "010"),
    "W": ("101", "101", "101", "101", "111", "111", "101"),
    "X": ("101", "101", "101", "010", "101", "101", "101"),
    "Y": ("101", "101", "101", "010", "010", "010", "010"),
    "Z": ("111", "001", "001", "010", "100", "100", "111"),
    "-": ("000", "000", "000", "111", "000", "000", "000"),
}
AIRCRAFT_LENGTH_METERS = {
    "A318": 31.4,
    "A319": 33.8,
    "A320": 37.6,
    "A321": 44.5,
    "A332": 58.8,
    "A333": 63.7,
    "A339": 63.7,
    "A343": 59.4,
    "A346": 75.4,
    "A359": 66.8,
    "A35K": 73.8,
    "A388": 72.7,
    "B737": 33.6,
    "B738": 39.5,
    "B739": 42.1,
    "B744": 70.7,
    "B748": 76.3,
    "B752": 47.3,
    "B763": 54.9,
    "B772": 63.7,
    "B773": 73.9,
    "B77L": 63.7,
    "B77W": 73.9,
    "B788": 56.7,
    "B789": 63.0,
    "B78X": 68.3,
    "C172": 8.3,
    "C208": 12.7,
    "E190": 36.2,
    "E195": 41.5,
}
VEHICLE_LENGTH_METERS = {
    "AMB": 6.5,
    "FIR": 9.0,
    "TUG": 5.0,
    "FOL": 4.8,
    "OPS": 4.8,
    "MNT": 6.0,
    "RSC": 8.5,
    "RWY": 4.8,
}
VEHICLE_ASSETS = {
    "AMB": "Ambulance.png",
    "FIR": "FireTruck.png",
    "TUG": "AircraftTug.png",
    "FOL": "Follow_Me.png",
    "OPS": "GeneralOperation.png",
    "MNT": "Maintenance.png",
    "RSC": "Rescue.png",
    "RWY": "RunwayInspection.png",
}
VIEW_LAYER_DEFAULTS = {
    "Geography": True,
    "Fixes": True,
    "NDBs": True,
    "VORs": True,
    "Airports": True,
    "Low Airways": True,
    "High Airways": True,
    "ARTCC": True,
    "ARTCC High": True,
    "ARTCC Low": True,
    "Holds": True,
    "Thresholds": True,
    "Regions": True,
    "Static Text": True,
}
LINE_SOURCE_LAYERS = {
    "RUNWAY": ("Geography",),
    "SID": ("Geography",),
    "STAR": ("Geography",),
    "GEO": ("",),
    "LOW AIRWAY": ("Low Airways",),
    "HIGH AIRWAY": ("High Airways",),
    "ARTCC": ("ARTCC",),
    "ARTCC HIGH": ("ARTCC High",),
    "ARTCC LOW": ("ARTCC Low",),
    "REGIONS": ("Regions",),
    "LABELS": ("Static Text",),
    "DIAGRAMS": ("Geography",),
}
POINT_SOURCE_LAYERS = {
    "FIXES": "Fixes",
    "NDB": "NDBs",
    "VOR": "VORs",
    "AIRPORT": "Airports",
}
SECTOR_GRID_CELL_DEGREES = 0.25


class _SpatialIndex:
    def __init__(self, cell_size: float = SECTOR_GRID_CELL_DEGREES) -> None:
        self.cell_size = cell_size
        self.cells: dict[tuple[int, int], list[object]] = {}

    @classmethod
    def from_lines(cls, lines: list[SectorLine]) -> _SpatialIndex:
        index = cls()
        for line in lines:
            index.add(
                line,
                line.min_latitude,
                line.max_latitude,
                line.min_longitude,
                line.max_longitude,
            )
        return index

    @classmethod
    def from_regions(cls, regions: list[SectorRegion]) -> _SpatialIndex:
        index = cls()
        for region in regions:
            index.add(
                region,
                region.min_latitude,
                region.max_latitude,
                region.min_longitude,
                region.max_longitude,
            )
        return index

    @classmethod
    def from_points(cls, points: list[SectorPoint]) -> _SpatialIndex:
        index = cls()
        for point in points:
            index.add(point, point.latitude, point.latitude, point.longitude, point.longitude)
        return index

    @classmethod
    def from_labels(cls, labels: list[SectorTextLabel]) -> _SpatialIndex:
        index = cls()
        for label in labels:
            index.add(label, label.latitude, label.latitude, label.longitude, label.longitude)
        return index

    def add(self, item: object, min_lat: float, max_lat: float, min_lon: float, max_lon: float) -> None:
        min_lat_cell, min_lon_cell = self._cell_for(min_lat, min_lon)
        max_lat_cell, max_lon_cell = self._cell_for(max_lat, max_lon)
        for lat_cell in range(min_lat_cell, max_lat_cell + 1):
            for lon_cell in range(min_lon_cell, max_lon_cell + 1):
                self.cells.setdefault((lat_cell, lon_cell), []).append(item)

    def query(self, min_lat: float, max_lat: float, min_lon: float, max_lon: float) -> list[object]:
        min_lat_cell, min_lon_cell = self._cell_for(min_lat, min_lon)
        max_lat_cell, max_lon_cell = self._cell_for(max_lat, max_lon)
        result: list[object] = []
        seen: set[int] = set()
        for lat_cell in range(min_lat_cell, max_lat_cell + 1):
            for lon_cell in range(min_lon_cell, max_lon_cell + 1):
                for item in self.cells.get((lat_cell, lon_cell), []):
                    item_id = id(item)
                    if item_id in seen:
                        continue
                    seen.add(item_id)
                    result.append(item)
        return result

    def _cell_for(self, latitude: float, longitude: float) -> tuple[int, int]:
        return (
            math.floor(latitude / self.cell_size),
            math.floor(longitude / self.cell_size),
        )


def _app_settings() -> QSettings:
    settings_path = os.environ.get(SETTINGS_PATH_ENV)
    if settings_path:
        return QSettings(settings_path, QSettings.Format.IniFormat)
    return QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION)


def _setting_bool(value: object, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _setting_string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if isinstance(value, tuple):
        return [str(item) for item in value if str(item)]
    text = str(value)
    return [text] if text else []


def _format_nm(value: float) -> str:
    return f"{value:g}"


def _sector_color_to_qcolor(color: SectorColor) -> QColor:
    return QColor(color.red, color.green, color.blue)


def _qcolor_to_sector_value(color: QColor) -> int:
    return (color.blue() * 65536) + (color.green() * 256) + color.red()


def _sector_color_hex(color: SectorColor) -> str:
    return _sector_color_to_qcolor(color).name().upper()


def _setting_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _nearest_range_preset(range_nm: float) -> float:
    clamped = max(RANGE_PRESETS_NM[0], min(RANGE_PRESETS_NM[-1], range_nm))
    return min(RANGE_PRESETS_NM, key=lambda preset: abs(preset - clamped))


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("EuroScope Scenario Studio")
    app.setApplicationVersion(__version__)
    app.setStyleSheet(APP_STYLESHEET)
    _load_radar_font()
    window = MainWindow()
    window.resize(1440, 900)
    window.show()
    return app.exec()


def _load_radar_font() -> None:
    global RADAR_FONT_FAMILY, RADAR_TEXT_ENABLED, _RADAR_FONT_LOAD_ATTEMPTED
    if _RADAR_FONT_LOAD_ATTEMPTED:
        return
    _RADAR_FONT_LOAD_ATTEMPTED = True
    if not RADAR_FONT_FILE.exists():
        return
    font_id = QFontDatabase.addApplicationFont(str(RADAR_FONT_FILE))
    if font_id < 0:
        return
    families = QFontDatabase.applicationFontFamilies(font_id)
    if not families:
        return
    RADAR_FONT_FAMILY = families[0]
    RADAR_TEXT_ENABLED = True


class ClickableFrame(QFrame):
    clicked = Signal()
    double_clicked = Signal()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit()
        super().mouseDoubleClickEvent(event)


class StripCategoryHeader(QFrame):
    toggled = Signal(str)

    def __init__(self, title: str, count: int) -> None:
        super().__init__()
        self.title = title
        self.count = count
        self.collapsed = False
        self.setObjectName("StripCategoryHeader")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 5)
        layout.setSpacing(6)
        self.arrow = QLabel()
        self.arrow.setObjectName("StripCategoryArrow")
        self.label = QLabel()
        self.label.setObjectName("StripCategoryText")
        layout.addWidget(self.arrow)
        layout.addWidget(self.label)
        layout.addStretch(1)
        self.set_collapsed(False)

    def set_collapsed(self, collapsed: bool) -> None:
        self.collapsed = collapsed
        self.arrow.setText(">" if collapsed else "v")
        self.label.setText(f"{self.title.upper()}  {self.count}")

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.toggled.emit(self.title)
        super().mousePressEvent(event)


class RadarCanvas(QWidget):
    aircraft_selected = Signal(object)
    aircraft_double_clicked = Signal(object)
    aircraft_moved = Signal(object)
    map_clicked = Signal(float, float)
    cursor_geo_changed = Signal(float, float)
    range_changed = Signal(float)
    diagram_visibility_changed = Signal()
    view_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.scenario = Scenario()
        self.sector_points: dict[str, SectorPoint] = {}
        self.sector_lines: list[SectorLine] = []
        self.sector_regions: list[SectorRegion] = []
        self.sector_labels: list[SectorTextLabel] = []
        self.sector_colors: dict[str, SectorColor] = {}
        self._line_index = _SpatialIndex()
        self._region_index = _SpatialIndex()
        self._point_index = _SpatialIndex()
        self._label_index = _SpatialIndex()
        self._line_pen_cache: dict[tuple[str, str], QPen] = {}
        self._region_brush_cache: dict[str, QColor] = {}
        self._label_pen_cache: dict[str, QColor] = {}
        self.selected: Aircraft | None = None
        self.show_routes = True
        self.show_sector_lines = True
        self.show_fixes = True
        self.view_layers = dict(VIEW_LAYER_DEFAULTS)
        self.hidden_diagram_labels: dict[str, set[str]] = {source: set() for source in DIAGRAM_SOURCES}
        self.range_nm = RANGE_PRESETS_NM[min(2, len(RANGE_PRESETS_NM) - 1)]
        self.vector_minutes = 1
        self.pixels_per_nm = 8.0
        self.center_lat = -6.1
        self.center_lon = 106.8
        self._last_mouse: QPoint | None = None
        self._panning = False
        self._pending_drag_aircraft: Aircraft | None = None
        self._drag_start_pos: QPoint | None = None
        self._dragging_aircraft: Aircraft | None = None
        self.aircraft_placement_mode = False
        self.icons = self._load_icons()

    def set_data(
        self,
        scenario: Scenario,
        sector_points: dict[str, SectorPoint],
        sector_lines: list[SectorLine],
        sector_regions: list[SectorRegion] | None = None,
        sector_labels: list[SectorTextLabel] | None = None,
        sector_colors: dict[str, SectorColor] | None = None,
        selected: Aircraft | None = None,
    ) -> None:
        self.scenario = scenario
        self.sector_points = sector_points
        self.sector_lines = sector_lines
        self.sector_regions = sector_regions or []
        self.sector_labels = sector_labels or []
        self.sector_colors = sector_colors or {}
        self._line_index = _SpatialIndex.from_lines(self.sector_lines)
        self._region_index = _SpatialIndex.from_regions(self.sector_regions)
        self._point_index = _SpatialIndex.from_points(list(self.sector_points.values()))
        self._label_index = _SpatialIndex.from_labels(self.sector_labels)
        self._line_pen_cache.clear()
        self._region_brush_cache.clear()
        self._label_pen_cache.clear()
        self.selected = selected
        self.fit_to_data()

    def set_sector_colors(self, sector_colors: dict[str, SectorColor]) -> None:
        self.sector_colors = sector_colors
        self._line_pen_cache.clear()
        self._region_brush_cache.clear()
        self._label_pen_cache.clear()
        self.update()

    def set_selected(self, aircraft: Aircraft | None) -> None:
        self.selected = aircraft
        self.update()

    def set_aircraft_placement_mode(self, enabled: bool) -> None:
        self.aircraft_placement_mode = enabled
        if enabled:
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.unsetCursor()
        self.update()

    def set_show_routes(self, show_routes: bool) -> None:
        self.show_routes = show_routes
        self.update()

    def set_show_sector_lines(self, show_sector_lines: bool) -> None:
        self.show_sector_lines = show_sector_lines
        self.update()

    def set_show_fixes(self, show_fixes: bool) -> None:
        self.show_fixes = show_fixes
        self.update()

    def set_view_layer_visible(self, layer: str, visible: bool) -> None:
        self.view_layers[layer] = visible
        self.update()

    def set_diagram_label_visible(self, source: str, label: str, visible: bool) -> None:
        hidden = self.hidden_diagram_labels.setdefault(source, set())
        if visible:
            hidden.discard(label)
        else:
            hidden.add(label)
        self.diagram_visibility_changed.emit()
        self.update()

    def set_diagram_source_visible(self, source: str, labels: list[str], visible: bool) -> None:
        hidden = self.hidden_diagram_labels.setdefault(source, set())
        if visible:
            hidden.difference_update(labels)
        else:
            hidden.update(labels)
        self.diagram_visibility_changed.emit()
        self.update()

    def set_range_nm(self, range_nm: float) -> None:
        self.range_nm = _nearest_range_preset(range_nm)
        self._sync_scale_to_range()
        self.range_changed.emit(self.range_nm)
        self.view_changed.emit()
        self.update()

    def set_vector_minutes(self, minutes: int) -> None:
        self.vector_minutes = minutes
        self.update()

    def fit_to_data(self) -> None:
        points = self.scenario.all_geo_points()
        if self.selected:
            points.extend(
                (point.latitude, point.longitude)
                for point in resolve_route_tokens(self.selected.route_tokens, self.sector_points)
            )
        if points:
            self.center_lat = (min(p[0] for p in points) + max(p[0] for p in points)) / 2.0
            self.center_lon = (min(p[1] for p in points) + max(p[1] for p in points)) / 2.0
            max_distance = 5.0
            for latitude, longitude in points:
                x_nm, y_nm = self._geo_to_nm(latitude, longitude)
                max_distance = max(max_distance, math.hypot(x_nm, y_nm))
            for preset in RANGE_PRESETS_NM:
                if max_distance <= preset * 0.82:
                    self.range_nm = preset
                    break
            else:
                self.range_nm = RANGE_PRESETS_NM[-1]
        self._sync_scale_to_range()
        self.range_changed.emit(self.range_nm)
        self.view_changed.emit()
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#010f1f"))
        self._sync_scale_to_range()
        self._draw_scope_background(painter)
        painter.setRenderHint(QPainter.Antialiasing, False)
        self._draw_regions(painter)
        self._draw_fixes(painter)
        painter.setRenderHint(QPainter.Antialiasing, True)
        self._draw_thresholds(painter)
        self._draw_holds(painter)
        self._draw_routes(painter)
        painter.setRenderHint(QPainter.Antialiasing, False)
        self._draw_sector_lines(painter)
        self._draw_sector_labels(painter)
        painter.setRenderHint(QPainter.Antialiasing, True)
        self._draw_targets(painter)
        self._draw_scope_overlay(painter)

    def wheelEvent(self, event) -> None:  # noqa: N802
        index = RANGE_PRESETS_NM.index(self.range_nm)
        if event.angleDelta().y() > 0:
            index = max(0, index - 1)
        else:
            index = min(len(RANGE_PRESETS_NM) - 1, index + 1)
        new_range = RANGE_PRESETS_NM[index]
        if new_range == self.range_nm:
            return

        cursor_position = event.position()
        cursor_lat, cursor_lon = self.screen_to_geo(cursor_position)
        self.range_nm = new_range
        self._sync_scale_to_range()

        x_nm = (cursor_position.x() - self.width() / 2.0) / self.pixels_per_nm
        y_nm = (self.height() / 2.0 - cursor_position.y()) / self.pixels_per_nm
        self.center_lat = cursor_lat - y_nm / 60.0
        cos_lat = max(0.15, math.cos(math.radians(self.center_lat)))
        self.center_lon = cursor_lon - x_nm / (60.0 * cos_lat)

        self.range_changed.emit(self.range_nm)
        self.view_changed.emit()
        self.update()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self._last_mouse = event.position().toPoint()
        if event.button() == Qt.RightButton:
            self._panning = True
            return
        if event.button() == Qt.LeftButton:
            if self.aircraft_placement_mode:
                lat, lon = self.screen_to_geo(event.position())
                self.map_clicked.emit(lat, lon)
                self._last_mouse = None
                return
            aircraft = self._aircraft_at(event.position())
            self.selected = aircraft
            self.aircraft_selected.emit(aircraft)
            if aircraft:
                self._pending_drag_aircraft = aircraft
                self._drag_start_pos = event.position().toPoint()
            self.update()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        lat, lon = self.screen_to_geo(event.position())
        self.cursor_geo_changed.emit(lat, lon)
        if self._last_mouse is None:
            return

        current_pos = event.position().toPoint()
        delta = current_pos - self._last_mouse
        self._last_mouse = current_pos

        if self._panning:
            cos_lat = max(0.15, math.cos(math.radians(self.center_lat)))
            self.center_lon -= delta.x() / (self.pixels_per_nm * 60.0 * cos_lat)
            self.center_lat += delta.y() / (self.pixels_per_nm * 60.0)
            self.update()
            return

        if self._pending_drag_aircraft is not None and self._drag_start_pos is not None:
            drag_distance = (current_pos - self._drag_start_pos).manhattanLength()
            if drag_distance >= QApplication.startDragDistance():
                self._dragging_aircraft = self._pending_drag_aircraft
                self._pending_drag_aircraft = None

        if self._dragging_aircraft:
            lat, lon, snapped_heading = self._snap_to_movement_surface(lat, lon, self._dragging_aircraft)
            self._dragging_aircraft.latitude = lat
            self._dragging_aircraft.longitude = lon
            if snapped_heading is not None:
                self._dragging_aircraft.heading_raw = snapped_heading
            self.aircraft_moved.emit(self._dragging_aircraft)
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        was_panning = self._panning
        if event.button() == Qt.RightButton:
            self._panning = False
            if was_panning:
                self.view_changed.emit()
        if event.button() == Qt.LeftButton:
            self._pending_drag_aircraft = None
            self._drag_start_pos = None
            self._dragging_aircraft = None
        self._last_mouse = None

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            aircraft = self._aircraft_at(event.position())
            if aircraft:
                self.selected = aircraft
                self.aircraft_selected.emit(aircraft)
                self.aircraft_double_clicked.emit(aircraft)
                self.update()
            return

        if event.button() == Qt.RightButton:
            lat, lon = self.screen_to_geo(event.position())
            self.center_lat = lat
            self.center_lon = lon
            self.view_changed.emit()
            self.update()

    def geo_to_screen(self, latitude: float, longitude: float) -> QPointF:
        x_nm, y_nm = self._geo_to_nm(latitude, longitude)
        return QPointF(
            self.width() / 2.0 + x_nm * self.pixels_per_nm,
            self.height() / 2.0 - y_nm * self.pixels_per_nm,
        )

    def screen_to_geo(self, point: QPointF) -> tuple[float, float]:
        x_nm = (point.x() - self.width() / 2.0) / self.pixels_per_nm
        y_nm = (self.height() / 2.0 - point.y()) / self.pixels_per_nm
        latitude = self.center_lat + y_nm / 60.0
        cos_lat = max(0.15, math.cos(math.radians(self.center_lat)))
        longitude = self.center_lon + x_nm / (60.0 * cos_lat)
        return latitude, longitude

    def _geo_to_nm(self, latitude: float, longitude: float) -> tuple[float, float]:
        cos_lat = max(0.15, math.cos(math.radians(self.center_lat)))
        return (
            (longitude - self.center_lon) * 60.0 * cos_lat,
            (latitude - self.center_lat) * 60.0,
        )

    def _sync_scale_to_range(self) -> None:
        self.pixels_per_nm = max(2.5, min(self.width(), self.height()) * 0.88 / (self.range_nm * 2.0))

    def _draw_scope_background(self, painter: QPainter) -> None:
        if RADAR_TEXT_ENABLED:
            painter.setFont(QFont(RADAR_FONT_FAMILY, 8, QFont.Bold))
            painter.setPen(QColor("#4cd7f6"))
            painter.drawText(14, 22, f"SCOPE: WIHH  RANGE {_format_nm(self.range_nm)} NM")
            painter.setPen(QColor("#bcc9cd"))
            painter.drawText(14, 38, f"CENTER {self.center_lat:.4f} {self.center_lon:.4f}")

    def _draw_sector_lines(self, painter: QPainter) -> None:
        if not self.show_sector_lines:
            return
        lat_min, lat_max, lon_min, lon_max = self._visible_geo_bounds(1.5)
        batches: dict[tuple[str, str], list[QLineF]] = {}
        batch_samples: dict[tuple[str, str], SectorLine] = {}
        half_width = self.width() / 2.0
        half_height = self.height() / 2.0
        cos_lat = max(0.15, math.cos(math.radians(self.center_lat)))
        x_scale = 60.0 * cos_lat * self.pixels_per_nm
        y_scale = 60.0 * self.pixels_per_nm
        margin = 180.0
        min_x = -margin
        max_x = self.width() + margin
        min_y = -margin
        max_y = self.height() + margin
        for item in self._line_index.query(lat_min, lat_max, lon_min, lon_max):
            if not isinstance(item, SectorLine):
                continue
            line = item
            if not self._line_lod_visible(line):
                continue
            if not self._line_source_visible(line.source):
                continue
            if not self._line_label_visible(line):
                continue
            if not self._line_intersects_bounds(line, lat_min, lat_max, lon_min, lon_max):
                continue
            x1 = half_width + (line.longitude1 - self.center_lon) * x_scale
            y1 = half_height - (line.latitude1 - self.center_lat) * y_scale
            x2 = half_width + (line.longitude2 - self.center_lon) * x_scale
            y2 = half_height - (line.latitude2 - self.center_lat) * y_scale
            if not self._screen_line_intersects_rect(x1, y1, x2, y2, min_x, max_x, min_y, max_y):
                continue
            key = (line.source, line.color_name)
            batches.setdefault(key, []).append(QLineF(x1, y1, x2, y2))
            batch_samples.setdefault(key, line)

        for key, lines in batches.items():
            painter.setPen(self._sector_line_pen(batch_samples[key]))
            painter.drawLines(lines)

    def _draw_regions(self, painter: QPainter) -> None:
        if not self.show_sector_lines or not self.view_layers.get("Regions", True):
            return
        lat_min, lat_max, lon_min, lon_max = self._visible_geo_bounds(0.5)
        painter.setPen(Qt.NoPen)
        for item in self._region_index.query(lat_min, lat_max, lon_min, lon_max):
            if not isinstance(item, SectorRegion):
                continue
            region = item
            if not self._region_intersects_bounds(region, lat_min, lat_max, lon_min, lon_max):
                continue
            points = [
                self.geo_to_screen(latitude, longitude)
                for latitude, longitude in region.points
            ]
            painter.setBrush(self._sector_region_color(region))
            painter.drawPolygon(QPolygonF(points))
        painter.setBrush(Qt.BrushStyle.NoBrush)

    def _draw_sector_labels(self, painter: QPainter) -> None:
        if not RADAR_TEXT_ENABLED or not self.show_sector_lines or not self.view_layers.get("Static Text", True):
            return
        painter.setFont(QFont(RADAR_FONT_FAMILY, 8, QFont.Bold))
        lat_min, lat_max, lon_min, lon_max = self._visible_geo_bounds(1.0)
        for item in self._label_index.query(lat_min, lat_max, lon_min, lon_max):
            if not isinstance(item, SectorTextLabel):
                continue
            label = item
            screen = self.geo_to_screen(label.latitude, label.longitude)
            if not self._point_near_view(screen):
                continue
            painter.setPen(self._sector_label_color(label))
            painter.drawText(screen, label.text[:48])

    def _draw_fixes(self, painter: QPainter) -> None:
        if not self.show_fixes or self.range_nm > 80:
            return
        painter.setFont(QFont(RADAR_FONT_FAMILY, 7))
        count = 0
        lat_min, lat_max, lon_min, lon_max = self._visible_geo_bounds(1.0)
        for item in self._point_index.query(lat_min, lat_max, lon_min, lon_max):
            if not isinstance(item, SectorPoint):
                continue
            point = item
            point_layer = POINT_SOURCE_LAYERS.get(point.source)
            if point_layer and not self.view_layers.get(point_layer, True):
                continue
            screen = self.geo_to_screen(point.latitude, point.longitude)
            if not self._point_near_view(screen):
                continue
            painter.setPen(QPen(QColor(78, 222, 163, 120), 1))
            if point.source == "VOR":
                painter.drawEllipse(screen, 3, 3)
            else:
                points = [
                    QPointF(screen.x(), screen.y() - 4),
                    QPointF(screen.x() + 4, screen.y() + 3),
                    QPointF(screen.x() - 4, screen.y() + 3),
                ]
                painter.drawPolygon(points)
            if FIX_LABELS_ENABLED:
                painter.setPen(QColor(188, 201, 205, 175))
                if RADAR_TEXT_ENABLED:
                    painter.drawText(screen + QPointF(7, -5), point.identifier)
                else:
                    self._draw_radar_glyph_text(
                        painter,
                        point.identifier,
                        screen + QPointF(7, -5),
                        QColor(188, 201, 205, 175),
                    )
            count += 1
            if count > 350:
                break

    def _draw_thresholds(self, painter: QPainter) -> None:
        if not self.view_layers.get("Thresholds", True):
            return
        painter.setFont(QFont(RADAR_FONT_FAMILY, 8, QFont.Bold))
        for threshold in self.scenario.thresholds:
            start = self.geo_to_screen(threshold.latitude1, threshold.longitude1)
            end = self.geo_to_screen(threshold.latitude2, threshold.longitude2)
            painter.setPen(QPen(QColor("#4cd7f6"), 2))
            painter.drawLine(start, end)
            if RADAR_TEXT_ENABLED:
                painter.drawText(end + QPointF(5, -5), threshold.name)

    def _draw_holds(self, painter: QPainter) -> None:
        if not self.view_layers.get("Holds", True):
            return
        painter.setFont(QFont(RADAR_FONT_FAMILY, 8, QFont.Bold))
        painter.setPen(QPen(QColor("#ffb95f"), 1, Qt.DashLine))
        for hold in self.scenario.holds:
            point = self.sector_points.get(hold.fix)
            if not point:
                continue
            screen = self.geo_to_screen(point.latitude, point.longitude)
            if not self._point_near_view(screen):
                continue
            painter.drawEllipse(screen, 8, 8)
            if RADAR_TEXT_ENABLED:
                painter.drawText(screen + QPointF(10, -8), f"HOLD {hold.fix}")

    def _draw_routes(self, painter: QPainter) -> None:
        if not self.show_routes or not self.selected:
            return
        points = resolve_route_tokens(self.selected.route_tokens, self.sector_points)
        if not points:
            return

        painter.setFont(QFont(RADAR_FONT_FAMILY, 8, QFont.Bold))
        painter.setPen(QPen(QColor("#4edea3"), 1, Qt.DashLine))
        previous = self.geo_to_screen(self.selected.latitude, self.selected.longitude)
        for point in points:
            current = self.geo_to_screen(point.latitude, point.longitude)
            painter.drawLine(previous, current)
            painter.drawEllipse(current, 3, 3)
            if RADAR_TEXT_ENABLED:
                painter.drawText(current + QPointF(6, -6), point.identifier)
            previous = current

    def _draw_targets(self, painter: QPainter) -> None:
        for aircraft in self.scenario.aircraft:
            point = self.geo_to_screen(aircraft.latitude, aircraft.longitude)
            if not self._point_near_view(point):
                continue
            selected = aircraft is self.selected
            self._draw_target_icon(painter, aircraft, point, selected)
            self._draw_tag(painter, aircraft, point, selected)

    def _draw_velocity_leader(self, painter: QPainter, aircraft: Aircraft, point: QPointF, selected: bool) -> None:
        speed = aircraft.ground_speed or _int_text(aircraft.flight_plan.cruise_speed)
        distance_pixels = speed * self.vector_minutes / 60.0 * self.pixels_per_nm
        distance_pixels = min(MAX_VELOCITY_LEADER_PIXELS, distance_pixels)
        heading_rad = math.radians(aircraft.heading_degrees - 90)
        end = QPointF(
            point.x() + math.cos(heading_rad) * distance_pixels,
            point.y() + math.sin(heading_rad) * distance_pixels,
        )
        painter.setPen(QPen(QColor("#4cd7f6") if selected else QColor(100, 116, 139, 160), 2 if selected else 1))
        painter.drawLine(point, end)

    def _draw_target_icon(self, painter: QPainter, aircraft: Aircraft, point: QPointF, selected: bool) -> None:
        pixmap = self._icon_for_aircraft(aircraft)
        if pixmap and not pixmap.isNull():
            size = self._target_icon_size(aircraft, pixmap)
            scaled = pixmap.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            rotated = scaled.transformed(QTransform().rotate(aircraft.heading_degrees), Qt.SmoothTransformation)
            painter.drawPixmap(
                int(point.x() - rotated.width() / 2),
                int(point.y() - rotated.height() / 2),
                rotated,
            )
        else:
            radius = max(2, int(round(self._target_icon_length_pixels(aircraft) / 2.0)))
            painter.setPen(QPen(QColor("#4cd7f6") if selected else QColor("#64748b"), 2))
            painter.drawEllipse(point, radius, radius)

    def _draw_radar_glyph_text(self, painter: QPainter, text: str, origin: QPointF, color: QColor) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        x = int(round(origin.x()))
        y = int(round(origin.y()))
        pixel = 1
        gap = 1
        for character in text.upper()[:8]:
            glyph = RADAR_GLYPHS.get(character)
            if glyph is None:
                x += 3 * (pixel + gap)
                continue
            for row_index, row in enumerate(glyph):
                for column_index, value in enumerate(row):
                    if value == "1":
                        painter.drawRect(
                            x + column_index * (pixel + gap),
                            y + row_index * (pixel + gap),
                            pixel,
                            pixel,
                        )
            x += (len(glyph[0]) + 1) * (pixel + gap)
        painter.setBrush(Qt.BrushStyle.NoBrush)

    def _draw_tag(self, painter: QPainter, aircraft: Aircraft, point: QPointF, selected: bool) -> None:
        if not RADAR_TEXT_ENABLED:
            return
        icon_radius = self._target_icon_length_pixels(aircraft) / 2.0
        block_origin = point + QPointF(max(38.0, icon_radius + 14.0), -28 if selected else -22)
        painter.setFont(QFont(RADAR_FONT_FAMILY, 9 if selected else 8, QFont.Bold))
        if selected:
            width = 236
            height = 58
            painter.setPen(QPen(QColor("#4cd7f6"), 1))
            painter.setBrush(QColor(1, 15, 31, 226))
            painter.drawRect(int(block_origin.x() - 4), int(block_origin.y() - 13), width, height)
            painter.setPen(QColor("#4cd7f6"))
            rows = [
                f"{aircraft.callsign} {aircraft.flight_plan.aircraft_type or 'TYPE'}",
                f"AFL FL{aircraft.actual_flight_level:03d}  CFL {aircraft.cleared_level_text}",
                f"{aircraft.flight_plan.departure or '----'} -> {aircraft.flight_plan.arrival or '----'}",
            ]
            for index, row in enumerate(rows):
                painter.drawText(block_origin + QPointF(0, index * 14), row[:36])
        else:
            painter.setPen(QColor("#d4e4fa") if aircraft.target_kind == "aircraft" else QColor("#4edea3"))
            painter.drawText(block_origin, f"{aircraft.callsign}")
            painter.setPen(QColor("#869397"))
            painter.drawText(block_origin + QPointF(0, 13), f"FL{aircraft.actual_flight_level:03d} {aircraft.display_speed or '---'}K")

    def _draw_scope_overlay(self, painter: QPainter) -> None:
        if not RADAR_TEXT_ENABLED:
            return
        painter.setFont(QFont(RADAR_FONT_FAMILY, 8, QFont.Bold))
        painter.setPen(QColor("#bcc9cd"))
        painter.drawText(12, self.height() - 18, f"ACTIVE TARGETS {len(self.scenario.aircraft):02d}  VECTOR {self.vector_minutes}M")

    def _grid_step_nm(self) -> float:
        if self.range_nm <= 0.2:
            return 0.02
        if self.range_nm <= 0.5:
            return 0.05
        if self.range_nm <= 1:
            return 0.1
        if self.range_nm <= 2:
            return 0.2
        if self.range_nm <= 5:
            return 0.5
        if self.range_nm <= 10:
            return 1
        if self.range_nm <= 20:
            return 2
        if self.range_nm <= 40:
            return 5
        return 10

    def _screen_line_intersects_rect(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        min_x: float,
        max_x: float,
        min_y: float,
        max_y: float,
    ) -> bool:
        if (min_x <= x1 <= max_x and min_y <= y1 <= max_y) or (
            min_x <= x2 <= max_x and min_y <= y2 <= max_y
        ):
            return True
        if max(x1, x2) < min_x or min(x1, x2) > max_x or max(y1, y2) < min_y or min(y1, y2) > max_y:
            return False
        line = QLineF(x1, y1, x2, y2)
        bounded = QLineF.IntersectionType.BoundedIntersection
        return (
            line.intersects(QLineF(min_x, min_y, max_x, min_y))[0] == bounded
            or line.intersects(QLineF(max_x, min_y, max_x, max_y))[0] == bounded
            or line.intersects(QLineF(max_x, max_y, min_x, max_y))[0] == bounded
            or line.intersects(QLineF(min_x, max_y, min_x, min_y))[0] == bounded
        )

    def _aircraft_at(self, point: QPointF) -> Aircraft | None:
        nearest: tuple[float, Aircraft] | None = None
        for aircraft in self.scenario.aircraft:
            screen = self.geo_to_screen(aircraft.latitude, aircraft.longitude)
            distance = math.hypot(screen.x() - point.x(), screen.y() - point.y())
            hit_radius = max(8.0, self._target_icon_length_pixels(aircraft) / 2.0)
            if distance <= hit_radius and (nearest is None or distance < nearest[0]):
                nearest = (distance, aircraft)
        return nearest[1] if nearest else None

    def _snap_to_movement_surface(
        self,
        latitude: float,
        longitude: float,
        aircraft: Aircraft | None = None,
    ) -> tuple[float, float, int | None]:
        tolerance_nm = max(0.015, min(0.08, 10.0 / max(self.pixels_per_nm, 1.0)))
        cos_lat = max(0.15, math.cos(math.radians(latitude)))
        lat_margin = tolerance_nm / 60.0
        lon_margin = tolerance_nm / (60.0 * cos_lat)
        candidates = self._line_index.query(
            latitude - lat_margin,
            latitude + lat_margin,
            longitude - lon_margin,
            longitude + lon_margin,
        )
        best: tuple[float, float, float, SectorLine] | None = None
        for item in candidates:
            if not isinstance(item, SectorLine) or not self._is_movement_surface_line(item):
                continue
            snapped = self._project_geo_to_line(latitude, longitude, item, cos_lat)
            if snapped is None:
                continue
            distance_nm, snapped_lat, snapped_lon = snapped
            if distance_nm <= tolerance_nm and (best is None or distance_nm < best[0]):
                best = (distance_nm, snapped_lat, snapped_lon, item)
        if best is None:
            return latitude, longitude, None
        heading = self._snap_heading_for_line(best[3], best[1], best[2], aircraft)
        return best[1], best[2], heading

    def _project_geo_to_line(
        self,
        latitude: float,
        longitude: float,
        line: SectorLine,
        cos_lat: float,
    ) -> tuple[float, float, float] | None:
        x1 = (line.longitude1 - longitude) * 60.0 * cos_lat
        y1 = (line.latitude1 - latitude) * 60.0
        x2 = (line.longitude2 - longitude) * 60.0 * cos_lat
        y2 = (line.latitude2 - latitude) * 60.0
        dx = x2 - x1
        dy = y2 - y1
        length_sq = dx * dx + dy * dy
        if length_sq <= 1e-9:
            return None
        t = max(0.0, min(1.0, -(x1 * dx + y1 * dy) / length_sq))
        snapped_x = x1 + t * dx
        snapped_y = y1 + t * dy
        distance_nm = math.hypot(snapped_x, snapped_y)
        snapped_lat = latitude + snapped_y / 60.0
        snapped_lon = longitude + snapped_x / (60.0 * cos_lat)
        return distance_nm, snapped_lat, snapped_lon

    def _snap_heading_for_line(
        self,
        line: SectorLine,
        snapped_latitude: float,
        snapped_longitude: float,
        aircraft: Aircraft | None,
    ) -> int:
        heading = self._bearing_degrees(line.latitude1, line.longitude1, line.latitude2, line.longitude2)
        reverse_heading = (heading + 180.0) % 360.0
        if aircraft is not None:
            movement_heading = self._bearing_degrees(
                aircraft.latitude,
                aircraft.longitude,
                snapped_latitude,
                snapped_longitude,
            )
            if self._heading_delta(reverse_heading, movement_heading) < self._heading_delta(heading, movement_heading):
                heading = reverse_heading
        rounded = int(round(heading)) % 360
        return 360 if rounded == 0 else rounded

    def _bearing_degrees(self, latitude1: float, longitude1: float, latitude2: float, longitude2: float) -> float:
        mean_latitude = (latitude1 + latitude2) / 2.0
        cos_lat = max(0.15, math.cos(math.radians(mean_latitude)))
        east_nm = (longitude2 - longitude1) * 60.0 * cos_lat
        north_nm = (latitude2 - latitude1) * 60.0
        if abs(east_nm) <= 1e-9 and abs(north_nm) <= 1e-9:
            return 0.0
        return (math.degrees(math.atan2(east_nm, north_nm)) + 360.0) % 360.0

    def _heading_delta(self, heading1: float, heading2: float) -> float:
        return abs((heading1 - heading2 + 180.0) % 360.0 - 180.0)

    def _is_movement_surface_line(self, line: SectorLine) -> bool:
        if line.color_name in MOVEMENT_SURFACE_COLORS:
            return True
        if line.source in MOVEMENT_SURFACE_SOURCES:
            return True
        label = line.label.upper()
        if any(token in label for token in MOVEMENT_SURFACE_EXCLUDED_LABEL_TOKENS):
            return False
        return any(token in label for token in MOVEMENT_SURFACE_LABEL_TOKENS)

    def _point_near_view(self, point: QPointF) -> bool:
        margin = 180
        return -margin <= point.x() <= self.width() + margin and -margin <= point.y() <= self.height() + margin

    def _line_source_visible(self, source: str) -> bool:
        layers = LINE_SOURCE_LAYERS.get(source)
        if not layers:
            return True
        return any(self.view_layers.get(layer, True) for layer in layers)

    def _line_label_visible(self, line: SectorLine) -> bool:
        if line.source not in self.hidden_diagram_labels or not line.label:
            return True
        return line.label not in self.hidden_diagram_labels[line.source]

    def _line_lod_visible(self, line: SectorLine) -> bool:
        return True

    def _visible_geo_bounds(self, margin_nm: float = 0.0) -> tuple[float, float, float, float]:
        margin_lat = margin_nm / 60.0
        cos_lat = max(0.15, math.cos(math.radians(self.center_lat)))
        margin_lon = margin_nm / (60.0 * cos_lat)
        half_lat = self.range_nm / 60.0 + margin_lat
        half_lon = self.range_nm / (60.0 * cos_lat) + margin_lon
        return (
            self.center_lat - half_lat,
            self.center_lat + half_lat,
            self.center_lon - half_lon,
            self.center_lon + half_lon,
        )

    def _line_intersects_bounds(
        self,
        line: SectorLine,
        lat_min: float,
        lat_max: float,
        lon_min: float,
        lon_max: float,
    ) -> bool:
        return (
            line.max_latitude >= lat_min
            and line.min_latitude <= lat_max
            and line.max_longitude >= lon_min
            and line.min_longitude <= lon_max
        )

    def _region_intersects_bounds(
        self,
        region: SectorRegion,
        lat_min: float,
        lat_max: float,
        lon_min: float,
        lon_max: float,
    ) -> bool:
        return (
            region.max_latitude >= lat_min
            and region.min_latitude <= lat_max
            and region.max_longitude >= lon_min
            and region.min_longitude <= lon_max
        )

    def _sector_color(self, color_name: str, fallback: QColor, alpha: int) -> QColor:
        sector_color = self.sector_colors.get(color_name)
        if not sector_color:
            color = QColor(fallback)
        else:
            color = QColor(sector_color.red, sector_color.green, sector_color.blue)
        color.setAlpha(alpha)
        return color

    def _sector_line_pen(self, line: SectorLine) -> QPen:
        key = (line.source, line.color_name)
        pen = self._line_pen_cache.get(key)
        if pen is None:
            pen = QPen(self._sector_line_color(line), 1)
            self._line_pen_cache[key] = pen
        return pen

    def _sector_line_color(self, line: SectorLine) -> QColor:
        fallbacks = {
            "RUNWAY": QColor(212, 228, 250),
            "SID": QColor(6, 182, 212),
            "STAR": QColor(255, 185, 95),
            "HIGH AIRWAY": QColor(6, 182, 212),
            "LOW AIRWAY": QColor(6, 182, 212),
            "ARTCC": QColor(78, 222, 163),
            "ARTCC HIGH": QColor(78, 222, 163),
            "ARTCC LOW": QColor(78, 222, 163),
            "GEO": QColor(100, 116, 139),
            "DIAGRAMS": QColor(255, 185, 95),
        }
        alphas = {
            "RUNWAY": 230,
            "SID": 130,
            "STAR": 135,
            "HIGH AIRWAY": 120,
            "LOW AIRWAY": 105,
            "ARTCC": 115,
            "ARTCC HIGH": 115,
            "ARTCC LOW": 100,
            "GEO": 155,
            "DIAGRAMS": 130,
        }
        return self._sector_color(
            line.color_name,
            fallbacks.get(line.source, QColor("#475569")),
            alphas.get(line.source, 65),
        )

    def _sector_region_color(self, region: SectorRegion) -> QColor:
        color = self._region_brush_cache.get(region.color_name)
        if color is None:
            color = self._sector_color(region.color_name, QColor(148, 163, 184), 20)
            self._region_brush_cache[region.color_name] = color
        return color

    def _sector_label_color(self, label: SectorTextLabel) -> QColor:
        color = self._label_pen_cache.get(label.color_name)
        if color is None:
            color = self._sector_color(label.color_name, QColor(188, 201, 205), 230)
            self._label_pen_cache[label.color_name] = color
        return color

    def _load_icons(self) -> dict[str, QPixmap]:
        icons: dict[str, QPixmap] = {}
        for key, filename in {"AIRCRAFT": "aircraft-icon.png", **VEHICLE_ASSETS}.items():
            path = ASSET_DIR / filename
            if path.exists():
                icons[key] = QPixmap(str(path))
        return icons

    def _icon_for_aircraft(self, aircraft: Aircraft) -> QPixmap | None:
        if aircraft.target_kind == "vehicle" or aircraft.symbol == "S":
            prefix = aircraft.callsign[:3].upper()
            return self.icons.get(prefix) or self.icons.get(aircraft.flight_plan.aircraft_type[:3].upper())
        return self.icons.get("AIRCRAFT")

    def _target_icon_size(self, aircraft: Aircraft, pixmap: QPixmap) -> QSize:
        length_pixels = self._target_icon_length_pixels(aircraft)
        source_longest_side = max(1, pixmap.width(), pixmap.height())
        scale = length_pixels / source_longest_side
        return QSize(
            max(1, int(round(pixmap.width() * scale))),
            max(1, int(round(pixmap.height() * scale))),
        )

    def _target_icon_length_pixels(self, aircraft: Aircraft) -> float:
        length_meters = self._target_length_meters(aircraft)
        physical_pixels = (length_meters / METERS_PER_NM) * self.pixels_per_nm
        if aircraft.target_kind == "vehicle" or aircraft.symbol == "S":
            minimum = MIN_VEHICLE_ICON_PIXELS
        else:
            minimum = MIN_AIRCRAFT_ICON_PIXELS
        return max(minimum, min(MAX_TARGET_ICON_PIXELS, physical_pixels))

    def _target_length_meters(self, aircraft: Aircraft) -> float:
        if aircraft.target_kind == "vehicle" or aircraft.symbol == "S":
            prefix = aircraft.callsign[:3].upper()
            type_prefix = aircraft.flight_plan.aircraft_type[:3].upper()
            return VEHICLE_LENGTH_METERS.get(prefix) or VEHICLE_LENGTH_METERS.get(type_prefix) or DEFAULT_VEHICLE_LENGTH_METERS

        type_code = re.sub(r"[^A-Z0-9]", "", aircraft.flight_plan.aircraft_type.upper())
        if type_code in AIRCRAFT_LENGTH_METERS:
            return AIRCRAFT_LENGTH_METERS[type_code]
        for known_type, length_meters in sorted(AIRCRAFT_LENGTH_METERS.items(), key=lambda item: len(item[0]), reverse=True):
            if type_code.startswith(known_type):
                return length_meters
        if aircraft.wake_category.upper().startswith("H"):
            return 70.0
        if aircraft.wake_category.upper().startswith("L"):
            return 20.0
        return DEFAULT_AIRCRAFT_LENGTH_METERS


class AircraftEditorDialog(QDialog):
    aircraft_saved = Signal(object)

    def __init__(self, aircraft: Aircraft, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.aircraft = aircraft
        self._editor_columns = 0
        self.setWindowTitle("Aircraft")
        self.setModal(False)
        self.setMinimumSize(560, 600)
        self.setStyleSheet(DIALOG_STYLESHEET)
        self._build_widgets()
        self._load_aircraft()
        self.resize(760, 660)

    def _build_widgets(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(10)
        body_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        scroll = QScrollArea()
        scroll.setObjectName("DialogScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(body)

        self.callsign = _dialog_line()
        self.aircraft_type = QComboBox()
        self.aircraft_type.setEditable(True)
        self.aircraft_type.addItems(["A320", "B738", "B772", "B777", "B787", "FIR0", "AMB0"])
        self.squawk = _dialog_line()
        self.squawk.setValidator(QRegularExpressionValidator(QRegularExpression("[0-7]{0,4}")))
        self.mode_c = QCheckBox()
        self.latitude = _dialog_double(-90, 90, 7)
        self.longitude = _dialog_double(-180, 180, 7)
        self.altitude = _dialog_int(-1000, 60000, 100)
        self.ground_speed = _dialog_int(0, 1200, 10)
        self.heading = _dialog_int(1, 360, 1)
        self.climb_rate = _dialog_int(-6000, 6000, 100)

        position = QGroupBox("Position")
        self.position_grid = QGridLayout(position)
        self.position_grid.setHorizontalSpacing(10)
        self.position_grid.setVerticalSpacing(8)
        self.mode_c.setText("Mode C")
        self.position_fields = [
            _dialog_field("Callsign", self.callsign),
            _dialog_field("Aircraft Type", self.aircraft_type),
            _dialog_field("Squawk", self.squawk),
            _dialog_field("Latitude", self.latitude),
            _dialog_field("Longitude", self.longitude),
            _dialog_field("Altitude", self.altitude),
            _dialog_field("Ground Speed", self.ground_speed),
            _dialog_field("Heading", self.heading),
            _dialog_field("Clm/Des Rate", self.climb_rate),
        ]
        body_layout.addWidget(position)

        self.departure = _dialog_line()
        self.arrival = _dialog_line()
        self.flight_type = QComboBox()
        self.flight_type.addItems(["IFR", "VFR", "SVFR"])
        self.engine_type = QComboBox()
        self.engine_type.addItems(["Jet", "Turboprop", "Piston"])
        self.route_text = QPlainTextEdit()
        self.route_text.setMinimumHeight(58)
        self.departure_time = _dialog_line("0000")
        self.enroute_time = _dialog_line("0000")
        self.cruise_altitude = _dialog_line()
        self.cruise_speed = _dialog_line()
        self.remarks = QPlainTextEdit()
        self.remarks.setMinimumHeight(46)
        flightplandb = QPushButton("FlightPlanDB")
        flightplandb.setMinimumHeight(30)
        flightplandb.clicked.connect(self._show_flightplandb_placeholder)

        flight_plan = QGroupBox("Flight Plan")
        self.fp_grid = QGridLayout(flight_plan)
        self.fp_grid.setHorizontalSpacing(10)
        self.fp_grid.setVerticalSpacing(8)
        self.flight_plan_fields = [
            _dialog_field("Departure ICAO", self.departure),
            _dialog_field("Arrival ICAO", self.arrival),
            _dialog_field("Flight Type", self.flight_type),
            _dialog_field("Engine Type", self.engine_type),
            _dialog_field("Departure Time", self.departure_time),
            _dialog_field("Enroute Time", self.enroute_time),
            _dialog_field("Cruise Altitude", self.cruise_altitude),
            _dialog_field("Cruise Airspeed", self.cruise_speed),
            flightplandb,
        ]
        self.route_field = _dialog_field("Route", self.route_text)
        self.remarks_field = _dialog_field("Remarks", self.remarks)
        body_layout.addWidget(flight_plan)

        self.delay_min = _dialog_int(0, 999, 1)
        self.delay_max = _dialog_int(0, 999, 1)
        self.descent_wpt = _dialog_line()
        self.descent_altitude = _dialog_int(0, 60000, 100)
        self.start_delay = _dialog_int(0, 999, 1)

        euroscope = QGroupBox("Euroscope Only")
        self.es_grid = QGridLayout(euroscope)
        self.es_grid.setHorizontalSpacing(10)
        self.es_grid.setVerticalSpacing(8)
        self.euroscope_fields = [
            _dialog_field("Min Delay", self.delay_min),
            _dialog_field("Max Delay", self.delay_max),
            _dialog_field("Start Delay", self.start_delay),
            _dialog_field("Descent Wpt", self.descent_wpt),
            _dialog_field("Descent Alt", self.descent_altitude),
        ]
        body_layout.addWidget(euroscope)
        body_layout.addStretch(1)
        layout.addWidget(scroll, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        save = QPushButton("Save")
        save.setObjectName("DialogPrimaryButton")
        close = QPushButton("Close")
        save.clicked.connect(self._save)
        close.clicked.connect(self.close)
        footer.addWidget(save)
        footer.addWidget(close)
        layout.addLayout(footer)
        self._layout_editor_fields()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._layout_editor_fields()

    def _layout_editor_fields(self) -> None:
        columns = 3 if self.width() >= 740 else 2 if self.width() >= 520 else 1
        if columns == self._editor_columns:
            return
        self._editor_columns = columns
        next_row = self._populate_grid(self.position_grid, self.position_fields, columns)
        self.position_grid.addWidget(self.mode_c, next_row, 0, 1, columns)
        next_row = self._populate_grid(self.fp_grid, self.flight_plan_fields, columns)
        self.fp_grid.addWidget(self.route_field, next_row, 0, 1, columns)
        self.fp_grid.addWidget(self.remarks_field, next_row + 1, 0, 1, columns)
        self._populate_grid(self.es_grid, self.euroscope_fields, columns)

    def _populate_grid(self, grid: QGridLayout, widgets: list[QWidget], columns: int) -> int:
        while grid.count():
            item = grid.takeAt(0)
            widget = item.widget()
            if widget:
                grid.removeWidget(widget)
        for column in range(3):
            grid.setColumnStretch(column, 1 if column < columns else 0)
        for index, widget in enumerate(widgets):
            row = index // columns
            column = index % columns
            grid.addWidget(widget, row, column)
        return math.ceil(len(widgets) / columns)

    def _load_aircraft(self) -> None:
        aircraft = self.aircraft
        self.callsign.setText(aircraft.callsign)
        self.aircraft_type.setCurrentText(aircraft.flight_plan.aircraft_type)
        self.squawk.setText(aircraft.squawk)
        self.mode_c.setChecked(aircraft.mode_c == "1")
        self.latitude.setValue(aircraft.latitude)
        self.longitude.setValue(aircraft.longitude)
        self.altitude.setValue(aircraft.altitude)
        self.ground_speed.setValue(aircraft.ground_speed)
        self.heading.setValue(max(1, min(360, int(round(aircraft.heading_degrees)) or 1)))
        self.departure.setText(aircraft.flight_plan.departure)
        self.arrival.setText(aircraft.flight_plan.arrival)
        self.flight_type.setCurrentText(_flight_type_label(aircraft.flight_plan.flight_type))
        self.route_text.setPlainText(aircraft.flight_plan.route_text)
        self.departure_time.setText(aircraft.flight_plan.departure_time or "0000")
        self.enroute_time.setText(aircraft.flight_plan.enroute_time or "0000")
        self.cruise_altitude.setText(aircraft.flight_plan.cruise_altitude)
        self.cruise_speed.setText(aircraft.flight_plan.cruise_speed)
        self.remarks.setPlainText(aircraft.flight_plan.remarks)
        self.delay_min.setValue(aircraft.delay_min or 0)
        self.delay_max.setValue(aircraft.delay_max or 0)

    def _save(self) -> None:
        aircraft = self.aircraft
        aircraft.callsign = self.callsign.text().strip().upper()
        aircraft.flight_plan.callsign = aircraft.callsign
        aircraft.flight_plan.aircraft_type = self.aircraft_type.currentText().strip().upper()
        aircraft.squawk = self.squawk.text().strip()
        aircraft.mode_c = "1" if self.mode_c.isChecked() else "0"
        aircraft.latitude = self.latitude.value()
        aircraft.longitude = self.longitude.value()
        aircraft.altitude = self.altitude.value()
        aircraft.ground_speed = self.ground_speed.value()
        aircraft.heading_raw = self.heading.value()
        aircraft.flight_plan.departure = self.departure.text().strip().upper()
        aircraft.flight_plan.arrival = self.arrival.text().strip().upper()
        aircraft.flight_plan.flight_type = self.flight_type.currentText()[:1].upper()
        aircraft.flight_plan.route_text = self.route_text.toPlainText().strip().upper()
        aircraft.flight_plan.departure_time = self.departure_time.text().strip()
        aircraft.flight_plan.enroute_time = self.enroute_time.text().strip()
        aircraft.flight_plan.cruise_altitude = self.cruise_altitude.text().strip()
        aircraft.flight_plan.cruise_speed = self.cruise_speed.text().strip()
        aircraft.flight_plan.remarks = self.remarks.toPlainText().strip()
        aircraft.delay_min = self.delay_min.value()
        aircraft.delay_max = self.delay_max.value()
        self.aircraft_saved.emit(aircraft)
        self.close()

    def _show_flightplandb_placeholder(self) -> None:
        QMessageBox.information(
            self,
            "FlightPlanDB",
            "FlightPlanDB querying is reserved for the next slice.",
        )


class DiagramDialog(QDialog):
    def __init__(self, canvas: RadarCanvas, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.canvas = canvas
        self._syncing = False
        self.lists: dict[str, QListWidget] = {}
        self.show_all_checks: dict[str, QCheckBox] = {}
        self.setWindowTitle("Diagrams")
        self.setMinimumSize(620, 390)
        self.resize(620, 390)
        self.setStyleSheet(DIAGRAM_STYLESHEET)
        self._build_widgets()

    def _build_widgets(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        columns = QHBoxLayout()
        columns.setSpacing(8)
        for source, title, show_all_text in (
            ("SID", "SIDs", "Show All SIDs"),
            ("STAR", "STARs", "Show All STARs"),
            ("GEO", "Geography", "Show All Geography"),
        ):
            column = QVBoxLayout()
            column.setSpacing(4)
            label = QLabel(title)
            label.setObjectName("DiagramColumnTitle")
            column.addWidget(label)

            list_widget = QListWidget()
            list_widget.setObjectName("DiagramList")
            self._populate_list(source, list_widget)
            list_widget.itemChanged.connect(lambda item, source=source: self._item_changed(source, item))
            self.lists[source] = list_widget
            column.addWidget(list_widget, 1)

            show_all = QCheckBox(show_all_text)
            show_all.setChecked(self._all_visible(source))
            show_all.toggled.connect(lambda checked, source=source: self._set_all(source, checked))
            self.show_all_checks[source] = show_all
            column.addWidget(show_all)
            columns.addLayout(column, 1)

        layout.addLayout(columns, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        footer.addWidget(close)
        layout.addLayout(footer)

    def _populate_list(self, source: str, list_widget: QListWidget) -> None:
        labels = self._labels_for_source(source)
        if not labels:
            item = QListWidgetItem("(none loaded)")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            list_widget.addItem(item)
            return

        hidden = self.canvas.hidden_diagram_labels.get(source, set())
        for text in labels:
            item = QListWidgetItem(text)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setData(Qt.ItemDataRole.UserRole, text)
            item.setCheckState(Qt.Unchecked if text in hidden else Qt.Checked)
            list_widget.addItem(item)

    def _labels_for_source(self, source: str) -> list[str]:
        labels = {line.label for line in self.canvas.sector_lines if line.source == source and line.label}
        return sorted(labels)

    def _all_visible(self, source: str) -> bool:
        labels = self._labels_for_source(source)
        hidden = self.canvas.hidden_diagram_labels.get(source, set())
        return bool(labels) and not any(label in hidden for label in labels)

    def _item_changed(self, source: str, item: QListWidgetItem) -> None:
        if self._syncing:
            return
        label = item.data(Qt.ItemDataRole.UserRole)
        if not label:
            return
        visible = item.checkState() == Qt.Checked
        self.canvas.set_diagram_label_visible(source, str(label), visible)
        self._refresh_show_all(source)

    def _set_all(self, source: str, checked: bool) -> None:
        list_widget = self.lists[source]
        labels = self._labels_for_source(source)
        self._syncing = True
        try:
            for row in range(list_widget.count()):
                item = list_widget.item(row)
                if item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                    item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        finally:
            self._syncing = False
        self.canvas.set_diagram_source_visible(source, labels, checked)

    def _refresh_show_all(self, source: str) -> None:
        show_all = self.show_all_checks[source]
        show_all.blockSignals(True)
        show_all.setChecked(self._all_visible(source))
        show_all.blockSignals(False)


class InfoSectorDialog(QDialog):
    info_saved = Signal(tuple)
    FIELD_DEFINITIONS = (
        ("name", "Name of sector", ""),
        ("callsign", "Default callsign", ""),
        ("wx_station", "Default WX station", ""),
        ("center_latitude", "Center latitude", "S002.19.45.342"),
        ("center_longitude", "Center longitude", "E115.18.14.097"),
        ("nm_latitude", "NM per degree latitude", "60"),
        ("nm_longitude", "NM per degree longitude", "ROUND(COS(latitude) * 60)"),
        ("magnetic_variation", "Magnetic variation", "-0"),
        ("scale_factor", "Scaling factor", "1"),
    )

    def __init__(self, info: SectorInfo, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.field_edits: dict[str, QLineEdit] = {}
        self.setWindowTitle("Info Sector")
        self.setMinimumSize(560, 430)
        self.resize(620, 470)
        self._build_widgets(info)

    def _build_widgets(self, info: SectorInfo) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        title = QLabel("[INFO]")
        title.setObjectName("DiagramColumnTitle")
        layout.addWidget(title)

        form = QGridLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)
        latitude_validator = QRegularExpressionValidator(
            QRegularExpression(r"^$|^[NS]\d{2,3}\.\d{2}\.\d{2}(?:\.\d+)?$"),
            self,
        )
        longitude_validator = QRegularExpressionValidator(
            QRegularExpression(r"^$|^[EW]\d{3}\.\d{2}\.\d{2}(?:\.\d+)?$"),
            self,
        )
        number_validator = QRegularExpressionValidator(
            QRegularExpression(r"^$|^-?\d+(?:\.\d+)?$"),
            self,
        )

        for row, (key, label_text, placeholder) in enumerate(self.FIELD_DEFINITIONS):
            label = QLabel(label_text)
            label.setObjectName("DialogFieldLabel")
            edit = _dialog_line()
            edit.setPlaceholderText(placeholder)
            if key == "center_latitude":
                edit.setValidator(latitude_validator)
            elif key == "center_longitude":
                edit.setValidator(longitude_validator)
            elif key in {"nm_latitude", "nm_longitude", "magnetic_variation", "scale_factor"}:
                edit.setValidator(number_validator)
            self.field_edits[key] = edit
            form.addWidget(label, row, 0)
            form.addWidget(edit, row, 1)

        form.setColumnStretch(1, 1)
        layout.addLayout(form, 1)
        self.set_info(info)

        footer = QHBoxLayout()
        footer.addStretch(1)
        save = QPushButton("Save")
        save.setObjectName("DialogPrimaryButton")
        save.clicked.connect(self._save)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        footer.addWidget(save)
        footer.addWidget(close)
        layout.addLayout(footer)

    def set_info(self, info: SectorInfo) -> None:
        lines = list(info.raw_lines)
        for index, (key, _label_text, _placeholder) in enumerate(self.FIELD_DEFINITIONS):
            self.field_edits[key].setText(lines[index] if index < len(lines) else "")

    def _save(self) -> None:
        lines = [self.field_edits[key].text().strip() for key, _label, _placeholder in self.FIELD_DEFINITIONS]
        while lines and not lines[-1]:
            lines.pop()
        self.info_saved.emit(tuple(lines))


class ThemeEditorDialog(QDialog):
    color_changed = Signal(str, int)

    def __init__(self, colors: dict[str, SectorColor], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.colors = dict(colors)
        self._syncing = False
        self._swatches: dict[str, QPushButton] = {}
        self._value_items: dict[str, QTableWidgetItem] = {}
        self._hex_items: dict[str, QTableWidgetItem] = {}
        self.setWindowTitle("Theme Colors")
        self.setMinimumSize(640, 500)
        self.resize(720, 560)
        self._build_widgets()

    def _build_widgets(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        self.table = QTableWidget(len(self.colors), 4)
        self.table.setHorizontalHeaderLabels(["Name", "Value", "RGB", "Color"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        for row, name in enumerate(sorted(self.colors, key=str.casefold)):
            color = self.colors[name]
            name_item = QTableWidgetItem(name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            value_item = QTableWidgetItem(str(color.value))
            value_item.setData(Qt.ItemDataRole.UserRole, name)
            hex_item = QTableWidgetItem(_sector_color_hex(color))
            hex_item.setFlags(hex_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            swatch = QPushButton()
            swatch.setObjectName("ColorSwatchButton")
            swatch.setFixedSize(44, 22)
            swatch.setToolTip(f"Change {name}")
            swatch.clicked.connect(lambda _checked=False, name=name: self._pick_color(name))

            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, value_item)
            self.table.setItem(row, 2, hex_item)
            self.table.setCellWidget(row, 3, swatch)
            self._value_items[name] = value_item
            self._hex_items[name] = hex_item
            self._swatches[name] = swatch
            self._sync_row(name)

        self.table.itemChanged.connect(self._item_changed)
        layout.addWidget(self.table, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        footer.addWidget(close)
        layout.addLayout(footer)

    def _item_changed(self, item: QTableWidgetItem) -> None:
        if self._syncing or item.column() != 1:
            return
        name = item.data(Qt.ItemDataRole.UserRole)
        if not name:
            return
        try:
            value = int(item.text().strip())
        except ValueError:
            self._sync_row(str(name))
            return
        if not 0 <= value <= 0xFFFFFF:
            self._sync_row(str(name))
            return
        self._set_color_value(str(name), value)

    def _pick_color(self, name: str) -> None:
        current = _sector_color_to_qcolor(self.colors[name])
        picked = QColorDialog.getColor(current, self, f"Change {name}")
        if not picked.isValid():
            return
        self._set_color_value(name, _qcolor_to_sector_value(picked))

    def _set_color_value(self, name: str, value: int) -> None:
        self.colors[name] = SectorColor(name, value)
        self._sync_row(name)
        self.color_changed.emit(name, value)

    def _sync_row(self, name: str) -> None:
        color = self.colors[name]
        qcolor = _sector_color_to_qcolor(color)
        self._syncing = True
        try:
            self._value_items[name].setText(str(color.value))
            self._hex_items[name].setText(qcolor.name().upper())
            self._swatches[name].setStyleSheet(f"background: {qcolor.name()};")
        finally:
            self._syncing = False


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        _load_radar_font()
        self.setStyleSheet(APP_STYLESHEET)
        self.setWindowTitle(f"EuroScope Scenario Studio v{__version__}")
        self.setMinimumSize(1180, 760)

        self.scenario = Scenario()
        self.sector_points: dict[str, SectorPoint] = {}
        self.sector_lines: list[SectorLine] = []
        self.sector_regions: list[SectorRegion] = []
        self.sector_labels: list[SectorTextLabel] = []
        self.sector_colors: dict[str, SectorColor] = {}
        self.sector_info = SectorInfo()
        self.sector_path: Path | None = None
        self.selected: Aircraft | None = None
        self.strip_rows: list[ClickableFrame] = []
        self.strip_category_rows: dict[str, tuple[StripCategoryHeader, list[ClickableFrame]]] = {}
        self.collapsed_strip_categories: set[str] = set()
        self.strip_filter_query = ""

        self.canvas = RadarCanvas()
        self.settings = _app_settings()
        self.layer_labels: dict[str, QLabel] = {}
        self.range_label = QLabel(f"{_format_nm(self.canvas.range_nm)} NM")
        self.cursor_label = QLabel("CTM05 CEILING:NFL195 000 27'42\"W")
        self.scenario_clock = QLabel("00:14:32Z")
        self.stack_count = QLabel("0 ACFT")
        self.strip_count = QLabel("0 STRIPS")
        self.timeline_time = QLabel("00:00:00")
        self.sector_status = QLabel("NO DATABASE")
        self.editor_dialogs: list[AircraftEditorDialog] = []
        self.diagram_dialog: DiagramDialog | None = None
        self.info_sector_dialog: InfoSectorDialog | None = None
        self.theme_dialog: ThemeEditorDialog | None = None
        self.left_sidebar_collapsed = False
        self.view_layer_actions: dict[str, QAction] = {}
        self.load_database_actions: dict[str, QAction] = {}
        self.theme_presets: dict[str, ThemePreset] = {
            UK_2026_09_INDONESIA_THEME.name: UK_2026_09_INDONESIA_THEME,
        }
        self.current_theme_name = ""
        self.pending_new_aircraft = False
        self._save_view_enabled = False
        self._load_view_layer_settings()

        self._build_menu_bar()
        self._build_tool_bar()
        self._build_window()
        self._wire_events()
        self._load_startup_data()
        self._restore_last_view()
        self._save_view_enabled = True
        self._install_shortcuts()

    def _build_window(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._build_work_area(), 1)
        self.setCentralWidget(root)

    def closeEvent(self, event) -> None:  # noqa: N802
        self._save_last_view()
        super().closeEvent(event)

    def _build_menu_bar(self) -> None:
        menu_bar = self.menuBar()
        menu_bar.setObjectName("MainMenuBar")

        file_menu = menu_bar.addMenu("Menu")
        self.load_database_menu = file_menu.addMenu("Load Database")
        for database_name in SECTOR_DATABASES:
            action = QAction(database_name, self)
            action.triggered.connect(lambda _checked=False, database_name=database_name: self.load_database(database_name))
            self.load_database_actions[database_name] = action
            self.load_database_menu.addAction(action)
        self.load_scenario_action = QAction("Load Scenario", self)
        self.load_scenario_action.setShortcut(QKeySequence.Open)
        self.load_scenario_action.triggered.connect(self.open_scenario)
        file_menu.addAction(self.load_scenario_action)
        self.save_scenario_action = QAction("Save Scenario", self)
        self.save_scenario_action.setShortcut(QKeySequence.Save)
        self.save_scenario_action.triggered.connect(self.save_scenario)
        file_menu.addAction(self.save_scenario_action)
        self.save_scenario_as_action = QAction("Save Scenario As", self)
        self.save_scenario_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.save_scenario_as_action.triggered.connect(self.save_scenario_as)
        file_menu.addAction(self.save_scenario_as_action)

        view_menu = menu_bar.addMenu("View")
        search = QAction("Search", self)
        search.setShortcut(QKeySequence.Find)
        search.triggered.connect(self.search_aircraft)
        view_menu.addAction(search)
        self.info_sector_action = QAction("Info Sector", self)
        self.info_sector_action.triggered.connect(self.open_info_sector_dialog)
        view_menu.addAction(self.info_sector_action)
        view_menu.addSeparator()
        for layer, checked in self.canvas.view_layers.items():
            action = QAction(layer, self)
            action.setCheckable(True)
            action.setChecked(checked)
            action.toggled.connect(lambda visible, layer=layer: self._set_view_layer(layer, visible))
            self.view_layer_actions[layer] = action
            view_menu.addAction(action)
        view_menu.addSeparator()
        self.diagrams_action = QAction("Diagrams", self)
        self.diagrams_action.setShortcut(QKeySequence("Ctrl+D"))
        self.diagrams_action.triggered.connect(self.open_diagrams_dialog)
        view_menu.addAction(self.diagrams_action)

        self.theme_menu = menu_bar.addMenu("Theme")
        self._refresh_theme_menu()

        help_menu = menu_bar.addMenu("Help")
        about = QAction(f"About EuroScope Scenario Studio v{__version__}", self)
        about.setEnabled(False)
        help_menu.addAction(about)

    def _refresh_theme_menu(self) -> None:
        if not hasattr(self, "theme_menu"):
            return
        self.theme_menu.clear()

        preset_menu = self.theme_menu.addMenu("Presets")
        for preset_name in sorted(self.theme_presets, key=str.casefold):
            action = QAction(preset_name, self)
            action.setCheckable(True)
            action.setChecked(preset_name == self.current_theme_name)
            action.triggered.connect(lambda _checked=False, preset_name=preset_name: self.apply_theme_preset(preset_name))
            preset_menu.addAction(action)
        if not self.theme_presets:
            empty = QAction("(none)", self)
            empty.setEnabled(False)
            preset_menu.addAction(empty)

        edit_action = QAction("Edit Colors...", self)
        edit_action.setEnabled(bool(self.sector_colors))
        edit_action.triggered.connect(self.open_theme_editor)
        self.theme_menu.addAction(edit_action)

    def apply_theme_preset(self, preset_name: str) -> None:
        preset = self.theme_presets.get(preset_name)
        if preset is None:
            return
        self._apply_theme_values(preset.colors, preset_name)

    def open_theme_editor(self) -> None:
        if not self.sector_colors:
            return
        if self.theme_dialog is not None:
            self.theme_dialog.close()
        dialog = ThemeEditorDialog(self.sector_colors, self)
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        dialog.color_changed.connect(lambda name, value: self._apply_theme_values({name: value}, "Custom"))
        dialog.destroyed.connect(lambda _=None: self._forget_theme_dialog())
        self.theme_dialog = dialog
        dialog.show()

    def _forget_theme_dialog(self) -> None:
        self.theme_dialog = None

    def _apply_theme_values(self, values: dict[str, int], theme_name: str) -> None:
        if not values:
            return
        colors = dict(self.sector_colors)
        for name, value in values.items():
            if 0 <= value <= 0xFFFFFF:
                colors[name] = SectorColor(name, value)
        self.sector_colors = colors
        self.canvas.set_sector_colors(colors)
        self.current_theme_name = theme_name
        self._refresh_theme_menu()

    def _build_tool_bar(self) -> None:
        toolbar = QToolBar("Scenario Tools", self)
        toolbar.setObjectName("ScenarioToolBar")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setIconSize(QSize(12, 12))
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)

        self.new_aircraft_action = QAction(QIcon(str(ASSET_DIR / "toolbar-aircraft.png")), "New Aircraft", self)
        self.new_aircraft_action.setCheckable(True)
        self.new_aircraft_action.setShortcut(QKeySequence("A"))
        self.new_aircraft_action.setToolTip("New Aircraft - click map to place")
        self.new_aircraft_action.triggered.connect(self.new_aircraft)

        self.ils_threshold_action = QAction(QIcon(str(ASSET_DIR / "toolbar-ils-threshold.png")), "ILS Threshold", self)
        self.ils_threshold_action.setToolTip("ILS Threshold")
        self.ils_threshold_action.triggered.connect(self.add_ils_threshold_placeholder)

        toolbar.addAction(self.new_aircraft_action)
        toolbar.addAction(self.ils_threshold_action)
        self.scenario_toolbar = toolbar
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

    def _load_view_layer_settings(self) -> None:
        for layer, default in VIEW_LAYER_DEFAULTS.items():
            value = self.settings.value(f"view_layers/{layer}")
            self.canvas.view_layers[layer] = _setting_bool(value, default)

    def _set_view_layer(self, layer: str, visible: bool) -> None:
        self.canvas.set_view_layer_visible(layer, visible)
        self.settings.setValue(f"view_layers/{layer}", visible)
        self.settings.sync()

    def _diagram_settings_key(self, path: Path, source: str) -> str:
        sector_id = hashlib.sha1(str(path.resolve()).encode("utf-8")).hexdigest()
        return f"diagram_visibility/{sector_id}/{source}"

    def _load_diagram_visibility(self, path: Path) -> dict[str, set[str]]:
        hidden_labels: dict[str, set[str]] = {source: set() for source in DIAGRAM_SOURCES}
        for source in DIAGRAM_SOURCES:
            value = self.settings.value(self._diagram_settings_key(path, source))
            hidden_labels[source] = set(_setting_string_list(value))
        return hidden_labels

    def _save_diagram_visibility(self) -> None:
        if self.sector_path is None:
            return
        for source in DIAGRAM_SOURCES:
            hidden = sorted(self.canvas.hidden_diagram_labels.get(source, set()))
            self.settings.setValue(self._diagram_settings_key(self.sector_path, source), hidden)
        self.settings.sync()

    def _restore_last_view(self) -> None:
        center_lat = _setting_float(self.settings.value("last_view/center_lat"))
        center_lon = _setting_float(self.settings.value("last_view/center_lon"))
        range_nm = _setting_float(self.settings.value("last_view/range_nm"))
        if center_lat is None or center_lon is None or range_nm is None:
            return

        self.canvas.center_lat = center_lat
        self.canvas.center_lon = center_lon
        self.canvas.range_nm = _nearest_range_preset(range_nm)
        self.canvas._sync_scale_to_range()
        self._range_changed(self.canvas.range_nm)
        self.canvas.update()

    def _save_last_view(self) -> None:
        if not self._save_view_enabled:
            return
        self.settings.setValue("last_view/center_lat", self.canvas.center_lat)
        self.settings.setValue("last_view/center_lon", self.canvas.center_lon)
        self.settings.setValue("last_view/range_nm", self.canvas.range_nm)
        self.settings.sync()

    def open_info_sector_dialog(self) -> None:
        if self.info_sector_dialog is not None:
            self.info_sector_dialog.set_info(self.sector_info)
            self.info_sector_dialog.raise_()
            self.info_sector_dialog.activateWindow()
            return
        dialog = InfoSectorDialog(self.sector_info, self)
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        dialog.info_saved.connect(self._save_sector_info)
        dialog.destroyed.connect(lambda _=None: setattr(self, "info_sector_dialog", None))
        self.info_sector_dialog = dialog
        dialog.show()

    def _save_sector_info(self, lines: tuple[str, ...]) -> None:
        if self.sector_path is None:
            self.sector_info = parse_sector_info_lines(lines)
            return
        try:
            self.sector_info = save_sector_info(self.sector_path, lines)
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "Info Sector", f"Could not save sector info:\n{exc}")
            return
        if self.info_sector_dialog is not None:
            self.info_sector_dialog.set_info(self.sector_info)

    def open_diagrams_dialog(self) -> None:
        if self.diagram_dialog is not None:
            self.diagram_dialog.raise_()
            self.diagram_dialog.activateWindow()
            return
        dialog = DiagramDialog(self.canvas, self)
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        dialog.destroyed.connect(lambda _=None: setattr(self, "diagram_dialog", None))
        self.diagram_dialog = dialog
        dialog.show()

    def _build_header(self) -> QWidget:
        header = QFrame()
        header.setObjectName("TopHeader")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(14)

        brand = QVBoxLayout()
        title = QLabel("EUROSCOPE\nSTUDIO")
        title.setObjectName("BrandTitle")
        subtitle = QLabel(f"v{__version__} / .TXT SCENARIO & ESE ENGINE")
        subtitle.setObjectName("BrandSubtitle")
        brand.addWidget(title)
        brand.addWidget(subtitle)
        layout.addLayout(brand)
        layout.addWidget(_chip("EGTT_SCTR.sct2 / EGTT.ese", "Linked", "secondary"))
        layout.addWidget(_nav_button("Radar\nScope", True))
        layout.addWidget(_nav_button("EuroScope\nData"))
        layout.addWidget(_nav_button("Aircraft\nPerformances"))
        layout.addWidget(_nav_button("Scenario\nRepository"))
        layout.addWidget(_nav_button("SCT2 / ESE\nSector"))
        layout.addStretch(1)
        layout.addWidget(_chip("EUROSCOPE REPO SYNC", "Ready", "secondary"))
        layout.addWidget(_small_button("PLAY"))
        layout.addWidget(_small_button("PAUSE"))
        layout.addWidget(QLabel("1X"))
        self.scenario_clock.setObjectName("Clock")
        layout.addWidget(self.scenario_clock)
        export = QPushButton("Export\n.TXT")
        export.setObjectName("PrimaryButton")
        export.clicked.connect(self.save_scenario_as)
        layout.addWidget(export)
        return header

    def _build_tactical_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("TacticalBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(6)
        layout.addWidget(QLabel("RADAR RANGE:"))
        down = _small_button("-")
        up = _small_button("+")
        down.clicked.connect(lambda: self._shift_range(-1))
        up.clicked.connect(lambda: self._shift_range(1))
        self.range_label.setObjectName("RangeReadout")
        layout.addWidget(down)
        layout.addWidget(self.range_label)
        layout.addWidget(up)
        layout.addWidget(_toggle_button("ES VECTOR TICKS (3M)", True))
        halo = _toggle_button("SEP HALO (3NM)", False)
        layout.addWidget(halo)
        route_toggle = _toggle_button("ROUTES: ON", True)
        route_toggle.toggled.connect(self.canvas.set_show_routes)
        layout.addWidget(route_toggle)
        layout.addStretch(1)
        layout.addWidget(QLabel("DUMMY CONTROLLER:"))
        layout.addWidget(_mono("EGLL_F_APP (119.725)", "secondary"))
        layout.addWidget(QLabel("| TAG:"))
        layout.addWidget(_mono("LL_N", "primary"))
        layout.addWidget(QLabel("ESE RUNWAY:"))
        layout.addWidget(_mono("EGLL: ARR 27R / DEP 27L", "secondary"))
        return bar

    def _build_work_area(self) -> QWidget:
        area = QWidget()
        layout = QHBoxLayout(area)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_traffic_stack())
        layout.addWidget(self.canvas, 1)
        return area

    def _build_layer_rail(self) -> QWidget:
        rail = QFrame()
        rail.setObjectName("LayerRail")
        rail.setFixedWidth(256)
        layout = QVBoxLayout(rail)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(10)
        title = QLabel("LAYER PRESETS")
        title.setObjectName("RailTitle")
        layout.addWidget(title)
        for text, active in (
            ("SIDs / STARs", True),
            ("High/Low Airways", True),
            ("Navaids & Fixes", True),
            ("Range Rings 5/10NM", True),
            ("Coastlines & FIR", False),
        ):
            row = _layer_row(text, active)
            layout.addWidget(row)
            self.layer_labels[text] = row.findChild(QLabel, "LayerDot")
        layout.addSpacing(14)
        layout.addWidget(QLabel("SWEEP LUMINESCENCE"))
        gain = QFrame()
        gain.setObjectName("GainBar")
        gain_inner = QFrame(gain)
        gain_inner.setObjectName("GainFill")
        gain_inner.setGeometry(0, 0, 176, 6)
        layout.addWidget(gain)
        gain_row = QHBoxLayout()
        gain_row.addWidget(QLabel("CRT GAIN"))
        gain_row.addStretch(1)
        gain_row.addWidget(QLabel("75%"))
        layout.addLayout(gain_row)
        layout.addStretch(1)
        footer = QFrame()
        footer.setObjectName("RailFooter")
        footer_layout = QVBoxLayout(footer)
        footer_layout.addWidget(_metric_row("ACTIVE TARGETS", self.stack_count))
        footer_layout.addWidget(_metric_row("FPS QUEUED", self.strip_count))
        layout.addWidget(footer)
        return rail

    def _build_traffic_stack(self) -> QWidget:
        self.traffic_dock = QFrame()
        self.traffic_dock.setObjectName("TrafficDock")
        self.traffic_dock.setFixedWidth(320)
        layout = QVBoxLayout(self.traffic_dock)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("DockHeader")
        header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.traffic_header = header
        header_layout = QHBoxLayout(header)
        self.traffic_header_layout = header_layout
        header_layout.setContentsMargins(0, 0, 0, 0)
        self.traffic_title_container = QWidget()
        title_box = QVBoxLayout(self.traffic_title_container)
        title_box.setContentsMargins(10, 10, 10, 10)
        title_box.setSpacing(2)
        title = QLabel("ATC SIMULATOR SCENARIO \nEDITOR")
        title.setObjectName("DockTitle")
        title.setAlignment(Qt.AlignCenter)
        self.sector_status.setObjectName("SectorStatus")
        self.sector_status.setAlignment(Qt.AlignCenter)
        title_box.addWidget(title)
        title_box.addWidget(self.sector_status)
        self.collapse_button = QPushButton("<")
        self.collapse_button.setObjectName("CollapseButton")
        self.collapse_button.setFixedSize(28, 28)
        self.collapse_button.clicked.connect(self.toggle_left_sidebar)
        self.traffic_title_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        header_layout.addWidget(self.traffic_title_container, 1)
        header_layout.addWidget(self.collapse_button)
        layout.addWidget(header)

        search = QLineEdit()
        search.setPlaceholderText("FILTER CALLSIGN / SQWK / PRF...")
        search.textChanged.connect(self._filter_strips)
        search.setObjectName("SearchInput")
        self.traffic_search_frame = QFrame()
        search_layout = QVBoxLayout(self.traffic_search_frame)
        search_layout.setContentsMargins(8, 6, 8, 6)
        search_layout.addWidget(search)
        layout.addWidget(self.traffic_search_frame)

        self.traffic_scroll = QScrollArea()
        self.traffic_scroll.setWidgetResizable(True)
        self.traffic_scroll.setFrameShape(QFrame.NoFrame)
        self.traffic_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.strip_container = QWidget()
        self.strip_layout = QVBoxLayout(self.strip_container)
        self.strip_layout.setContentsMargins(0, 0, 0, 0)
        self.strip_layout.setSpacing(0)
        self.strip_layout.addStretch(1)
        self.traffic_scroll.setWidget(self.strip_container)
        layout.addWidget(self.traffic_scroll, 1)
        return self.traffic_dock

    def toggle_left_sidebar(self) -> None:
        self.left_sidebar_collapsed = not self.left_sidebar_collapsed
        self.traffic_dock.setFixedWidth(44 if self.left_sidebar_collapsed else 320)
        side_margin = 7 if self.left_sidebar_collapsed else 10
        self.traffic_header_layout.setContentsMargins(side_margin, 8, side_margin, 8)
        self.traffic_title_container.setVisible(not self.left_sidebar_collapsed)
        self.traffic_search_frame.setVisible(not self.left_sidebar_collapsed)
        self.traffic_scroll.setVisible(not self.left_sidebar_collapsed)
        self.collapse_button.setText(">" if self.left_sidebar_collapsed else "<")
        self.canvas.update()

    def _build_timeline(self) -> QWidget:
        timeline = QFrame()
        timeline.setObjectName("Timeline")
        layout = QVBoxLayout(timeline)
        layout.setContentsMargins(12, 6, 12, 7)
        layout.setSpacing(4)
        top = QHBoxLayout()
        top.addWidget(QLabel("SCENARIO:"))
        self.timeline_time.setObjectName("TimelineClock")
        top.addWidget(self.timeline_time)
        top.addWidget(QLabel("/ 01:00:00"))
        top.addStretch(1)
        for text in ("T+05:00: INGRESS", "T+16:20: HANDOFF EGLL_F -> EGLL_TWR", "T+22:15: SQUAWK 7700", "T+38:40: HOLD ENTRY LAM"):
            top.addWidget(_event_chip(text))
        layout.addLayout(top)
        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, 3600)
        slider.setValue(872)
        slider.setTickInterval(300)
        slider.setTickPosition(QSlider.TicksBelow)
        slider.valueChanged.connect(self._timeline_changed)
        self.timeline_slider = slider
        layout.addWidget(slider)
        self._timeline_changed(slider.value())
        return timeline

    def _wire_events(self) -> None:
        self.canvas.aircraft_selected.connect(lambda aircraft: self.select_aircraft(aircraft, snap_to_target=False))
        self.canvas.aircraft_double_clicked.connect(self.open_aircraft_editor)
        self.canvas.aircraft_moved.connect(self._aircraft_changed)
        self.canvas.map_clicked.connect(self._place_new_aircraft)
        self.canvas.cursor_geo_changed.connect(self._cursor_changed)
        self.canvas.range_changed.connect(self._range_changed)
        self.canvas.diagram_visibility_changed.connect(self._save_diagram_visibility)
        self.canvas.view_changed.connect(self._save_last_view)

    def _install_shortcuts(self) -> None:
        QShortcut(QKeySequence.Delete, self, self.delete_selected_aircraft)
        QShortcut(QKeySequence("R"), self, self.canvas.fit_to_data)
        QShortcut(QKeySequence("I"), self, self.open_aircraft_editor)

    def _load_startup_data(self) -> None:
        self.load_database("Indonesia", refresh=False, warn_if_missing=False)
        if SAMPLE_SCENARIO.exists():
            self.load_scenario(SAMPLE_SCENARIO)
        else:
            self._refresh_all()

    def load_database(self, database_name: str, refresh: bool = True, warn_if_missing: bool = True) -> None:
        path = SECTOR_DATABASES[database_name]
        if not path.exists():
            self.sector_status.setText(f"NO DATABASE: {database_name}")
            if warn_if_missing:
                QMessageBox.warning(
                    self,
                    "Load Database",
                    (
                        f"{database_name} database is not available.\n\n"
                        "Build it with:\n"
                        f"python -m ase_editor.build_sector_database {database_name.lower()}"
                    ),
                )
            if refresh:
                self._refresh_all()
            return

        sector_data = load_sector_database(path)
        self.sector_points = sector_data.points
        self.sector_lines = sector_data.lines
        self.sector_regions = sector_data.regions
        self.sector_labels = sector_data.labels
        self.sector_colors = sector_data.colors
        self.sector_info = sector_data.info
        self.theme_presets[VACCC_INDONESIA_PRESET_NAME] = preset_from_sector_colors(
            VACCC_INDONESIA_PRESET_NAME,
            self.sector_colors,
        )
        self.current_theme_name = VACCC_INDONESIA_PRESET_NAME
        self.sector_path = path
        self.canvas.hidden_diagram_labels = self._load_diagram_visibility(path)
        if self.diagram_dialog is not None:
            self.diagram_dialog.close()
        if self.info_sector_dialog is not None:
            self.info_sector_dialog.close()
        if self.theme_dialog is not None:
            self.theme_dialog.close()
        self.sector_status.setText(
            f"DB: {database_name}  {len(self.sector_points)} pts / {len(self.sector_lines)} lines"
        )
        self._refresh_theme_menu()
        if refresh:
            self._refresh_all()

    def load_scenario(self, path: Path) -> None:
        try:
            self.scenario = parse_scenario_file(path)
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "Open Scenario", f"Could not load scenario:\n{exc}")
            return
        self._classify_targets()
        self.selected = self.scenario.aircraft[0] if self.scenario.aircraft else None
        self._refresh_all()

    def open_scenario(self) -> None:
        start = str(self.scenario.source_path.parent if self.scenario.source_path else ROOT)
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Open Scenario",
            start,
            "Scenario Files (*.txt *.acs *.air);;All Files (*)",
        )
        if filename:
            self.load_scenario(Path(filename))

    def save_scenario(self) -> None:
        if self.scenario.source_path is None:
            self.save_scenario_as()
            return
        self.save_scenario_to_path(self.scenario.source_path)

    def save_scenario_as(self) -> None:
        start = str(self.scenario.source_path if self.scenario.source_path else ROOT / "scenario.txt")
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Scenario",
            start,
            "Scenario Files (*.txt);;All Files (*)",
        )
        if filename:
            self.save_scenario_to_path(Path(filename))

    def save_scenario_to_path(self, path: str | Path) -> None:
        output_path = Path(path)
        try:
            write_scenario_file(self.scenario, output_path)
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "Save Scenario", f"Could not save scenario:\n{exc}")
            return
        self.scenario.source_path = output_path
        QMessageBox.information(self, "Save Scenario", f"Saved scenario:\n{output_path}")

    def new_aircraft(self, checked: bool = True) -> None:
        self._set_aircraft_placement_mode(checked)

    def _set_aircraft_placement_mode(self, enabled: bool) -> None:
        self.pending_new_aircraft = enabled
        self.new_aircraft_action.blockSignals(True)
        self.new_aircraft_action.setChecked(enabled)
        self.new_aircraft_action.blockSignals(False)
        self.canvas.set_aircraft_placement_mode(enabled)

    def _place_new_aircraft(self, latitude: float, longitude: float) -> None:
        if not self.pending_new_aircraft:
            return
        self._set_aircraft_placement_mode(False)
        callsign = self._unique_callsign("NEW001")
        aircraft = Aircraft(
            callsign=callsign,
            squawk="0000",
            mode_c="1",
            latitude=latitude,
            longitude=longitude,
            altitude=int(self.scenario.airport_altitude or 0),
            ground_speed=250,
            heading_raw=90,
            flight_plan=FlightPlan(callsign=callsign, aircraft_type="A320", departure="WIHH", arrival="WIII"),
            cleared_flight_level=30,
            perf_profile="A320.prf",
            target_kind="aircraft",
            pseudo_pilot="ALL",
        )
        self.scenario.aircraft.append(aircraft)
        self.select_aircraft(aircraft)

    def copy_aircraft(self) -> None:
        if not self.selected:
            return
        callsign, ok = QInputDialog.getText(
            self, "Copy Target", "New callsign", text=self._unique_callsign(self.selected.callsign)
        )
        if not ok or not callsign.strip():
            return
        copied = deepcopy(self.selected)
        copied.callsign = self._unique_callsign(callsign.strip().upper())
        copied.flight_plan.callsign = copied.callsign
        copied.latitude = self.canvas.center_lat
        copied.longitude = self.canvas.center_lon
        self.scenario.aircraft.append(copied)
        self.select_aircraft(copied)

    def delete_selected_aircraft(self) -> None:
        if not self.selected:
            return
        self.scenario.aircraft = [aircraft for aircraft in self.scenario.aircraft if aircraft is not self.selected]
        self.selected = self.scenario.aircraft[0] if self.scenario.aircraft else None
        self._refresh_all()

    def search_aircraft(self) -> None:
        text, ok = QInputDialog.getText(self, "Search Target / Fix", "Callsign or waypoint")
        if not ok or not text.strip():
            return
        query = text.strip().upper()
        for aircraft in self.scenario.aircraft:
            if aircraft.callsign.upper() == query:
                self.select_aircraft(aircraft)
                return
        point = self.sector_points.get(query)
        if point:
            self.canvas.center_lat = point.latitude
            self.canvas.center_lon = point.longitude
            self.canvas.update()
            self._save_last_view()

    def add_ils_threshold_placeholder(self) -> None:
        QMessageBox.information(
            self,
            "ILS Threshold",
            "ILS threshold authoring is reserved for the next implementation slice.",
        )

    def select_aircraft(self, aircraft: Aircraft | None, snap_to_target: bool = True) -> None:
        self.selected = aircraft
        if aircraft is not None and snap_to_target:
            self.canvas.center_lat = aircraft.latitude
            self.canvas.center_lon = aircraft.longitude
            self._save_last_view()
        self.canvas.set_selected(aircraft)
        self._refresh_strips()

    def open_aircraft_editor(self, aircraft: Aircraft | None = None) -> None:
        target = aircraft if aircraft is not None else self.selected
        if target is None:
            return
        self.select_aircraft(target)
        dialog = AircraftEditorDialog(target, self)
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        dialog.aircraft_saved.connect(self._aircraft_changed)
        dialog.destroyed.connect(lambda _=None, dialog=dialog: self._forget_editor(dialog))
        self.editor_dialogs.append(dialog)
        dialog.show()

    def _forget_editor(self, dialog: AircraftEditorDialog) -> None:
        if dialog in self.editor_dialogs:
            self.editor_dialogs.remove(dialog)

    def _aircraft_changed(self, aircraft: Aircraft) -> None:
        self.selected = aircraft
        self._classify_target(aircraft)
        self.canvas.update()
        self._refresh_strips()
        self._refresh_metrics()

    def _cursor_changed(self, latitude: float, longitude: float) -> None:
        ns = "N" if latitude >= 0 else "S"
        ew = "E" if longitude >= 0 else "W"
        self.cursor_label.setText(f"CTM05 CEILING:NFL195  {abs(latitude):06.3f}{ns} {abs(longitude):07.3f}{ew}")

    def _range_changed(self, range_nm: float) -> None:
        self.range_label.setText(f"{_format_nm(range_nm)} NM")

    def _timeline_changed(self, seconds: int) -> None:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        remaining = seconds % 60
        self.timeline_time.setText(f"{hours:02d}:{minutes:02d}:{remaining:02d}")

    def _shift_range(self, direction: int) -> None:
        index = RANGE_PRESETS_NM.index(self.canvas.range_nm)
        index = max(0, min(len(RANGE_PRESETS_NM) - 1, index + direction))
        self.canvas.set_range_nm(RANGE_PRESETS_NM[index])

    def _refresh_all(self) -> None:
        self.canvas.set_data(
            self.scenario,
            self.sector_points,
            self.sector_lines,
            self.sector_regions,
            self.sector_labels,
            self.sector_colors,
            self.selected,
        )
        self._refresh_strips()
        self._refresh_metrics()

    def _refresh_metrics(self) -> None:
        active = len(self.scenario.aircraft)
        strips = sum(1 for aircraft in self.scenario.aircraft if aircraft.route_tokens)
        self.stack_count.setText(f"{active} ACFT")
        self.strip_count.setText(f"{strips} STRIPS")

    def _refresh_strips(self) -> None:
        while self.strip_layout.count() > 1:
            item = self.strip_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.strip_rows = []
        self.strip_category_rows = {}
        groups = (
            ("Ground Vehicle", [target for target in self.scenario.aircraft if target.target_kind == "vehicle"]),
            ("Aircraft", [target for target in self.scenario.aircraft if target.target_kind != "vehicle"]),
        )
        for title, aircraft_group in groups:
            if not aircraft_group:
                continue
            header = self._strip_category_header(title, len(aircraft_group))
            header.toggled.connect(self._toggle_strip_category)
            self.strip_layout.insertWidget(self.strip_layout.count() - 1, header)
            group_rows: list[ClickableFrame] = []
            for aircraft in aircraft_group:
                row = self._flight_strip(aircraft)
                row.clicked.connect(lambda aircraft=aircraft: self.select_aircraft(aircraft))
                row.double_clicked.connect(lambda aircraft=aircraft: self.open_aircraft_editor(aircraft))
                self.strip_layout.insertWidget(self.strip_layout.count() - 1, row)
                self.strip_rows.append(row)
                group_rows.append(row)
            self.strip_category_rows[title] = (header, group_rows)
        self._apply_strip_visibility()

    def _strip_category_header(self, title: str, count: int) -> StripCategoryHeader:
        header = StripCategoryHeader(title, count)
        header.set_collapsed(title in self.collapsed_strip_categories)
        return header

    def _flight_strip(self, aircraft: Aircraft) -> ClickableFrame:
        selected = aircraft is self.selected
        row = ClickableFrame()
        row.setObjectName("FlightStripSelected" if selected else "FlightStrip")
        row.setProperty("searchText", " ".join([
            aircraft.callsign,
            aircraft.squawk,
            aircraft.perf_profile,
            aircraft.flight_plan.aircraft_type,
            aircraft.flight_plan.departure,
            aircraft.flight_plan.arrival,
        ]).upper())
        layout = QVBoxLayout(row)
        layout.setContentsMargins(6, 8, 8, 7)
        layout.setSpacing(4)

        top = QHBoxLayout()
        top.setSpacing(4)
        callsign = QLabel(aircraft.callsign)
        callsign.setObjectName("StripCallsignSelected" if selected else "StripCallsign")
        top.addWidget(callsign)
        type_label = QLabel(aircraft.flight_plan.aircraft_type or "")
        type_label.setObjectName("StripType")
        top.addWidget(type_label)
        top.addStretch(1)
        squawk = QLabel(f"SQ {aircraft.squawk} [{aircraft.transponder_mode_text}]")
        squawk.setObjectName("SquawkPill")
        top.addWidget(squawk)
        layout.addLayout(top)

        bottom = QHBoxLayout()
        bottom.setSpacing(6)
        route = QLabel(f"{aircraft.flight_plan.departure or '----'} -> {aircraft.flight_plan.arrival or '----'} [{(aircraft.route_tokens or ['NO ROUTE'])[0]}]")
        route.setObjectName("StripRoute")
        bottom.addWidget(route)
        bottom.addStretch(1)
        layout.addLayout(bottom)
        return row

    def _filter_strips(self, text: str) -> None:
        self.strip_filter_query = text.strip().upper()
        self._apply_strip_visibility()

    def _toggle_strip_category(self, title: str) -> None:
        if title in self.collapsed_strip_categories:
            self.collapsed_strip_categories.remove(title)
        else:
            self.collapsed_strip_categories.add(title)
        header_rows = self.strip_category_rows.get(title)
        if header_rows:
            header_rows[0].set_collapsed(title in self.collapsed_strip_categories)
        self._apply_strip_visibility()

    def _apply_strip_visibility(self) -> None:
        query = getattr(self, "strip_filter_query", "")
        for row in self.strip_rows:
            row.setVisible(query in row.property("searchText"))
        for title, (header, rows) in self.strip_category_rows.items():
            any_match = any(not row.isHidden() for row in rows)
            header.setVisible(any_match)
            if title in self.collapsed_strip_categories:
                for row in rows:
                    row.setVisible(False)

    def _classify_targets(self) -> None:
        for aircraft in self.scenario.aircraft:
            self._classify_target(aircraft)

    def _classify_target(self, aircraft: Aircraft) -> None:
        prefix = aircraft.callsign[:3].upper()
        aircraft.target_kind = "vehicle" if aircraft.symbol == "S" or prefix in VEHICLE_ASSETS else "aircraft"
        if aircraft.target_kind == "vehicle" and not aircraft.flight_plan.aircraft_type:
            aircraft.flight_plan.aircraft_type = prefix or "GND"
        if aircraft.target_kind == "aircraft" and not aircraft.perf_profile and aircraft.flight_plan.aircraft_type:
            aircraft.perf_profile = f"{aircraft.flight_plan.aircraft_type}.prf"

    def _unique_callsign(self, base: str) -> str:
        root = "".join(char for char in base.upper() if char.isalnum())[:10] or "NEW"
        callsigns = {aircraft.callsign.upper() for aircraft in self.scenario.aircraft}
        if root not in callsigns:
            return root
        for index in range(1, 1000):
            candidate = f"{root[:7]}{index:03d}"[:10]
            if candidate not in callsigns:
                return candidate
        return root[:6] + "9999"


def _line(text: str = "") -> QLineEdit:
    edit = QLineEdit(text)
    edit.setMinimumHeight(28)
    return edit


def _dialog_line(text: str = "") -> QLineEdit:
    edit = QLineEdit(text)
    edit.setFixedHeight(34)
    return edit


def _dialog_double(minimum: float, maximum: float, decimals: int) -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(minimum, maximum)
    spin.setDecimals(decimals)
    spin.setSingleStep(0.001)
    spin.setFixedHeight(34)
    return spin


def _dialog_int(minimum: int, maximum: int, step: int) -> QSpinBox:
    spin = QSpinBox()
    spin.setRange(minimum, maximum)
    spin.setSingleStep(step)
    spin.setFixedHeight(34)
    return spin


def _dialog_field(label: str, widget: QWidget) -> QWidget:
    container = QWidget()
    expands_vertically = isinstance(widget, QPlainTextEdit)
    vertical_policy = QSizePolicy.Policy.Expanding if expands_vertically else QSizePolicy.Policy.Fixed
    container.setSizePolicy(QSizePolicy.Policy.Expanding, vertical_policy)
    widget.setMinimumWidth(0)
    if isinstance(widget, QComboBox):
        widget.setFixedHeight(34)
    widget.setSizePolicy(QSizePolicy.Policy.Expanding, vertical_policy)
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(3)
    title = QLabel(label)
    title.setObjectName("DialogFieldLabel")
    layout.addWidget(title)
    layout.addWidget(widget)
    if expands_vertically:
        container.setMinimumHeight(widget.minimumHeight() + title.sizeHint().height() + 6)
    else:
        container.setFixedHeight(widget.minimumHeight() + title.sizeHint().height() + 5)
    return container


def _double_spin(minimum: float, maximum: float, decimals: int) -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(minimum, maximum)
    spin.setDecimals(decimals)
    spin.setSingleStep(0.001)
    spin.setMinimumHeight(28)
    return spin


def _int_spin(minimum: int, maximum: int, step: int) -> QSpinBox:
    spin = QSpinBox()
    spin.setRange(minimum, maximum)
    spin.setSingleStep(step)
    spin.setMinimumHeight(28)
    return spin


def _row(*widgets: QWidget) -> QWidget:
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    for widget in widgets:
        layout.addWidget(widget)
    return container


def _field(label: str, widget: QWidget) -> QWidget:
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    caption = QLabel(label)
    caption.setObjectName("FieldLabel")
    layout.addWidget(caption)
    layout.addWidget(widget)
    return container


def _section_title(title: str, trailing: str | QWidget) -> QWidget:
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    label = QLabel(title.upper())
    label.setObjectName("SectionTitle")
    layout.addWidget(label)
    layout.addStretch(1)
    if isinstance(trailing, QWidget):
        layout.addWidget(trailing)
    elif trailing:
        chip = QLabel(trailing)
        chip.setObjectName("MiniPillGreen")
        layout.addWidget(chip)
    return container


def _divider() -> QWidget:
    line = QFrame()
    line.setObjectName("Divider")
    line.setFixedHeight(1)
    return line


def _chip(text: str, status: str, color: str) -> QWidget:
    container = QFrame()
    container.setObjectName("HeaderChip")
    layout = QHBoxLayout(container)
    layout.setContentsMargins(10, 5, 10, 5)
    layout.addWidget(QLabel(text))
    dot = QLabel(status)
    dot.setObjectName("ChipStatusSecondary" if color == "secondary" else "ChipStatusPrimary")
    layout.addWidget(dot)
    return container


def _nav_button(text: str, active: bool = False) -> QLabel:
    label = QLabel(text)
    label.setObjectName("NavActive" if active else "NavItem")
    label.setAlignment(Qt.AlignCenter)
    return label


def _small_button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("SmallButton")
    return button


def _toggle_button(text: str, checked: bool) -> QPushButton:
    button = QPushButton(text)
    button.setCheckable(True)
    button.setChecked(checked)
    button.setObjectName("ToggleButton")
    return button


def _layer_row(text: str, active: bool) -> QWidget:
    row = QFrame()
    row.setObjectName("LayerRow")
    layout = QHBoxLayout(row)
    layout.setContentsMargins(8, 6, 8, 6)
    layout.addWidget(QLabel(text))
    layout.addStretch(1)
    dot = QLabel()
    dot.setObjectName("LayerDot")
    dot.setProperty("active", active)
    dot.setFixedSize(9, 9)
    layout.addWidget(dot)
    return row


def _metric_row(label: str, value: QLabel) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(QLabel(label))
    layout.addStretch(1)
    value.setObjectName("MetricValue")
    layout.addWidget(value)
    return row


def _event_chip(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("EventChip")
    return label


def _mono(text: str, color: str = "plain") -> QLabel:
    label = QLabel(text)
    label.setObjectName(f"Mono{color.title()}")
    return label


def _int_text(text: str) -> int:
    match = re.search(r"\d+", text or "")
    return int(match.group(0)) if match else 0


def _flight_type_label(value: str) -> str:
    normalized = (value or "").upper()
    if normalized == "V":
        return "VFR"
    if normalized == "S":
        return "SVFR"
    return "IFR"


DIALOG_STYLESHEET = """
QDialog, QWidget {
    background: #051424;
    color: #d4e4fa;
    font-family: Inter, Segoe UI, Arial, sans-serif;
    font-size: 13px;
}
QGroupBox {
    background: #0d1c2d;
    border: 1px solid rgba(56, 189, 248, 0.18);
    border-radius: 2px;
    margin-top: 10px;
    padding: 8px;
    font-weight: 700;
}
QGroupBox::title {
    color: #4cd7f6;
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}
QLabel {
    background: transparent;
    color: #bcc9cd;
}
QLineEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox, QListWidget {
    background: #010f1f;
    color: #d4e4fa;
    border: 1px solid #122131;
    border-radius: 1px;
    padding: 4px 6px;
    selection-background-color: #273647;
    selection-color: #ffffff;
}
QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QListWidget:focus {
    border-color: rgba(76, 215, 246, 0.55);
}
QLineEdit:disabled, QSpinBox:disabled {
    background: #0a1726;
    color: #607586;
    border-color: #122131;
}
QComboBox {
    padding-right: 24px;
}
QSpinBox, QDoubleSpinBox {
    padding-right: 24px;
}
QComboBox::drop-down {
    border-left: 1px solid #122131;
    width: 18px;
}
QComboBox::down-arrow {
    image: url(asset/dropdown-arrow.svg);
    width: 10px;
    height: 7px;
}
QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 18px;
    border-left: 1px solid #122131;
    border-bottom: 1px solid #122131;
}
QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 18px;
    border-left: 1px solid #122131;
}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    image: url(asset/spin-up-arrow.svg);
    width: 8px;
    height: 5px;
}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    image: url(asset/spin-down-arrow.svg);
    width: 8px;
    height: 5px;
}
QComboBox QAbstractItemView {
    background: #010f1f;
    color: #d4e4fa;
    border: 1px solid rgba(76, 215, 246, 0.35);
    selection-background-color: #122131;
    selection-color: #4cd7f6;
}
QPushButton {
    background: #122131;
    color: #d4e4fa;
    border: 1px solid rgba(56, 189, 248, 0.18);
    border-radius: 2px;
    padding: 5px 10px;
    min-height: 22px;
    font-family: JetBrains Mono, Consolas, monospace;
    font-size: 10px;
    font-weight: 700;
}
QPushButton:hover {
    background: #1c2b3c;
    border-color: rgba(76, 215, 246, 0.45);
}
QPushButton#DialogPrimaryButton {
    background: #4cd7f6;
    color: #003640;
    border: 0;
}
QPushButton#DialogPrimaryButton:hover {
    background: #6ee2fb;
}
QCheckBox {
    background: transparent;
    color: #d4e4fa;
}
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid rgba(76, 215, 246, 0.35);
    background: #010f1f;
    border-radius: 2px;
}
QCheckBox::indicator:checked {
    image: url(asset/check-v.svg);
    background: #4cd7f6;
    border-color: #4cd7f6;
}
QScrollBar:vertical {
    background: #010f1f;
    width: 10px;
}
QScrollBar::handle:vertical {
    background: #273647;
    border-radius: 2px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
"""


DIAGRAM_STYLESHEET = """
QDialog, QWidget {
    background: #051424;
    color: #d4e4fa;
    font-family: Inter, Segoe UI, Arial, sans-serif;
    font-size: 13px;
}
QLabel#DiagramColumnTitle {
    color: #4cd7f6;
    font-weight: 700;
    font-family: JetBrains Mono, Consolas, monospace;
}
QListWidget {
    background: #010f1f;
    color: #d4e4fa;
    border: 1px solid rgba(56, 189, 248, 0.18);
    selection-background-color: #122131;
    selection-color: #4cd7f6;
    font-family: JetBrains Mono, Consolas, monospace;
    font-size: 11px;
}
QListWidget::item {
    min-height: 18px;
}
QListWidget::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid rgba(76, 215, 246, 0.35);
    background: #010f1f;
    border-radius: 2px;
}
QListWidget::indicator:checked {
    image: url(asset/check-v.svg);
    background: #4cd7f6;
    border-color: #4cd7f6;
}
QCheckBox {
    background: transparent;
    color: #d4e4fa;
    font-family: JetBrains Mono, Consolas, monospace;
    font-size: 11px;
}
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid rgba(76, 215, 246, 0.35);
    background: #010f1f;
    border-radius: 2px;
}
QCheckBox::indicator:checked {
    image: url(asset/check-v.svg);
    background: #4cd7f6;
    border: 1px solid #4cd7f6;
}
QPushButton {
    background: #122131;
    color: #d4e4fa;
    border: 1px solid rgba(56, 189, 248, 0.18);
    border-radius: 2px;
    padding: 5px 24px;
    font-family: JetBrains Mono, Consolas, monospace;
    font-size: 10px;
    font-weight: 700;
}
QPushButton:hover {
    background: #1c2b3c;
    border-color: rgba(76, 215, 246, 0.45);
}
"""


APP_STYLESHEET = """
QMenuBar {
    background: #f4f4f4;
    color: #111111;
    border-bottom: 1px solid #c7c7c7;
    font-family: Segoe UI, Arial, sans-serif;
    font-size: 12px;
}
QMenuBar::item {
    background: transparent;
    padding: 3px 8px;
}
QMenuBar::item:selected {
    background: #4cd7f6;
    color: #003640;
}
QMenuBar::item:pressed {
    background: #122131;
    color: #ffffff;
}
QMenu {
    background: #f8f8f8;
    color: #111111;
    border: 1px solid #9ca3af;
    font-family: Segoe UI, Arial, sans-serif;
    font-size: 12px;
}
QMenu::item {
    padding: 4px 34px 4px 28px;
}
QMenu::item:selected {
    background: #4cd7f6;
    color: #003640;
}
QMenu::item:disabled {
    color: #7b8794;
}
QMenu::indicator {
    width: 16px;
    height: 16px;
}
QMenu::indicator:checked {
    image: url(asset/check-v.svg);
    background: #8ecbff;
    border: 1px solid #0078d7;
}
QMenu::separator {
    height: 1px;
    background: #c7c7c7;
    margin: 3px 0;
}
QToolBar#ScenarioToolBar {
    background: #0d1c2d;
    border: 0;
    border-bottom: 1px solid rgba(56, 189, 248, 0.16);
    spacing: 4px;
    padding: 4px 6px;
}
QToolBar#ScenarioToolBar QToolButton {
    background: #010f1f;
    border: 1px solid rgba(76, 215, 246, 0.30);
    border-radius: 2px;
    padding: 2px;
    min-width: 18px;
    min-height: 18px;
}
QToolBar#ScenarioToolBar QToolButton:hover {
    background: #122131;
    border-color: #4cd7f6;
}
QToolBar#ScenarioToolBar QToolButton:checked {
    background: #1c2b3c;
    border-color: #ffb95f;
}
QToolBar#ScenarioToolBar QToolButton:pressed {
    background: #1c2b3c;
    border-color: #ffb95f;
}
QMainWindow, QWidget {
    background: #051424;
    color: #d4e4fa;
    font-family: Inter, Segoe UI, Arial, sans-serif;
    font-size: 13px;
}
QFrame#TopHeader {
    background: #010f1f;
    border-bottom: 1px solid rgba(56, 189, 248, 0.14);
}
QLabel#BrandTitle {
    color: #4cd7f6;
    font-size: 15px;
    font-weight: 700;
    line-height: 16px;
}
QLabel#BrandSubtitle, QLabel#RailTitle, QLabel#FieldLabel {
    color: #bcc9cd;
    font-family: JetBrains Mono, Consolas, monospace;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0px;
}
QLabel#NavActive {
    background: #06b6d4;
    color: #003640;
    border-radius: 2px;
    font-weight: 700;
    padding: 8px 12px;
}
QLabel#NavItem {
    color: #bcc9cd;
    padding: 8px 10px;
}
QFrame#HeaderChip {
    background: #0d1c2d;
    border: 1px solid #122131;
    border-radius: 2px;
}
QLabel#ChipStatusSecondary, QLabel#MetricValue {
    color: #4edea3;
    font-family: JetBrains Mono, Consolas, monospace;
    font-size: 11px;
    font-weight: 700;
}
QLabel#ChipStatusPrimary, QLabel#Clock, QLabel#RangeReadout, QLabel#TimelineClock {
    color: #ffb95f;
    font-family: JetBrains Mono, Consolas, monospace;
    font-size: 11px;
    font-weight: 700;
}
QFrame#TacticalBar {
    background: #0d1c2d;
    border-bottom: 1px solid rgba(56, 189, 248, 0.12);
}
QFrame#LayerRail, QFrame#TrafficDock, QWidget#qt_scrollarea_viewport {
    background: #010f1f;
}
QFrame#TrafficDock {
    border-left: 1px solid rgba(56, 189, 248, 0.10);
    border-right: 1px solid rgba(56, 189, 248, 0.10);
}
QFrame#DockHeader, QFrame#Timeline {
    background: #0d1c2d;
}
QLabel#DockTitle, QLabel#SectionTitle {
    color: #d4e4fa;
    font-size: 14px;
    font-weight: 700;
}
QLabel#SectorStatus {
    color: #4cd7f6;
    font-family: JetBrains Mono, Consolas, monospace;
    font-size: 10px;
    font-weight: 700;
}
QFrame#StripCategoryHeader {
    background: #0d1c2d;
    border-bottom: 1px solid rgba(56, 189, 248, 0.16);
}
QFrame#StripCategoryHeader:hover {
    background: #122131;
}
QLabel#StripCategoryText, QLabel#StripCategoryArrow {
    color: #ffb95f;
    font-family: JetBrains Mono, Consolas, monospace;
    font-size: 10px;
    font-weight: 700;
}
QLabel#StripCategoryArrow {
    min-width: 10px;
}
QFrame#LayerRow {
    background: #0d1c2d;
    border-radius: 2px;
}
QFrame#LayerRow:hover {
    background: #122131;
}
QLabel#LayerDot {
    background: #3d494c;
    border-radius: 4px;
}
QLabel#LayerDot[active="true"] {
    background: #4edea3;
}
QFrame#GainBar {
    background: #273647;
    border-radius: 3px;
    min-height: 6px;
    max-height: 6px;
}
QFrame#GainFill {
    background: #4cd7f6;
    border-radius: 3px;
}
QFrame#RailFooter {
    background: #0d1c2d;
    border-radius: 2px;
}
QFrame#FlightStripSelected {
    background: #122131;
    border-left: 4px solid #4cd7f6;
    border-bottom: 1px solid rgba(56, 189, 248, 0.16);
}
QFrame#FlightStrip {
    background: #051424;
    border-left: 4px solid #3d494c;
    border-bottom: 1px solid rgba(56, 189, 248, 0.12);
}
QFrame#FlightStrip:hover {
    background: #0d1c2d;
}
QLabel#StripCallsignSelected, QLabel#StripCallsign {
    color: #4cd7f6;
    font-family: JetBrains Mono, Consolas, monospace;
    font-size: 13px;
    font-weight: 700;
}
QLabel#StripCallsign {
    color: #d4e4fa;
}
QLabel#StripType, QLabel#StripRoute {
    color: #bcc9cd;
    font-family: JetBrains Mono, Consolas, monospace;
    font-size: 11px;
    font-weight: 600;
}
QLabel#StripRoute {
    color: #d4e4fa;
    font-size: 12px;
}
QLabel#MiniPill, QLabel#MiniPillGreen, QLabel#SquawkPill {
    background: #273647;
    color: #bcc9cd;
    border-radius: 2px;
    padding: 2px 5px;
    font-family: JetBrains Mono, Consolas, monospace;
    font-size: 10px;
}
QLabel#MiniPillGreen {
    color: #4edea3;
}
QLabel#SquawkPill {
    color: #6ffbbe;
    font-size: 11px;
}
QLabel#MonoPrimary {
    color: #4cd7f6;
    font-family: JetBrains Mono, Consolas, monospace;
    font-size: 11px;
    font-weight: 700;
}
QLabel#MonoSecondary {
    color: #4edea3;
    font-family: JetBrains Mono, Consolas, monospace;
    font-size: 11px;
    font-weight: 700;
}
QLabel#MonoTertiary {
    color: #ffb95f;
    font-family: JetBrains Mono, Consolas, monospace;
    font-size: 11px;
    font-weight: 700;
}
QLabel#MonoPlain {
    color: #d4e4fa;
    font-family: JetBrains Mono, Consolas, monospace;
    font-size: 11px;
}
QPushButton {
    background: #122131;
    color: #d4e4fa;
    border: 1px solid rgba(56, 189, 248, 0.18);
    border-radius: 2px;
    padding: 6px 8px;
    font-family: JetBrains Mono, Consolas, monospace;
    font-size: 10px;
    font-weight: 700;
}
QPushButton:hover {
    background: #1c2b3c;
    border-color: rgba(76, 215, 246, 0.45);
}
QPushButton#PrimaryButton {
    background: #4cd7f6;
    color: #003640;
    border: 0;
}
QPushButton#SmallButton {
    padding: 4px 7px;
    min-width: 24px;
}
QPushButton#CollapseButton {
    background: #122131;
    color: #4cd7f6;
    border: 1px solid rgba(76, 215, 246, 0.24);
    border-radius: 2px;
    padding: 0;
    font-size: 12px;
}
QPushButton#ToggleButton:checked {
    background: #122131;
    color: #4cd7f6;
    border-color: rgba(76, 215, 246, 0.35);
}
QLineEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QListWidget, QComboBox {
    background: #010f1f;
    color: #d4e4fa;
    border: 1px solid #122131;
    border-radius: 2px;
    padding: 4px 6px;
    selection-background-color: #273647;
    font-family: JetBrains Mono, Consolas, monospace;
    font-size: 11px;
}
QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: #4cd7f6;
}
QComboBox {
    padding-right: 24px;
}
QSpinBox, QDoubleSpinBox {
    padding-right: 24px;
}
QComboBox::drop-down {
    border-left: 1px solid #122131;
    width: 18px;
}
QComboBox::down-arrow {
    image: url(asset/dropdown-arrow.svg);
    width: 10px;
    height: 7px;
}
QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 18px;
    border-left: 1px solid #122131;
    border-bottom: 1px solid #122131;
}
QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 18px;
    border-left: 1px solid #122131;
}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    image: url(asset/spin-up-arrow.svg);
    width: 8px;
    height: 5px;
}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    image: url(asset/spin-down-arrow.svg);
    width: 8px;
    height: 5px;
}
QLineEdit#SearchInput {
    background: #010f1f;
}
QFrame#Divider {
    background: rgba(56, 189, 248, 0.14);
}
QLabel#DockCallsign {
    color: #4cd7f6;
    font-family: JetBrains Mono, Consolas, monospace;
    font-size: 11px;
    font-weight: 700;
}
QLabel#EventChip {
    color: #bcc9cd;
    font-family: JetBrains Mono, Consolas, monospace;
    font-size: 10px;
}
QSlider::groove:horizontal {
    background: #273647;
    height: 10px;
    border-radius: 5px;
}
QSlider::sub-page:horizontal {
    background: #4cd7f6;
    border-radius: 5px;
}
QSlider::handle:horizontal {
    background: #ffb95f;
    width: 14px;
    margin: -5px 0;
    border-radius: 2px;
}
QScrollArea {
    border: 0;
}
"""
