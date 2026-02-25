# LXB-Link

## 1. Scope
LXB-Link 是 PC 侧到 Android 端的协议客户端层，负责可靠发送命令、接收响应。

## 2. Architecture
代码目录：`src/lxb_link/`

```
src/lxb_link/
├── __init__.py
├── client.py               # 主客户端 API
├── transport.py            # 可靠 UDP 传输 (Stop-and-Wait ARQ)
├── protocol.py             # 协议帧编解码
└── constants.py            # 命令常量定义
```

### 架构层次

```
应用层 (Cortex, MapBuilder)
        ↓
  LXBLinkClient (统一 API)
        ↓
  ProtocolFrame (协议编解码)
        ↓
  Transport (可靠 UDP 传输)
        ↓
  UDP Socket (网络通信)
```

## 3. Core Flow

### 3.1 命令执行流程

```
client.tap(500, 800)
    │
    v
编码为协议帧 (MAGIC + CMD + LEN + SEQ + PAYLOAD + CHECKSUM)
    │
    v
发送 + 等待 ACK (超时重传，最多 MAX_RETRIES)
    │
    v
接收响应帧 + 校验
    │
    v
解析结果并返回
```

### 3.2 可靠传输原理

Stop-and-Wait ARQ 协议：
1. 发送数据帧后启动定时器
2. 收到 ACK 后确认发送成功
3. 超时未收到 ACK 则自动重传

## 4. 协议帧结构规范

### 4.1 帧格式（字节级）

```
┌─────────┬─────────┬─────────┬─────────┬─────────┬─────────┬─────────┐
│ Magic   │ Ver     │ Seq     │ Cmd     │ Len     │ Data    │ CRC32   │
│ 2 bytes │ 1 byte  │ 4 bytes │ 1 byte  │ 2 bytes │ N bytes │ 4 bytes │
│ 0xAA55  │ 0x01    │ uint32  │  uint8  │ uint16  │ payload │ uint32  │
└─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┘

总长度: 14 + N bytes (不含 UDP/IP 头)
```

### 4.2 字段说明

| 字段 | 大小 | 值域 | 说明 |
|------|------|------|------|
| Magic | 2B | 0xAA55 | 协议魔数，用于帧同步 |
| Ver | 1B | 0x01 | 协议版本号 |
| Seq | 4B | 0 - 2³²-1 | 序列号（循环使用） |
| Cmd | 1B | 0x00 - 0xFF | 命令 ID |
| Len | 2B | 0 - 65535 | Payload 长度 |
| Data | NB | - | 命令参数 |
| CRC32 | 4B | 0 - 2³²-1 | 校验和（CRC32） |

### 4.3 Checksum 计算

使用 CRC32 算法：

$$
\text{CRC32} = \text{CRC32}(\text{Magic} \| \text{Ver} \| \text{Seq} \| \text{Cmd} \| \text{Len} \| \text{Data})
$$

实现：
```python
import zlib

frame_without_crc = header + payload
crc = zlib.crc32(frame_without_crc) & 0xFFFFFFFF
```

### 4.4 字节序

所有多字节字段使用**网络字节序（Big Endian）**：

```python
HEADER_FORMAT = '>HBIBH'  # '>' = Big Endian
```

## 5. Stop-and-Wait ARQ 算法

### 5.1 形式化定义

定义可靠传输协议为三元组 $(\mathcal{P}, \mathcal{T}, \mathcal{R})$：

- **协议状态** $\mathcal{P} = \{IDLE, SEND, WAIT, RETRY\}$
- **超时计时器** $\mathcal{T} = (t_{start}, t_{timeout})$
- **重传计数器** $\mathcal{R} = (r_{current}, r_{max})$

### 5.2 超时与重传

**静态超时**：$t_{timeout} = 1000 \text{ms}$（可配置）

**重传策略**：
```
if r_current < r_max then
    t_start ← current_time()
    r_current ← r_current + 1
    retransmit(frame)
else
    raise TimeoutError
```

### 5.3 RTT 估计

当前实现使用**固定超时**，未进行动态 RTT 估计。

未来可扩展为 Jacobson/Karels 算法：
$$
SRTT_{k+1} = (1 - \alpha) \cdot SRTT_k + \alpha \cdot RTT_k
$$
$$
RTO_{k+1} = SRTT_{k+1} + 4 \cdot RTTVAR
$$

## 6. Command Categories

### 感知层 (Sense)
- `get_activity` - 获取当前 Activity
- `get_screen_size` - 获取屏幕尺寸
- `find_node` - 单字段节点查找
- `find_node_compound` - 多条件组合查找
- `dump_actions` - 导出可操作节点
- `dump_hierarchy` - 导出完整 UI 树

### 输入层 (Input)
- `tap` - 点击
- `swipe` - 滑动
- `long_press` - 长按
- `input_text` - 输入文本
- `key_event` - 按键事件 (BACK/HOME)

### 生命周期 (Lifecycle)
- `launch_app` - 启动应用
- `stop_app` - 停止应用
- `list_apps` - 列出应用
- `wake` / `unlock` - 唤醒/解锁

## 7. 为什么选择 UDP？

### 7.1 设计考量

| 特性 | TCP | UDP | 选择 |
|------|-----|-----|------|
| 连接建立 | 三次握手 | 无连接 | UDP 更快 |
| 拥塞控制 | 内置（可能慢） | 无 | UDP 可控 |
| 穿透性 | 中等 | **高** | **UDP 优** |
| 首包延迟 | RTT × 2 | RTT | UDP 更低 |
| 可靠性 | 内置 | 需自实现 | ARQ 实现 |

### 7.2 核心原因：内网穿透适配

**问题场景**：
许多用户没有公网 IP，需要使用内网穿透工具（如 frp、ngrok、cpolar）来访问 Android 设备。

**UDP 优势**：
1. **更好的穿透性能**：UDP 无连接特性在 NAT 穿透中表现更好
2. **更低的延迟**：无需三次握手，首包延迟更低
3. **更灵活的控制**：可以自定义重传策略，适应不同网络质量
4. **更少的开销**：头部开销小（8 bytes vs 20 bytes）

## 8. Design Principles

### 8.1 可靠性设计
- 超时重传机制 (MAX_RETRIES=3)
- Checksum 校验数据完整性
- 序列号机制防止重复处理

### 8.2 检索优先策略
- `find_node_compound` 优先 (多条件组合，定位准确)
- `find_node` 兜底 (单字段，兼容性好)

## 9. Code Structure

| 文件 | 职责 | 关键内容 |
|------|------|----------|
| `client.py` | 统一 API 入口 | `LXBLinkClient` 类 |
| `transport.py` | 传输层实现 | `_send_frame`, `_recv_frame`, `send_reliable` |
| `protocol.py` | 协议编解码 | `ProtocolFrame.encode/decode` |
| `constants.py` | 命令/常量定义 | CMD_* 常量 |

## 10. Cross References
- `docs/zh/lxb_server.md` - Android 端实现
- `docs/zh/lxb_cortex.md` - Cortex 使用示例
