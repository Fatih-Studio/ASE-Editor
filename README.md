# EuroScope Scenario Studio Prototype

Native Python desktop prototype for editing EuroScope scenario situations. The interface follows the local PRD and the Stitch reference in `stitch_flight_scenario_route_editor/` while keeping the implementation Python-first for this milestone.

## Run

```powershell
python -m pip install -r requirements.txt
python -m ase_editor
```

On startup the app loads `WIHH_example.txt` and, when present, reads fix coordinates plus a bounded sector-line preview from `WIII_Demo.sct`.

## Current Milestone

- Parses the provided EuroScope-style scenario sample.
- Uses a cleaned Stitch-inspired workbench with traffic strip stack and central radar scope.
- Shows aircraft, ground vehicles, ILS/threshold lines, range rings, 30-degree compass ticks, navaid/fix symbols, and basic SCT2 sector lines on a dark tactical radar canvas.
- Supports pan, zoom, aircraft selection, basic drag-to-move, search, copy, delete, and in-memory aircraft edits.
- Uses the icons in `asset/` for aircraft and ground vehicles.
- Shows PRD-style target datablocks for the selected target and compact labels for other targets.
- Opens an ASE-style aircraft editor popup when a radar target or traffic strip is double-clicked.
- Includes mouse-wheel range presets, 3-minute vector leaders, route assembler, and FPDB placeholder controls in the popup editor.
- Keeps EuroScope `.txt` export and FlightPlanDB integration as later milestones.

## Verify

```powershell
python -m pytest -q
```
