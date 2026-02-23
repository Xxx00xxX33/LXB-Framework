# LXB-WebConsole

## 1. Scope
`LXB-WebConsole` 是统一 Web 调试入口，承载连接管理、命令调试、建图、地图查看与 Cortex 执行。

## 2. Architecture
- 后端：`web_console/app.py`（Flask）
- 前端模板：`web_console/templates/*.html`
- 前端脚本：`web_console/static/js/main.js`

## 3. Core Flow
1. 用户在壳页面建立设备连接。
2. 在子页面执行对应任务：命令调试、建图、路由执行。
3. 前端调用 `/api/*`，后端驱动 `LXB-Link` 与业务模块。
4. 结果以日志、状态和图结构回显。

## 4. Key Interfaces & Data Shapes
- 页面：`/`, `/command_studio`, `/map_builder`, `/map_viewer`, `/cortex_route`
- API 分组：
  - 连接：`/api/connect`, `/api/disconnect`, `/api/status`
  - 命令：`/api/command/*`
  - 建图：`/api/explore/*`, `/api/maps/*`
  - Cortex：`/api/cortex/*`

## 5. Failure Modes & Recovery
- 连接失败：目标设备不可达、会话断开。
- 执行失败：命令超时、返回码异常。
- 建图/路由失败：模块内部异常或状态中断。

## 6. Observability
- 控制台日志按模块与阶段输出。
- 支持任务轮询、运行状态与增量日志读取。

## 7. Configuration
- 连接参数：`host`, `port`
- Cortex 配置：LLM 参数、FSM 参数
- MapBuilder 配置：探索深度、时延、输出目录

## 8. Constraints & Compatibility
- 路由路径保持历史兼容（本轮不改 API 路由）。
- 页面展示命名统一为 LXB 模块风格。

## 9. Current Gaps
- 页面与后端配置项较多，仍需持续分层与精简。
- 大任务日志在长会话下需要更强的筛选策略。

## 10. Cross References
- `docs/zh/lxb_link.md`
- `docs/zh/lxb_map_builder.md`
- `docs/zh/lxb_cortex.md`
