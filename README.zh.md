# LXB-Framework

Android 端侧自动化框架（当前主线：**APK 端内闭环**）。

[English](README.md) | [中文](README.zh.md)

本项目已从早期“PC + Android 联动控制台”形态，切换到**手机端主导执行**：
- 用户在 Android App 内直接输入任务
- FSM 在设备端执行
- LLM/VLM 规划与执行循环由端侧服务发起
- 任务与定时调度在 App 内管理

当前阶段：**Alpha / 快速迭代**

---

## 核心能力

### 1) 基于 Map 的 Route-Then-Act

LXB 先构建可复用导航地图，再分两段执行自动化：
- **Route**：从入口页到目标页的确定性导航
- **Act**：到达目标上下文后再进行 VLM 驱动操作

这种设计能显著减少“盲点试错”，提高任务可复现性与稳定性。

### 2) 基于 Shizuku + app_process 的后台运行

LXB 通过 **Shizuku + app_process** 启动 `lxb-core`，而不是依赖：
- 约束较强的 `adb` 流程，或
- 仅依赖 APK 前台生命周期

工程意义：
- 更适合端侧长时运行
- 能支撑定时任务的自动触发与执行
- 相比纯 APK 前台执行，更不容易被常见生命周期波动打断

---

## 快速开始（仅 Android）

### 1. 安装 Shizuku

- GitHub: https://github.com/RikkaApps/Shizuku
- 按 Shizuku 官方说明在手机上启动 Shizuku 服务。

注意：
- 启动 LXB 前，Shizuku 必须处于运行状态。
- 小米/MIUI 建议将 LXB 电池策略设为`无限制`，避免后台被杀。

### 2. 安装 LXB-Ignition APK

- 从 Releases 下载：https://github.com/wuwei-crg/LXB-Framework/releases
- 安装 `lxb-ignition-vX.Y.Z.apk`。

### 3. 授权并启动后端服务

在 LXB App 内：
1. 打开应用，按提示授予 Shizuku 权限。
2. 进入首页。
3. 点击 `Start Service`（通过 Shizuku 拉起端侧 lxb-core 进程）。
4. 确认服务状态为 running。

### 4. 配置模型接口

在 Config 页面设置：
- API Base URL
- API Key
- LLM 模型
- VLM 模型

保存后可先测试简单任务（例如“打开 Bilibili，准备发一条动态”）。

---

## 当前产品形态

- **Map 驱动的 Route-Then-Act 执行**
- **Shizuku/app_process 支撑的后台保活与定时任务**
- FSM 执行链路（init -> app resolve -> route plan -> routing -> vision act）
- 任务队列 + 定时任务执行
- Trace/状态消息实时推送回前端
- 配置/任务/定时任务的端侧持久化

---

## 演示

### 1) MapBuilder - 导航地图构建

<img src="resources/map_building (speed x 5).gif" alt="地图构建（5倍速）" width="700">

### 2) MapBuilder - 图结构可视化

<img src="resources/map_visualization.gif" alt="地图可视化" width="700">

### 3) Auto Run - 自动点咖啡

`[GIF_PLACEHOLDER_AUTO_RUN_ORDER_COFFEE]`

### 4) Auto Run - 完成学习强国答题

`[GIF_PLACEHOLDER_AUTO_RUN_XXQG_QUIZ]`

---

## 架构（占位）

TODO：后续替换为新架构图。

`[ARCHITECTURE_PLACEHOLDER_V2]`

建议架构图模块：
- Android UI 层（Chat / Config / Tasks / Schedules）
- Command Client
- lxb-core 服务（FSM、TaskManager、Scheduler、Trace Push）
- Shizuku Bridge
- Android 系统交互层（输入、截图、Activity、应用生命周期）
- 远程模型接口（LLM/VLM）

---

## 开发者说明

Android 调试安装：

```bash
cd android/LXB-Ignition
./gradlew :app:installDebug
```

本地 release 打包：

```bash
powershell -ExecutionPolicy Bypass -File .\.release_local\release\build_release.ps1 -Version X.Y.Z
```

---

## 许可证

MIT，详见 [LICENSE](LICENSE)。
