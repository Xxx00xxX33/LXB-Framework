# LXB-WebConsole

## 1. Scope
`LXB-WebConsole` is the unified web entry for connection management, command debugging, map building, map viewing, and Cortex execution.

## 2. Architecture
- Backend: `web_console/app.py` (Flask)
- Frontend templates: `web_console/templates/*.html`
- Frontend scripts: `web_console/static/js/main.js`

## 3. Core Flow
1. User establishes device connection in the shell page.
2. User runs tasks in sub-pages: command debug, mapping, route execution.
3. Frontend calls `/api/*`; backend drives `LXB-Link` and runtime modules.
4. Results are rendered as logs, status, and graph data.

## 4. Key Interfaces & Data Shapes
- Pages: `/`, `/command_studio`, `/map_builder`, `/map_viewer`, `/cortex_route`
- API groups:
  - Connection: `/api/connect`, `/api/disconnect`, `/api/status`
  - Commands: `/api/command/*`
  - Mapping: `/api/explore/*`, `/api/maps/*`
  - Cortex: `/api/cortex/*`

## 5. Failure Modes & Recovery
- Connection failure: device unreachable or disconnected session.
- Execution failure: timeout or non-success response.
- Mapping/routing failure: module runtime exception or interrupted state.

## 6. Observability
- Logs are emitted by module and stage.
- Supports task polling, run status, and incremental log retrieval.

## 7. Configuration
- Connection params: `host`, `port`
- Cortex params: LLM and FSM settings
- MapBuilder params: depth, delay, output directory

## 8. Constraints & Compatibility
- API route paths remain backward compatible in this iteration.
- Display naming is unified under LXB module naming.

## 9. Current Gaps
- Page and backend config surface is still broad.
- Long-running logs need stronger filtering in large sessions.

## 10. Cross References
- `docs/en/lxb_link.md`
- `docs/en/lxb_map_builder.md`
- `docs/en/lxb_cortex.md`
