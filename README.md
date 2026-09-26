# EuroScope Scenario Studio Prototype

Native Python desktop prototype for editing EuroScope scenario situations. The app is currently a PySide6 workbench that loads a EuroScope scenario `.txt` file such as `WIHH_example.txt`, overlays packaged Indonesia sector database data, and lets us inspect and edit traffic on a dark tactical radar canvas.

The current implementation follows the local PRD, and the source of truth is now the Python app in `ase_editor/`.

Current version: `v1.4.0`.

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

We are at `v1.4.0`, the FlightPlanDB routes and checkpoint suggestions release.

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
- [x] ILS threshold popup with integrated list management, creation/editing, canvas selection, validation, and deletion.
- [x] FlightPlanDB generation, compact flight-plan route import, and editable simulation checkpoint suggestions.
- [x] Structure-preserving EuroScope scenario `.txt` export and atomic save/save-as workflows.
- [x] Parse-export-parse coverage for uncommon records, optional-record absence, duplicate records, safe callsign edits, and save failures.
- [x] Layer toggles, diagram visibility controls, collapsed traffic categories, last-view restore, and settings persistence.
- [x] Parser, exporter, sector database, and UI smoke tests for the current baseline.

Still placeholder / not done:

- [ ] Broader aircraft, route-token, and scenario-metadata validation.
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

## ILS Threshold Authoring

Click **ILS Threshold** in the toolbar to open the popup. Its left-hand list contains existing thresholds; the right-hand form contains only the threshold name, threshold latitude/longitude, and far-end latitude/longitude. Fields are read-only until you press the **pen** icon to edit or the **+** icon at the upper right to create a new threshold. The active pen or plus stays highlighted with inverted colors. Opening this dialog cancels aircraft placement mode.

During creation or editing, use the **check** icon at the lower right to apply changes or the **cross** to discard the draft. Both keep the popup open and return the fields to read-only mode. The list and filter are disabled during a draft. Icon actions have tooltips and accessible names; the old text buttons below the list and in the footer are removed.

Each coordinate panel has a **crosshair** icon for choosing its position from the map. It is enabled only while creating or editing. Click it to temporarily hide the popup, then left-click the map to fill that panel's latitude and longitude to seven decimal places. You can pan and zoom before choosing. **Escape** cancels the pick and returns to the unchanged draft. Picking does not move aircraft or apply the draft; press the check icon to commit the threshold changes.

The configuration popup uses a compact dark navy layout with cyan accents, a filterable threshold list, and separate coordinate panels. The defined count and coordinate summaries come from the current scenario. Filtering out the selected threshold clears selection so Edit/Delete cannot act on a hidden result.

Authored records use the far-end coordinate form from `WIHH_example.txt`:

```text
ILS<runway name>:<threshold latitude>:<threshold longitude>:<far end latitude>:<far end longitude>
ILS06:-6.2722343:106.8787898:-6.2609290:106.9036165
```

Names are trimmed and uppercased; new or renamed thresholds must use `ILS01`–`ILS36`, optionally followed by `L`, `C`, or `R`. Names must be unique ignoring case. Coordinates must be finite, with latitude within ±90 and longitude within ±180. Authored coordinates use seven decimal places, and the two positions must differ at that precision. Validation errors appear beside the fields and leave the scenario unchanged.

Click a popup list row to view its fields and center the canvas on its midpoint, or click its visible canvas segment to select without moving the map. Double-click a canvas threshold to open its configuration, or use **I**; the pen must still be pressed to unlock editing. The **trash** icon removes the selected threshold immediately and is disabled during editing. Aircraft take priority where canvas targets overlap. Hidden thresholds remain available in the popup list. Close the popup and use the existing **Save Scenario** / **Save Scenario As** actions to persist changes to disk.

Editing preserves the existing object and source record, including extra fields and untouched coordinate precision. The cross or **Escape** in the popup cancels the current draft and restores the prior selection; **Escape** in read-only mode closes the popup. Closing the window also discards any unsaved draft. Changes already applied with the check or trash remain in the scenario. Unchanged saves preserve the original data. Unchanged legacy names remain editable, though actual edits must pass coordinate and duplicate validation. The heading-only form (`ILS<runway name>:<threshold latitude>:<threshold longitude>:<runway heading>`) remains preserved as raw text and is not shown in the authoring list. Renaming a threshold does not rewrite aircraft route text. Endpoint dragging and undo/redo are deferred.

## FlightPlanDB Routes and Checkpoints

For one-time setup, install the dependencies with `python -m pip install -r requirements.txt`. Create a `.env` file beside this README (copy `.env.example` if needed), then add your key:

```dotenv
FLIGHTPLANDB_API_KEY=your-api-key-here
```

