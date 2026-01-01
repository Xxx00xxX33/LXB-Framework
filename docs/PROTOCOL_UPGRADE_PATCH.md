# LXB-Link 协议修正与漏洞补丁

## 📋 修正摘要

本文档针对 `PROTOCOL_UPGRADE_PROPOSAL.md` 中的**架构偏离**和**安全漏洞**进行修正。

### 核心修正原则

1. **Binary First** - 捍卫二进制优先，拒绝 JSON 膨胀
2. **Zero Copy** - 数据结构设计支持零拷贝解析
3. **Deterministic Size** - 优先使用定长结构，变长数据需显式标记
4. **Endianness Enforcement** - 强制小端序 (Little Endian)

### 修正概览

| 问题类别 | 原建议 | 修正方案 | 收益 |
|---------|--------|---------|------|
| JSON 膨胀 | FIND_NODE 返回 JSON | 紧凑二进制 (8B/node) | 节省 95% 带宽 |
| 并发冲突 | 无会话管理 | 引入 Session ID + 状态机 | 防止指令交叉 |
| 分片阻塞 | 单通道传输 | 双通道架构 (Control/Data) | 避免心跳饿死 |
| 字符串冗余 | 重复传输类名 | 字符串常量池 | UI 树压缩 60% |
| 字节序未定义 | 未明确规定 | 强制 Little Endian | 跨平台兼容 |

---

## 1. 捍卫二进制 (Binary Defense)

### 1.1 `CMD_FIND_NODE (0x32)` - 纯二进制响应

**原建议的问题**:
```python
# 错误示例 - 返回 JSON
{
  "nodes": [
    {"x": 500, "y": 800, "text": "登录", "id": "btn_login"}
  ]
}
# 单个节点 ~60 bytes (JSON + UTF-8)
```

**修正方案 - 三种返回模式的二进制定义**:

#### Mode 0: 仅中心坐标 (推荐用于快速点击)

```c
// 请求 (7+ bytes)
struct FindNodeRequest {
    uint8   match_type;     // 0=精确文本, 1=包含, 2=正则, 3=resource-id
    uint8   return_mode;    // 0=坐标, 1=边界框, 2=完整
    uint8   multi_match;    // 0=首个, 1=所有 (最多 255 个)
    uint16  timeout_ms;     // 查找超时 (LE)
    uint16  query_len;      // 查询字符串长度 (LE)
    char    query_str[];    // UTF-8 字符串 (无 null 终止符)
};

// 响应 Mode 0 (1 + 1 + N*4 bytes)
struct FindNodeResponse_Coords {
    uint8   status;         // 0=未找到, 1=成功, 2=超时, 3=错误
    uint8   count;          // 匹配数量 (最多 255)

    struct Coord {
        uint16  x;          // 中心 X 坐标 (LE)
        uint16  y;          // 中心 Y 坐标 (LE)
    } coords[count];        // 4 bytes per node
};

// 示例: 查找到 3 个 "登录" 按钮
// Payload: [0x01][0x03] [500,800] [520,1200] [510,900]
// Total: 1 + 1 + 3*4 = 14 bytes
// vs JSON: ~180 bytes (节省 92%)
```

#### Mode 1: 边界框 (用于手势规划)

```c
// 响应 Mode 1 (1 + 1 + N*8 bytes)
struct FindNodeResponse_Boxes {
    uint8   status;
    uint8   count;

    struct BoundingBox {
        uint16  left;       // LE
        uint16  top;        // LE
        uint16  right;      // LE
        uint16  bottom;     // LE
    } boxes[count];         // 8 bytes per node
};

// 示例: 1 个节点边界框
// Payload: [0x01][0x01] [100,200,600,300]
// Total: 10 bytes vs JSON: ~80 bytes
```

#### Mode 2: 完整节点信息 (用于复杂决策)

```c
// 响应 Mode 2 (变长)
struct FindNodeResponse_Full {
    uint8   status;
    uint8   count;

    struct NodeInfo {
        uint16  center_x;       // LE
        uint16  center_y;       // LE
        uint16  left, top;      // LE
        uint16  right, bottom;  // LE
        uint8   flags;          // bit0=clickable, bit1=visible,
                                // bit2=enabled, bit3=focused
        uint8   class_id;       // 类名索引 (见字符串池)
        uint16  text_len;       // LE
        char    text[];         // UTF-8 (无 null)
        uint16  res_id_len;     // LE
        char    resource_id[];  // UTF-8 (无 null)
    } nodes[count];
};

// 示例: 1 个完整节点
// [0x01][0x01] + [500,800,100,200,600,300][0x05][0x42]["登录"][0x000D]["btn_login"]
// Total: 2 + (12 + 2 + 6 + 2 + 9) = 33 bytes
// vs JSON: ~120 bytes (节省 72%)
```

**关键优化点**:
- **坐标压缩**: `uint16` 最大支持 65535,覆盖所有移动设备分辨率
- **Flags 位掩码**: 8 个布尔值压缩为 1 字节
- **类名索引化**: 不传输完整类名,用 1 字节 ID 引用字符串池 (见 1.4)

---

### 1.2 `CMD_INPUT_TEXT (0x20)` - 纯字节流

**原建议的问题**:
```python
# 错误 - 包装成 JSON
{
  "method": 1,
  "text": "Hello World",
  "clear_first": true
}
```

**修正方案**:

