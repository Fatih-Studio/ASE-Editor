# Changelog

## v1.3.0

ILS threshold authoring release.

Implemented:

- Replaces the ILS toolbar placeholder with a compact dark dialog for threshold name, threshold coordinates, and far-end coordinates, with inline errors and Create/Save/Cancel actions.
- Keeps the ILS Thresholds list inside the toolbar popup, alongside the form. Saves keep the popup open for further edits; the main sidebar remains dedicated to traffic.
- Uses upper-right plus, pen, and trash icons and lower-right check/cross actions instead of text buttons. Fields stay read-only until plus or pen is pressed; active creation/editing uses an inverted highlight, and cancel restores the original values and selection.
- Adds a map-pick crosshair to each coordinate panel. Picking temporarily hides the popup, fills only the requested coordinate pair, and leaves changes in the draft until confirmed. Escape returns without changing the draft; scenario replacement and window closure clear pick mode.
- Restyles the compact popup with a navy header/footer, cyan accents, filterable threshold cards, defined count, and coordinate panels. Validation feedback remains readable when resizing.
- Synchronizes threshold list and canvas selection, with segment and endpoint highlighting and double-click editing.
- Routes Delete and I shortcuts to the selected aircraft or threshold while preserving dialog text entry; hidden thresholds remain manageable from the list.
- Adds model-level validation and atomic in-memory creation/editing, including runway-name rules, duplicate detection, coordinate bounds, finite values, seven-decimal precision, and distinct endpoints.
- Preserves object identity, source-record position, extra fields, untouched precision, legacy names, malformed records, and heading-only records during far-end threshold authoring.
- Reuses structure-preserving export and atomic scenario saves. Threshold edits and deletion refresh without refitting the map.

Verified:

- All 112 parser, exporter, sector, save-safety, model, and offscreen UI tests pass, including 49 new threshold tests.
- Inspected the rendered popup and main-window layout and exercised create/edit/save/reload/delete/export against the WIHH sample; original nonblank records were preserved.
- The Windows sandbox test run used workspace-local temporary directories with inherited permissions to avoid the existing pytest directory ACL issue.

Deferred:

- Heading-form authoring, endpoint dragging, undo/redo, broader validation, and automatic route-reference updates.

## v1.2.0

Round-trip safety release.

Implemented:

- Retains ordered source records, duplicates, unknown content, extra fields, and untouched malformed records during export.
- Preserves all `PSEUDOPILOT` placements and global records between aircraft sections.
- Keeps absent and empty optional records distinct, and preserves single-value versus range delays.
- Patches only edited fields; aircraft renames update matching `$FP` and `SIMDATA` callsigns while preserving existing mismatches.
- Makes no-op aircraft dialog saves preserve original values, including raw headings and missing flight plans/delays.
- Writes, flushes, synchronizes, and closes a temporary file before atomic destination replacement; failed saves retain the existing file and active source path.
- Adds uncommon-record fixtures, parse-export-parse stability checks, copy/delete/create coverage, offscreen editor tests, and injected save-failure tests.
- Documents intentional formatting normalization and the save/preservation contract in README.

Verified:

- All 63 parser, exporter, sector, save-failure, and offscreen UI tests pass.
- The Windows sandbox test run used inherited permissions for pytest temporary directories to avoid its restrictive-directory ACL issue.

## v1.1.0

Saveable scenario export release.

Implemented:

- Adds normalized EuroScope scenario `.txt` serialization.
- Preserves global and aircraft-local unknown lines during parse-edit-export.
- Saves edited scenarios through `Menu > Save`, `Menu > Save As...`, and the header export button.
- Adds parse-edit-export regression coverage for sample traffic, edited aircraft fields, unknown lines, and UI save actions.

Verified:

- Parser, exporter, sector database, and UI smoke coverage pass.

## v1.0.0

Baseline interactive workbench release.

Implemented:

- Parses the sample scenario and full sector display data.
- Loads packaged Indonesia sector data from SQLite instead of manual `.sct` selection.
- Adds a `Theme` menu with the current `vACC Indonesia` color preset, a UK 2026/09-inspired preset, and manual sector color editing.
- Adds `View > Info Sector` for inspecting and saving sector `[INFO]` metadata through a structured form.
- Provides the radar canvas, strip stack, layer controls, diagram visibility, and popup aircraft editor.
- Supports in-memory aircraft placement, selection, movement, copy, delete, and edit flows.
- Marks scenario save/export as the next milestone instead of treating it as complete.

Verified:

- Parser, sector database, and UI smoke coverage pass for the v1.0.0 baseline.

Known gaps:

- EuroScope scenario `.txt` export/save is still pending.
- Parse-edit-export round-trip safety is still pending.
- Scenario edits are not persisted back to disk yet.
- FlightPlanDB integration and ILS threshold creation are still placeholder workflows.
- Sector geometry editing and `.sct` export/write-back are not implemented yet.

Planned next:

- `v1.1` Saveable Scenario Slice.
- `v1.2` Round-Trip Safety.
- `v1.3` Real Authoring Tools.
- `v1.4` FlightPlanDB / Route Tools.
- `v1.5` Sector Editing.
