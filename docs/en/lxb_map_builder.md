# LXB-MapBuilder

## 1. Scope
`LXB-MapBuilder` builds app navigation maps from real-device interaction and outputs pages, transitions, popups, and block pages.

## 2. Architecture
- Code path: `src/auto_map_builder`
- Current primary engine: `node_explorer.py` (`NodeMapBuilder`)
- Archived approaches: `src/auto_map_builder/legacy`

## 3. Core Flow
1. Launch app and collect `screenshot + dump_actions`.
2. Run VLM analysis to extract `PAGE/NAV/POPUP/BLOCK`.
3. Bind VLM points to XML nodes and build locators.
4. Queue node tasks and loop: home-reset -> replay -> tap -> re-analyze.
5. Persist `pages/transitions/popups/blocks` into final map.

## 4. Key Interfaces & Data Shapes
- Entry: `NodeMapBuilder.explore(package_name)`
- Core types: `NodeLocator`, `NavNode`, `Transition`, `NavigationMap`
- Retrieval strategy: `find_node_compound` first, `find_node` fallback (retrieval-only)

## 5. Failure Modes & Recovery
- Binding failure: VLM points cannot map reliably to XML nodes.
- Retrieval failure: no stable candidate from search commands.
- Interrupt failure: popup/block pages break route continuity.
- Recovery actions: retry, app restart, task re-queue.

## 6. Observability
- Real-time logs include VLM stage, binding stage, queue state, and tap chain.
- Failure reasons are emitted by stage for troubleshooting.

## 7. Configuration
- Limits: `max_pages`, `max_depth`, `max_time_seconds`
- Timing/runtime: `action_delay_ms`, `click_delay`, concurrency settings

## 8. Constraints & Compatibility
- Depends on visible XML node quality at runtime.
- Cross-device portability relies on retrieval-based locators rather than fixed coordinate scripts.

## 9. Current Gaps
- Weak-feature nodes remain unstable in highly dynamic screens.
- Semantic drift between VLM and XML still requires operational tuning.

## 10. Cross References
- `docs/en/lxb_link.md`
- `docs/en/lxb_cortex.md`
- `docs/en/lxb_web_console.md`
