# LXB-Link 协议升级建议书

## 📋 执行摘要

当前 LXB-Link 协议定位为**传输可靠的远程控制协议**,主要服务于基础的设备操作(点击/滑动/截图)。为支持 **LXB-Cortex 智能调度系统**的混合感知架构,需要进行以下升级:

1. **新增感知层指令集** - 支持 Activity 查询、UI 树获取、计算卸载查找
2. **扩展输入能力** - 文本输入、物理按键、应用生命周期管理
3. **重构命名空间** - 分层 ISA 架构,支持未来 256+ 指令扩展
4. **优化数据结构** - 变长数据压缩传输,支持 JSON/Protobuf 混合策略

---

## 1. 缺失的指令集 (Missing Capabilities)

### 1.1 感知层 (Sense Layer) - `0x30-0x3F`

#### `CMD_GET_ACTIVITY (0x30)` - 获取前台 Activity

**用途**: 支持 Cortex L1 查表策略,实现状态机路由

**Request Payload**:
```
无 Payload (Length = 0)
```

**Response Payload**:
```python
struct GetActivityResponse:
    uint8   success         # 0=失败, 1=成功
    uint16  package_len     # 包名长度 (N)
    char[]  package_name    # 包名 (e.g., "com.tencent.mm")
    uint16  activity_len    # Activity 长度 (M)
    char[]  activity_name   # Activity 完整路径

# 示例: "com.tencent.mm" + ".ui.LauncherUI"
# Total: 1 + 2 + N + 2 + M bytes
```

**实现要点**:
- Android 端通过 `ActivityManager.getRunningTasks()` 或 `UsageStatsManager` 获取
- 兼容 Android 5.0+ 权限限制 (需要 `PACKAGE_USAGE_STATS`)
- 典型 RTT: < 5ms (无需截图,仅字符串返回)

---

#### `CMD_DUMP_HIERARCHY (0x31)` - 导出 UI 层级树

**用途**: 支持 Cortex L2 结构化分析

**Request Payload**:
```python
struct DumpHierarchyRequest:
    uint8   format          # 0=XML, 1=JSON, 2=Binary(自定义)
    uint8   compress        # 0=原始, 1=zlib, 2=lz4
    uint16  max_depth       # 最大遍历深度 (0=无限制, 建议 8)
```

**Response Payload**:
```python
struct DumpHierarchyResponse:
    uint8   success         # 状态码
    uint32  original_size   # 原始数据大小
    uint32  compressed_size # 压缩后大小
    uint8   format          # 实际返回格式 (回显请求)
    uint8   compress        # 实际压缩算法
    char[]  data            # 层级树数据

# 注意: 大数据需使用 IMG_CHUNK 分片机制传输 (复用现有逻辑)
```

**数据格式示例 (JSON)**:
```json
{
  "window": "com.tencent.mm/com.tencent.mm.ui.LauncherUI",
  "timestamp": 1735689600000,
  "nodes": [
    {
      "id": "com.tencent.mm:id/search_bar",
      "class": "android.widget.EditText",
      "text": "",
      "desc": "搜索",
      "bounds": [100, 200, 500, 280],
      "clickable": true,
      "index": 0,
      "children": []
    }
  ]
}
```

**实现要点**:
- Android 端使用 `UiAutomator.dumpWindowHierarchy()` 或 `AccessibilityService`
- **压缩必要性**: 典型微信主界面 XML ~50KB, 压缩后 ~8KB
- 建议默认使用 `format=1 (JSON)` + `compress=1 (zlib)` 平衡可读性与效率
- 超大树 (>100KB) 自动触发分片传输

---

#### `CMD_FIND_NODE (0x32)` - 计算卸载查找 ⭐核心创新

**用途**: 避免传输巨大 XML,将查找逻辑下放到设备端执行

