# LXB-Server

## 1. Scope
LXB-Server is the Android-side service core, receiving protocol commands and executing input injection, node retrieval, and state acquisition.

## 2. Architecture
Code directory: `android/LXB-Ignition/lxb-core/`

```
lxb-core/
├── protocol/               # Protocol parsing and dispatch
├── dispatcher/            # Command dispatcher
├── perception/            # Perception engine
└── executors/             # Executor implementation
```

### Service Architecture

```
Shizuku IPC
       │
       v
LXB-Server Core
       │
       ├──> Perception Engine (Accessibility Service)
       │      └── Get UI tree, node attributes
       │
       └──> Executors (Input/Lifecycle)
              └── Inject input, app control
```

## 3. Core Flow

### 3.1 Command Processing Flow

```
Receive UDP frame
    │
    v
Parse frame (CMD ID + Payload)
    │
    v
Dispatch to corresponding engine
    │
    ├──> Perception Commands → AccessibilityService → UI tree data
    │
    └──> Execution Commands → Input Manager → Device operations
    │
    v
Generate response frame
```

### 3.2 Perception Engine Principle

**AccessibilityService Mechanism**:
- Inherits Android AccessibilityService
- Listens to UI change events
- Traverses UI tree to extract node information

**Node Attribute Extraction**:
- `getText()` - Visible text
- `getResourceName()` - Resource ID
- `getBoundsInScreen()` - Screen coordinates
- `isClickable()` - Clickability

### 3.3 Input Injection Methods

| Method | Implementation Principle | Priority |
|--------|------------------|----------|
| Accessibility API | `performAction(ACTION_CLICK)` | Highest |
| Clipboard | Set clipboard + paste | Medium |
| Shell input | `input text` command | Lowest (fallback) |

## 4. Latency Analysis

### 4.1 UI Tree Retrieval Performance

| Operation | Average Time | Influencing Factors |
|-----------|--------------|-------------------|
| `get_root_in_active_window` | 5-15ms | Page complexity |
| Full UI tree traversal (1000 nodes) | 20-50ms | Node count, nesting depth |
| `find_node` single-field search | 10-30ms | Tree traversal range |
| `find_node_compound` multi-condition | 15-40ms | Condition count |

### 4.2 Latency Optimization Strategies

1. **Node filtering**: Only return visible, interactive nodes
2. **Depth limit**: `max_depth` parameter limits traversal depth
3. **Early termination**: Return immediately upon finding matching node

## 5. Tree Serialization

### 5.1 UI Tree to JSON

**JSON Schema**:

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

### 5.2 Node Filtering Strategy

**Filtering rules**:

```python
def should_include(node: AccessibilityNodeInfo) -> bool:
    """
    Determine if node should be included in output
    """
    # 1. Filter invisible nodes
    if not node.isVisibleToUser():
        return False

    # 2. Filter off-screen nodes
    bounds = node.getBoundsInScreen()
    screen = get_screen_size()
    if (bounds.right < 0 or bounds.bottom < 0 or
        bounds.left > screen.width or bounds.top > screen.height):
        return False

    # 3. Filter pure layout nodes (optional)
    if is_layout_only(node):
        return False

    return True
```

**Invisible node handling**:
- `isVisibleToUser() = false` → Filtered directly
- `bounds_in_screen = false` → Filtered directly
- Off-screen nodes → Not included in output

### 5.3 Binary Format Optimization

To reduce transmission overhead, use binary format:

**Node structure (15 bytes fixed length)**:

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

**Flags bit field definition**:

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

### 6.1 Single-Field Search (FIND_NODE)

**Algorithm**:
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

### 6.2 Multi-Condition Search (FIND_NODE_COMPOUND)

**Condition tuple**: $(field, operator, value)$

**Supported operators**:
- `EQ`: Equals
- `CONTAINS`: Contains
- `STARTS_WITH`: Prefix match
- `REGEX`: Regular expression

## 7. Failure Modes

| Failure Type | Cause | Handling |
|--------------|-------|----------|
| Service disconnect | System reclaims service | Return error code |
| UI tree empty | Page loading | Return empty list |
| Insufficient permissions | Shizuku unauthorized | Return permission error |

## 8. Code Structure

| Java File | Responsibility |
|-----------|----------------|
| `PerceptionEngine.java` | Perception engine entry |
| `CommandDispatcher.java` | Command routing dispatch |
| `NodeFinder.java` | Node search logic |

## 9. Cross References
- `docs/en/lxb_link.md` - Protocol definition
- `docs/en/lxb_web_console.md` - Web console
