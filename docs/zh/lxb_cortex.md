# LXB-Cortex

## 1. Scope
LXB-Cortex 实现 Route-Then-Act 自动化：先用地图路由到目标页面，再执行任务动作。

## 2. Architecture
代码目录：`src/cortex/`

```
src/cortex/
├── __init__.py
├── fsm_runtime.py          # FSM 状态机引擎
├── route_then_act.py       # Route-Then-Act 核心逻辑
└── fsm_instruction.py      # 指令解析器
```

### 模块关系

```
LXB-Link (设备通信)
       │
       v
LXB-Cortex
   ├── Routing Phase   → 路由阶段 (确定性导航)
   └── Action Phase    → 执行阶段 (VLM 指导)
```

## 3. Core Flow

### 3.1 三阶段执行

```
┌─────────────────────────────────────────────────────────┐
│ Phase 1: Planning (规划阶段)                             │
│                                                          │
│  APP_RESOLVE → 选择目标应用                              │
│  ROUTE_PLAN  → 规划目标页面                                │
└─────────────────────────────────────────────────────────┘
                         │
                         v
┌─────────────────────────────────────────────────────────┐
│ Phase 2: Routing (路由阶段)                             │
│                                                          │
│  1. BFS 路径规划：在地图中查找从首页到目标页的最短路径 │
│  2. 路径重放：依次点击路径上的节点                         │
│  3. 路由恢复：处理弹窗、节点缺失等异常                     │
└─────────────────────────────────────────────────────────┘
                         │
                         v
┌─────────────────────────────────────────────────────────┐
│ Phase 3: Action (执行阶段)                               │
│                                                          │
│  FSM 状态机循环 (VISION_ACT):                              │
│    a. 截图 → VLM 分析 → 生成动作                            │
│    b. 执行动作 (TAP/SWIPE/INPUT/BACK)                      │
│    c. 循环检测 → 防止重复无效动作                          │
│    d. DONE → 任务完成                                        │
└─────────────────────────────────────────────────────────┘
```

### 3.2 FSM 状态机

```
         ┌─────────┐
         │  INIT   │  初始化、探测坐标空间
         └────┬────┘
              │
    ┌─────────┴─────────┐
    │   APP_RESOLVE       │  LLM 选择应用
    │   ROUTE_PLAN         │  LLM 规划页面
    └───┬───────────────┬─┘
       │              │
       │              └──> ROUTING
       │
       └──> ROUTING      路由到目标页
              │
              v
         VISION_ACT      视觉执行 (循环)
              │
         ┌──┴──┐
         │DONE │  成功
         └────┘
```

## 4. 坐标空间校准 (Coordinate Calibration)

### 4.1 问题背景

**问题**：VLM 输出的坐标是模型内部坐标系，与设备屏幕像素不匹配

例如：
- VLM 可能返回 [0, 0, 1000, 1000]（归一化坐标）
- 设备屏幕是 [0, 0, 1080, 2400]（像素坐标）
- 不同 VLM 模型的坐标范围不同（有的用 0-1000，有的用 0-1）

### 4.2 校准图像设计

**解决方案**：发送校准图像（四角彩色标记）→ VLM 识别 → 计算映射范围 → 运行时映射

校准图像格式：
- 黑色背景 (RGB: 0, 0, 0)
- 四角 L 形彩色标记（200×200 像素）
  - 左上：红色 (255, 0, 0)
  - 右上：绿色 (0, 255, 0)
  - 右下：蓝色 (0, 0, 255)
  - 左下：黄色 (255, 255, 0)

### 4.3 数学模型

#### 4.3.1 线性缩放模型

使用简单线性变换（非 Homography）：

$$
P_{device} = M \times P_{vlm}
$$

其中：
- $P_{device} = (x_{screen}, y_{screen})^T$ 是屏幕像素坐标
- $P_{vlm} = (x_{vlm}, y_{vlm})^T$ 是 VLM 输出坐标
- $M = \begin{bmatrix} s_x & 0 \\ 0 & s_y \end{bmatrix}$ 是对角缩放矩阵

缩放因子：
$$
s_x = \frac{W_{screen} - 1}{\max_x}, \quad s_y = \frac{H_{screen} - 1}{\max_y}
$$

完整映射公式：
$$
x_{screen} = \left\lfloor \frac{x_{vlm}}{\max_x} \times (W_{screen} - 1) \right\rceil
$$
$$
y_{screen} = \left\lfloor \frac{y_{vlm}}{\max_y} \times (H_{screen} - 1) \right\rceil
$$

#### 4.3.2 校准过程

**步骤 1**：VLM 识别四角标记位置

发送校准图像，VLM 返回：
$$
C_{tl} = (x_{tl}, y_{tl}), \quad C_{tr} = (x_{tr}, y_{tr})
$$
$$
C_{br} = (x_{br}, y_{br}), \quad C_{bl} = (x_{bl}, y_{bl})
$$

**步骤 2**：计算 VLM 坐标范围

$$
\max_x = \max(x_{tl}, x_{tr}, x_{br}, x_{bl})
$$
$$
\max_y = \max(y_{tl}, y_{tr}, y_{br}, y_{bl})
$$