**Request Payload**:
```python
struct FindNodeRequest:
    uint8   match_type      # 匹配方式
                            # 0=精确文本, 1=包含文本, 2=正则表达式
                            # 3=resource-id, 4=class, 5=描述
    uint8   return_mode     # 返回模式
                            # 0=仅中心坐标, 1=边界框, 2=完整节点信息
    uint16  query_len       # 查询字符串长度
    char[]  query_str       # 查询内容 (e.g., "微信", ".*登录.*")
    uint16  timeout_ms      # 查找超时 (建议 3000ms)
    uint8   multi_match     # 0=返回首个, 1=返回所有匹配
```

**Response Payload**:
```python
struct FindNodeResponse:
    uint8   success         # 0=未找到, 1=找到, 2=超时
    uint8   count           # 匹配节点数量

    # 根据 return_mode 返回不同结构:
    # Mode 0 (中心坐标):
    struct Coordinate {
        uint16  x
        uint16  y
    } coords[count];

    # Mode 1 (边界框):
    struct BoundingBox {
        uint16  left
        uint16  top
        uint16  right
        uint16  bottom
    } boxes[count];

    # Mode 2 (完整信息):
    struct NodeInfo {
        uint16  x, y                # 中心坐标
        uint16  left, top, right, bottom  # 边界
        uint8   clickable           # 布尔标志
        uint16  text_len            # 文本长度
        char[]  text                # 节点文本
        uint16  id_len              # resource-id 长度
        char[]  resource_id         # resource-id
    } nodes[count];
```

**实现要点**:
- Android 端使用 `UiSelector` 或 `AccessibilityNodeInfo` 遍历
- **性能优化**: 典型查找时间 < 500ms (无需传输完整树)
- **带宽节约**: 查询 "登录" 按钮仅返回 4 字节坐标 vs 50KB XML
- **失败重试**: 支持动态等待 (元素可能延迟加载)

---

### 1.2 输入扩展层 (Input Extension) - `0x20-0x2F`

#### `CMD_INPUT_TEXT (0x20)` - 文本输入

**用途**: 支持表单填充、搜索输入等场景

**Request Payload**:
```python
struct InputTextRequest:
    uint8   method          # 输入方式
                            # 0=ADB输入法, 1=剪贴板粘贴, 2=AccessibilityService
    uint8   clear_first     # 是否先清空 (0=否, 1=是)
    uint16  text_len        # 文本长度 (UTF-8)
    char[]  text            # 文本内容
    uint16  target_x        # 目标输入框坐标 (可选, 0=当前焦点)
    uint16  target_y
```

**Response Payload**:
```python
struct InputTextResponse:
    uint8   success         # 0=失败, 1=成功
    uint8   actual_method   # 实际使用的方法 (可能降级)
```

**实现要点**:
- **Method 0 (ADB 输入法)**: 最可靠,需安装 `ADBKeyboard.apk`
- **Method 1 (剪贴板)**: 最快 (~50ms), 但会污染剪贴板
- **Method 2 (无障碍)**: 需要权限,兼容性最好
- 自动处理特殊字符转义 (空格/换行/表情符号)

---

#### `CMD_KEY_EVENT (0x21)` - 物理按键

**用途**: 模拟 Home/Back/Enter 等系统按键

**Request Payload**:
```python
struct KeyEventRequest:
    uint8   keycode         # Android KeyEvent 常量
                            # 3=HOME, 4=BACK, 66=ENTER,
                            # 24/25=音量, 26=电源
    uint8   action          # 0=按下, 1=抬起, 2=点击(按下+抬起)
    uint32  meta_state      # 修饰键状态 (Shift/Ctrl/Alt)
```

**常用 Keycode 快捷定义**:
```python
KEY_HOME    = 3
KEY_BACK    = 4
KEY_ENTER   = 66
KEY_DELETE  = 67
KEY_MENU    = 82
KEY_RECENT  = 187   # 多任务
```

**Response**: 标准 ACK

---

### 1.3 生命周期管理 (Lifecycle) - `0x40-0x4F`

#### `CMD_RESTART_APP (0x40)` - 重启应用

**用途**: Agent 卡死时强制重启

**Request Payload**:
```python
struct RestartAppRequest:
    uint16  package_len
    char[]  package_name    # e.g., "com.tencent.mm"
    uint8   force_stop      # 0=正常退出, 1=强制停止 (am force-stop)
    uint16  delay_ms        # 停止后等待多久再启动
```

