# Changelog

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
