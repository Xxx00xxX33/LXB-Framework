# LXB-Cortex

## 1. Scope
`LXB-Cortex` provides a route-then-act runtime: route to target page first, then execute task actions.

## 2. Architecture
- Code path: `src/cortex`
- Main modules: `route_then_act.py`, `fsm_runtime.py`
- Dependencies: map outputs from `LXB-MapBuilder` and device APIs from `LXB-Link`

## 3. Core Flow
1. Accept user task.
2. Resolve target app and target page.
3. Plan and replay route based on map.
4. Enter action stage after page arrival (VLM/FSM).

## 4. Key Interfaces & Data Shapes
- Route types: `RouteMap`, `RouteEdge`, `RoutePlan`
- Runtime configs: `RouteConfig`, `FSMConfig`
- Web APIs: `/api/cortex/*`

## 5. Failure Modes & Recovery
- Missing route: target page unreachable or map incomplete.
- Route drift: node retrieval mismatch or page shift.
- Recovery: retries, re-routing, app restart and replay.

## 6. Observability
- Task logs include stage transitions, commands, responses, and recovery events.
- Supports task polling and cancellation.

## 7. Configuration
- LLM planner settings (model, temperature, timeout).
- Route retry and FSM execution settings.

## 8. Constraints & Compatibility
- Strongly depends on map quality, especially backbone route completeness.
- Locator semantics must stay aligned with `LXB-MapBuilder` outputs.

## 9. Current Gaps
- High-dynamic pages still challenge stable page arrival checks.
- Interrupt handling quality depends on recovery strategy tuning.

## 10. Cross References
- `docs/en/lxb_map_builder.md`
- `docs/en/lxb_link.md`
- `docs/en/lxb_web_console.md`