**步骤 3**：运行时坐标映射

```python
def map_coordinates(raw_x, raw_y, max_x, max_y, screen_w, screen_h):
    """
    使用线性缩放映射 VLM 坐标到屏幕坐标

    Args:
        raw_x, raw_y: VLM 输出坐标
        max_x, max_y: 校准得到的 VLM 坐标范围
        screen_w, screen_h: 屏幕尺寸

    Returns:
        (screen_x, screen_y): 屏幕像素坐标
    """
    # 线性映射
    screen_x = int(round((raw_x / max_x) * (screen_w - 1)))
    screen_y = int(round((raw_y / max_y) * (screen_h - 1)))

    return screen_x, screen_y
```

## 5. FSM 形式化定义

### 5.1 五元组定义

定义有限状态机 $M = (S, \Sigma, \delta, s_0, F)$：

- **状态集** $S = \{s_{init}, s_{app\_resolve}, s_{route\_plan}, s_{routing}, s_{vision\_act}, s_{done}, s_{fail}\}$
- **输入字母表** $\Sigma = \{\text{CMD}, \text{RESPONSE}, \text{TIMEOUT}, \text{ERROR}, \text{DONE}, \text{FAIL}\}$
- **转移函数** $\delta: S \times \Sigma \to S$
- **初始状态** $s_0 = s_{init}$
- **接受状态** $F = \{s_{done}\}$

### 5.2 状态转移表

| 当前状态 | 输入事件 | 下一状态 | 动作 |
|----------|----------|----------|------|
| INIT | 设备就绪 | APP_RESOLVE | 启动 LLM 规划 |
| APP_RESOLVE | APP_选定 | ROUTE_PLAN | 规划目标页 |
| ROUTE_PLAN | 路径确定 | ROUTING | 开始路由 |
| ROUTING | 路由成功 | VISION_ACT | 开始执行 |
| ROUTING | 路由失败 × N | FAIL | 路由失败 |
| VISION_ACT | DONE | DONE | 任务完成 |
| VISION_ACT | 超时 × N | FAIL | 执行超时 |
| VISION_ACT | 其他 | VISION_ACT | 继续循环 |

### 5.3 VISION_ACT 循环检测

定义循环状态：
$$
\text{LoopDetected} = (c_{same} \geq 3) \land (a_{stable} \geq 3)
$$

其中：
- $c_{same}$：相同命令连续执行次数
- $a_{stable}$：Activity 保持不变的次数

## 6. BFS 路径规划

### 6.1 图模型定义

定义导航图 $G = (V, E)$：
- **顶点集** $V$：应用中的所有页面（page_id）
- **边集** $E$：页面间的跳转关系（transitions）
- **边权重**：每条边关联一个定位符 $locator(e)$

### 6.2 BFS 算法

```
Algorithm 2: BFS Path Finding for Route-Then-Act
Input: Graph G = (V, E), start vertex s, target vertex t
Output: Shortest path P = [v_0, v_1, ..., v_k] where v_0 = s, v_k = t

1:  if s = t then return [s]
2:
3:  queue ← [(s, [s])]     // (current_vertex, path_so_far)
4:  visited ← {s}
5:
6:  while queue is not empty do
7:      (v, path) ← queue.dequeue()
8:
9:      for each edge e ∈ out_edges(v) do
10:         u ← e.to
11:
12:         if u = t then
13:             return path + [u]
14:         end if
15:
16:         if u ∉ visited then
17:             visited ← visited ∪ {u}
18:             queue.enqueue((u, path + [u]))
19:         end if
20:     end for
21: end while
22:
23:  return ⊥  // No path found
```

### 6.3 周期处理

**问题**：图可能包含环（A → B → A）

**解决方案**：
1. `visited` 集合记录已访问顶点
2. 仅当目标顶点未访问时才入队
3. 确保每个顶点最多被访问一次

## 7. Design Principles

### 7.1 路由阶段确定性
- 使用 BFS 算法确保找到最短路径
- 基于 XML 层次结构定位，不依赖坐标硬编码
- 路径可重现、可验证

### 7.2 执行阶段反思机制
- LLM 每回合输出结构化分析（step_review、reflection）
- 收集 lessons（经验教训）反馈给后续回合
- 防止重复无效动作（循环检测）

### 7.3 分离关注点
- Routing 负责到达目标页（确定性）
- Action 负责执行具体任务（VLM 引导）
- 失败恢复与主流程解耦

## 8. Code Structure

| 文件 | 职责 | 关键类/函数 |
|------|------|--------------|
| `fsm_runtime.py` | FSM 引擎 | `CortexFSMEngine`, `_run_vision_state`, `_probe_coordinate_space` |
| `route_then_act.py` | 路由核心 | `RouteThenActCortex`, `_bfs_path`, `_execute_route` |
| `fsm_instruction.py` | 指令解析 | `parse_instructions`, `validate_allowed` |

## 9. Cross References
- `docs/zh/lxb_map_builder.md` - 地图构建
- `docs/zh/lxb_link.md` - 设备通信
