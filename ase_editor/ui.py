from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import math
import re
import sys

from PySide6.QtCore import QPoint, QPointF, QRegularExpression, QSize, Qt, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QIcon,
    QKeySequence,
    QPainter,
    QPen,
    QPixmap,
    QRegularExpressionValidator,
    QShortcut,
    QTransform,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
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
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .models import Aircraft, FlightPlan, Scenario
from .parser import parse_scenario_file
from .sector import (
    SectorLine,
    SectorPoint,
    load_sector_lines,
    load_sector_points,
    resolve_route_tokens,
)


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_SCENARIO = ROOT / "WIHH_example.txt"
DEFAULT_SECTOR = ROOT / "WIII_Demo.sct"
ASSET_DIR = ROOT / "asset"
RANGE_PRESETS_NM = (10, 20, 40, 80, 120)
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
    "GEO": ("Geography",),
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


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("EuroScope Scenario Studio")
    app.setStyleSheet(APP_STYLESHEET)
    window = MainWindow()
    window.resize(1440, 900)
    window.show()
    return app.exec()


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


class RadarCanvas(QWidget):
    aircraft_selected = Signal(object)
    aircraft_double_clicked = Signal(object)
    aircraft_moved = Signal(object)
    map_clicked = Signal(float, float)
    cursor_geo_changed = Signal(float, float)
    range_changed = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.scenario = Scenario()
        self.sector_points: dict[str, SectorPoint] = {}
        self.sector_lines: list[SectorLine] = []
        self.selected: Aircraft | None = None
        self.show_routes = True
        self.show_sector_lines = True
        self.show_fixes = True
        self.view_layers = dict(VIEW_LAYER_DEFAULTS)
        self.hidden_diagram_labels: dict[str, set[str]] = {"SID": set(), "STAR": set(), "GEO": set()}
        self.range_nm = 40
        self.vector_minutes = 3
        self.pixels_per_nm = 8.0
        self.center_lat = -6.1
        self.center_lon = 106.8
        self._last_mouse: QPoint | None = None
        self._panning = False
        self._dragging_aircraft: Aircraft | None = None
        self.aircraft_placement_mode = False
        self.icons = self._load_icons()

    def set_data(
        self,
        scenario: Scenario,
        sector_points: dict[str, SectorPoint],
        sector_lines: list[SectorLine],
        selected: Aircraft | None = None,
    ) -> None:
        self.scenario = scenario
        self.sector_points = sector_points
        self.sector_lines = sector_lines
        self.selected = selected
        self.fit_to_data()

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
        self.update()

    def set_diagram_source_visible(self, source: str, labels: list[str], visible: bool) -> None:
        hidden = self.hidden_diagram_labels.setdefault(source, set())
        if visible:
            hidden.difference_update(labels)
        else:
            hidden.update(labels)
        self.update()

    def set_range_nm(self, range_nm: int) -> None:
        self.range_nm = max(RANGE_PRESETS_NM[0], min(RANGE_PRESETS_NM[-1], range_nm))
        self._sync_scale_to_range()
        self.range_changed.emit(self.range_nm)
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
        self._sync_scale_to_range()
        self.range_changed.emit(self.range_nm)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#010f1f"))
        self._sync_scale_to_range()
        self._draw_scope_background(painter)
        self._draw_sector_lines(painter)
        self._draw_fixes(painter)
        self._draw_thresholds(painter)
        self._draw_holds(painter)
        self._draw_routes(painter)
        self._draw_targets(painter)
        self._draw_scope_overlay(painter)

    def wheelEvent(self, event) -> None:  # noqa: N802
        index = RANGE_PRESETS_NM.index(self.range_nm)
        if event.angleDelta().y() > 0:
            index = max(0, index - 1)
        else:
            index = min(len(RANGE_PRESETS_NM) - 1, index + 1)
        self.set_range_nm(RANGE_PRESETS_NM[index])

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
                self._dragging_aircraft = aircraft
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

        if self._dragging_aircraft:
            self._dragging_aircraft.latitude = lat
            self._dragging_aircraft.longitude = lon
            self.aircraft_moved.emit(self._dragging_aircraft)
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.RightButton:
            self._panning = False
        if event.button() == Qt.LeftButton:
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
        center = QPointF(self.width() / 2.0, self.height() / 2.0)
        radius = self.range_nm * self.pixels_per_nm
        painter.setPen(QPen(QColor(56, 189, 248, 22), 1))

        grid_step_nm = self._grid_step_nm()
        value = -self.range_nm
        while value <= self.range_nm:
            x = center.x() + value * self.pixels_per_nm
            y = center.y() + value * self.pixels_per_nm
            painter.drawLine(int(x), 0, int(x), self.height())
            painter.drawLine(0, int(y), self.width(), int(y))
            value += grid_step_nm

        painter.setPen(QColor("#4cd7f6"))
        painter.drawText(14, 22, f"SCOPE: WIHH  RANGE {self.range_nm} NM")
        painter.setPen(QColor("#bcc9cd"))
        painter.drawText(14, 38, f"CENTER {self.center_lat:.4f} {self.center_lon:.4f}")

    def _draw_sector_lines(self, painter: QPainter) -> None:
        if not self.show_sector_lines:
            return
        colors = {
            "RUNWAY": QColor(212, 228, 250, 120),
            "SID": QColor(6, 182, 212, 66),
            "STAR": QColor(255, 185, 95, 70),
            "HIGH AIRWAY": QColor(6, 182, 212, 60),
            "LOW AIRWAY": QColor(6, 182, 212, 45),
            "ARTCC": QColor(78, 222, 163, 55),
            "ARTCC HIGH": QColor(78, 222, 163, 55),
            "ARTCC LOW": QColor(78, 222, 163, 45),
            "GEO": QColor(100, 116, 139, 65),
            "REGIONS": QColor(148, 163, 184, 55),
            "LABELS": QColor(188, 201, 205, 55),
            "DIAGRAMS": QColor(255, 185, 95, 60),
        }
        for line in self.sector_lines:
            if not self._line_source_visible(line.source):
                continue
            if not self._line_label_visible(line):
                continue
            start = self.geo_to_screen(line.latitude1, line.longitude1)
            end = self.geo_to_screen(line.latitude2, line.longitude2)
            if not self._point_near_view(start) and not self._point_near_view(end):
                continue
            painter.setPen(QPen(colors.get(line.source, QColor("#475569")), 1))
            painter.drawLine(start, end)

    def _draw_fixes(self, painter: QPainter) -> None:
        if not self.show_fixes or self.range_nm > 80:
            return
        painter.setFont(QFont("JetBrains Mono", 7))
        count = 0
        for point in self.sector_points.values():
            point_layer = POINT_SOURCE_LAYERS.get(point.source)
            if point_layer and not self.view_layers.get(point_layer, True):
                continue
            screen = self.geo_to_screen(point.latitude, point.longitude)
            if not self._point_near_view(screen):
                continue
            painter.setPen(QPen(QColor(78, 222, 163, 120), 1))
            if point.source == "VOR":
                painter.drawRect(int(screen.x() - 3), int(screen.y() - 3), 6, 6)
            else:
                points = [
                    QPointF(screen.x(), screen.y() - 4),
                    QPointF(screen.x() + 4, screen.y() + 3),
                    QPointF(screen.x() - 4, screen.y() + 3),
                ]
                painter.drawPolygon(points)
            painter.setPen(QColor(188, 201, 205, 140))
            painter.drawText(screen + QPointF(6, -4), point.identifier)
            count += 1
            if count > 350:
                break

    def _draw_thresholds(self, painter: QPainter) -> None:
        if not self.view_layers.get("Thresholds", True):
            return
        painter.setFont(QFont("JetBrains Mono", 8, QFont.Bold))
        for threshold in self.scenario.thresholds:
            start = self.geo_to_screen(threshold.latitude1, threshold.longitude1)
            end = self.geo_to_screen(threshold.latitude2, threshold.longitude2)
            painter.setPen(QPen(QColor("#4cd7f6"), 2))
            painter.drawLine(start, end)
            painter.drawText(end + QPointF(5, -5), threshold.name)

    def _draw_holds(self, painter: QPainter) -> None:
        if not self.view_layers.get("Holds", True):
            return
        painter.setFont(QFont("JetBrains Mono", 8, QFont.Bold))
        painter.setPen(QPen(QColor("#ffb95f"), 1, Qt.DashLine))
        for hold in self.scenario.holds:
            point = self.sector_points.get(hold.fix)
            if not point:
                continue
            screen = self.geo_to_screen(point.latitude, point.longitude)
            if not self._point_near_view(screen):
                continue
            painter.drawEllipse(screen, 8, 8)
            painter.drawText(screen + QPointF(10, -8), f"HOLD {hold.fix}")

    def _draw_routes(self, painter: QPainter) -> None:
        if not self.show_routes or not self.selected:
            return
        points = resolve_route_tokens(self.selected.route_tokens, self.sector_points)
        if not points:
            return

        painter.setFont(QFont("JetBrains Mono", 8, QFont.Bold))
        painter.setPen(QPen(QColor("#4edea3"), 1, Qt.DashLine))
        previous = self.geo_to_screen(self.selected.latitude, self.selected.longitude)
        for point in points:
            current = self.geo_to_screen(point.latitude, point.longitude)
            painter.drawLine(previous, current)
            painter.drawEllipse(current, 3, 3)
            painter.drawText(current + QPointF(6, -6), point.identifier)
            previous = current

    def _draw_targets(self, painter: QPainter) -> None:
        for aircraft in self.scenario.aircraft:
            point = self.geo_to_screen(aircraft.latitude, aircraft.longitude)
            if not self._point_near_view(point):
                continue
            selected = aircraft is self.selected
            self._draw_velocity_leader(painter, aircraft, point, selected)
            self._draw_target_icon(painter, aircraft, point, selected)
            self._draw_tag(painter, aircraft, point, selected)

    def _draw_velocity_leader(self, painter: QPainter, aircraft: Aircraft, point: QPointF, selected: bool) -> None:
        speed = aircraft.ground_speed or _int_text(aircraft.flight_plan.cruise_speed)
        distance_nm = speed * self.vector_minutes / 60.0
        heading_rad = math.radians(aircraft.heading_degrees - 90)
        end = QPointF(
            point.x() + math.cos(heading_rad) * distance_nm * self.pixels_per_nm,
            point.y() + math.sin(heading_rad) * distance_nm * self.pixels_per_nm,
        )
        painter.setPen(QPen(QColor("#4cd7f6") if selected else QColor(100, 116, 139, 160), 2 if selected else 1))
        painter.drawLine(point, end)

    def _draw_target_icon(self, painter: QPainter, aircraft: Aircraft, point: QPointF, selected: bool) -> None:
        pixmap = self._icon_for_aircraft(aircraft)
        size = 34 if selected else 24
        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            rotated = scaled.transformed(QTransform().rotate(aircraft.heading_degrees), Qt.SmoothTransformation)
            painter.drawPixmap(
                int(point.x() - rotated.width() / 2),
                int(point.y() - rotated.height() / 2),
                rotated,
            )
        else:
            painter.setPen(QPen(QColor("#4cd7f6") if selected else QColor("#64748b"), 2))
            painter.drawEllipse(point, 5, 5)

    def _draw_tag(self, painter: QPainter, aircraft: Aircraft, point: QPointF, selected: bool) -> None:
        block_origin = point + QPointF(38, -28 if selected else -22)
        painter.setFont(QFont("JetBrains Mono", 9 if selected else 8, QFont.Bold))
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
        painter.setFont(QFont("JetBrains Mono", 8, QFont.Bold))
        painter.setPen(QColor("#bcc9cd"))
        painter.drawText(12, self.height() - 18, f"ACTIVE TARGETS {len(self.scenario.aircraft):02d}  VECTOR {self.vector_minutes}M")

    def _grid_step_nm(self) -> int:
        if self.range_nm <= 10:
            return 1
        if self.range_nm <= 20:
            return 2
        if self.range_nm <= 40:
            return 5
        return 10

    def _aircraft_at(self, point: QPointF) -> Aircraft | None:
        nearest: tuple[float, Aircraft] | None = None
        for aircraft in self.scenario.aircraft:
            screen = self.geo_to_screen(aircraft.latitude, aircraft.longitude)
            distance = math.hypot(screen.x() - point.x(), screen.y() - point.y())
            if distance <= 22 and (nearest is None or distance < nearest[0]):
                nearest = (distance, aircraft)
        return nearest[1] if nearest else None

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


