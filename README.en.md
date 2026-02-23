# LXB-Framework (English)

## Project Positioning
LXB-Framework is an Android automation system with two core goals:
1. Build reusable navigation maps (LXB-MapBuilder).
2. Route to a target page first, then execute tasks (LXB-Cortex).

## Module Overview
- `LXB-Link`: protocol client and transport adaptation (code: `src/lxb_link`).
- `LXB-MapBuilder`: node-driven mapping engine (code: `src/auto_map_builder`).
- `LXB-Cortex`: Route-Then-Act and FSM runtime (code: `src/cortex`).
- `LXB-Server`: Android-side execution/perception service (code: `android/LXB-Ignition/lxb-core`).
- `LXB-WebConsole`: web control and debugging frontend (code: `web_console`).

## Quick Start
1. Install dependencies
```bash
pip install -r requirements.txt
```

2. Run web console
```bash
cd web_console
python app.py
```

3. Open
- `http://localhost:5000/`

## Documentation Index
- Chinese: `docs/zh/README.md`
- English: `docs/en/README.md`

## Current Capabilities and Limits
- Mapping uses a practical “VLM semantics + XML retrieval binding” strategy.
- Routing phase is designed for deterministic behavior, decoupled from VLM actioning.
- Locator execution is retrieval-first to reduce hard-coded coordinate dependency.

## Compatibility Notes
- Legacy doc paths under `docs/*.md` are kept as migration entry points.
- Current maintained baseline is `docs/zh` and `docs/en`.