**Response**: 标准 ACK

---

#### `CMD_GET_CLIPBOARD (0x41)` - 获取剪贴板

**用途**: 验证码识别、内容验证

**Request Payload**: 无

**Response Payload**:
```python
struct ClipboardResponse:
    uint8   has_content     # 0=空, 1=有内容
    uint8   content_type    # 0=文本, 1=URI, 2=Intent
    uint32  text_len
    char[]  text            # UTF-8 文本
    uint64  timestamp       # 剪贴板时间戳 (毫秒)
```

**实现要点**:
- Android 10+ 需要前台应用才能访问剪贴板
- 建议配合 `INPUT_TEXT(method=1)` 实现双向同步

---

#### `CMD_SET_CLIPBOARD (0x42)` - 设置剪贴板

**Request Payload**:
```python
struct SetClipboardRequest:
    uint32  text_len
    char[]  text
```

---

### 1.4 调试增强 (Debug) - `0x50-0x5F`

#### `CMD_GET_DEVICE_INFO (0x50)` - 获取设备信息

**用途**: Agent 启动时获取设备能力

**Response Payload**:
```python
struct DeviceInfo:
    uint16  screen_width
    uint16  screen_height
    uint8   android_version # e.g., 13 = Android 13
    uint16  manufacturer_len
    char[]  manufacturer    # "Xiaomi"
    uint16  model_len
    char[]  model           # "MI 11"
    uint32  capabilities    # 位掩码: bit0=无障碍, bit1=悬浮窗...
```

---

#### `CMD_LOGCAT (0x51)` - 获取日志片段

**用途**: 调试 Agent 行为

**Request Payload**:
```python
struct LogcatRequest:
    uint8   level           # 0=Verbose, 3=Error
    uint16  tag_len
    char[]  tag_filter      # 过滤标签 (e.g., "ActivityManager")
    uint16  max_lines       # 最多返回行数
```

---

## 2. 命名空间重构 (Namespace Optimization)

### 2.1 分层 ISA 架构

当前线性增长的 CMD ID (`0x01-0x14`) 在扩展到 50+ 指令时会难以管理。建议采用 **分层指令集架构 (Layered ISA)**:

```
┌─────────────────┬──────────────────┬─────────────────────────────┐
│  Layer          │  Range           │  Purpose                    │
├─────────────────┼──────────────────┼─────────────────────────────┤
│  Link Layer     │  0x00 - 0x0F     │  握手/ACK/心跳/元数据       │
│  Input Layer    │  0x10 - 0x1F     │  点击/滑动/按键/文本        │
│  Input Ext      │  0x20 - 0x2F     │  文本输入/按键事件          │
│  Sense Layer    │  0x30 - 0x3F     │  Activity/UI树/查找节点     │
│  Lifecycle      │  0x40 - 0x4F     │  重启/剪贴板/应用管理       │
│  Debug Layer    │  0x50 - 0x5F     │  日志/性能监控/设备信息     │
│  Media Layer    │  0x60 - 0x6F     │  截图/录屏/音频采集         │
│  Reserved       │  0x70 - 0xEF     │  未来扩展 (AI/多模态/...)   │
│  System/Vendor  │  0xF0 - 0xFF     │  厂商自定义/实验性功能      │
└─────────────────┴──────────────────┴─────────────────────────────┘
```

### 2.2 指令 ID 重新分配方案

#### **Link Layer (0x00-0x0F)** - 协议基础设施
```python
CMD_HANDSHAKE       = 0x01  # [保持不变]
CMD_ACK             = 0x02  # [保持不变]
CMD_HEARTBEAT       = 0x03  # [新增] 保活心跳
CMD_NOOP            = 0x04  # [新增] 空操作 (用于测试延迟)
CMD_PROTOCOL_VER    = 0x05  # [新增] 协议版本协商
# 0x06-0x0F: 预留给传输层扩展
```