class RouteTargetDock(QWidget):
    aircraft_changed = Signal(object)
    route_changed = Signal(object)
    export_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setFixedWidth(384)
        self.aircraft: Aircraft | None = None
        self._loading = False
        self._build_widgets()
        self._wire_widgets()
        self._set_enabled(False)

    def set_aircraft(self, aircraft: Aircraft | None) -> None:
        self.aircraft = aircraft
        self._loading = True
        try:
            self._set_enabled(aircraft is not None)
            if aircraft is None:
                self._clear()
                return
            self.target_title.setText(f"{aircraft.callsign} ({aircraft.perf_profile or aircraft.flight_plan.aircraft_type or 'NO PERF'})")
            self.origin.setText(aircraft.flight_plan.departure)
            self.destination.setText(aircraft.flight_plan.arrival)
            self.departure_runway.setText(_route_runway(aircraft.flight_plan.route_text, aircraft.flight_plan.departure))
            self.arrival_runway.setText(_route_runway(aircraft.flight_plan.route_text, aircraft.flight_plan.arrival))
            self.route_text.setPlainText(aircraft.route_source)
            self.callsign.setText(aircraft.callsign)
            self.aircraft_type.setText(aircraft.flight_plan.aircraft_type)
            self.wake_category.setText(aircraft.wake_category)
            self.squawk.setText(aircraft.squawk)
            self.mode_c.setChecked(aircraft.mode_c == "1")
            self.latitude.setValue(aircraft.latitude)
            self.longitude.setValue(aircraft.longitude)
            self.altitude.setValue(aircraft.altitude)
            self.cleared_fl.setValue(aircraft.cleared_flight_level or aircraft.actual_flight_level)
            self.ground_speed.setValue(aircraft.ground_speed)
            self.heading.setValue(max(1, min(360, int(round(aircraft.heading_degrees)) or 1)))
            self.ias_variation.setValue(aircraft.ias_variation)
            self.dummy_controller.setText(aircraft.dummy_controller)
            self.perf_profile.setText(aircraft.perf_profile)
            self.delay.setText(aircraft.delay_text)
            self.remarks.setPlainText(aircraft.flight_plan.remarks)
            self._refresh_waypoints()
        finally:
            self._loading = False

    def sync_position_fields(self) -> None:
        if not self.aircraft or self._loading:
            return
        self._loading = True
        self.latitude.setValue(self.aircraft.latitude)
        self.longitude.setValue(self.aircraft.longitude)
        self._loading = False

    def _build_widgets(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        layout.addWidget(_section_title("FPDB & EuroScope Route Assembler", ".ESE ROUTING"))
        route_grid = QGridLayout()
        self.origin = _line("EGLL")
        self.departure_runway = _line("27L")
        self.destination = _line("EDDF")
        self.arrival_runway = _line("25C")
        route_grid.addWidget(_field("ORIGIN ICAO", self.origin), 0, 0)
        route_grid.addWidget(_field("DEP RWY", self.departure_runway), 0, 1)
        route_grid.addWidget(_field("DEST ICAO", self.destination), 1, 0)
        route_grid.addWidget(_field("ARR RWY", self.arrival_runway), 1, 1)
        layout.addLayout(route_grid)
        self.fetch_route = QPushButton("PARSE ROUTE TO EUROSCOPE .TXT")
        self.fetch_route.setObjectName("PrimaryButton")
        layout.addWidget(self.fetch_route)
        self.route_text = QPlainTextEdit()
        self.route_text.setMinimumHeight(76)
        layout.addWidget(_field("EUROSCOPE ROUTE STRING (.TXT FORMAT)", self.route_text))

        self.waypoints = QListWidget()
        self.waypoints.setMinimumHeight(86)
        waypoint_buttons = QHBoxLayout()
        self.add_waypoint = QPushButton("ADD")
        self.remove_waypoint = QPushButton("REMOVE")
        self.move_up = QPushButton("UP")
        self.move_down = QPushButton("DOWN")
        for button in (self.add_waypoint, self.remove_waypoint, self.move_up, self.move_down):
            waypoint_buttons.addWidget(button)
        layout.addLayout(waypoint_buttons)
        layout.addWidget(_field("ROUTE TOKENS", self.waypoints))

        layout.addWidget(_divider())
        self.target_title = QLabel("No Target")
        self.target_title.setObjectName("DockCallsign")
        layout.addWidget(_section_title("EuroScope Flight Plan & Target", self.target_title))

        form_grid = QGridLayout()
        self.callsign = _line()
        self.aircraft_type = _line()
        self.wake_category = _line()
        self.squawk = _line()
        self.squawk.setValidator(QRegularExpressionValidator(QRegularExpression("[0-7]{0,4}")))
        self.mode_c = QCheckBox("MODE C")
        self.latitude = _double_spin(-90, 90, 7)
        self.longitude = _double_spin(-180, 180, 7)
        self.altitude = _int_spin(-1000, 60000, 100)
        self.cleared_fl = _int_spin(0, 660, 10)
        self.ground_speed = _int_spin(0, 1200, 10)
        self.heading = _int_spin(1, 360, 1)
        self.ias_variation = _int_spin(-99, 99, 1)
        self.dummy_controller = _line()
        self.perf_profile = _line()
        self.delay = _line()
        self.remarks = QPlainTextEdit()
        self.remarks.setMaximumHeight(70)

        form_grid.addWidget(_field("CALLSIGN", self.callsign), 0, 0)
        form_grid.addWidget(_field("TYPE / WAKE", _row(self.aircraft_type, self.wake_category)), 0, 1)
        form_grid.addWidget(_field("LAT / LON", _row(self.latitude, self.longitude)), 1, 0)
        form_grid.addWidget(_field("SQUAWK & MODE", _row(self.squawk, self.mode_c)), 1, 1)
        form_grid.addWidget(_field("INITIAL / CLEARED FL", _row(self.altitude, self.cleared_fl)), 2, 0)
        form_grid.addWidget(_field("INITIAL IAS / HDG", _row(self.ground_speed, self.heading)), 2, 1)
        form_grid.addWidget(_field("IAS VARIATION", self.ias_variation), 3, 0)
        form_grid.addWidget(_field("TARGET CONTROLLER", self.dummy_controller), 3, 1)
        form_grid.addWidget(_field("PERF PROFILE", self.perf_profile), 4, 0)
        form_grid.addWidget(_field("START DELAY", self.delay), 4, 1)
        layout.addLayout(form_grid)
        layout.addWidget(_field("REMARKS", self.remarks))
        self.commit = QPushButton("UPDATE EUROSCOPE SCENARIO DEFINITION")
        self.commit.setObjectName("PrimaryButton")
        layout.addWidget(self.commit)
        layout.addStretch(1)
        layout.addWidget(_divider())
        layout.addWidget(_section_title("EuroScope Scenario Authoring & Export", ""))
        export_row = QHBoxLayout()
        self.copy_txt = QPushButton("COPY .TXT BLOCK")
        self.generate_ese = QPushButton("GENERATE .ESE ROUTE")
        export_row.addWidget(self.copy_txt)
        export_row.addWidget(self.generate_ese)
        layout.addLayout(export_row)
        self.export_txt = QPushButton("EXPORT EUROSCOPE SCENARIO (.TXT)")
        self.export_txt.setObjectName("PrimaryButton")
        self.sync_repo = QPushButton("SYNC TO EUROSCOPE SCENARIO REPOSITORY")
        layout.addWidget(self.export_txt)
        layout.addWidget(self.sync_repo)

    def _wire_widgets(self) -> None:
        self.fetch_route.clicked.connect(self._show_flightplandb_placeholder)
        self.add_waypoint.clicked.connect(self._add_waypoint)
        self.remove_waypoint.clicked.connect(self._remove_waypoint)
        self.move_up.clicked.connect(lambda: self._move_waypoint(-1))
        self.move_down.clicked.connect(lambda: self._move_waypoint(1))
        self.commit.clicked.connect(self._field_changed)
        for button in (self.copy_txt, self.generate_ese, self.export_txt, self.sync_repo):
            button.clicked.connect(self.export_requested)

        for edit in (
            self.origin,
            self.destination,
            self.callsign,
            self.aircraft_type,
            self.wake_category,
            self.squawk,
            self.dummy_controller,
            self.perf_profile,
            self.delay,
        ):
            edit.textEdited.connect(self._field_changed)
        for spin in (
            self.latitude,
            self.longitude,
            self.altitude,
            self.cleared_fl,
            self.ground_speed,
            self.heading,
            self.ias_variation,
        ):
            spin.valueChanged.connect(self._field_changed)
        self.mode_c.stateChanged.connect(self._field_changed)
        self.remarks.textChanged.connect(self._field_changed)
        self.route_text.textChanged.connect(self._route_text_changed)

    def _set_enabled(self, enabled: bool) -> None:
        for child in self.findChildren(QWidget):
            child.setEnabled(enabled)

    def _clear(self) -> None:
        for edit in (
            self.origin,
            self.departure_runway,
            self.destination,
            self.arrival_runway,
            self.callsign,
            self.aircraft_type,
            self.wake_category,
            self.squawk,
            self.dummy_controller,
            self.perf_profile,
            self.delay,
        ):
            edit.clear()
        self.mode_c.setChecked(False)
        self.latitude.setValue(0)
        self.longitude.setValue(0)
        self.altitude.setValue(0)
        self.cleared_fl.setValue(0)
        self.ground_speed.setValue(0)
        self.heading.setValue(1)
        self.ias_variation.setValue(0)
        self.route_text.clear()
        self.remarks.clear()
        self.waypoints.clear()
        self.target_title.setText("No Target")

    def _field_changed(self) -> None:
        if self._loading or self.aircraft is None:
            return
        aircraft = self.aircraft
        aircraft.callsign = self.callsign.text().strip().upper()
        aircraft.flight_plan.callsign = aircraft.callsign
        aircraft.flight_plan.departure = self.origin.text().strip().upper()
        aircraft.flight_plan.arrival = self.destination.text().strip().upper()
        aircraft.flight_plan.aircraft_type = self.aircraft_type.text().strip().upper()
        aircraft.wake_category = self.wake_category.text().strip().upper()
        aircraft.squawk = self.squawk.text().strip()
        aircraft.mode_c = "1" if self.mode_c.isChecked() else "0"
        aircraft.latitude = self.latitude.value()
        aircraft.longitude = self.longitude.value()
        aircraft.altitude = self.altitude.value()
        aircraft.cleared_flight_level = self.cleared_fl.value()
        aircraft.ground_speed = self.ground_speed.value()
        aircraft.heading_raw = self.heading.value()
        aircraft.ias_variation = self.ias_variation.value()
        aircraft.dummy_controller = self.dummy_controller.text().strip().upper()
        aircraft.perf_profile = self.perf_profile.text().strip()
        aircraft.flight_plan.remarks = self.remarks.toPlainText().strip()
        self._apply_delay_text(aircraft)
        self.target_title.setText(f"{aircraft.callsign} ({aircraft.perf_profile or aircraft.flight_plan.aircraft_type or 'NO PERF'})")
        self.aircraft_changed.emit(aircraft)

    def _route_text_changed(self) -> None:
        if self._loading or self.aircraft is None:
            return
        self.aircraft.editor_route = self.route_text.toPlainText().strip().upper()
        self._refresh_waypoints()
        self.route_changed.emit(self.aircraft)

    def _refresh_waypoints(self) -> None:
        self.waypoints.clear()
        if self.aircraft:
            self.waypoints.addItems(self.aircraft.route_tokens)

    def _add_waypoint(self) -> None:
        if not self.aircraft:
            return
        waypoint, ok = QInputDialog.getText(self, "Add Waypoint", "Waypoint")
        if ok and waypoint.strip():
            self._set_route_tokens([*self.aircraft.route_tokens, waypoint.strip().upper()])

    def _remove_waypoint(self) -> None:
        row = self.waypoints.currentRow()
        if row < 0 or not self.aircraft:
            return
        tokens = self.aircraft.route_tokens
        del tokens[row]
        self._set_route_tokens(tokens)

    def _move_waypoint(self, delta: int) -> None:
        row = self.waypoints.currentRow()
        if row < 0 or not self.aircraft:
            return
        tokens = self.aircraft.route_tokens
        new_row = row + delta
        if not 0 <= new_row < len(tokens):
            return
        tokens[row], tokens[new_row] = tokens[new_row], tokens[row]
        self._set_route_tokens(tokens)
        self.waypoints.setCurrentRow(new_row)

    def _set_route_tokens(self, tokens: list[str]) -> None:
        self.route_text.setPlainText(" ".join(tokens))

    def _show_flightplandb_placeholder(self) -> None:
        QMessageBox.information(
            self,
            "FlightPlanDB",
            "FlightPlanDB querying is reserved for the next slice. "
            "The route assembler already captures origin, destination, runway, and normalized tokens.",
        )

    def _apply_delay_text(self, aircraft: Aircraft) -> None:
        text = self.delay.text().strip()
        if not text:
            aircraft.delay_min = None
            aircraft.delay_max = None
            return
        parts = text.split(":", 1)
        try:
            aircraft.delay_min = int(parts[0])
            aircraft.delay_max = int(parts[1]) if len(parts) > 1 else None
        except ValueError:
            pass


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


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setStyleSheet(APP_STYLESHEET)
        self.setWindowTitle("EuroScope Scenario Studio")
        self.setMinimumSize(1180, 760)

        self.scenario = Scenario()
        self.sector_points: dict[str, SectorPoint] = {}
        self.sector_lines: list[SectorLine] = []
        self.sector_path: Path | None = None
        self.selected: Aircraft | None = None
        self.strip_rows: list[ClickableFrame] = []

        self.canvas = RadarCanvas()
        self.layer_labels: dict[str, QLabel] = {}
        self.range_label = QLabel("40 NM")
        self.cursor_label = QLabel("CTM05 CEILING:NFL195 000 27'42\"W")
        self.scenario_clock = QLabel("00:14:32Z")
        self.stack_count = QLabel("0 ACFT")
        self.strip_count = QLabel("0 STRIPS")
        self.timeline_time = QLabel("00:00:00")
        self.sector_status = QLabel("NO SCT")
        self.editor_dialogs: list[AircraftEditorDialog] = []
        self.diagram_dialog: DiagramDialog | None = None
        self.left_sidebar_collapsed = False
        self.view_layer_actions: dict[str, QAction] = {}
        self.pending_new_aircraft = False

        self._build_menu_bar()
        self._build_tool_bar()
        self._build_window()
        self._wire_events()
        self._load_startup_data()
        self._install_shortcuts()

    def _build_window(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._build_work_area(), 1)
        self.setCentralWidget(root)

    def _build_menu_bar(self) -> None:
        menu_bar = self.menuBar()
        menu_bar.setObjectName("MainMenuBar")

        file_menu = menu_bar.addMenu("Menu")
        self.load_sector_action = QAction("Load Sector Files (.sct)", self)
        self.load_sector_action.setShortcut(QKeySequence("Ctrl+Shift+O"))
        self.load_sector_action.triggered.connect(self.open_sector_file)
        self.load_scenario_action = QAction("Load Scenario (.txt)", self)
        self.load_scenario_action.setShortcut(QKeySequence.Open)
        self.load_scenario_action.triggered.connect(self.open_scenario)
        file_menu.addAction(self.load_sector_action)
        file_menu.addAction(self.load_scenario_action)

        view_menu = menu_bar.addMenu("View")
        search = QAction("Search", self)
        search.setShortcut(QKeySequence.Find)
        search.triggered.connect(self.search_aircraft)
        view_menu.addAction(search)
        view_menu.addSeparator()
        for layer, checked in VIEW_LAYER_DEFAULTS.items():
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

        help_menu = menu_bar.addMenu("Help")
        about = QAction("About EuroScope Scenario Studio", self)
        about.setEnabled(False)
        help_menu.addAction(about)

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

    def _set_view_layer(self, layer: str, visible: bool) -> None:
        self.canvas.set_view_layer_visible(layer, visible)

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
        subtitle = QLabel(".TXT SCENARIO & ESE ENGINE")
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
        export.clicked.connect(self.save_draft_placeholder)
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
        header_layout.setContentsMargins(10, 8, 10, 8)
        self.traffic_title_container = QWidget()
        title_box = QVBoxLayout(self.traffic_title_container)
        title_box.setContentsMargins(0, 0, 0, 0)
        title_box.setSpacing(2)
        title = QLabel("EUROSCOPE TRAFFIC\nSTACK")
        title.setObjectName("DockTitle")
        self.sector_status.setObjectName("SectorStatus")
        title_box.addWidget(title)
        title_box.addWidget(self.sector_status)
        self.collapse_button = QPushButton("<")
        self.collapse_button.setObjectName("CollapseButton")
        self.collapse_button.setFixedSize(28, 28)
        self.collapse_button.clicked.connect(self.toggle_left_sidebar)
        header_layout.addWidget(self.traffic_title_container)
        header_layout.addStretch(1)
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
        self.canvas.aircraft_selected.connect(self.select_aircraft)
        self.canvas.aircraft_double_clicked.connect(self.open_aircraft_editor)
        self.canvas.aircraft_moved.connect(self._aircraft_changed)
        self.canvas.map_clicked.connect(self._place_new_aircraft)
        self.canvas.cursor_geo_changed.connect(self._cursor_changed)
        self.canvas.range_changed.connect(self._range_changed)

    def _install_shortcuts(self) -> None:
        QShortcut(QKeySequence.Delete, self, self.delete_selected_aircraft)
        QShortcut(QKeySequence("R"), self, self.canvas.fit_to_data)
        QShortcut(QKeySequence("I"), self, self.open_aircraft_editor)

    def _load_startup_data(self) -> None:
        if DEFAULT_SECTOR.exists():
            self.load_sector(DEFAULT_SECTOR, refresh=False)
        if SAMPLE_SCENARIO.exists():
            self.load_scenario(SAMPLE_SCENARIO)
        else:
            self._refresh_all()

    def load_sector(self, path: Path, refresh: bool = True) -> None:
        self.sector_points = load_sector_points(path)
        self.sector_lines = load_sector_lines(path, max_lines=8000, balanced=True)
        self.sector_path = path
        self.canvas.hidden_diagram_labels = {"SID": set(), "STAR": set(), "GEO": set()}
        if self.diagram_dialog is not None:
            self.diagram_dialog.close()
        self.sector_status.setText(f"SCT: {path.name}")
        if refresh:
            self._refresh_all()

    def open_sector_file(self) -> None:
        start = str(self.sector_path.parent if self.sector_path else ROOT)
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Load Sector File",
            start,
            "Sector Files (*.sct *.sct2);;All Files (*)",
        )
        if filename:
            self.load_sector(Path(filename))

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
                self.canvas.center_lat = aircraft.latitude
                self.canvas.center_lon = aircraft.longitude
                self.canvas.update()
                return
        point = self.sector_points.get(query)
        if point:
            self.canvas.center_lat = point.latitude
            self.canvas.center_lon = point.longitude
            self.canvas.update()

    def save_draft_placeholder(self) -> None:
        QMessageBox.information(
            self,
            "Export TXT",
            "EuroScope .txt export and repository sync are reserved for the next implementation slice.",
        )

    def add_ils_threshold_placeholder(self) -> None:
        QMessageBox.information(
            self,
            "ILS Threshold",
            "ILS threshold authoring is reserved for the next implementation slice.",
        )

    def select_aircraft(self, aircraft: Aircraft | None) -> None:
        self.selected = aircraft
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

    def _range_changed(self, range_nm: int) -> None:
        self.range_label.setText(f"{range_nm} NM")

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
        self.canvas.set_data(self.scenario, self.sector_points, self.sector_lines, self.selected)
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
        for aircraft in self.scenario.aircraft:
            row = self._flight_strip(aircraft)
            row.clicked.connect(lambda aircraft=aircraft: self.select_aircraft(aircraft))
            row.double_clicked.connect(lambda aircraft=aircraft: self.open_aircraft_editor(aircraft))
            self.strip_layout.insertWidget(self.strip_layout.count() - 1, row)
            self.strip_rows.append(row)

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
        query = text.strip().upper()
        for row in self.strip_rows:
            row.setVisible(query in row.property("searchText"))

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


def _route_runway(route: str, icao: str) -> str:
    if not route or not icao:
        return ""
    match = re.search(rf"\b{re.escape(icao)}/([0-9]{{2}}[LRC]?)\b", route, flags=re.IGNORECASE)
    return match.group(1).upper() if match else ""


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
QComboBox::drop-down {
    border-left: 1px solid #122131;
    width: 18px;
}
QComboBox::down-arrow {
    image: none;
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 6px solid #ffffff;
    margin-right: 5px;
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
QComboBox::drop-down {
    border-left: 1px solid #122131;
    width: 18px;
}
QComboBox::down-arrow {
    image: none;
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 6px solid #ffffff;
    margin-right: 5px;
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