```c
// 请求 (9+ bytes)
struct InputTextRequest {
    uint8   method;         // 0=ADB, 1=Clipboard, 2=Accessibility
    uint8   flags;          // bit0=clear_first, bit1=press_enter_after
                            // bit2=hide_keyboard_after, bit3-7=保留
    uint16  target_x;       // 目标坐标 (0=当前焦点) LE
    uint16  target_y;       // LE
    uint16  delay_ms;       // 每字符输入延迟 (用于模拟真人) LE
    uint16  text_len;       // UTF-8 字节数 (LE)
    uint8   text[];         // 原始 UTF-8 字节流 (无 null)
};

// 响应 (2 bytes)
struct InputTextResponse {
    uint8   status;         // 0=失败, 1=成功, 2=部分成功
    uint8   actual_method;  // 实际使用的方法 (可能降级)
};

// 示例: 输入 "微信支付"
// Request: [0x01][0x01][0,0][0,0][50][0x000C]["微信支付"]
// Total: 9 + 12 = 21 bytes
// vs JSON: ~65 bytes
```

**关键设计**:
- **Flags 位掩码**: 4 个布尔选项压缩为 1 字节
- **延迟控制**: 支持模拟真人输入,防反作弊检测
- **坐标可选**: `(0,0)` 表示使用当前焦点,避免无效坐标传输

---

### 1.3 `CMD_DUMP_HIERARCHY (0x31)` - 扁平化二进制编码

**原建议的问题**:
- 完全依赖 JSON,失去二进制协议的意义
- 50KB XML 压缩后仍有 8KB,在弱网下需 2-3 秒

**修正方案 - 类 Parcel 的扁平化编码**:

#### 方案 A: 自定义二进制格式 (推荐)

```c
// 响应头 (14 bytes)
struct HierarchyHeader {
    uint8   version;        // 编码版本 (当前 0x01)
    uint8   compress;       // 0=原始, 1=zlib, 2=lz4
    uint32  original_size;  // 原始数据大小 (LE)
    uint32  compressed_size;// 压缩后大小 (LE)
    uint16  node_count;     // 节点总数 (LE)
    uint16  string_pool_size; // 字符串池条目数 (LE)
};

// 字符串池 (紧凑编码)
struct StringPool {
    struct StringEntry {
        uint8   str_len;    // 最长 255 字节
        char    str[];      // UTF-8 (无 null)
    } entries[string_pool_size];
};

// 节点数组 (扁平化存储)
struct UINode {
    uint8   parent_index;   // 父节点索引 (0xFF=根节点)
    uint8   child_count;    // 子节点数量
    uint8   flags;          // bit0=clickable, bit1=visible,
                            // bit2=enabled, bit3=focused,
                            // bit4=scrollable, bit5=editable
    uint8   class_id;       // 类名在字符串池中的索引
    uint16  left, top;      // LE
    uint16  right, bottom;  // LE
    uint8   text_id;        // 文本在字符串池中的索引 (0xFF=空)
    uint8   res_id;         // resource-id 索引 (0xFF=空)
    uint8   desc_id;        // content-desc 索引 (0xFF=空)
} nodes[node_count];        // 15 bytes per node (定长!)

// 完整结构
// [Header 14B] [StringPool] [Nodes Array] → 压缩 → 分片传输
```

**编码示例** (微信主界面 ~100 个节点):
```
原始数据:
- Header: 14 bytes
- StringPool: ~50 条 × 平均 20B = 1000 bytes
- Nodes: 100 × 15 = 1500 bytes
- Total: ~2.5 KB (未压缩)

压缩后 (zlib):
- ~800 bytes (压缩率 68%)

vs JSON 方案:
- 原始 JSON: ~50 KB
- 压缩后: ~8 KB
- 收益: 节省 90% 带宽!
```

#### 方案 B: 强制压缩的 JSON (备选)

如果必须保留 JSON 的可读性 (用于调试):

```c
// 响应头 (10 bytes)
struct HierarchyResponse {
    uint8   format;         // 必须是 0x01 (JSON)
    uint8   compress;       // 必须是 0x01 (zlib) 或 0x02 (lz4)
    uint32  original_size;  // LE
    uint32  compressed_size;// LE
    uint8   data[];         // 压缩后的 JSON
};

// 规则:
// 1. 禁止返回未压缩的 JSON (format=1, compress=0)
// 2. 如果 original_size > 10KB, 自动触发分片传输
// 3. JSON 必须精简: 去除空格/换行, 使用短字段名
```

**精简 JSON 格式** (强制):
```json
{
  "w": "com.tencent.mm/LauncherUI",
  "t": 1735689600000,
  "n": [
    {
      "i": "search_bar",
      "c": "EditText",
      "txt": "",
      "d": "搜索",
      "b": [100,200,500,280],
      "f": 5,
      "kids": []
    }
  ]
}
```

**字段缩写映射**:
- `w` = window
- `t` = timestamp
- `n` = nodes
- `i` = id
- `c` = class
- `txt` = text
- `d` = desc
- `b` = bounds
- `f` = flags (位掩码: clickable=1, visible=2, enabled=4...)

**强制规则**: 客户端库必须提供 `expand_json()` 工具函数还原完整字段名

---

### 1.4 字符串常量池 (String Pool) 设计

**问题**: UI 树中 "android.widget.TextView" 出现 50+ 次,浪费 1.5KB

**解决方案**: 预定义常量池 + 动态扩展

#### 预定义类名常量 (0x00-0x3F)

```python
# constants.py
CLASS_POOL = {
    0x00: "android.view.View",
    0x01: "android.view.ViewGroup",
    0x02: "android.widget.TextView",
    0x03: "android.widget.EditText",
    0x04: "android.widget.Button",
    0x05: "android.widget.ImageView",
    0x06: "android.widget.LinearLayout",
    0x07: "android.widget.RelativeLayout",
    0x08: "android.widget.FrameLayout",
    0x09: "android.widget.ListView",
    0x0A: "android.widget.RecyclerView",
    0x0B: "android.widget.ScrollView",
    # ... 共 64 个常用类 (0x00-0x3F)

    # 0x40-0xFE: 动态扩展 (在 StringPool 中定义)
    0xFF: None  # 特殊标记: 无类名
}
```

