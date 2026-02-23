# LXB-MapBuilder

## 1. Scope
`LXB-MapBuilder` 负责基于真实设备交互构建应用导航图，输出页面、跳转边、弹窗与异常页信息。

## 2. Architecture
- 代码路径：`src/auto_map_builder`
- 当前主引擎：`node_explorer.py`（`NodeMapBuilder`）
- 归档方案：`src/auto_map_builder/legacy`

## 3. Core Flow
1. 启动目标应用并采集 `screenshot + dump_actions`。
2. 调 VLM 分析页面，提取 `PAGE/NAV/POPUP/BLOCK`。
3. 将 VLM 节点与 XML 节点绑定并构建 locator。
4. 节点入队，循环执行：回首页 -> 路径重放 -> 点击 -> 再分析。
5. 记录 `pages/transitions/popups/blocks`，最终输出 map。

## 4. Key Interfaces & Data Shapes
- 入口：`NodeMapBuilder.explore(package_name)`
- 核心结构：`NodeLocator`, `NavNode`, `Transition`, `NavigationMap`
- 定位检索：`find_node_compound` 优先，`find_node` 兜底（retrieval-only）

## 5. Failure Modes & Recovery
- 绑定失败：VLM 坐标与 XML 无法可靠对应。
- 定位失败：检索无候选或候选不稳定。
- 中断失败：弹窗/异常页导致链路断开。
- 恢复动作：重试、重启应用、重新入队。

## 6. Observability
- 实时日志包含：VLM 分析、绑定结果、队列状态、点击链路。
- 构建器记录失败原因，便于按阶段排障。

## 7. Configuration
- 探索上限：`max_pages`, `max_depth`, `max_time_seconds`
- 行为参数：`action_delay_ms`, `click_delay`, 并发模式相关参数

## 8. Constraints & Compatibility
- 强依赖当前页面可见 XML 节点质量。
- 多机型通用性依赖检索定位策略，不依赖固定坐标硬编码。

## 9. Current Gaps
- 弱特征节点在高动态页面中仍可能不稳定。
- VLM 与 XML 语义漂移场景下仍需手工调参与复核。

## 10. Cross References
- `docs/zh/lxb_link.md`
- `docs/zh/lxb_cortex.md`
- `docs/zh/lxb_web_console.md`
