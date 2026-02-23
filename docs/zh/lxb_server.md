# LXB-Server

## 1. Scope
`LXB-Server` 是 Android 端服务核心，负责接收协议命令并执行输入注入、节点检索、状态获取等能力。

## 2. Architecture
- 代码路径：`android/LXB-Ignition/lxb-core`
- 核心模块：
  - 协议与分发：`protocol/`, `dispatcher/`
  - 感知引擎：`perception/PerceptionEngine.java`
  - 执行引擎：输入/生命周期相关执行组件

## 3. Core Flow
1. 接收二进制命令帧。
2. 解析命令 ID 与 payload。
3. 分发到对应引擎（感知或执行）。
4. 生成响应并返回客户端。

## 4. Key Interfaces & Data Shapes
- `FIND_NODE`：单字段匹配。
- `FIND_NODE_COMPOUND`：多条件匹配。
- `DUMP_ACTIONS`：可交互节点导出。
- 应用控制：`LAUNCH_APP`, `STOP_APP`。

## 5. Failure Modes & Recovery
- 反射/API 访问失败。
- 节点树不可用或瞬态为空。
- 应用生命周期命令执行失败。

## 6. Observability
- 服务端标准输出日志包含命令接收、匹配数量、异常原因。
- 建议结合 WebConsole 日志做端到端排障。

## 7. Configuration
- 启动参数与设备运行环境。
- 与宿主 App（Ignition）的连接上下文。

## 8. Constraints & Compatibility
- 节点匹配行为由 Android runtime 与 UI 树状态决定。
- 与 `LXB-Link` 协议字段定义需要保持一致。

## 9. Current Gaps
- 不同 ROM/系统版本下 UI 树可见性差异会影响匹配稳定性。
- 部分命令在特定应用（高安全策略）下存在限制。

## 10. Cross References
- `docs/zh/lxb_link.md`
- `docs/zh/lxb_web_console.md`
- `android/LXB-Ignition/README.md`