#### 动态字符串池编码

```c
// StringPool 条目
struct StringEntry {
    uint8   id;             // 0x40-0xFE 可用 (0x00-0x3F 保留给预定义)
    uint8   length;         // 字符串长度
    char    data[];         // UTF-8 数据
};

// 示例: 自定义控件 "com.tencent.mm.ui.CustomButton"
// [0x40][0x22]["com.tencent.mm.ui.CustomButton"]
// 34 bytes (首次传输)

// 后续节点引用:
// class_id = 0x40 (仅 1 byte!)
```

**收益计算**:
```
微信主界面统计:
- TextView: 30 次 × 28 bytes = 840 bytes
- 改用索引: 30 × 1 byte = 30 bytes
- 节省: 810 bytes (单个类名)

总收益 (10 种常用类):
- 原始: ~5000 bytes
- 索引化: ~200 bytes
- 节省: 96%
```

---

### 1.5 坐标压缩 (可选优化)

**场景**: 大部分手机屏幕 < 4096×4096, `uint16` 的高 4 bits 浪费

**方案**: 12-bit 坐标打包

```c
// 标准方案 (推荐 - 简单)
struct Coord16 {
    uint16  x;  // 0-65535
    uint16  y;
};  // 4 bytes

// 压缩方案 (复杂度高 - 不推荐)
struct Coord12 {
    // 打包 2 个坐标到 3 bytes
    // X: 12 bits (0-4095)
    // Y: 12 bits (0-4095)
    uint8   packed[3];  // [XXXX XXXX][YYYY XXXX][YYYY YYYY]
};  // 3 bytes per coord

// 解包代码 (Python)
def unpack_coord12(data):
    x = ((data[0] << 4) | (data[1] >> 4)) & 0xFFF
    y = ((data[1] << 8) | data[2]) & 0xFFF
    return x, y
```

**权衡**:
- 节省: 25% 空间 (4B → 3B)
- 代价: 解析复杂度 +50%, CPU 开销增加
- 建议: **仅在极端带宽受限场景启用** (通过 `HANDSHAKE` 协商)

---

## 2. 漏洞修补 (Vulnerability Patch)

### 2.1 并发冲突问题

**漏洞描述**:
```python
# Cortex 同时发送两条指令
t=0ms:  Client 发送 CMD_TAP(seq=100)
t=1ms:  Client 发送 CMD_DUMP_HIERARCHY(seq=101)
t=5ms:  Server 响应 ACK(seq=101)  # UI 树的 ACK
t=10ms: Server 响应 ACK(seq=100)  # TAP 的 ACK (延迟)

# 问题: Client 无法区分哪个 ACK 对应哪个指令!
# 如果 DUMP_HIERARCHY 触发了 UI 变化, TAP 可能点击错误位置
```

**修正方案 1: 扩展 ACK 结构 (推荐)**

```c
// 当前 ACK (仅序列号)
struct ACK_Old {
    // Payload: 空
    // 依赖帧头的 seq 字段
};

// 修正后的 ACK (回显指令)
struct ACK_Enhanced {
    uint8   cmd_echo;       // 回显被确认的指令 ID
    uint32  seq_echo;       // 回显序列号 (冗余校验)
    uint8   status;         // 0=成功, 1=失败, 2=部分成功
    uint16  error_code;     // 错误码 (status!=0 时有效)
};  // 8 bytes

// 示例
Client → Server: [seq=100, CMD_TAP, ...]
Server → Client: [seq=100, CMD_ACK, payload=[0x10, 0x00000064, 0x00, 0x0000]]
                                             ^^^^  ^^^^^^^^
                                           TAP=0x10  seq=100
```

**修正方案 2: Session ID (用于复杂场景)**

```c
// 扩展帧头
struct FrameHeader {
    uint16  magic;          // 0xAA55
    uint8   version;        // 0x01
    uint8   session_id;     // 会话 ID (0x00=默认, 0x01-0xFF=并发会话)
    uint32  seq;            // LE
    uint8   cmd;
    uint16  length;         // LE
    // ... data + crc32
};

// 使用场景
// Session 0: 控制流 (TAP/SWIPE/KEY_EVENT)
// Session 1: 数据流 (DUMP_HIERARCHY/SCREENSHOT)
// Session 2: 调试流 (LOGCAT/PERF_STATS)

// Client 同时发送:
[session=0, seq=100, CMD_TAP]
[session=1, seq=101, CMD_DUMP_HIERARCHY]

// Server 响应:
[session=0, seq=100, CMD_ACK]  // TAP 完成
[session=1, seq=101, CMD_IMG_META]  // 开始传输 UI 树
```

**兼容性处理**:
```python
# protocol.py
def pack(seq, cmd, payload, session_id=0):
    if session_id == 0:
        # v1.0 兼容模式 (不传 session_id)
        header = struct.pack('<HBIBxx', MAGIC, VERSION, seq, cmd)
    else:
        # v2.0 模式
        header = struct.pack('<HBBIB', MAGIC, VERSION, session_id, seq, cmd)
    # ...
```

---

### 2.2 分片风暴与 QoS

**漏洞描述**:
```python
# 场景: 低带宽网络 (2G: 100 KB/s)
t=0s:   Client 发送 CMD_DUMP_HIERARCHY
t=0.1s: Server 开始发送 500KB UI 树 (500 个 1KB 分片)
t=0.2s: Client 心跳包被分片淹没, 无法及时发送
t=3s:   Server 认为 Client 断连, 停止传输
t=3.5s: Client 心跳包终于发出, 但为时已晚

# 结果: 传输失败, 需要重试, 浪费 3 秒
```

