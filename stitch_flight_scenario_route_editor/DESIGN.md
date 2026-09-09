---
name: Vector Tactical ATC
colors:
  surface: '#051424'
  surface-dim: '#051424'
  surface-bright: '#2c3a4c'
  surface-container-lowest: '#010f1f'
  surface-container-low: '#0d1c2d'
  surface-container: '#122131'
  surface-container-high: '#1c2b3c'
  surface-container-highest: '#273647'
  on-surface: '#d4e4fa'
  on-surface-variant: '#bcc9cd'
  inverse-surface: '#d4e4fa'
  inverse-on-surface: '#233143'
  outline: '#869397'
  outline-variant: '#3d494c'
  surface-tint: '#4cd7f6'
  primary: '#4cd7f6'
  on-primary: '#003640'
  primary-container: '#06b6d4'
  on-primary-container: '#00424f'
  inverse-primary: '#00687a'
  secondary: '#4edea3'
  on-secondary: '#003824'
  secondary-container: '#00a572'
  on-secondary-container: '#00311f'
  tertiary: '#ffb95f'
  on-tertiary: '#472a00'
  tertiary-container: '#e79400'
  on-tertiary-container: '#563400'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#acedff'
  primary-fixed-dim: '#4cd7f6'
  on-primary-fixed: '#001f26'
  on-primary-fixed-variant: '#004e5c'
  secondary-fixed: '#6ffbbe'
  secondary-fixed-dim: '#4edea3'
  on-secondary-fixed: '#002113'
  on-secondary-fixed-variant: '#005236'
  tertiary-fixed: '#ffddb8'
  tertiary-fixed-dim: '#ffb95f'
  on-tertiary-fixed: '#2a1700'
  on-tertiary-fixed-variant: '#653e00'
  background: '#051424'
  on-background: '#d4e4fa'
  surface-variant: '#273647'
typography:
  headline-lg:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: 0em
  body-lg:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-md:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  label-lg:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-md:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 14px
    letterSpacing: 0.03em
  label-sm:
    fontFamily: JetBrains Mono
    fontSize: 10px
    fontWeight: '500'
    lineHeight: 12px
    letterSpacing: 0.04em
  code-datablock:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '700'
    lineHeight: 13px
    letterSpacing: 0.05em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  space-2xs: 0.125rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1rem
  space-xl: 1.5rem
  space-2xl: 2rem
  panel-dock-width: 20rem
  panel-strip-width: 16rem
  timeline-shelf-height: 4.5rem
  tactical-toolbar-height: 2.75rem
---

## Brand & Style

This design system delivers a high-density, mission-critical workspace tailored for air traffic controllers, simulation engineers, and VATSIM airspace designers. The visual philosophy translates the specialized functionalism of terminal radar approach control (TRACON) and en-route centers into a refined desktop web application.

The emotional signature is razor-sharp precision, calm control under high data load, and tactical depth. It blends modern tactical Glassmorphism with authentic radar vector graphics:
- **Atmospheric Obsidian:** Deep, calibrated dark foundations eliminate night-ops eye fatigue while allowing phosphor-bright elements to punch through without visual noise.
- **Phosphor Vector Fidelity:** Dynamic vector data (targets, velocity vectors, route ribbons, separation halos) evokes specialized CRT radar scopes modernized with subtle luminescence.
- **Instrument Precision:** Monospaced metric alignment, tight operational clearances, and zero unnecessary visual ornament. Every pixel, line weight, and tone communicates state, altitude, or spatial intent.

## Colors

The palette is engineered specifically for situational awareness in an information-dense environment. It operates exclusively in dark mode.

### Scope & Surface Tokens
- **Canvas Base (`#060a12`):** Primary radar void with an ultra-subtle coordinate grid.
- **Surface Elevation 1 (`#0a0f18`):** Scope sub-layers, sector sectorization fills, range ring strokes.
- **Surface Elevation 2 (`#0f172a`):** Docked sidebars, scenario timeline shelf, and primary toolbars.
- **Surface Floating (`#131d2e`):** Detachable flight strip bays, popover menus, datablock inspector modals.
- **Surface Border Glass (`rgba(56, 189, 248, 0.14)`):** Crisp edge definition for panel separation.

### Tactical Data & Phosphor Accents
- **Vector Cyan (`#06b6d4` / `#38bdf8`):** Primary radar targets, active flight plans, selected vector lines, and primary callout tags. Emits a calibrated 4px outer bloom (`rgba(6, 182, 212, 0.35)`).
- **Phosphor Emerald (`#10b981` / `#34d399`):** Established state, assigned altitudes reached, handoff acknowledged, standard navigation fixes, and VOR/NDB nodes.
- **Tactical Amber (`#f59e0b`):** Altitude deviation warnings, route conflict alerts (STCA), squawk emergency alerts (7700/7600), and scrubber scrub markers.
- **Threat Crimson (`#ef4444`):** Minimum Safe Altitude Warning (MSAW), active loss of separation, critical scenario errors.
- **Muted Radar Slate (`#475569` / `#64748b`):** Inactive flight tracks, sector boundary baselines, historical track breadcrumbs, and ghost targets.

## Typography

Typography balances ergonomic UI controls with strict FAA/Eurocontrol datablock legibility.

- **Dual-Engine Model:** `Inter` handles operational tooling, dropdown menus, scenario metadata dialogs, and dock management. `JetBrains Mono` governs all telemetry, radar callsign datablocks, flight strips, coordinate displays, and heading/altitude readout tags.
- **Tabular Figures & Scannability:** All numeric values must use `font-variant-numeric: tabular-nums` to ensure jitter-free telemetry updates as aircraft climb, turn, and accelerate.
- **Radar Datablock Format:** Aircraft tags leverage `code-datablock` arranged in a 2 to 3-line format (Line 1: Callsign & Wake Category; Line 2: Assigned/Current Altitude & Groundspeed; Line 3: Destination & Squawk). All characters are capitalized for rapid cognition.

