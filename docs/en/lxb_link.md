# LXB-Link

## 1. Scope
LXB-Link is the PC-side to Android-side protocol client layer, responsible for reliably sending commands and receiving responses.

## 2. Architecture
Code directory: `src/lxb_link/`

```
src/lxb_link/
├── __init__.py
├── client.py               # Main client API
├── transport.py            # Reliable UDP transport (Stop-and-Wait ARQ)
├── protocol.py             # Protocol frame encoding/decoding
└── constants.py            # Command constants definition
```

### Architecture Layers

```
Application Layer (Cortex, MapBuilder)
        ↓
  LXBLinkClient (Unified API)
        ↓
  ProtocolFrame (Protocol Encoding)
        ↓
  Transport (Reliable UDP)
        ↓
  UDP Socket (Network)
```

## 3. Core Flow

### 3.1 Command Execution Flow

```
client.tap(500, 800)
    │
    v
Encode to protocol frame (MAGIC + CMD + LEN + SEQ + PAYLOAD + CHECKSUM)
    │
    v
Send + Wait ACK (timeout retransmit, max MAX_RETRIES)
    │
    v
Receive response frame + verify
    │
    v
Parse result and return
```

### 3.2 Reliable Transport Principle

Stop-and-Wait ARQ protocol:
1. Start timer after sending data frame
2. Confirm send success upon receiving ACK
3. Auto retransmit on timeout without ACK

## 4. Protocol Frame Specification

### 4.1 Frame Structure (Byte-Level)

```
┌─────────┬─────────┬─────────┬─────────┬─────────┬─────────┬─────────┐
│ Magic   │ Ver     │ Seq     │ Cmd     │ Len     │ Data    │ CRC32   │
│ 2 bytes │ 1 byte  │ 4 bytes │ 1 byte  │ 2 bytes │ N bytes │ 4 bytes │
│ 0xAA55  │ 0x01    │ uint32  │  uint8  │ uint16  │ payload │ uint32  │
└─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┘

Total length: 14 + N bytes (excluding UDP/IP headers)
```

### 4.2 Field Descriptions

| Field | Size | Range | Description |
|-------|------|-------|-------------|
| Magic | 2B | 0xAA55 | Protocol magic number for frame synchronization |
| Ver | 1B | 0x01 | Protocol version |
| Seq | 4B | 0 - 2³²-1 | Sequence number (cyclic) |
| Cmd | 1B | 0x00 - 0xFF | Command ID |
| Len | 2B | 0 - 65535 | Payload length |
| Data | NB | - | Command parameters |
| CRC32 | 4B | 0 - 2³²-1 | Checksum (CRC32) |

### 4.3 Checksum Calculation

Uses CRC32 algorithm:

$$
\text{CRC32} = \text{CRC32}(\text{Magic} \| \text{Ver} \| \text{Seq} \| \text{Cmd} \| \text{Len} \| \text{Data})
$$

Implementation:
```python
import zlib

frame_without_crc = header + payload
crc = zlib.crc32(frame_without_crc) & 0xFFFFFFFF
```

### 4.4 Byte Order

All multi-byte fields use **Network Byte Order (Big Endian)**:

```python
HEADER_FORMAT = '>HBIBH'  # '>' = Big Endian
```

## 5. Stop-and-Wait ARQ Algorithm

### 5.1 Formal Definition

Define reliable transport protocol as tuple $(\mathcal{P}, \mathcal{T}, \mathcal{R})$:

- **Protocol states** $\mathcal{P} = \{IDLE, SEND, WAIT, RETRY\}$
- **Timeout timer** $\mathcal{T} = (t_{start}, t_{timeout})$
- **Retransmission counter** $\mathcal{R} = (r_{current}, r_{max})$

### 5.2 Timeout and Retransmission

**Static timeout**: $t_{timeout} = 1000 \text{ms}$ (configurable)

