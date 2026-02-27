<div align="center">

# LXB-Framework

### 基于视觉语言模型的 Android 自动化框架

**Route-Then-Act**：构建导航地图，路由到目标页面，然后使用 VLM 指导执行任务。

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/wuwei-crg/LXB-Framework.svg?style=social)](https://github.com/wuwei-crg/LXB-Framework)
[![文档](https://img.shields.io/badge/docs-latest-brightgreen.svg)](docs/zh)

---

[English](README.md) | [中文文档](README.zh.md)

</div>

---

> **在正式开始之前，先叠个甲**
>
> 这是一个本科生的探索性项目，Work in Progress，别抱太高期望。
> 代码目前比较粗糙，很多 Corner Case 没有覆盖，后续也不一定会持续维护更新。
> 只是在折腾的过程中发现"VLM + XML 无障碍树"这个组合挺有意思的，
> 就把思路和实现都记录下来，希望能给同样在这个方向探索的人提供一点参考。
>
> 如果你是相关领域的研究者或工程师，发现了问题或者有更好的想法，
> 欢迎开 Issue 或提 PR，非常感谢。求轻喷——孩子还小，怕生。

---

## 演示

### 构建导航地图

LXB-MapBuilder 自动探索 App，构建可复用的导航图。

<img src="resources/map_building (speed x 5).gif" alt="地图构建（5倍速）" width="700">

构建完成后可视化查看导航图结构：

<img src="resources/map_visualization.gif" alt="地图可视化" width="700">

### Route-Then-Act 执行流程

地图构建完成后，LXB-Cortex 分三个阶段完成任务：

**阶段一 — 初始化与规划**：LLM 基于 App 状态生成路由计划（纯文本，无需截图）。

<img src="resources/Route-then-Act-Init-and-Planning (speed x 2).gif" alt="初始化与规划（2倍速）" width="700">

**阶段二 — 路由导航**：BFS 确定性导航至目标页面，全程零 VLM 调用。

<img src="resources/Route-then_act_routing(real time).gif" alt="路由导航（实时）" width="700">

**阶段三 — 任务执行**：在目标页面上由 VLM 引导完成具体操作。

<img src="resources/Route-then-act-acting(speed x 5)).gif" alt="任务执行（5倍速）" width="700">

---

## 概述

LXB-Framework 是一个面向 Android 自动化的工程体系，核心目标是：

1. **自动构建可复用的应用导航地图**（LXB-MapBuilder）
2. **先路由到目标页面，再使用 VLM 指导执行任务**（LXB-Cortex）

### 核心特性

- **地图驱动自动化**：一次构建应用导航地图，多次复用执行任务
- **Route-Then-Act 模式**：确定性导航 + AI 引导执行
- **VLM-XML 融合**：结合视觉语言模型语义理解与 XML 层次结构实现可靠定位
- **检索优先定位**：使用 resource_id/text 而非硬编码坐标
- **Web 控制台**：统一的调试、建图和任务执行界面

## 架构

![LXB-Framework 架构图](resources/architecture.svg)

## 模块介绍

| 模块 | 描述 | 代码路径 |
| --- | --- | --- |
| **LXB-Link** | 设备通信客户端，可靠 UDP 协议 | `src/lxb_link/` |
| **LXB-Server** | Android 端服务，输入注入和 UI 感知 | `android/LXB-Ignition/` |
| **LXB-MapBuilder** | 使用 VLM+XML 自动构建应用导航地图 | `src/auto_map_builder/` |
| **LXB-Cortex** | Route-Then-Act 自动化引擎，FSM 运行时 | `src/cortex/` |
| **LXB-WebConsole** | Web 调试和任务执行界面 | `web_console/` |

## 快速开始

### 前置要求

- Python 3.9+
- 已安装 Shizuku 的 Android 设备
- VLM API Key（支持 OpenAI 兼容接口）

### 安装

```bash
# 克隆仓库
git clone https://github.com/wuwei-crg/LXB-Framework.git
cd LXB-Framework

# 安装依赖
pip install -r requirements.txt
```

### 启动 Web 控制台

```bash
cd web_console
python app.py
```

然后访问 `http://localhost:5000/`

## 设计理念

### Route-Then-Act

LXB-Framework 将导航与执行彻底分离，而不是每个动作都调用 VLM：

1. **构建地图**：自动生成 App 导航结构图
2. **确定性路由**：BFS 寻路到目标页面，全程零 VLM 调用
3. **任务执行**：在目标页上使用 VLM 指导执行

![LXB-Cortex 状态机](resources/cortex_state_machine.svg)

这种方式减少了 VLM API 调用，提高了可靠性，并实现了任务可重现性。

### VLM-XML 融合

- **VLM** 提供语义理解（这是什么元素？）
- **XML** 提供精确定位（resource_id、bounds）
- **融合** 通过点包含匹配将 VLM 检测结果对齐到 XML 节点

![VLM-XML 融合引擎](resources/fusion_engine.svg)

### 检索优先定位

使用稳定的语义属性（resource_id、content description）而非硬编码坐标来定位元素，确保在不同设备和屏幕尺寸上的可靠性。

## 项目结构

```text
LXB-Framework/
├── android/LXB-Ignition/    # Android 服务 (Shizuku)
├── docs/
│   ├── zh/                  # 中文文档
│   └── en/                  # 英文文档
├── examples/                # 使用示例
├── resources/               # 架构图与演示 GIF
├── src/
│   ├── cortex/              # Route-Then-Act 引擎
│   ├── auto_map_builder/    # 地图构建引擎
│   └── lxb_link/            # 设备通信
└── web_console/             # Web 界面
```

## 贡献

欢迎贡献！请随时提交 Pull Request。

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

---

<div align="center">

**[文档](docs/zh)** | **[示例](examples/)** | **[问题反馈](https://github.com/wuwei-crg/LXB-Framework/issues)**

</div>