#### **Input Layer (0x10-0x1F)** - 基础交互
```python
CMD_TAP             = 0x10  # [迁移] 原 0x03
CMD_SWIPE           = 0x11  # [迁移] 原 0x04
CMD_LONG_PRESS      = 0x12  # [新增] 长按
CMD_MULTI_TOUCH     = 0x13  # [新增] 多点触控
CMD_GESTURE         = 0x14  # [新增] 复杂手势 (捏合/旋转)
CMD_WAKE            = 0x1A  # [迁移] 原 0x0A
# 0x15-0x1F: 预留
```

#### **Input Extension (0x20-0x2F)** - 高级输入
```python
CMD_INPUT_TEXT      = 0x20  # [新增] 文本输入
CMD_KEY_EVENT       = 0x21  # [新增] 物理按键
CMD_PASTE           = 0x22  # [新增] 粘贴操作
# 0x23-0x2F: 预留
```

#### **Sense Layer (0x30-0x3F)** - 感知能力 ⭐核心升级
```python
CMD_GET_ACTIVITY    = 0x30  # [新增] 获取 Activity
CMD_DUMP_HIERARCHY  = 0x31  # [新增] 导出 UI 树
CMD_FIND_NODE       = 0x32  # [新增] 计算卸载查找
CMD_GET_FOCUSED     = 0x33  # [新增] 获取焦点元素
CMD_WAIT_FOR        = 0x34  # [新增] 等待元素出现
CMD_OCR_REGION      = 0x35  # [新增] 指定区域 OCR (设备端)
# 0x36-0x3F: 预留给 AI 增强
```

#### **Lifecycle (0x40-0x4F)** - 应用管理
```python
CMD_RESTART_APP     = 0x40  # [新增] 重启应用
CMD_GET_CLIPBOARD   = 0x41  # [新增] 获取剪贴板
CMD_SET_CLIPBOARD   = 0x42  # [新增] 设置剪贴板
CMD_INSTALL_APK     = 0x43  # [新增] 安装应用
CMD_UNINSTALL       = 0x44  # [新增] 卸载应用
CMD_CLEAR_DATA      = 0x45  # [新增] 清除应用数据
# 0x46-0x4F: 预留
```

#### **Debug Layer (0x50-0x5F)** - 调试工具
```python
CMD_GET_DEVICE_INFO = 0x50  # [新增] 设备信息
CMD_LOGCAT          = 0x51  # [新增] 日志获取
CMD_PERF_STATS      = 0x52  # [新增] 性能统计
CMD_TRACE_DUMP      = 0x53  # [新增] 堆栈跟踪
# 0x54-0x5F: 预留
```

#### **Media Layer (0x60-0x6F)** - 媒体采集
```python
CMD_SCREENSHOT      = 0x60  # [迁移] 原 0x09 (单帧)
CMD_IMG_REQ         = 0x61  # [迁移] 原 0x10 (分片请求)
CMD_IMG_META        = 0x62  # [迁移] 原 0x11
CMD_IMG_CHUNK       = 0x63  # [迁移] 原 0x12
CMD_IMG_MISSING     = 0x64  # [迁移] 原 0x13
CMD_IMG_FIN         = 0x65  # [迁移] 原 0x14
CMD_START_RECORD    = 0x66  # [新增] 开始录屏
CMD_STOP_RECORD     = 0x67  # [新增] 停止录屏
CMD_AUDIO_CAPTURE   = 0x68  # [新增] 音频采集
# 0x69-0x6F: 预留给流媒体
```

### 2.3 版本兼容性策略

为保证向后兼容,建议在握手阶段协商协议版本:

```python
# HANDSHAKE Payload 扩展
struct HandshakeRequest:
    uint16  protocol_version    # 0x0100 = v1.0, 0x0200 = v2.0
    uint32  capabilities        # 位掩码声明支持的功能

# Server 返回
struct HandshakeResponse:
    uint16  accepted_version    # Server 选择的版本
    uint32  server_capabilities # Server 支持的功能
```

**迁移路径**:
- **Phase 1 (v1.1)**: 新增指令保持旧 ID,新增 `CMD_PROTOCOL_VER` 用于声明
- **Phase 2 (v2.0)**: 完全切换到新命名空间,v1.x 客户端通过版本号降级

---

## 3. 数据结构建议 (Data Structures)

