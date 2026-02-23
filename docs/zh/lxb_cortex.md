# LXB-Cortex

## 1. Scope
`LXB-Cortex` 提供 route-then-act 执行框架：先用地图路由到目标页，再执行任务动作。

## 2. Architecture
- 代码路径：`src/cortex`
- 核心实现：`route_then_act.py`, `fsm_runtime.py`
- 依赖：`LXB-MapBuilder` 产出的 map + `LXB-Link` 客户端

## 3. Core Flow
1. 输入用户任务。
2. 解析目标应用与目标页面。
3. 基于 map 做路径规划与重放。
4. 到达目标页后进入动作阶段（可结合 VLM/FSM）。

## 4. Key Interfaces & Data Shapes
- 路由核心类型：`RouteMap`, `RouteEdge`, `RoutePlan`
- 运行配置：`RouteConfig`, `FSMConfig`
- Web API：`/api/cortex/*`

## 5. Failure Modes & Recovery
- 路径缺失：目标页不可达或 map 不完整。
- 路由漂移：节点检索失败或页面状态偏移。
- 恢复策略：重试、重路由、重启应用后回放。

## 6. Observability
- 任务级日志包含阶段、命令、响应与恢复事件。
- 支持轮询任务状态与取消操作。

## 7. Configuration
- LLM 规划参数（模型、温度、超时）。
- 路由重试参数与 FSM 执行参数。

## 8. Constraints & Compatibility
- 依赖 map 质量，尤其是关键页面链路完整性。
- 与 `LXB-MapBuilder` 的 locator 语义必须一致。

## 9. Current Gaps
- 高动态页面下，目标页判定与回放稳定性仍需持续优化。
- 中断场景（弹窗、风控）恢复仍依赖策略配置。

## 10. Cross References
- `docs/zh/lxb_map_builder.md`
- `docs/zh/lxb_link.md`
- `docs/zh/lxb_web_console.md`