Save the file and launch with `python -m ase_editor`. The app automatically reads this project-local file at startup, including when launched from another working directory. Restart the app after changing the key. `.env` and `.env.*` are excluded from Git; `.env.example` contains only an empty template. Keep real keys out of tracked files and shared copies of the project.

Existing environment variables take precedence over `.env`, so a permanent Windows user environment variable is also supported. To use a temporary terminal override:

```powershell
$env:FLIGHTPLANDB_API_KEY = "<your-api-key>"
python -m ase_editor
```

Open an aircraft editor, enter different four-letter departure and arrival ICAOs, and click **FlightPlanDB**. Generation uses the current editor fields, including unsaved edits. Cruise altitude accepts feet (`35000`) or a flight level (`FL350`, `F350`); cruise airspeed accepts knots (`420`, `N0420`). Leave these fields blank to use the service defaults. Mach and metric notation are not supported in this release.

The app generates a remote plan and fetches its nodes, then fills the **FlighPlan** draft with compact airway text, for example `WIII DCT KASAL G461 SBR W33 RABOL DCT WADD`. Direct legs use `DCT`; unsupported track/procedure compression retains the individual fixes. A status message reports the airports, waypoint count, distance and request quota when available. Generation creates a plan on FlightPlanDB even if you later discard the local draft. Requests are not automatically retried; a timeout may occur after a remote plan has already been created. Authentication, quota, network and invalid-response failures leave your drafts intact.

**FlighPlan** is the complete filed route in `$FP`. **Checkpoints** is the separate sequence stored in `$ROUTE` that the scenario aircraft follows from its current position. Importing a flight-plan route preserves existing checkpoints. The radar prefers nonempty `$ROUTE` and continues resolving identifiers against the loaded sector database; generated fixes absent from that database remain in the text but are not drawn.

After generation, click **Suggest checkpoints**. The preview proposes a downstream waypoint from the nearest route segment, using heading to distinguish nearby segments. It uses the current editor position and heading, and shows the distance from the suggested segment. Review the first-checkpoint selector and the editable remaining fixes. Each selector entry includes its sequence number so repeated identifiers can be selected separately. Changing the first checkpoint rebuilds the preview. The old checkpoints are shown as reference; you can manually replace the destination airport ending with your approach, for example `ELNIR KOMIT ILS24`. The app does not infer runways or automatically join approach routes.

**Apply checkpoints** copies the preview into the checkpoint draft; **Cancel** leaves that draft unchanged. **Save** in the aircraft editor applies both drafts to the aircraft. Close or Escape discards unsaved edits. Use **Save Scenario** / **Save Scenario As** to write the scenario file. Editing the generation inputs or filed route invalidates checkpoint suggestions; if edited during a request, its result is discarded. The editor remains responsive while generating, with duplicate generation and Save temporarily disabled.

Using data from the [Flight Plan Database](https://flightplandatabase.com). See its [API documentation](https://flightplandatabase.com/dev/api) for authentication, generation, units, and request limits. FlightPlanDB data is for flight simulation.

## Future Updates

ILS threshold authoring shipped in v1.3; FlightPlanDB generation and checkpoint suggestions shipped in v1.4. Route search, runway selection, automatic approach merging, additional navigation data loading, and broader validation remain future work.

### v1.5: Sector Editing

- Move beyond sector display/reference into editable sector metadata, colors, geometry, and eventually `.sct` export.

`WIII_Demo.txt` is not a scenario export target; it mirrors sector data and belongs with `WIII_Demo.sct`.

## Project Layout

- `ase_editor/__main__.py` - CLI entry point for `python -m ase_editor`.
- `ase_editor/models.py` - scenario, aircraft, flight-plan, threshold, hold, and route data models.
- `ase_editor/parser.py` - EuroScope scenario `.txt` parser.
- `ase_editor/records.py` - shared record field maps and original-value snapshots.
- `ase_editor/exporter.py` - structure-preserving EuroScope scenario `.txt` serializer and atomic file writer.
- `ase_editor/flightplandb.py` - API client, input normalization, typed generation results, and safe error handling.
- `ase_editor/route_tools.py` - compact airway formatting and position/heading-based checkpoint suggestions.
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
- `tests/test_thresholds.py` and `tests/test_threshold_ui.py` - threshold validation, create/edit/delete, preservation, selection, shortcuts, and save/reload coverage.
- `tests/test_ui_smoke.py` - offscreen PySide6 smoke tests for the current UI workflow.
- `tests/test_flightplandb.py`, `tests/test_route_tools.py`, and `tests/test_flightplandb_ui.py` - mocked API, route conversion, checkpoint preview, and asynchronous editor coverage.
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