### 3.1 变长数据传输策略

针对 `DUMP_HIERARCHY` 和 `FIND_NODE` 等返回大数据的场景:

#### **策略 A: 复用分片机制 (推荐用于 >10KB 数据)**

```python
# DUMP_HIERARCHY 返回流程:
1. Client 发送 CMD_DUMP_HIERARCHY(format=JSON, compress=zlib)
2. Server 生成数据并分片 (复用 IMG_CHUNK 机制)
3. 使用新的 chunk_type 区分数据类型:

   struct DataChunk:
       uint8   chunk_type      # 0=图片, 1=JSON, 2=XML, 3=二进制
       uint32  chunk_index
       uint32  total_chunks
       uint16  chunk_size
       char[]  chunk_data
```

**优势**:
- 复用现有的可靠传输逻辑 (选择性重传)
- 自动处理 >64KB 数据
- 统一的错误恢复机制

---

#### **策略 B: 内联压缩 (用于 <10KB 数据)**

```python
# FIND_NODE 返回 (典型 <1KB):
struct FindNodeResponse:
    uint8   compress        # 0=原始, 1=zlib, 2=lz4
    uint16  original_size   # 压缩前大小
    uint16  data_len        # 当前 Payload 长度
    char[]  data            # 压缩后数据

# 示例: 查找 "登录" 返回 10 个坐标
# 原始: 10 * 4 bytes = 40 bytes
# 压缩: ~25 bytes (zlib)
# 收益: 不明显,建议不压缩
```

**压缩决策表**:
```
┌─────────────────────┬──────────────┬──────────────┐
│  Data Type          │  Typical Size│  Strategy    │
├─────────────────────┼──────────────┼──────────────┤
│  Activity Name      │  ~50 bytes   │  原始传输    │
│  FIND_NODE (坐标)   │  ~100 bytes  │  原始传输    │
│  FIND_NODE (完整)   │  ~2 KB       │  zlib 压缩   │
│  UI Hierarchy       │  ~50 KB      │  zlib + 分片 │
│  Screenshot         │  ~100 KB     │  JPEG + 分片 │
│  Logcat             │  ~10 KB      │  lz4 压缩    │
└─────────────────────┴──────────────┴──────────────┘
```

---

### 3.2 格式选择: JSON vs Protobuf vs 自定义二进制

#### **JSON (推荐用于 UI Hierarchy)**

**优势**:
- 人类可读,方便调试
- Python/Java 原生支持
- 压缩后与 Protobuf 相差不大 (~20%)

**示例 - UI 节点 JSON 格式**:
```json
{
  "id": "com.tencent.mm:id/btn_login",
  "cls": "Button",
  "txt": "登录",
  "desc": "",
  "bnds": [100, 500, 300, 580],  // [left, top, right, bottom]
  "click": 1,
  "vis": 1,
  "kids": []
}
```

**压缩效果**:
```
原始 JSON:  52,341 bytes
zlib 压缩:   7,892 bytes  (85% 压缩率)
lz4 压缩:    9,234 bytes  (82% 压缩率, 速度快 3x)
```

---

#### **自定义二进制 (推荐用于高频指令)**

针对 `FIND_NODE` 返回坐标这种高频场景:

```python
# 方案 1: 紧凑二进制
struct CompactCoords:
    uint8   count           # 最多 255 个节点
    struct {
        uint16  x
        uint16  y
    } coords[count];        # 4 bytes per node

# 方案 2: 差分编码 (进一步压缩)
struct DeltaCoords:
    uint8   count
    uint16  base_x          # 第一个坐标
    uint16  base_y
    struct {
        int8   delta_x      # 相对偏移 (-128~127)
        int8   delta_y
    } deltas[count-1];      # 2 bytes per node

# 示例: 10 个坐标
# JSON:       ~200 bytes
# 紧凑二进制:   41 bytes
# 差分编码:     23 bytes  (节省 88%)
```

**建议**:
- `FIND_NODE` 返回坐标: **自定义二进制 (差分编码)**
- `DUMP_HIERARCHY`: **JSON + zlib**
- `GET_ACTIVITY`: **原始字符串 (UTF-8)**

