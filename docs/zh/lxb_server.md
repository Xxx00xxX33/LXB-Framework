# LXB-Server

## 1. Scope
LXB-Server 是 Android 端服务核心，接收协议命令并执行输入注入、节点检索、状态获取。

## 2. Architecture
代码目录：`android/LXB-Ignition/lxb-core/`

```
lxb-core/
├── protocol/               # 协议解析与分发
├── dispatcher/            # 命令分发器
├── perception/            # 感知引擎
└── executors/             # 执行器实现
```

### 服务架构

```
Shizuku IPC
       │
       v
LXB-Server Core
       │
       ├──> Perception Engine (Accessibility Service)
       │      └── 获取 UI 树、节点属性
       │
       └──> Executors (Input/Lifecycle)
              └── 注入输入、应用控制
```

## 3. Core Flow

### 3.1 命令处理流程

```
接收 UDP 帧
    │
    v
解析帧 (CMD ID + Payload)
    │
    v
分发到对应引擎
    │
    ├──> Perception Commands → AccessibilityService → UI 树数据
    │
    └──> Execution Commands → Input Manager → 设备操作
    │
    v
生成响应帧
```

### 3.2 感知引擎原理

**AccessibilityService 机制**：
- 继承 Android AccessibilityService
- 监听 UI 变化事件
- 遍历 UI 树提取节点信息

**节点属性提取**：
- `getText()` - 可见文本
- `getResourceName()` - Resource ID
- `getBoundsInScreen()` - 屏幕坐标
- `isClickable()` - 可点击性

### 3.3 输入注入方式

| 方式 | 实现原理 | 优先级 |
|------|----------|--------|
| Accessibility API | `performAction(ACTION_CLICK)` | 最高 |
| Clipboard | 设置剪贴板 + 粘贴 | 中 |
| Shell input | `input text` 命令 | 最低 (降级) |

## 4. Latency Analysis (延迟分析)

### 4.1 UI 树检索性能

| 操作 | 平均耗时 | 影响因素 |
|------|----------|----------|
| `get_root_in_active_window` | 5-15ms | 页面复杂度 |
| 遍历完整 UI 树（1000节点） | 20-50ms | 节点数量、嵌套深度 |
| `find_node` 单字段查找 | 10-30ms | 树遍历范围 |
| `find_node_compound` 多条件 | 15-40ms | 条件数量 |

### 4.2 延迟优化策略

1. **节点过滤**：仅返回可见、可交互节点
2. **深度限制**：`max_depth` 参数限制遍历深度
3. **早期终止**：找到匹配节点后立即返回

## 5. Tree Serialization (树序列化)

### 5.1 UI 树转 JSON

**JSON Schema**：

```json
{
  "version": 1,
  "root": {
    "index": 0,
    "class": "android.widget.FrameLayout",
    "bounds": [0, 0, 1080, 2400],
    "text": "",
    "resource_id": "com.app:id/root",
    "clickable": false,
    "visible": true,
    "enabled": true,
    "children": [
      {
        "index": 1,
        "parent_index": 0,
        "class": "android.widget.Button",
        "bounds": [100, 200, 500, 250],
        "text": "Submit",
        "resource_id": "com.app:id/submit",
        "clickable": true,
        "visible": true,
        "enabled": true,
        "children": []
      }
    ]
  }
}
```

### 5.2 节点过滤策略

**过滤规则**：

```python
def should_include(node: AccessibilityNodeInfo) -> bool:
    """
    判断节点是否应包含在输出中
    """
    # 1. 不可见节点过滤
    if not node.isVisibleToUser():
        return False

    # 2. 屏幕外节点过滤
    bounds = node.getBoundsInScreen()
    screen = get_screen_size()
    if (bounds.right < 0 or bounds.bottom < 0 or
        bounds.left > screen.width or bounds.top > screen.height):
        return False

    # 3. 纯布局节点过滤（可选）
    if is_layout_only(node):
        return False

    return True
```

**不可见节点处理**：
- `isVisibleToUser() = false` → 直接过滤
- `bounds_in_screen = false` → 直接过滤
- Off-screen 节点 → 不包含在输出中

### 5.3 二进制格式优化

为减少传输开销，使用二进制格式：

**Node 结构（15 bytes 固定长度）**：

```
┌─────────────┬─────────────┬─────────────┬─────────────────────────┐
│ Field       │ Size        │ Type        │ Description             │
├─────────────┼─────────────┼─────────────┼─────────────────────────┤
│ parent_idx  │ 1 byte      │ uint8       │ Parent index (0xFF=root) │
│ child_count │ 1 byte      │ uint8       │ Number of children      │
│ flags       │ 1 byte      │ uint8       │ Bit field (see below)   │
│ left        │ 2 bytes     │ uint16      │ Bounds left             │
│ top         │ 2 bytes     │ uint16      │ Bounds top              │
│ right       │ 2 bytes     │ uint16      │ Bounds right            │
│ bottom      │ 2 bytes     │ uint16      │ Bounds bottom           │
│ class_id    │ 1 byte      │ uint8       │ Class name (string pool)│
│ text_id     │ 1 byte      │ uint8       │ Text (string pool)      │
│ res_id      │ 1 byte      │ uint8       │ Resource ID (string pool)│
│ desc_id     │ 1 byte      │ uint8       │ Content desc (string)   │
└─────────────┴─────────────┴─────────────┴─────────────────────────┘
```

**Flags 位域定义**：

```
Bit 0: clickable
Bit 1: visible
Bit 2: enabled
Bit 3: focused
Bit 4: scrollable
Bit 5: editable
Bit 6: checkable
Bit 7: checked
```

## 6. Node Matching

### 6.1 单字段查找 (FIND_NODE)

**算法**：
```
Algorithm 3: Single-Field Node Search
Input: UI tree T, field f, operator op, value v
Output: List of matching nodes M

1:  M ← ∅
2:  stack ← [T.root]
3:
4:  while stack is not empty do
5:      node ← stack.pop()
6:
7:      if matches(node, f, op, v) then
8:          M ← M ∪ {node}
9:      end if
10:
11:     for each child ∈ node.children do
12:         stack.push(child)
13:     end for
14: end while
15:
16: return M
```

### 6.2 多条件查找 (FIND_NODE_COMPOUND)

**条件三元组**：$(field, operator, value)$

**支持的操作符**：
- `EQ`: 等于
- `CONTAINS`: 包含
- `STARTS_WITH`: 前缀匹配
- `REGEX`: 正则表达式

## 7. Failure Modes

| 失败类型 | 原因 | 处理 |
|----------|------|------|
| Service 断开 | 系统回收服务 | 返回错误码 |
| UI 树为空 | 页面加载中 | 返回空列表 |
| 权限不足 | Shizuku 未授权 | 返回权限错误 |

## 8. Code Structure

| Java 文件 | 职责 |
|----------|------|
| `PerceptionEngine.java` | 感知引擎入口 |
| `CommandDispatcher.java` | 命令路由分发 |
| `NodeFinder.java` | 节点查找逻辑 |

## 9. Cross References
- `docs/zh/lxb_link.md` - 协议定义
- `docs/zh/lxb_web_console.md` - Web 控制台
