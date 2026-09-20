# EuroScope Scenario Studio Prototype

Native Python desktop prototype for editing EuroScope scenario situations. The app is currently a PySide6 workbench that loads a EuroScope scenario `.txt` file such as `WIHH_example.txt`, overlays packaged Indonesia sector database data, and lets us inspect and edit traffic on a dark tactical radar canvas.

The current implementation follows the local PRD, and the source of truth is now the Python app in `ase_editor/`.

Current version: `v1.2.0`.

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

We are at `v1.2.0`, the round-trip safety release.

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
- [x] Structure-preserving EuroScope scenario `.txt` export and atomic save/save-as workflows.
- [x] Parse-export-parse coverage for uncommon records, optional-record absence, duplicate records, safe callsign edits, and save failures.
- [x] Layer toggles, diagram visibility controls, collapsed traffic categories, last-view restore, and settings persistence.
- [x] Parser, exporter, sector database, and UI smoke tests for the current baseline.

Still placeholder / not done:

- [ ] FlightPlanDB integration.
- [ ] Real ILS threshold creation.
- [ ] Sector geometry editing.
- [ ] `.sct` export/write-back.
- [ ] Broader tests for theme editing, sector info saving, and database rebuild output.

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

## Round-Trip and Save Contract

Loaded records retain their order, duplicates, unknown text, and unrecognized extra fields. Untouched records (including malformed or unsupported records) are emitted verbatim apart from line endings and trailing blank lines. Edited records patch only the affected fields. Multiple `PSEUDOPILOT` directives are retained, including directives with no following aircraft. Recognized global records end aircraft context; unknown records retain their original position without guessing their meaning.

Missing `$FP`, `SIMDATA`, `$ROUTE`, and `DELAY` records stay missing unless corresponding data is authored. Present-but-empty records survive. A single delay (`DELAY:5`) remains distinct from a range (`DELAY:5:5`). Accepting the aircraft dialog without changes preserves the original values, including raw heading units and absent optional records.

Renaming or copying an aircraft updates only `$FP` and `SIMDATA` callsign fields that matched its original callsign. Pre-existing mismatches, unknown text, route text, and other fields are preserved. Ordinary edits affect the effective (last) occurrence of duplicate scalar records; earlier occurrences remain intact.

Intentional export normalization:

- UTF-8 without BOM, LF line endings, and one final newline; exact blank-line layout is not guaranteed.
- Generated or edited coordinates use seven decimal places; generated airport altitude uses a decimal representation. Untouched numeric spelling is retained.
- Missing aircraft records that are authored are appended to the aircraft block in `$FP`, `SIMDATA`, `$ROUTE`, `DELAY` order. A new aircraft pilot directive precedes its position record.
- Newly added global records precede loaded records in pilot, altitude, threshold, hold, weather, unknown-record order. New/copied aircraft follow the last original aircraft block, before trailing global records. Loaded records keep their relative order.

Saving first serializes in memory, then writes and flushes a temporary file in the destination directory, synchronizes it to disk, closes it, and replaces the destination. A failure before replacement leaves the existing destination unchanged. Temporary files are removed where possible, the error is shown, and failed Save As does not change the active scenario path. This does not provide backups or crash recovery.

## Future Updates

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
- `ase_editor/records.py` - shared record field maps and original-value snapshots.
- `ase_editor/exporter.py` - structure-preserving EuroScope scenario `.txt` serializer and atomic file writer.
- `ase_editor/sector.py` - full sector parsing helpers for `.sct`-style points, lines, regions, labels, and colors.
- `ase_editor/sector_database.py` - SQLite sector database build/load helpers.
- `ase_editor/build_sector_database.py` - CLI entry point for rebuilding packaged sector databases.
- `ase_editor/theme.py` - built-in sector color presets and `.sct` color-theme helpers.
- `ase_editor/ui.py` - PySide6 app, radar canvas, dialogs, menus, toolbars, and editor workflow.
- `tests/test_parser.py` - parser and sector parsing coverage.
- `tests/test_exporter.py` - parse-edit-export and serializer coverage.
- `tests/test_round_trip.py` and `tests/fixtures/` - uncommon-record, structural preservation, and repeated export coverage.
- `tests/test_save_safety.py` - atomic replacement and injected disk-failure coverage.
- `tests/test_round_trip_ui.py` - no-op editing, callsign changes, copy/delete, and failed-save UI coverage.
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