**修正方案: 双通道架构**

#### Channel 设计

```c
// 扩展帧头 (增加 channel 字段)
struct FrameHeader_v2 {
    uint16  magic;          // 0xAA55
    uint8   version;        // 0x02 (启用通道)
    uint8   channel;        // 0=Control, 1=Data, 2=Debug
    uint32  seq;            // LE (每个通道独立序列号)
    uint8   cmd;
    uint16  length;         // LE
};

// 通道定义
enum Channel {
    CH_CONTROL = 0,     // 控制通道: 心跳/ACK/小指令 (优先级最高)
    CH_DATA = 1,        // 数据通道: 截图/UI树/大数据 (优先级中)
    CH_DEBUG = 2        // 调试通道: 日志/性能监控 (优先级低)
};
```

#### QoS 策略

```python
# Server 端发送队列
class QoSScheduler:
    def __init__(self):
        self.queues = {
            CH_CONTROL: Queue(maxsize=10),   # 控制通道: 10 包缓冲
            CH_DATA: Queue(maxsize=1000),    # 数据通道: 1000 包缓冲
            CH_DEBUG: Queue(maxsize=100)
        }

    def send_next_packet(self):
        # 优先级调度: Control > Data > Debug
        # 比例: 5:3:1 (每发 5 个控制包, 3 个数据包, 1 个调试包)

        for _ in range(5):
            if not self.queues[CH_CONTROL].empty():
                self._send(self.queues[CH_CONTROL].get())

        for _ in range(3):
            if not self.queues[CH_DATA].empty():
                self._send(self.queues[CH_DATA].get())

        if not self.queues[CH_DEBUG].empty():
            self._send(self.queues[CH_DEBUG].get())
```

**指令分配**:
```python
# constants.py
CHANNEL_MAP = {
    # Control Channel (必须快速响应)
    CMD_HANDSHAKE: CH_CONTROL,
    CMD_ACK: CH_CONTROL,
    CMD_HEARTBEAT: CH_CONTROL,
    CMD_TAP: CH_CONTROL,
    CMD_SWIPE: CH_CONTROL,
    CMD_KEY_EVENT: CH_CONTROL,
    CMD_FIND_NODE: CH_CONTROL,      # 快速查找
    CMD_GET_ACTIVITY: CH_CONTROL,

    # Data Channel (大数据传输)
    CMD_DUMP_HIERARCHY: CH_DATA,
    CMD_IMG_REQ: CH_DATA,
    CMD_IMG_META: CH_DATA,
    CMD_IMG_CHUNK: CH_DATA,
    CMD_SCREENSHOT: CH_DATA,

    # Debug Channel (可丢弃)
    CMD_LOGCAT: CH_DEBUG,
    CMD_PERF_STATS: CH_DEBUG,
}
```

**带宽限制**:
```python
# transport.py
class DataChannelLimiter:
    """限制数据通道发送速率, 避免饿死控制通道"""

    def __init__(self, max_kbps=500):
        self.max_bytes_per_sec = max_kbps * 1024
        self.window_size = 1.0  # 1 秒滑动窗口
        self.sent_bytes = []    # [(timestamp, bytes), ...]

    def can_send(self, packet_size):
        now = time.time()

        # 清理过期记录
        self.sent_bytes = [(t, b) for t, b in self.sent_bytes
                          if now - t < self.window_size]

        # 计算当前窗口已发送字节数
        current_usage = sum(b for _, b in self.sent_bytes)

        # 判断是否超限
        if current_usage + packet_size > self.max_bytes_per_sec:
            return False

        self.sent_bytes.append((now, packet_size))
        return True
```

---

### 2.3 字节序陷阱

**漏洞描述**:
```python
# Android (Java) - 默认 Big Endian
ByteBuffer buf = ByteBuffer.allocate(4);
buf.putInt(0x12345678);
// 存储: [0x12, 0x34, 0x56, 0x78]

# Python - struct 默认 Native (可能是 Little Endian)
data = struct.pack('I', 0x12345678)
// 存储: [0x78, 0x56, 0x34, 0x12]

# 结果: 解析错误!
# Python 收到的 text_len = 0x12345678
# 实际应该是 0x78563412
```

**修正方案 1: 强制字节序声明**

```python
# protocol.py - 所有 pack/unpack 必须显式指定 '<' (Little Endian)

# 错误写法 (字节序不确定)
struct.pack('HH', x, y)         # ❌ 危险!

# 正确写法 (强制小端)
struct.pack('<HH', x, y)        # ✅ 安全

# 完整示例
FRAME_HEADER_FORMAT = '<HBIBH'  # < 表示 Little Endian
#                      ^ 必须放在最前面

def pack(seq, cmd, payload):
    header = struct.pack(FRAME_HEADER_FORMAT,
                        MAGIC, VERSION, seq, cmd, len(payload))
    # ...
```

**修正方案 2: 协议规范强制要求**

在 `PROTOCOL.md` 中添加:

```markdown
## 字节序规范 (Endianness Specification)

**强制要求**: LXB-Link 协议的所有多字节整数**必须**使用 **Little Endian (小端序)** 编码。

### 各语言实现要求

#### Python
```python
# 使用 struct 模块时, 必须在 format string 开头加 '<'
struct.pack('<I', value)   # ✅ 正确
struct.pack('I', value)    # ❌ 错误 (字节序不确定)
```

#### Java/Kotlin (Android)
```java
// 使用 ByteBuffer 时, 必须设置 LITTLE_ENDIAN
ByteBuffer buffer = ByteBuffer.allocate(4);
buffer.order(ByteOrder.LITTLE_ENDIAN);  // ✅ 必须!
buffer.putInt(value);
```

#### C/C++
```c
// 使用条件编译处理不同平台
#include <endian.h>

