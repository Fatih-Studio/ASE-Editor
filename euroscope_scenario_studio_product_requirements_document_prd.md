# Product Requirements Document (PRD): EuroScope Scenario Studio (NextGen)

**Document Version:** 1.0.0  
**Status:** Approved for Implementation  
**Product Category:** ATC Simulation & Scenario Engineering Tool  
**Target Simulator:** EuroScope (v3.2d+ compatible)  
**Reference Legacy Utility:** Craig Phillips ASE (Aircraft Situation Editor)  

---

## 1. Executive Summary & Vision

### 1.1 Problem Statement
In virtual Air Traffic Control networks (such as VATSIM, IVAO, and training organizations), realistic radar simulations are paramount for controller checkout sessions, sweeps, and mentoring. Currently, creating EuroScope scenario files (`.txt`) and associated sector package routes (`.ese`) requires either error-prone manual text file scripting or relying on legacy, 32-bit Windows utilities (like Craig Phillips ASE, built in 2009–2011 on .NET 2.0) that lack modern web convenience, real-time route databases, and intuitive collaborative workflow integrations.

### 1.2 Product Vision
**EuroScope Scenario Studio** is a modern, high-performance web-based scenario authoring environment. It combines an interactive tactical radar scope canvas, direct API integrations with **FlightPlanDB** for instant route parsing, comprehensive EuroScope data structure modeling (Holding stacks, dummy controllers, `.prf` aircraft profiles, IAS variation), and dual export capabilities (`.txt` scenario definition & `.ese` routing blocks) along with EuroScope Scenario Repository syncing.

---

## 2. Target Personas & Use Cases

### 2.1 Personas
1. **ATC Training Mentors & Examiners:** Need to quickly craft complex tactical traffic situations (holding stacks, sequencing bottlenecks, emergencies such as 7700 squawks) for student checkrides.
2. **Facility Engineers & Scenario Authors:** FIR/vACC staff responsible for authoring training packages reflecting seasonal airway shifts, new STARs, and realistic traffic volumes.
3. **Sweeper & Solo Practice Controllers:** Individual controllers seeking customized self-training radar drills with authentic aircraft dynamics and vector responses.

### 2.2 Primary User Stories
- *As an instructor,* I want to import a real-world route from FlightPlanDB between `EGLL` and `EDDF` so that I do not have to look up airway fixes manually.
- *As a scenario designer,* I want an interactive radar scope where I can pan, zoom, click, and drag aircraft spawn vectors, speeds, and altitudes directly on top of SCT2 sector map lines.
- *As a EuroScope specialist,* I want all exported files to strictly adhere to EuroScope's scenario syntax (including dummy controllers, scratchpads, and IAS variation).

---

## 3. System Architecture & Key Modules

