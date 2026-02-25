# LXB-MapBuilder

## 1. Scope
LXB-MapBuilder 负责基于真实设备交互构建应用导航图，输出页面、跳转边、弹窗信息。

## 2. Architecture
代码目录：`src/auto_map_builder/`

```
src/auto_map_builder/
├── __init__.py
├── node_explorer.py        # 主引擎：节点驱动建图 (v5)
├── fusion_engine.py        # VLM-XML 融合引擎
├── vlm_engine.py          # VLM API 封装
├── models.py               # 数据结构定义
└── legacy/                 # 归档策略 (v1-v4)
```

### 模块关系

```
LXB-Link (设备交互)
       │
       v
NodeMapBuilder
       │
       ├──> VLM Engine (视觉分析)
       │      └── 识别页面类型、可交互元素
       │
       └──> Fusion Engine
              └── VLM+XML 节点融合
```

## 3. Core Flow

### 3.1 建图主流程

```
1. 启动应用 → 首页分析
   │
   v
2. VLM 分析首页 → 识别 NAV 节点 (导航元素)
   │
   v
3. 遍历 NAV 节点 → 点击 → 分析新页面
   │
   v
4. 判断页面类型：
   - PAGE → 入队待探索
   - NAV → 跳过
   - POPUP → 记录并关闭
   - BLOCK → 等待或重试
   │
   v
5. 路径重放 → 从首页回到目标页
   │
   v
6. 递归探索 → 深度优先 (DFS)
   │
   v
7. 生成地图 JSON → 保存文件
```

### 3.2 VLM 页面分类

| 类型 | 说明 | 处理 |
|------|------|------|
| PAGE | 独立功能页面，有多个可交互元素 | 创建页面节点，探索 NAV 节点 |
| NAV | 导航元素 (标签、菜单、按钮) | 点击进入其他页面 |
| POPUP | 弹窗、广告遮罩 | 记录定位符并关闭 |
| BLOCK | 加载中、空状态 | 等待或重试 |
| NODE | 可交互元素 (按钮、输入框) | 绑定 XML，创建定位符 |

## 4. VLM-XML 融合算法 (核心创新)

### 4.1 融合原理

```
VLM 检测 (bbox + label)
        +
XML 节点 (bounds + resource_id)
        ↓
    IoU 计算 (重叠度)
        ↓
   选择最佳匹配
        ↓
  FusedNode (VLM 语义 + XML 属性)
```

**融合意义**：
- VLM 提供语义理解 (这是什么按钮)
- XML 提供精确定位 (resource_id, bounds)
- 结合两者得到可靠的自动化定位符

### 4.2 数学形式化定义

#### 4.2.1 IoU (Intersection over Union) 计算

给定两个边界框：
- VLM 检测框：$B_{vlm} = (x_1^{vlm}, y_1^{vlm}, x_2^{vlm}, y_2^{vlm})$
- XML 节点框：$B_{xml} = (x_1^{xml}, y_1^{xml}, x_2^{xml}, y_2^{xml})$

IoU 定义为：

$$
\text{IoU}(B_{vlm}, B_{xml}) = \frac{A(B_{vlm} \cap B_{xml})}{A(B_{vlm} \cup B_{xml})}
$$

其中：
- 交集区域：
  $$
  A(B_{vlm} \cap B_{xml}) = \max(0, \min(x_2^{vlm}, x_2^{xml}) - \max(x_1^{vlm}, x_1^{xml})) \\
  \times \max(0, \min(y_2^{vlm}, y_2^{xml}) - \max(y_1^{vlm}, y_1^{xml}))
  $$

- 并集区域：
  $$
  A(B_{vlm} \cup B_{xml}) = A(B_{vlm}) + A(B_{xml}) - A(B_{vlm} \cap B_{xml})
  $$

- 单个框面积：
  $$
  A(B) = (x_2 - x_1) \times (y_2 - y_1)
  $$

#### 4.2.2 选择函数 (Selection Function)

定义选择函数 $f: \mathcal{B} \times \mathcal{B}^n \to \mathbb{N} \cup \{\bot\}$：

$$
f(B_{vlm}, \{B_{xml}^1, ..., B_{xml}^n\}) = \begin{cases}
i^* & \text{if } \exists i: \text{IoU}(B_{vlm}, B_{xml}^i) \geq \tau \land i^* = \arg\max_j \text{IoU}(B_{vlm}, B_{xml}^j) \\
\bot & \text{otherwise}
\end{cases}
$$

其中：
- $\tau$ 是 IoU 阈值（默认 $\tau = 0.3$）
- $i^*$ 是最佳匹配的 XML 节点索引
- $\bot$ 表示无匹配（VLM 检测框为误报）

#### 4.2.3 坐标归一化线性变换

给定 VLM 归一化坐标 $(x', y') \in [0, 1000]^2$ 和屏幕尺寸 $W \times H$：

$$
\begin{bmatrix} x \\ y \end{bmatrix} =
\begin{bmatrix} \frac{W}{1000} & 0 \\ 0 & \frac{H}{1000} \end{bmatrix}
\begin{bmatrix} x' \\ y' \end{bmatrix} =
\begin{bmatrix} x' \cdot \frac{W}{1000} \\ y' \cdot \frac{H}{1000} \end{bmatrix}
$$