uint32_t to_le32(uint32_t val) {
#if __BYTE_ORDER == __LITTLE_ENDIAN
    return val;
#else
    return __bswap_32(val);
#endif
}
```

### 验证测试

所有实现必须通过以下测试:
```python
# 测试用例: 编码 0x12345678
expected = b'\x78\x56\x34\x12'  # Little Endian
assert pack_uint32(0x12345678) == expected
```
```

**修正方案 3: 运行时检测**

```python
# protocol.py - 启动时检测字节序
import sys

def check_endianness():
    """检测当前平台字节序, 如果不是小端则警告"""
    test_val = 0x12345678
    packed = struct.pack('I', test_val)  # 不加 '<', 使用 native

    if packed == b'\x78\x56\x34\x12':
        # Little Endian - OK
        pass
    elif packed == b'\x12\x34\x56\x78':
        # Big Endian - 需要显式转换
        print("WARNING: Platform is Big Endian, forcing Little Endian conversion",
              file=sys.stderr)
    else:
        raise RuntimeError("Unknown endianness!")

# 在模块导入时自动检测
check_endianness()
```

---

## 3. 极致优化 (Optimization)

### 3.1 字符串去重 - 完整实现

#### 预定义常量池 (静态)

```python
# constants.py
# 常用 Android 类名 (0x00-0x3F)
PREDEFINED_CLASSES = [
    "android.view.View",
    "android.view.ViewGroup",
    "android.widget.TextView",
    "android.widget.EditText",
    "android.widget.Button",
    "android.widget.ImageView",
    "android.widget.ImageButton",
    "android.widget.LinearLayout",
    "android.widget.RelativeLayout",
    "android.widget.FrameLayout",
    "android.widget.ListView",
    "android.widget.RecyclerView",
    "android.widget.ScrollView",
    "android.widget.HorizontalScrollView",
    "android.webkit.WebView",
    # ... 共 64 个常用类
]

# 常用文本 (0x40-0x7F)
PREDEFINED_TEXTS = [
    "",                 # 0x40: 空字符串 (高频!)
    "确定",             # 0x41
    "取消",             # 0x42
    "返回",             # 0x43
    "搜索",             # 0x44
    "设置",             # 0x45
    "更多",             # 0x46
    # ... 共 64 个常用文本
]

# 索引映射
CLASS_TO_ID = {cls: i for i, cls in enumerate(PREDEFINED_CLASSES)}
TEXT_TO_ID = {txt: i + 0x40 for i, txt in enumerate(PREDEFINED_TEXTS)}
```

#### 动态字符串池 (运行时)

```python
# protocol.py
class StringPool:
    """动态字符串池 - 用于 UI 树传输"""

    def __init__(self):
        self.pool = {}          # {string: id}
        self.next_id = 0x80     # 动态 ID 从 0x80 开始

    def add(self, s):
        """添加字符串, 返回 ID"""
        # 检查预定义池
        if s in CLASS_TO_ID:
            return CLASS_TO_ID[s]
        if s in TEXT_TO_ID:
            return TEXT_TO_ID[s]

        # 检查动态池
        if s in self.pool:
            return self.pool[s]

        # 新增
        if self.next_id > 0xFE:
            raise ValueError("String pool overflow (max 255 entries)")

        self.pool[s] = self.next_id
        self.next_id += 1
        return self.pool[s]

    def pack(self):
        """序列化字符串池"""
        # 仅打包动态部分 (0x80-0xFE)
        entries = sorted(self.pool.items(), key=lambda x: x[1])
        packed = struct.pack('<H', len(entries))  # 条目数

        for string, str_id in entries:
            encoded = string.encode('utf-8')
            packed += struct.pack('<BB', str_id, len(encoded))
            packed += encoded

        return packed

    @staticmethod
    def unpack(data):
        """反序列化字符串池"""
        offset = 0
        count = struct.unpack('<H', data[offset:offset+2])[0]
        offset += 2

        pool = {}
        for _ in range(count):
            str_id, length = struct.unpack('<BB', data[offset:offset+2])
            offset += 2

            string = data[offset:offset+length].decode('utf-8')
            offset += length

            pool[str_id] = string

        return pool, offset

# 使用示例
pool = StringPool()
class_id = pool.add("android.widget.TextView")  # → 0x02 (预定义)
text_id = pool.add("登录")                       # → 0x80 (动态)
text_id2 = pool.add("登录")                      # → 0x80 (复用)

packed_pool = pool.pack()  # 仅包含 "登录" (6 bytes)
```

#### UI 树打包 (使用字符串池)

```python
# protocol.py
def pack_hierarchy_with_pool(nodes):
    """打包 UI 树, 使用字符串池"""
    pool = StringPool()
    packed_nodes = b''

    for node in nodes:
        # 收集所有字符串
        class_id = pool.add(node['class'])
        text_id = pool.add(node.get('text', ''))
        res_id = pool.add(node.get('resource_id', ''))

        # 打包节点 (使用 ID)
        packed_nodes += struct.pack('<BBBHHHH',
            node['parent_index'],
            node['child_count'],
            node['flags'],
            class_id,
            node['bounds'][0], node['bounds'][1],  # left, top
            node['bounds'][2], node['bounds'][3]   # right, bottom
        )
        packed_nodes += struct.pack('<BBB', text_id, res_id, 0xFF)

    # 组装最终数据
    header = struct.pack('<HIIIHH',
        0x01,                    # version
        len(packed_nodes),       # original_size
        0,                       # compressed_size (稍后填充)
        len(nodes),              # node_count
        len(pool.pool)           # string_pool_size
    )

    pool_data = pool.pack()
    final_data = header + pool_data + packed_nodes

    # 压缩
    compressed = zlib.compress(final_data, level=6)

    # 更新压缩后大小
    final_header = struct.pack('<HIIIHH',
        0x01,
        len(final_data),
        len(compressed),
        len(nodes),
        len(pool.pool)
    )

    return final_header + compressed
```

