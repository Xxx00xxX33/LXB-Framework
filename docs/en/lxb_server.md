# LXB-Server

## 1. Scope
`LXB-Server` is the Android-side runtime service that executes protocol commands for input injection, node retrieval, and app lifecycle actions.

## 2. Architecture
- Code path: `android/LXB-Ignition/lxb-core`
- Main components:
  - Protocol and dispatch: `protocol/`, `dispatcher/`
  - Perception engine: `perception/PerceptionEngine.java`
  - Execution engine: input and lifecycle command handlers

## 3. Core Flow
1. Receive binary command frame.
2. Parse command ID and payload.
3. Dispatch to perception or execution logic.
4. Encode and return response.

## 4. Key Interfaces & Data Shapes
- `FIND_NODE`: single-field query.
- `FIND_NODE_COMPOUND`: multi-condition query.
- `DUMP_ACTIONS`: interactive node export.
- App lifecycle commands: `LAUNCH_APP`, `STOP_APP`.

## 5. Failure Modes & Recovery
- Reflection/API access failure.
- UI tree unavailable or transiently empty.
- App lifecycle command failure.

## 6. Observability
- Server logs include command receipt, match counts, and exceptions.
- Use together with WebConsole logs for end-to-end debugging.

## 7. Configuration
- Runtime startup context and Android environment.
- Host app (Ignition) integration settings.

## 8. Constraints & Compatibility
- Matching behavior depends on runtime UI tree visibility.
- Protocol fields must stay aligned with `LXB-Link` definitions.

## 9. Current Gaps
- OEM/ROM differences can change UI tree behavior.
- Some apps with strict protection may limit command effectiveness.

## 10. Cross References
- `docs/en/lxb_link.md`
- `docs/en/lxb_web_console.md`
- `android/LXB-Ignition/README.md`