## Layout & Spacing

The layout is built for high-resolution desktop viewports (1920×1080 and ultrawide tactical displays), utilizing a full-viewport canvas architecture with zero-scroll window containment.

- **Primary Radar Canvas:** Occupies 100% of the viewport substrate. All UI panels float or dock directly over this coordinate plane.
- **Docking Rails & Layout Anchors:**
  - **Top Tactical Bar (`tactical-toolbar-height`):** Quick tools (Range zoom, separation ring rings toggle, sector presets, scenario run/pause state, simulation speed multiplier: 1x/2x/4x/8x).
  - **Left Navigation & Outliner Dock (`panel-dock-width`):** Flight plan tree, waypoint catalog, sector boundaries, and FlightPlanDB importer.
  - **Right Flight Strip & Inspector Dock (`panel-strip-width`):** Electronic flight progress strips (FPS), target details, and assigned cleared routing.
  - **Bottom Scenario Scrubber Shelf (`timeline-shelf-height`):** Keyframe scrubber, event triggers, conflict prediction timelines, and scenario recording markers.
- **Compact Spacing Rhythm:** Built on a strict 4px base increment (`space-xs` to `space-md`), minimizing padding to maximize data density per screen inch while maintaining clear visual hierarchy.

## Elevation & Depth

This system avoids heavy drop-shadows typical of consumer apps, replacing them with translucent luminescence, edge highlights, and high-frequency backdrop blurs that evoke night avionics displays.

- **Layer 0 (Canvas Base):** Infinite dark grid plane with range rings rendered at 8% opacity cyan strokes.
- **Layer 1 (Glassmorphic Docks & Rails):** `background: rgba(15, 23, 42, 0.78); backdrop-filter: blur(16px); border: 1px solid rgba(56, 189, 248, 0.12); box-shadow: 0 4px 20px rgba(0, 0, 0, 0.45);`
- **Layer 2 (Detached Toolbars & Context Menus):** `background: rgba(19, 29, 46, 0.90); backdrop-filter: blur(20px); border: 1px solid rgba(56, 189, 248, 0.28); box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6);`
- **Vector Target Bloom:** Aircraft blips, velocity leader lines, and separation rings feature hardware-accelerated CSS drop-filters (`drop-shadow(0 0 3px rgba(6, 182, 212, 0.6))`) to simulate phosphor CRT glow without reducing reading clarity.

## Shapes

The design uses tight, technical corners (`roundedness: 1`). 

- Standard inputs, dock tabs, and radar datablock cards use 2px to 4px border radii to project an industrial, military-spec hardware feel.
- Waypoint icons and navigation aids use crisp geometric forms: equilateral triangles for reporting fixes, octagons for VORs, squares with center dots for NDBs, and small diamond/square blips for primary radar returns.
- Flight progress strip bays retain sharp, carded edges with 2px dividers, honoring the physical format of traditional wooden and plastic ATC strip holders modernized for digital screens.

## Components

### Aircraft Targets & Datablocks
- **Primary Blip:** A 6×6px diamond or cross marker indicating current coordinate. A 1px line (velocity vector leader) extends forward proportional to ground speed (e.g., 1-minute, 2-minute, or 3-minute prediction tick marks).
- **Leader Line:** A 1px angled cyan line linking the blip to the three-line datablock. The datablock supports click-and-drag re-positioning across 8 compass quadrants to deconflict overlapping radar tags.
- **Status Accents:** Uncontrolled traffic appears in Slate (`#64748b`); active controlled aircraft glow in Cyan (`#06b6d4`); handoff-ready aircraft flash in Phosphor Emerald (`#10b981`); conflict warnings trigger an Amber (`#f59e0b`) pulse box around the tag.

### Electronic Flight Progress Strips (FPS)
- Segmented rectangular blocks featuring callsign, aircraft type, squawk code, assigned flight level (AFL), cleared flight level (CFL), departure/destination ICAO, and route fix times.
- State changes (e.g., clearance delivery, pushback, taxi, takeoff) update the strip's left border status indicator (3px vertical colored strip).
- Draggable reordering allows controllers to sequence departures and arrivals vertically.

### Tactical Buttons & Mode Selectors
- **Primary Action (Run / Insert Target):** Filled cyan button (`#06b6d4`) with dark text (`#060a12`), active phosphor highlight, 4px radius, `font-weight: 600`.
- **Secondary Action (Range / Layer Toggles):** Ghost surface with semi-transparent cyan borders (`border: 1px solid rgba(56, 189, 248, 0.25)`), transitioning to 40% fill on hover.
- **State Switchers (1x, 2x, 4x, Pause):** Monospaced segmented button group with crisp 1px active separator borders.

### Scenario Timeline & Scrubber
- Full-width bottom dock displaying scenario duration (HH:MM:SS format).
- Features dual-tier ruler markings (minutes and seconds), event keyframe markers (e.g., altitude change, engine failure injection, weather front cross), and draggable scrubber playhead glowing in Tactical Amber.

### Inputs & Vector Parameter Controls
- Inputs (Heading ° selector, Altitude FL stepper, Airspeed knots) feature embedded unit labels inside the right rail of the input field (e.g., `FL340`, `HDG 270°`, `250 KT`).
- Dark obsidian fill (`#0b1320`), monospaced value text, and active 1px glowing cyan border when focused.