---

#### **Protobuf (可选,用于未来扩展)**

如果后续需要跨语言支持 (C++/Go 客户端):

```protobuf
message UINode {
    string resource_id = 1;
    string class_name = 2;
    string text = 3;
    Rect bounds = 4;
    bool clickable = 5;
    repeated UINode children = 6;
}

message Rect {
    int32 left = 1;
    int32 top = 2;
    int32 right = 3;
    int32 bottom = 4;
}
```

**对比**:
```
UI 树 (100 nodes):
- JSON + zlib:    7.8 KB
- Protobuf:       6.2 KB  (节省 20%)
- 编码速度:       Protobuf 快 2-3x
- 解析速度:       相当
- 调试难度:       Protobuf 需要工具解码
```

**推荐方案**: 先用 JSON,待协议稳定后可选迁移到 Protobuf

---

### 3.3 数据流优化建议

#### **优化 1: 增量 UI 树传输**

对于连续调用 `DUMP_HIERARCHY` 的场景 (例如 Agent 轮询):

```python
# 第一次: 完整树
CMD_DUMP_HIERARCHY → 返回完整 JSON (50 KB)

# 后续: 仅返回变化的节点
CMD_DUMP_HIERARCHY_DIFF → 返回差异 (2 KB)
{
  "removed": ["id1", "id2"],
  "added": [...新节点...],
  "updated": {"id3": {"text": "新文本"}}
}
```

---

#### **优化 2: 服务端缓存**

对于 `FIND_NODE` 查询,如果 UI 树未变化:

```python
# Server 维护 UI 树缓存
cache = {
    "tree_version": 12345,      # 基于窗口变化递增
    "last_activity": "LauncherUI",
    "hierarchy": {...}
}

# Client 请求时携带版本号
CMD_FIND_NODE(query="登录", tree_version=12345)

# Server 对比版本:
if cache.tree_version == request.tree_version:
    # 直接在缓存中查找 (节省 dump 时间)
    return find_in_cache(query)
else:
    # 重新 dump 并更新缓存
    refresh_cache()
    return find(query)
```

**性能提升**:
- Dump UI 树: ~300ms
- 缓存查找: ~10ms
- **提速 30x**

---

#### **优化 3: 流式传输 (针对日志)**

对于 `CMD_LOGCAT` 这种可能持续输出的场景:

```python
# 请求
CMD_LOGCAT_STREAM(tag="ActivityManager", duration=5000ms)

# 响应 (分批推送)
Stream {
    uint32  sequence        # 流序列号
    uint8   is_final        # 0=持续, 1=结束
    uint16  log_count       # 本批日志条数
    char[]  logs            # 日志内容
}
```

---

## 4. 实施路线图 (Implementation Roadmap)

### Phase 1: 核心感知能力 (Week 1-2)
**目标**: 支持 Cortex L1/L2

- [ ] 实现 `CMD_GET_ACTIVITY (0x30)`
- [ ] 实现 `CMD_FIND_NODE (0x32)` - 仅支持 `return_mode=0` (坐标)
- [ ] 实现 `CMD_INPUT_TEXT (0x20)` - 仅 `method=1` (剪贴板)
- [ ] 实现 `CMD_KEY_EVENT (0x21)` - 支持 BACK/HOME/ENTER
- [ ] 迁移现有指令 ID 到新命名空间 (向后兼容模式)

**验证标准**: Cortex 能通过查表+查找完成 "微信发送消息" 流程

---

### Phase 2: 完整 UI 树支持 (Week 3-4)
**目标**: 支持复杂场景分析

- [ ] 实现 `CMD_DUMP_HIERARCHY (0x31)` - JSON + zlib
- [ ] 实现 `CMD_FIND_NODE` 的 `return_mode=2` (完整节点)
- [ ] 实现分片传输的 `chunk_type` 扩展
- [ ] 实现 `CMD_GET_CLIPBOARD (0x41)` / `CMD_SET_CLIPBOARD (0x42)`
- [ ] Android 端适配 AccessibilityService