```
┌────────────────────────────────────────────────────────────────────────┐
│                     EuroScope Scenario Studio Core                     │
├───────────────────┬───────────────────────────────┬────────────────────┤
│ 1. Radar Scope    │ 2. Traffic Stack & Physics    │ 3. FlightPlanDB    │
│    Engine         │    Manager                    │    & ESE Parser    │
│ • WebGL/Canvas2D  │ • Call sign / Squawk / Type   │ • Origin / Dest ICAO│
│ • SCT2 / ESE Map  │ • Cleared FL / Target IAS     │ • Route string to  │
│ • Range Rings     │ • IAS Variation (±kt)         │   EuroScope syntax │
│ • Vector Leaders  │ • Dummy Controller Ownership  │ • SID/STAR Auto-fix│
├───────────────────┴───────────────────────────────┴────────────────────┤
│ 4. Timeline & Scenario Event Orchestration (00:00 - 01:00:00)          │
│ • Ingress spawns, Controller handoffs, Squawk 7700 alerts, Holds       │
├────────────────────────────────────────────────────────────────────────┤
│ 5. Exporter & Repository Service                                       │
│ • EuroScope Scenario (.txt)  • .ESE Routing Generator • Cloud Repo Sync│
└────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Functional Requirements

### 4.1 Sector & Geo Data Ingestion (`.sct2` & `.ese`)
- **FR-1.1:** System shall parse standard EuroScope `.sct2` sector files including:
  - VORs, NDBs, and Fixes/Intersections with coordinate resolution.
  - High and Low altitude Airways.
  - SIDs, STARs, and Runway centerline projections.
  - FIR geographic boundaries and Coastlines.
- **FR-1.2:** System shall support `.ese` routing files to assign designated coordination points and sector handoff gates.

### 4.2 Tactical Radar Scope Canvas
- **FR-2.1:** Hardware-accelerated radar display replicating realistic CRT/LCD tactical phosphor aesthetics.
- **FR-2.2:** Range scaling toggle (5, 10, 20, 40, 80 NM) with customizable range rings and 30° compass ticks.
- **FR-2.3:** Velocity vector leaders configurable for 1, 2, or 3-minute projections based on assigned Ground Speed (`GS`).
- **FR-2.4:** Tactical Separation Halos (standard 3 NM terminal, 5 NM en-route) around selected radar targets.
- **FR-2.5:** Target data block formatting conforming to EuroScope standard tags:
  - Line 1: `CALLSIGN` | Aircraft Type / Wake Category (`B772/H`) | Assigned Controller (`LL_N`) | Squawk Code (`SQ 4201 [C]`).
  - Line 2: Actual Flight Level (`AFL`) / Cleared Flight Level (`CFL`) | Indicated Airspeed (`IAS`) & Variation (`±kt`).
  - Line 3: Origin `→` Destination `[` Route fix / STAR `]`.

### 4.3 FlightPlanDB Route Integration & Assembler
- **FR-3.1:** Origin/Destination ICAO query engine connected to FlightPlanDB API.
- **FR-3.2:** Automatic route string normalization into EuroScope scenario route line syntax:
  - *Format:* `<WAYPOINT_LIST> | <DISTANCE_NM> | <CRUISE_FL>`.
  - *Example:* `LAM6V LAM DVR UL9 KONAN UL607 SPI UT180 PSA`.
- **FR-3.3:** Automatic association of runway departure (`27L`, `09R`, etc.) and arrival configurations.

### 4.4 Aircraft Physics & Scenario Properties Editor
- **FR-4.1:** Configuration of initial spawn state:
  - Initial 3D Position (`Lat / Lon / Altitude`).
  - Initial Assigned Heading (`001° - 360°`).
  - Initial Indicated Airspeed (`IAS`) and ground performance curve.
- **FR-4.2:** **EuroScope-Specific Parameters**:
  - `IASVARIATION`: Airspeed variation parameter simulating headwind/tailwind variance and FMC throttle deviations.
  - `DUMMY_CONTROLLER`: Binding of simulated controllers (`EGLL_APP`, `LON_C`, `EGLL_TWR`) for automated handoff responses.
  - `PERF_PROFILE`: Binding to EuroScope `.prf` performance definitions (e.g., `A320.prf`, `B772.prf`) governing realistic climb and descent rates.
  - Transponder Squawk & Mode (`Mode A/C` or `Mode S`).

### 4.5 Scenario Event Timeline & Ingress Control
- **FR-5.1:** 60-minute scrubber timeline with second-level precision (`hh:mm:ss`).
- **FR-5.2:** Timeline Event Pins:
  - `T+00:00` initial scenario baseline targets.
  - `T+XX:XX` dynamic ingress spawns (e.g., aircraft enters FIR boundary).
  - Emergency/Tactical triggers (Squawk 7700 squawk shift, Comm failure 7600).
  - Automated hold entry events at designated fix stacks (e.g., `LAM`, `BIG`, `DVR`).

### 4.6 Export & Sync Engine
- **FR-6.1:** One-click generation of native EuroScope `.txt` scenario files according to official EuroScope scenario format specifications.
- **FR-6.2:** Copy-to-clipboard raw `.txt` code block for rapid debugging.
- **FR-6.3:** `.ese` route definition block generator for sector package maintainers.
- **FR-6.4:** Cloud Scenario Repository API synchronization for multi-instructor shared repositories.

---

## 5. Non-Functional Requirements (NFR)

1. **Performance:** Radar canvas rendering must maintain a steady 60 FPS with up to 150 simultaneous targets and 5,000 sector vector primitives.
2. **Browser Compatibility:** Full desktop browser compatibility across Chromium (Chrome, Edge, Brave), Firefox, and Safari with WebGL enabled.
3. **Responsiveness:** Minimum desktop resolution target: `1440 × 900 px`; optimized for dual-monitor workstation layouts (`1920 × 1080 px` and `2560 × 1440 px`).
4. **Data Integrity:** Strict input validation on transponder squawks (4-digit octal `0000 - 7777`), flight levels (`000 - 660`), and headings (`001 - 360`).

---

## 6. Release Roadmap

- **Milestone 1 (MVP - v0.9):**
  - Interactive Radar Scope with basic sector line visualization.
  - FlightPlanDB route query & EuroScope `.txt` export.
  - Manual aircraft spawn and physics editing.
- **Milestone 2 (EuroScope Complete - v1.0 - Current Design Baseline):**
  - Full EuroScope `.prf` profile bindings, dummy controller assignment, and `IASVARIATION`.
  - Timeline scrubber with ingress events and emergency transponder states.
  - Direct `.ese` routing generator.
- **Milestone 3 (Collaborative & Live Testing - v1.2):**
  - Multi-user real-time collaborative editing via WebSocket.
  - Simulated radar preview playback engine within the browser canvas.
  - Direct bi-directional EuroScope Scenario Repository Cloud Sync.