**压缩效果对比**:
```
微信主界面 (100 个节点):

方案 1: JSON
- 原始: 52 KB
- zlib: 8 KB

方案 2: 二进制 (无字符串池)
- 原始: 10 KB (每个节点重复类名)
- zlib: 3.5 KB

方案 3: 二进制 + 字符串池
- 原始: 2.5 KB (类名索引化)
- zlib: 800 bytes

收益: 比 JSON 方案节省 90%!
```

---

### 3.2 差分编码优化

**场景**: `FIND_NODE` 返回多个相邻节点 (例如列表项)

```python
# 原始坐标
coords = [(100, 200), (100, 300), (100, 400), (100, 500)]
# 标准编码: 4 * 4 = 16 bytes

# 观察: X 坐标相同, Y 坐标等差
```

**优化方案: 差分编码**

```c
// 响应结构
struct FindNodeResponse_Delta {
    uint8   status;
    uint8   count;
    uint8   encoding;       // 0=绝对坐标, 1=差分编码

    // encoding=1 时:
    uint16  base_x;         // 第一个坐标 (LE)
    uint16  base_y;         // LE

    struct Delta {
        int8   dx;          // 相对偏移 (-128~127)
        int8   dy;
    } deltas[count-1];      // 2 bytes per delta
};

// 示例: 4 个坐标
// 绝对编码: [0x01][0x04][0x00] + 4*4 = 19 bytes
// 差分编码: [0x01][0x04][0x01][100,200] + [(0,100), (0,100), (0,100)]
//         = 1 + 1 + 1 + 4 + 3*2 = 13 bytes
// 节省: 31%
```

**实现**:

```python
# protocol.py
def pack_find_node_response(coords, use_delta=True):
    if not coords:
        return struct.pack('<BB', 0, 0)  # status=0, count=0

    if len(coords) == 1 or not use_delta:
        # 绝对坐标
        data = struct.pack('<BBB', 1, len(coords), 0)
        for x, y in coords:
            data += struct.pack('<HH', x, y)
        return data

    # 检查是否适合差分编码
    base_x, base_y = coords[0]
    can_use_delta = True

    for i in range(1, len(coords)):
        dx = coords[i][0] - coords[i-1][0]
        dy = coords[i][1] - coords[i-1][1]

        if dx < -128 or dx > 127 or dy < -128 or dy > 127:
            can_use_delta = False
            break

    if can_use_delta:
        # 差分编码
        data = struct.pack('<BBBHH', 1, len(coords), 1, base_x, base_y)

        for i in range(1, len(coords)):
            dx = coords[i][0] - coords[i-1][0]
            dy = coords[i][1] - coords[i-1][1]
            data += struct.pack('<bb', dx, dy)  # 有符号

        return data
    else:
        # 降级到绝对坐标
        return pack_find_node_response(coords, use_delta=False)
```

---

### 3.3 位域压缩 (Bit Fields)

**场景**: 节点 flags 包含 8 个布尔值

```python
# 错误方案 - 每个 flag 用 1 byte
struct NodeFlags:
    uint8 clickable
    uint8 visible
    uint8 enabled
    uint8 focused
    uint8 scrollable
    uint8 editable
    uint8 checkable
    uint8 checked
# Total: 8 bytes

# 正确方案 - 位掩码
struct NodeFlags:
    uint8 flags  # bit0=clickable, bit1=visible, ...
# Total: 1 byte (节省 87.5%)
```

**实现**:

```python
# constants.py
# Flag 位定义
FLAG_CLICKABLE  = 0x01  # bit 0
FLAG_VISIBLE    = 0x02  # bit 1
FLAG_ENABLED    = 0x04  # bit 2
FLAG_FOCUSED    = 0x08  # bit 3
FLAG_SCROLLABLE = 0x10  # bit 4
FLAG_EDITABLE   = 0x20  # bit 5
FLAG_CHECKABLE  = 0x40  # bit 6
FLAG_CHECKED    = 0x80  # bit 7

# protocol.py
def encode_flags(clickable, visible, enabled, focused,
                scrollable, editable, checkable, checked):
    """编码 flags 为单字节"""
    flags = 0
    if clickable: flags |= FLAG_CLICKABLE
    if visible: flags |= FLAG_VISIBLE
    if enabled: flags |= FLAG_ENABLED
    if focused: flags |= FLAG_FOCUSED
    if scrollable: flags |= FLAG_SCROLLABLE
    if editable: flags |= FLAG_EDITABLE
    if checkable: flags |= FLAG_CHECKABLE
    if checked: flags |= FLAG_CHECKED
    return flags

def decode_flags(flags):
    """解码 flags 字节"""
    return {
        'clickable': bool(flags & FLAG_CLICKABLE),
        'visible': bool(flags & FLAG_VISIBLE),
        'enabled': bool(flags & FLAG_ENABLED),
        'focused': bool(flags & FLAG_FOCUSED),
        'scrollable': bool(flags & FLAG_SCROLLABLE),
        'editable': bool(flags & FLAG_EDITABLE),
        'checkable': bool(flags & FLAG_CHECKABLE),
        'checked': bool(flags & FLAG_CHECKED),
    }

# 使用
flags = encode_flags(
    clickable=True,
    visible=True,
    enabled=False,
    focused=False,
    scrollable=True,
    editable=False,
    checkable=False,
    checked=False
)
# flags = 0x13 (0001 0011)
```