**验证标准**: 导出完整微信主界面 UI 树 < 2 秒

---

### Phase 3: 生命周期与调试 (Week 5)
**目标**: 提升 Agent 鲁棒性

- [ ] 实现 `CMD_RESTART_APP (0x40)`
- [ ] 实现 `CMD_GET_DEVICE_INFO (0x50)`
- [ ] 实现 `CMD_LOGCAT (0x51)`
- [ ] 实现握手阶段的协议版本协商
- [ ] 添加服务端 UI 树缓存机制

**验证标准**: Agent 遇到异常能自动重启目标应用并恢复

---

### Phase 4: 性能优化 (Week 6+)
**目标**: 达到工业级性能

- [ ] `FIND_NODE` 引入差分编码坐标
- [ ] 实现增量 UI 树传输 (`DUMP_HIERARCHY_DIFF`)
- [ ] 压缩算法从 zlib 迁移到 lz4 (提速 3x)
- [ ] 添加性能监控 (`CMD_PERF_STATS`)
- [ ] 完整协议文档 + API Reference

**验证标准**:
- `FIND_NODE` 平均延迟 < 50ms
- `DUMP_HIERARCHY` 压缩后 < 10KB
- 40% 丢包率下成功率 > 99%

---

## 5. 关键设计决策总结

### 决策 1: 计算卸载 vs 全量传输
**选择**: `FIND_NODE` 计算卸载

**理由**:
- 典型场景: 查找 1 个 "登录" 按钮
  - 方案 A (全量): 传输 50KB XML + PC 端解析
  - 方案 B (卸载): 传输 20B 查询 + 手机端查找 + 返回 4B 坐标
- **带宽节约**: 2500x
- **延迟优化**: 从 500ms → 50ms (手机端查找更快)

---

### 决策 2: JSON vs Protobuf
**选择**: JSON (可后续迁移)

**理由**:
- 开发速度优先 (易于调试)
- 压缩后大小差距 <20%
- Python 生态友好
- 待协议稳定后可平滑迁移到 Protobuf

---

### 决策 3: 分层 ISA vs 线性编号
**选择**: 分层 ISA

**理由**:
- 支持 256 条指令 (当前仅 20 条)
- 语义分组便于维护 (感知层/输入层/调试层)
- 预留厂商扩展空间 (`0xF0-0xFF`)
- 便于实现权限控制 (例如禁用 Debug Layer)

---

### 决策 4: 压缩策略
**选择**: 混合策略

```
< 1KB:   不压缩 (CPU 开销 > 传输收益)
1-10KB:  zlib (通用性好)
> 10KB:  lz4 + 分片 (速度优先)
```

---

## 6. 协议安全性增强建议

虽然不是核心需求,但建议在 Phase 2 后考虑:

### 6.1 认证机制
```python
# HANDSHAKE 扩展
struct HandshakeRequest:
    uint32  client_id       # 设备唯一标识
    char[32] token_hash     # SHA256(shared_secret + timestamp)
    uint64  timestamp       # 防重放攻击
```

### 6.2 敏感指令保护
```python
# 危险指令需要二次确认
CMD_UNINSTALL, CMD_CLEAR_DATA, CMD_INSTALL_APK
→ 返回 challenge_code
→ Client 需发送 CMD_CONFIRM(challenge_code) 才执行
```

### 6.3 加密传输 (可选)
```python
# 使用 AES-GCM 加密 Payload
struct SecureFrame:
    uint16  magic           # 0xAA55
    uint8   version
    uint32  seq
    uint8   cmd
    uint16  encrypted_len
    char[]  nonce           # 12 bytes
    char[]  encrypted_data  # AES-GCM
    char[]  auth_tag        # 16 bytes
    uint32  crc32
```

**场景**: 传输包含隐私的剪贴板内容、日志等

---

## 7. 附录: 完整指令速查表

### Link Layer (0x00-0x0F)
| CMD ID | Name | Purpose | Payload Size |
|--------|------|---------|--------------|
| 0x01 | HANDSHAKE | 握手连接 | Variable |
| 0x02 | ACK | 确认响应 | 0 |
| 0x03 | HEARTBEAT | 保活心跳 | 0 |

