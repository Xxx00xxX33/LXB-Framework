# LXB-Link

## 1. Scope
`LXB-Link` 是 PC 侧到 Android 端的协议客户端层，负责可靠发送命令、接收响应并提供统一 API。

## 2. Architecture
- 客户端入口：`src/lxb_link/client.py`
- 传输层：`src/lxb_link/transport.py`
- 协议编解码：`src/lxb_link/protocol.py`
- 常量与错误：`src/lxb_link/constants.py`

## 3. Core Flow
1. 上层调用 `LXBLinkClient` 方法（如 `tap`, `find_node`, `dump_actions`）。
2. 客户端按命令格式编码 payload。
3. 传输层执行可靠发送并等待响应。
4. 协议层解包并转换为 Python 结构。

## 4. Key Interfaces & Data Shapes
- `find_node(query, match_type, return_mode, multi_match, timeout_ms)`
- `find_node_compound(conditions, return_mode, multi_match, timeout_ms)`
- `dump_actions()` -> `{node_count, nodes, ...}`
- `launch_app(package_name, clear_task, wait)`
- `stop_app(package_name)`

## 5. Failure Modes & Recovery
- 网络失败：超时、重试失败、响应校验失败。
- 协议失败：payload 长度/格式不合法。
- 业务失败：目标节点不存在或匹配为空。

## 6. Observability
- 客户端日志记录命令发送与响应结果。
- 上层建议按命令维度统计成功率和超时率。

## 7. Configuration
- 目标设备地址与端口。
- 命令级超时参数（如 `timeout_ms`）。

## 8. Constraints & Compatibility
- 命令语义以 Android 端实现为准（`LXB-Server`）。
- `find_node` 与 `find_node_compound` 均返回候选结果，需要上层做策略选优。

## 9. Current Gaps
- 跨页面动态 UI 的稳定匹配仍依赖上层策略（例如 map_builder 的二次筛选）。
- 协议层调优需要结合真实设备网络条件验证。

## 10. Cross References
- `docs/zh/lxb_server.md`
- `docs/zh/lxb_map_builder.md`
- `docs/zh/lxb_cortex.md`