---

## 4. 协议版本升级路径

### 4.1 版本定义

```python
# constants.py
PROTOCOL_VERSION_1_0 = 0x0100  # 当前版本 (兼容模式)
PROTOCOL_VERSION_2_0 = 0x0200  # 新版本 (二进制优先)

# 特性位掩码 (用于能力协商)
FEATURE_BINARY_HIERARCHY = 0x0001  # 支持二进制 UI 树
FEATURE_STRING_POOL      = 0x0002  # 支持字符串池
FEATURE_DELTA_ENCODING   = 0x0004  # 支持差分编码
FEATURE_MULTI_CHANNEL    = 0x0008  # 支持多通道
FEATURE_ENHANCED_ACK     = 0x0010  # 支持增强 ACK
FEATURE_QOS              = 0x0020  # 支持 QoS
```

### 4.2 握手协商

```c
// HANDSHAKE 请求 (v2.0)
struct HandshakeRequest_v2 {
    uint16  protocol_version;   // 0x0200 LE
    uint32  features;           // 支持的特性位掩码 LE
    uint16  client_name_len;    // 客户端名称长度 LE
    char    client_name[];      // UTF-8 (e.g., "LXB-Cortex/1.0")
};

// HANDSHAKE 响应
struct HandshakeResponse_v2 {
    uint16  accepted_version;   // Server 选择的版本 LE
    uint32  features;           // Server 支持的特性 LE
    uint16  server_name_len;    // LE
    char    server_name[];      // UTF-8 (e.g., "LXB-Link-Android/2.0")
};

// 协商逻辑
// 1. Client 发送自己支持的最高版本 (0x0200)
// 2. Server 对比自己的版本:
//    - 如果 Server 是 v1.0 → 返回 0x0100 (降级)
//    - 如果 Server 是 v2.0 → 返回 0x0200 (启用新特性)
// 3. 双方取 features 的交集作为实际启用的特性
```

### 4.3 兼容性实现

```python
# transport.py
class LXBTransport:
    def __init__(self):
        self.protocol_version = PROTOCOL_VERSION_1_0
        self.features = 0

    def handshake(self):
        # 发送 v2.0 握手
        request = struct.pack('<HI',
            PROTOCOL_VERSION_2_0,
            FEATURE_BINARY_HIERARCHY |
            FEATURE_STRING_POOL |
            FEATURE_DELTA_ENCODING |
            FEATURE_MULTI_CHANNEL
        )

        response = self.send_reliable(CMD_HANDSHAKE, request)

        # 解析响应
        accepted_ver, server_features = struct.unpack('<HI', response[:6])

        # 协商结果
        self.protocol_version = accepted_ver
        self.features = server_features & (
            FEATURE_BINARY_HIERARCHY |
            FEATURE_STRING_POOL |
            FEATURE_DELTA_ENCODING |
            FEATURE_MULTI_CHANNEL
        )

        print(f"Negotiated protocol: v{accepted_ver>>8}.{accepted_ver&0xFF}")
        print(f"Enabled features: 0x{self.features:04X}")

    def dump_hierarchy(self):
        if self.features & FEATURE_BINARY_HIERARCHY:
            # 使用二进制格式
            return self._dump_hierarchy_binary()
        else:
            # 降级到 JSON 格式
            return self._dump_hierarchy_json()
```

---

## 5. 性能基准测试 (Benchmarks)

### 5.1 编码性能对比

```python
# benchmark.py
import time
import json
import zlib

def benchmark_encoding():
    # 测试数据: 100 个节点
    nodes = [generate_mock_node() for _ in range(100)]

    # 方案 1: JSON
    start = time.time()
    json_data = json.dumps(nodes).encode('utf-8')
    json_compressed = zlib.compress(json_data)
    json_time = time.time() - start

    # 方案 2: 二进制 (无字符串池)
    start = time.time()
    binary_data = pack_nodes_simple(nodes)
    binary_compressed = zlib.compress(binary_data)
    binary_time = time.time() - start

    # 方案 3: 二进制 + 字符串池
    start = time.time()
    pooled_data = pack_hierarchy_with_pool(nodes)
    pooled_time = time.time() - start

    print(f"{'Scheme':<20} {'Raw Size':<12} {'Compressed':<12} {'Time (ms)':<12}")
    print(f"{'-'*60}")
    print(f"{'JSON':<20} {len(json_data):<12} {len(json_compressed):<12} {json_time*1000:.2f}")
    print(f"{'Binary':<20} {len(binary_data):<12} {len(binary_compressed):<12} {binary_time*1000:.2f}")
    print(f"{'Binary+Pool':<20} {len(pooled_data):<12} {'N/A':<12} {pooled_time*1000:.2f}")

# 预期结果:
# Scheme               Raw Size     Compressed   Time (ms)
# ------------------------------------------------------------
# JSON                 52341        8234         12.5
# Binary               10240        3456         3.2
# Binary+Pool          2567         N/A          4.8
#
# 结论: Binary+Pool 最小, Binary 最快, JSON 最慢
```

### 5.2 解析性能对比