**Retransmission strategy**:
```
if r_current < r_max then
    t_start ← current_time()
    r_current ← r_current + 1
    retransmit(frame)
else
    raise TimeoutError
```

### 5.3 RTT Estimation

Current implementation uses **fixed timeout**, no dynamic RTT estimation.

Future extension to Jacobson/Karels algorithm:
$$
SRTT_{k+1} = (1 - \alpha) \cdot SRTT_k + \alpha \cdot RTT_k
$$
$$
RTO_{k+1} = SRTT_{k+1} + 4 \cdot RTTVAR
$$

## 6. Command Categories

### Perception Layer (Sense)
- `get_activity` - Get current Activity
- `get_screen_size` - Get screen size
- `find_node` - Single-field node search
- `find_node_compound` - Multi-condition combined search
- `dump_actions` - Export operable nodes
- `dump_hierarchy` - Export complete UI tree

### Input Layer (Input)
- `tap` - Tap
- `swipe` - Swipe
- `long_press` - Long press
- `input_text` - Input text
- `key_event` - Key event (BACK/HOME)

### Lifecycle (Lifecycle)
- `launch_app` - Launch app
- `stop_app` - Stop app
- `list_apps` - List apps
- `wake` / `unlock` - Wake/unlock

## 7. Why UDP?

### 7.1 Design Considerations

| Feature | TCP | UDP | Choice |
|---------|-----|-----|--------|
| Connection Setup | 3-way handshake | Connectionless | UDP faster |
| Congestion Control | Built-in (may be slow) | None | UDP controllable |
| NAT Traversal | Moderate | **High** | **UDP better** |
| First-packet Latency | RTT × 2 | RTT | UDP lower |
| Reliability | Built-in | Must implement | ARQ implemented |

### 7.2 Core Reason: NAT Traversal Adaptation

**Problem Scenario**:
Many users don't have public IP addresses and need to use NAT traversal tools (like frp, ngrok, cpolar) to access Android devices.

**UDP Advantages**:
1. **Better NAT traversal**: Connectionless nature performs better in NAT traversal scenarios
2. **Lower latency**: No 3-way handshake, lower first-packet latency
3. **Flexible control**: Customizable retransmission strategy for different network conditions
4. **Less overhead**: Smaller header (8 bytes vs 20 bytes)

**Academic Formulation**:
> LXB-Link adopts UDP as the transport protocol to accommodate diverse network deployment environments. Particularly in scenarios lacking public IP addresses, users often require NAT traversal tools for device connectivity, where UDP's connectionless nature and superior NAT traversal performance can provide more stable communication quality. We implement a Stop-and-Wait ARQ protocol at the application layer to ensure reliable transmission.

### 7.3 Comparison with ADB

| Feature | ADB Forward | LXB-Link UDP |
|---------|-------------|--------------|
| Configuration complexity | Requires USB or wireless pairing | Only IP + port needed |
| Cross-device access | Difficult | **Supported (via tunneling)** |
| Concurrency | Limited (single connection) | **Good** |
| Scalability | Restricted | **Strong** |

## 8. Design Principles

### 8.1 Reliability Design
- Timeout retransmission mechanism (MAX_RETRIES=3)
- Checksum verifies data integrity
- Sequence number prevents duplicate processing

### 8.2 Retrieval-First Strategy
- `find_node_compound` priority (multi-condition combination, accurate positioning)
- `find_node` fallback (single field, good compatibility)

## 9. Code Structure

| File | Responsibility | Key Content |
|------|----------------|--------------|
| `client.py` | Unified API entry | `LXBLinkClient` class |
| `transport.py` | Transport layer implementation | `_send_frame`, `_recv_frame`, `send_reliable` |
| `protocol.py` | Protocol encoding/decoding | `ProtocolFrame.encode/decode` |
| `constants.py` | Command/constants definition | CMD_* constants |

## 10. Cross References
- `docs/en/lxb_server.md` - Android-side implementation
- `docs/en/lxb_cortex.md` - Cortex usage examples
