# LXB-Framework（中文）

## 项目定位
LXB-Framework 是一个面向 Android 自动化的工程体系，核心目标是：
1. 构建可复用的页面导航图（LXB-MapBuilder）。
2. 先路由到目标页，再执行任务（LXB-Cortex）。

## 模块总览
- `LXB-Link`：设备通信客户端与协议适配（代码：`src/lxb_link`）。
- `LXB-MapBuilder`：节点驱动建图引擎（代码：`src/auto_map_builder`）。
- `LXB-Cortex`：Route-Then-Act 与 FSM 执行（代码：`src/cortex`）。
- `LXB-Server`：Android 端执行/感知服务（代码：`android/LXB-Ignition/lxb-core`）。
- `LXB-WebConsole`：Web 控制台与调试入口（代码：`web_console`）。

## 快速启动
1. 安装依赖
```bash
pip install -r requirements.txt
```

2. 启动控制台
```bash
cd web_console
python app.py
```

3. 访问
- `http://localhost:5000/`

## 文档索引
- 中文：`docs/zh/README.md`
- 英文：`docs/en/README.md`

## 当前能力与限制
- 建图采用“VLM 语义 + XML 检索绑定”的实用策略。
- 路由阶段强调确定性，可与 VLM 执行阶段解耦。
- 定位策略以检索为主（retrieval-first），避免坐标硬编码依赖。

## 兼容说明
- 本仓库保留历史文档路径（`docs/*.md`）作为迁移入口。
- 当前维护基线以 `docs/zh` 与 `docs/en` 为准。