```python
def benchmark_decoding():
    # 解析 100 个节点
    json_data = generate_json_hierarchy()
    binary_data = generate_binary_hierarchy()

    # JSON 解析
    start = time.time()
    for _ in range(1000):
        nodes = json.loads(json_data)
    json_time = time.time() - start

    # 二进制解析
    start = time.time()
    for _ in range(1000):
        nodes = unpack_hierarchy(binary_data)
    binary_time = time.time() - start

    print(f"JSON decode:    {json_time*1000:.2f} ms (1000 iterations)")
    print(f"Binary decode:  {binary_time*1000:.2f} ms (1000 iterations)")
    print(f"Speedup:        {json_time/binary_time:.2f}x")

# 预期结果:
# JSON decode:    234.5 ms
# Binary decode:  45.2 ms
# Speedup:        5.2x
```

---

## 6. 迁移指南 (Migration Guide)

### 6.1 客户端迁移

```python
# 旧代码 (v1.0)
client = LXBLinkClient('192.168.1.100')
client.handshake()
img = client.request_screenshot()

# 新代码 (v2.0) - 向后兼容
client = LXBLinkClient('192.168.1.100', protocol_version='2.0')
client.handshake()  # 自动协商

# 使用新特性
if client.supports(FEATURE_BINARY_HIERARCHY):
    hierarchy = client.dump_hierarchy_binary()  # 快 10x
else:
    hierarchy = client.dump_hierarchy()  # 降级到 JSON
```

### 6.2 Android 端迁移

```kotlin
// UiHierarchyDumper.kt
class UiHierarchyDumper(val protocolVersion: Int) {
    fun dumpHierarchy(format: DumpFormat): ByteArray {
        return when (protocolVersion) {
            0x0100 -> dumpAsJson()          // v1.0
            0x0200 -> dumpAsBinary()        // v2.0
            else -> throw UnsupportedVersionException()
        }
    }

    private fun dumpAsBinary(): ByteArray {
        val nodes = collectNodes()
        val stringPool = StringPool()

        val output = ByteArrayOutputStream()
        val buffer = ByteBuffer.allocate(1024)
        buffer.order(ByteOrder.LITTLE_ENDIAN)  // 强制小端!

        // 写入头
        buffer.putShort(0x01)  // version
        buffer.putInt(0)       // original_size (稍后填充)
        buffer.putInt(0)       // compressed_size
        buffer.putShort(nodes.size.toShort())
        buffer.putShort(0)     // string_pool_size (稍后填充)

        // 写入字符串池
        // ...

        // 写入节点
        for (node in nodes) {
            buffer.put(node.parentIndex.toByte())
            buffer.put(node.childCount.toByte())
            buffer.put(node.flags)
            buffer.put(stringPool.add(node.className).toByte())
            buffer.putShort(node.bounds.left.toShort())
            buffer.putShort(node.bounds.top.toShort())
            buffer.putShort(node.bounds.right.toShort())
            buffer.putShort(node.bounds.bottom.toShort())
            // ...
        }

        return output.toByteArray()
    }
}
```

---

## 7. 总结与建议

### 7.1 核心修正点

| 修正项 | 原建议 | 修正后 | 收益 |
|-------|--------|--------|------|
| FIND_NODE | JSON 响应 | 二进制 (4-15B/node) | 节省 92% |
| INPUT_TEXT | JSON 包装 | 纯字节流 | 节省 67% |
| DUMP_HIERARCHY | JSON 可选 | 二进制+字符串池 | 节省 90% |
| 并发控制 | 无 | Session ID + 增强 ACK | 防冲突 |
| QoS | 无 | 双通道 + 带宽限制 | 避免阻塞 |
| 字节序 | 未定义 | 强制 Little Endian | 跨平台 |
| 字符串冗余 | 重复传输 | 常量池 + 动态池 | 节省 96% |

### 7.2 优先级建议

**P0 (必须立即修正)**:
1. 强制字节序为 Little Endian (修改所有 `struct.pack`)
2. `FIND_NODE` 改为二进制响应
3. `INPUT_TEXT` 去除 JSON 包装

**P1 (重要优化)**:
4. 增强 ACK 结构 (回显 cmd)
5. `DUMP_HIERARCHY` 实现二进制格式
6. 字符串常量池

**P2 (性能优化)**:
7. 双通道架构
8. 差分编码
9. QoS 限速

### 7.3 实施检查清单

- [ ] 修改 `constants.py` - 添加预定义常量池
- [ ] 修改 `protocol.py` - 所有 pack/unpack 强制 `'<'` 前缀
- [ ] 实现 `StringPool` 类
- [ ] 重构 `pack_find_node_response()` 为二进制
- [ ] 重构 `pack_input_text()` 去除 JSON
- [ ] 实现 `pack_hierarchy_binary()` + 字符串池
- [ ] 扩展 ACK 结构添加 `cmd_echo`
- [ ] 添加协议版本协商逻辑
- [ ] 实现双通道发送调度器
- [ ] 编写单元测试验证字节序
- [ ] 更新 `PROTOCOL.md` 文档
- [ ] Android 端同步修改 `ByteBuffer.order()`

### 7.4 性能目标

修正后的协议应达到:

| 指标 | 当前 (JSON) | 目标 (Binary) | 提升 |
|------|-------------|---------------|------|
| FIND_NODE 响应 | ~200B | ~14B | 14x |
| UI 树传输 | ~8KB | ~800B | 10x |
| 编码速度 | 12.5ms | 4.8ms | 2.6x |
| 解析速度 | 234ms | 45ms | 5.2x |
| 内存占用 | 52KB | 2.5KB | 20x |

---

**最终建议**: 在开始实施前,建议创建 `protocol_v2` 分支,保持 v1.0 代码不变,待 v2.0 测试稳定后再合并。同时,所有二进制格式必须编写详细的 **解析器测试用例** (包括错误数据测试),确保鲁棒性。
