# EuroScope Scenario Studio Prototype

Native Python desktop prototype for editing EuroScope scenario situations. The app is currently a PySide6 workbench that loads a EuroScope scenario `.txt` file such as `WIHH_example.txt`, overlays packaged Indonesia sector database data, and lets us inspect and edit traffic on a dark tactical radar canvas.

The current implementation follows the local PRD and the Stitch reference in `stitch_flight_scenario_route_editor/`, but the source of truth is now the Python app in `ase_editor/`.

Current version: `v1.0.0`.

Version log: see `CHANGELOG.md`.

## Run

```powershell
python -m pip install -r requirements.txt
python -m ase_editor
```

On startup the app loads the scenario sample `WIHH_example.txt` and the packaged Indonesia sector database when available. `WIII_Demo.sct` is now the rebuild source for that database, and `WIII_Demo.txt` is treated as sector/source data, not as the scenario export target for the next milestone.

The Indonesia sector database is stored at `data/sector/indonesia.sqlite3`. Rebuild it after changing `WIII_Demo.sct` with:

```powershell
python -m ase_editor.build_sector_database indonesia
```

## Current Position

We are at `v1.0.0`, the interactive prototype / alpha-workbench baseline.

Implemented checklist:

- [x] App version source in `ase_editor/__init__.py`.
- [x] Startup scenario loading from `WIHH_example.txt`.
- [x] EuroScope scenario parser for aircraft blocks, flight plans, airport altitude, METAR, ILS thresholds, holding data, delay, route, and unknown-line preservation.
- [x] Core data models for scenario, aircraft, flight plan, thresholds, holds, sector points, sector lines, regions, labels, colors, and sector info.
- [x] Full `.sct` sector parsing for points, lines, colors, regions, labels, and `[INFO]`.
- [x] Packaged SQLite sector database at `data/sector/indonesia.sqlite3`.
- [x] Database builder CLI through `python -m ase_editor.build_sector_database indonesia`.
- [x] Packaged Indonesia database loading through `Menu > Load Database > Indonesia`.
- [x] Radar canvas rendering for aircraft, ground vehicles, routes, fixes, ILS/threshold lines, holds, labels, regions, and sector geometry.
- [x] Viewport/spatial indexing for dense sector rendering.
- [x] Theme menu with `vACC Indonesia`, `UK 2026/09`, and manual color editing.
- [x] `View > Info Sector` dialog for structured sector `[INFO]` metadata editing.
- [x] Aircraft workflows for select, search, copy, delete, drag-to-move, and click-to-place new aircraft.
- [x] Aircraft editor popup for callsign, position, squawk, altitude, speed, heading, route, delay, and flight-plan fields.
- [x] Layer toggles, diagram visibility controls, collapsed traffic categories, last-view restore, and settings persistence.
- [x] Parser, sector database, and UI smoke tests for the current baseline.

Still placeholder / not done:

- [ ] EuroScope scenario `.txt` export and save.
- [ ] Parse-edit-export round-trip safety.
- [ ] Scenario edits persisted back to disk.
- [ ] FlightPlanDB integration.
- [ ] Real ILS threshold creation.
- [ ] Sector geometry editing.
- [ ] `.sct` export/write-back.
- [ ] Broader tests for theme editing, sector info saving, database rebuild output, and export behavior.

## Milestone: v1.0.0 Alpha Workbench Baseline

Goal: establish a usable local scenario-editing workbench that can load real sample data, display it geographically, and support in-memory traffic edits.

Status: reached.

Acceptance snapshot:

- Load `WIHH_example.txt` with 14 sample targets.
- Load the packaged Indonesia sector database with points, full line geometry, regions, labels, and colors when available.
- Render aircraft, vehicles, routes, fixes, thresholds, holds, and sector geometry on the radar canvas.
- Select targets from the canvas or strip stack.
- Create a new aircraft from the toolbar and place it on the canvas.
- Edit aircraft and flight-plan fields through the popup editor.
- Toggle view layers and diagram labels, with visibility and last-view settings restored between app launches.
- Inspect and edit sector `[INFO]` metadata from a structured `View > Info Sector` form.
- Switch or manually edit sector color themes from `Theme`.
- Verify parser and UI behavior with `pytest`.

## Future Updates

### v1.1: Saveable Scenario Slice

- Implement EuroScope scenario `.txt` export from the current in-memory scenario, using `WIHH_example.txt` as the reference shape.
- Preserve unknown lines during export so hand-authored scenario content is not lost.
- Add focused tests for parse-edit-export behavior.
- Replace export placeholders with real file save actions.

### v1.2: Round-Trip Safety

- Harden parse-edit-export behavior for global scenario lines, aircraft-local unknown lines, delays, route text, and flight-plan fields.
- Add regression fixtures for less common EuroScope scenario records.

### v1.3: Real Authoring Tools

- Replace the ILS threshold placeholder with a real creation/edit workflow.
- Add validation feedback for aircraft, thresholds, route tokens, and scenario metadata.

### v1.4: FlightPlanDB / Route Tools

- Connect route lookup or import.
- Normalize route tokens and insert generated route text into aircraft flight plans.

### v1.5: Sector Editing

- Move beyond sector display/reference into editable sector metadata, colors, geometry, and eventually `.sct` export.

`WIII_Demo.txt` is not a scenario export target; it mirrors sector data and belongs with `WIII_Demo.sct`.

## Project Layout

- `ase_editor/__main__.py` - CLI entry point for `python -m ase_editor`.
- `ase_editor/models.py` - scenario, aircraft, flight-plan, threshold, hold, and route data models.
- `ase_editor/parser.py` - EuroScope scenario `.txt` parser.
- `ase_editor/sector.py` - full sector parsing helpers for `.sct`-style points, lines, regions, labels, and colors.
- `ase_editor/sector_database.py` - SQLite sector database build/load helpers.
- `ase_editor/build_sector_database.py` - CLI entry point for rebuilding packaged sector databases.
- `ase_editor/theme.py` - built-in sector color presets and `.sct` color-theme helpers.
- `ase_editor/ui.py` - PySide6 app, radar canvas, dialogs, menus, toolbars, and editor workflow.
- `tests/test_parser.py` - parser and sector parsing coverage.
- `tests/test_ui_smoke.py` - offscreen PySide6 smoke tests for the current UI workflow.
- `asset/` - icons used by aircraft, vehicles, toolbar actions, and Qt styles.
- `WIHH_example.txt` - startup scenario sample and next export reference.
- `data/sector/indonesia.sqlite3` - packaged Indonesia sector database loaded by the app.
- `WIII_Demo.sct` - Indonesia sector source used to rebuild the packaged database.
- `WIII_Demo.txt` - sector/source duplicate; not the scenario save/export target.

## Verify

```powershell
python -m pytest -q
```

The UI smoke tests skip automatically when PySide6 is not installed.