### Input Layer (0x10-0x1F)
| CMD ID | Name | Purpose | Payload Size |
|--------|------|---------|--------------|
| 0x10 | TAP | 点击屏幕 | 4 bytes |
| 0x11 | SWIPE | 滑动手势 | 10 bytes |
| 0x1A | WAKE | 唤醒设备 | 0 |

### Input Extension (0x20-0x2F)
| CMD ID | Name | Purpose | Payload Size |
|--------|------|---------|--------------|
| 0x20 | INPUT_TEXT | 文本输入 | Variable |
| 0x21 | KEY_EVENT | 物理按键 | 6 bytes |

### Sense Layer (0x30-0x3F) ⭐
| CMD ID | Name | Purpose | Payload Size |
|--------|------|---------|--------------|
| 0x30 | GET_ACTIVITY | 获取前台 Activity | 0 |
| 0x31 | DUMP_HIERARCHY | 导出 UI 树 | 4 bytes |
| 0x32 | FIND_NODE | 计算卸载查找 | Variable |

### Lifecycle (0x40-0x4F)
| CMD ID | Name | Purpose | Payload Size |
|--------|------|---------|--------------|
| 0x40 | RESTART_APP | 重启应用 | Variable |
| 0x41 | GET_CLIPBOARD | 获取剪贴板 | 0 |
| 0x42 | SET_CLIPBOARD | 设置剪贴板 | Variable |

### Debug Layer (0x50-0x5F)
| CMD ID | Name | Purpose | Payload Size |
|--------|------|---------|--------------|
| 0x50 | GET_DEVICE_INFO | 设备信息 | 0 |
| 0x51 | LOGCAT | 日志获取 | Variable |

### Media Layer (0x60-0x6F)
| CMD ID | Name | Purpose | Payload Size |
|--------|------|---------|--------------|
| 0x60 | SCREENSHOT | 单帧截图 | 0 |
| 0x61 | IMG_REQ | 分片截图请求 | 0 |
| 0x62 | IMG_META | 截图元数据 | 12 bytes |
| 0x63 | IMG_CHUNK | 截图分片 | Variable |
| 0x64 | IMG_MISSING | 补包请求 | Variable |
| 0x65 | IMG_FIN | 传输完成 | 0 |

---

## 8. 总结与下一步

### 核心改进
1. **新增 15+ 条指令**,覆盖 Cortex 的 L1/L2 感知需求
2. **分层 ISA 架构**,支持未来扩展到 256 条指令
3. **计算卸载设计** (`FIND_NODE`),节省 99% 带宽
4. **混合数据格式** (JSON + 二进制 + 分片),兼顾效率与可读性

### 量化收益
| 指标 | 当前协议 | 升级后协议 |
|------|---------|----------|
| 查找元素 | 需截图 (~100KB) | 发送查询 (~20B) |
| 获取 Activity | 不支持 | < 5ms |
| UI 树分析 | 需 VLM (~5s) | 结构化查询 (~50ms) |
| 指令数量 | 10 条 | 30+ 条 |
| 扩展性 | 线性增长 | 分层命名空间 |

### 建议优先级
**P0 (必须)**: `GET_ACTIVITY`, `FIND_NODE`, `INPUT_TEXT`, `KEY_EVENT`
**P1 (重要)**: `DUMP_HIERARCHY`, `RESTART_APP`, 命名空间迁移
**P2 (优化)**: 压缩/缓存优化, 增量传输, 设备信息

### 下一步行动
1. **更新 `PROTOCOL.md`** - 添加新指令规范
2. **修改 `constants.py`** - 定义新的 CMD ID
3. **扩展 `protocol.py`** - 添加新的 pack/unpack 方法
4. **实现 Android 端** - 需要 AccessibilityService 权限
5. **测试验证** - 在实际微信/支付宝等应用中测试

**预计工作量**: 4-6 周 (含 Android 端实现和测试)

---

**附加建议**: 在开始编码前,建议先用 Python Mock 实现所有新指令的客户端 API,验证 Cortex 的调用流程是否流畅,避免后期大规模返工。
