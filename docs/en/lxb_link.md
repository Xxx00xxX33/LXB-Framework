# LXB-Link

## 1. Scope
`LXB-Link` is the PC-to-Android protocol client layer. It provides reliable command transport and a unified high-level API.

## 2. Architecture
- Client entry: `src/lxb_link/client.py`
- Transport: `src/lxb_link/transport.py`
- Protocol codec: `src/lxb_link/protocol.py`
- Constants and errors: `src/lxb_link/constants.py`

## 3. Core Flow
1. Upper layer calls `LXBLinkClient` APIs (for example `tap`, `find_node`, `dump_actions`).
2. Client encodes command payload.
3. Transport performs reliable send and waits for response.
4. Protocol layer unpacks binary data to Python structures.

## 4. Key Interfaces & Data Shapes
- `find_node(query, match_type, return_mode, multi_match, timeout_ms)`
- `find_node_compound(conditions, return_mode, multi_match, timeout_ms)`
- `dump_actions()` -> `{node_count, nodes, ...}`
- `launch_app(package_name, clear_task, wait)`
- `stop_app(package_name)`

## 5. Failure Modes & Recovery
- Transport failure: timeout, retry exhaustion, invalid response.
- Protocol failure: malformed payload length or field decoding.
- Business failure: no matching node candidates.

## 6. Observability
- Client logs command send/response lifecycle.
- Upper layers should track per-command success and timeout rates.

## 7. Configuration
- Device host and port.
- Command-level timeout settings (`timeout_ms`).

## 8. Constraints & Compatibility
- Runtime semantics are defined by Android-side `LXB-Server` implementation.
- `find_node` and `find_node_compound` return candidates; upper layers still need selection strategy.

## 9. Current Gaps
- Stable matching for dynamic UI still depends on upper-layer heuristics.
- Transport tuning should be validated against real weak-network environments.

## 10. Cross References
- `docs/en/lxb_server.md`
- `docs/en/lxb_map_builder.md`
- `docs/en/lxb_cortex.md`