完整形式：
$$
x_{pixel} = \left\lfloor \frac{x_{vlm} \times W_{screen}}{1000} \right\rceil
$$
$$
y_{pixel} = \left\lfloor \frac{y_{vlm} \times H_{screen}}{1000} \right\rceil
$$

### 4.3 融合算法伪代码

```
Algorithm 1: VLM-XML Fusion
Input: VLM detections D_vlm = {d_1, ..., d_m}, XML nodes N_xml = {n_1, ..., n_n}
Output: Fused nodes F = {f_1, ..., f_k}

1:  F ← ∅
2:  U ← ∅              // Used XML node indices
3:
4:  for each detection d_i ∈ D_vlm do
5:      best_idx ← -1
6:      best_iou ← 0
7:
8:      for each node n_j ∈ N_xml do
9:          if j ∈ U then continue
10:
11:             iou ← IoU(d_i.bbox, n_j.bounds)
12:             if iou > best_iou and iou ≥ τ then
13:                 best_iou ← iou
14:                 best_idx ← j
15:             end if
16:         end for
17:
18:         if best_idx ≠ -1 then
19:             U ← U ∪ {best_idx}
20:             f ← CreateFusedNode(d_i, N_xml[best_idx], best_iou)
21:             F ← F ∪ {f}
22:         end if
23:     end for
24:
25:     return F
```

### 4.4 Prompt 设计

**目标**：让 VLM 只识别用于页面导航的核心 UI 元素，过滤掉动态内容

```python
_PROMPT_OD = """分析这张手机 App 截图，**只识别用于页面导航的核心 UI 元素**。

**必须识别**（这些是页面跳转的锚点）：
1. 顶部导航栏：返回按钮、标题栏按钮、搜索入口、菜单按钮
2. 底部导航栏：首页/消息/购物车/我的等 Tab 按钮
3. 顶部 Tab 切换：如"关注"、"推荐"、"热门"等分类标签
4. 悬浮按钮：发布按钮、客服按钮、回到顶部等
5. 侧边栏入口：抽屉菜单按钮

**不要识别**（这些是动态内容，不是导航）：
- 商品卡片、商品图片、商品价格、商品标题
- 信息流中的任何内容（帖子、文章、视频缩略图）
- 广告横幅、促销活动、优惠券
- 列表中的每一项数据
- 搜索历史、推荐词、热搜词
- 用户头像、用户名、评论内容
- 任何滚动区域内的动态内容

**坐标格式**：像素坐标 [x1, y1, x2, y2]

返回 JSON：
```json
{
  "elements": [
    {"label": "nav_button", "bbox": [20, 50, 80, 110], "text": "返回"},
    {"label": "tab", "bbox": [55, 180, 165, 241], "text": "推荐"},
    {"label": "bottom_nav", "bbox": [100, 2700, 200, 2772], "text": "首页"}
  ]
}
```

label 类型：nav_button, tab, bottom_nav, fab, search, menu, icon
只返回 JSON，最多 15 个元素。"""
```

## 5. Exploration Strategy

### 5.1 深度优先搜索 (DFS)
```
从首页开始：
  for nav_node in page.nav_nodes:
    click nav_node
    new_page = analyze()
    if new_page.type == PAGE:
      explore(new_page, depth + 1)
```

### 5.2 路径重放机制

回到已探索页面时：
1. 重放从首页到该页的路径
2. 依次点击路径上的节点
3. 失败时标记边为无效

## 6. Data Structures

### 6.1 NavigationMap (输出地图)

```json
{
  "package": "com.example.app",
  "pages": {
    "home": {"name": "首页", "target_aliases": ["main"]},
    "settings": {"name": "设置", "features": ["搜索框"]}
  },
  "transitions": [
    {
      "from": "home",
      "to": "settings",
      "locator": {"text": "设置", "resource_id": "..."}
    }
  ],
  "popups": [{"type": "ad", "close_locator": {...}}],
  "blocks": [{"type": "loading", "identifiers": [...]}]
}
```

### 6.2 Locator (定位符)

```python
{
  "resource_id": "com.app:id/button",  # 精确 ID
  "text": "提交",                      # 辅助文本
  "bounds_hint": [100, 200, 500, 250],  # 坐标提示
  "class_name": "android.widget.Button"  # 类名
}
```

## 7. Design Decisions

### 7.1 节点驱动 (v5)
- **原因**：坐标硬编码不通用，不同设备/分辨率会失效
- **方案**：使用 VLM 理解语义 + XML 提供精确定位

### 7.2 Retrieval-First 定位
- **原因**：减少对坐标的依赖
- **方案**：优先用 resource_id/text 检索，坐标仅作 hint

### 7.3 探索限制
- `max_pages` - 防止无限探索
- `max_depth` - 控制探索深度
- `max_time_seconds` - 超时停止

## 8. Code Structure

| 文件 | 职责 | 关键类/函数 |
|------|------|--------------|
| `node_explorer.py` | 主建图引擎 | `NodeMapBuilder.explore()` |
| `fusion_engine.py` | 融合引擎 | `compute_iou()`, `fuse()` |
| `vlm_engine.py` | VLM 封装 | `_call_api()`, `_run_od()` |
| `models.py` | 数据结构 | `XMLNode`, `FusedNode`, `NavigationMap` |

## 9. Cross References
- `docs/zh/lxb_link.md` - 设备通信
- `docs/zh/lxb_cortex.md` - 自动化执行
