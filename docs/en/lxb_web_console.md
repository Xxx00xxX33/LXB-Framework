# LXB-WebConsole

## 1. Scope
LXB-WebConsole is the unified web entry point providing interfaces for connection management, command debugging, map building, map viewing, and Cortex execution.

## 2. Architecture
Code directory: `web_console/`

```
web_console/
├── app.py                 # Flask backend service
├── templates/             # HTML templates
│   ├── index.html         # Connection status page
│   ├── command_studio.html
│   ├── map_builder.html
│   ├── map_viewer.html
│   └── cortex_route.html
└── static/
    └── js/
        └── main.js        # Frontend interaction logic
```

### Module Relationships

```
Web Browser (User Interface)
       │
       v
Flask Backend (app.py)
       │
       ├──> LXB-Link (Device Communication)
       ├──> LXB-Cortex (Automation Execution)
       └──> LXB-MapBuilder (Map Building)
```

## 3. Core Flow

### 3.1 Connection Management Flow

```
User enters device info (IP + Port)
       │
       v
Create LXBLinkClient instance
       │
       v
Handshake verification
       │
       v
Display device info
```

### 3.2 Command Debug Flow

```
User selects command type (TAP/SWIPE/INPUT/...)
       │
       v
Frontend form fills parameters
       │
       v
POST /api/command/execute
       │
       v
Backend executes command
       │
       v
Frontend displays results
```

### 3.3 Map Building Flow

```
User configures map building parameters
       │
       v
Start NodeMapBuilder
       │
       v
Real-time progress push
       │
       v
Frontend updates UI (progress, screenshots, nodes)
       │
       v
Complete and save map JSON
```

### 3.4 Cortex Execution Flow

```
User enters task description
       │
       v
Select or upload map
       │
       v
Create CortexFSMEngine
       │
       v
Real-time log push (FSM state, route trace)
       │
       v
Frontend visualization display
```

## 4. Screen Mirroring Implementation

### 4.1 Transport Protocol

**Approach**: **HTTP Fragmented Transfer** (not MJPEG, not WebSocket)

**Reasoning**:
- HTTP compatibility, no additional protocol negotiation needed
- Fragmented transfer handles large images (avoids 2MB limit)
- Selective retransmission improves reliability

### 4.2 Protocol Flow

```
┌─────────────┐                                    ┌─────────────┐
│   Client    │                                    │   Server    │
└──────┬──────┘                                    └──────┬──────┘
       │                                                  │
       │  1. IMG_REQ (seq)                               │
       │─────────────────────────────────────────────────>│
       │                                                  │
       │  2. IMG_META (img_id, total_size, num_chunks)   │
       │<─────────────────────────────────────────────────│
       │                                                  │
       │  3. IMG_CHUNK (burst mode, no ACK per chunk)    │
       │<─────────────────────────────────────────────────│
       │     └───> chunk_0, chunk_1, ..., chunk_n         │
       │                                                  │
       │  4. IMG_MISSING (missing_indices) [if needed]    │
       │─────────────────────────────────────────────────>│
       │                                                  │
       │  5. Missing chunks (retransmit)                   │
       │<─────────────────────────────────────────────────│
       │                                                  │
       │  6. IMG_FIN (img_id) + ACK                       │
       │─────────────────────────────────────────────────>│
       │                                                  │
       │  7. ACK (confirmation)                           │
       │<─────────────────────────────────────────────────│
       └                                                  ┘
```

### 4.3 Parameter Configuration

| Parameter | Value | Description |
|-----------|-------|-------------|
| Chunk size | 32KB | Balance transfer efficiency and packet loss impact |
| Compression format | JPEG | Image compression |
| JPEG quality | 85 | Visual quality vs file size balance |
| Timeout | 2s | Single chunk receive timeout |
| Max retries | 3 | Missing chunk retransmission attempts |

### 4.4 Performance Metrics

| Metric | Value |
|--------|-------|
| Chunk count | ~30-60 (1080×2400 JPEG) |
| Full transfer time | 200-500ms (LAN) |
| Frame rate | 2-5 FPS (network/compression dependent) |
| Bandwidth usage | 500KB - 2MB per frame |

### 4.5 Code Implementation

```python
# Server-Pull model
def request_screenshot_fragmented(self):
    """
    Request fragmented screenshot transfer
    """
    # Step 1: Send IMG_REQ
    seq_req = self._next_seq()
    req_frame = ProtocolFrame.pack(seq_req, CMD_IMG_REQ, b'')
    self._send_frame(req_frame)

    # Step 2: Receive IMG_META
    img_id, total_size, num_chunks = self._wait_for_img_meta()

    # Step 3: Receive all chunks (burst mode)
    chunks = self._receive_chunks_with_retries(img_id, num_chunks)

    # Step 4: Send IMG_FIN + wait for ACK
    self._send_img_fin_with_ack(img_id)

    # Step 5: Assemble complete image
    return b''.join(chunks)
```

## 5. Concurrency Model

### 5.1 Task Queue Design

**Current implementation**: **Single-threaded sequential execution**

```python
# Flask single-threaded processing
@app.route('/api/command/execute', methods=['POST'])
def execute_command():
    # Blocking execution, waits for command completion
    result = client.tap(x, y)
    return jsonify(result)
```

### 5.2 Concurrency Control

**Global lock**: Ensures commands for same device execute in order

```python
import threading

_device_locks = {}  # {device_id: Lock}

def get_device_lock(device_id):
    if device_id not in _device_locks:
        _device_locks[device_id] = threading.Lock()
    return _device_locks[device_id]

@app.route('/api/command/execute')
def execute_command():
    device_id = request.form.get('device_id')
    lock = get_device_lock(device_id)
    with lock:
        result = client.execute(...)
    return jsonify(result)
```

### 5.3 Future Extension: Async Task Queue

**Optional approaches**:

1. **Celery + Redis**:
   - Pros: Mature task queue, supports distributed execution
   - Cons: Increased deployment complexity

2. **asyncio + aiohttp**:
   - Pros: Native async, no additional dependencies
   - Cons: Requires refactoring existing synchronous code

3. **Python Queue + ThreadPool**:
   - Pros: Simple, no additional services
   - Cons: Single-machine limitation

## 6. Real-time Progress Push

### 6.1 Polling Mechanism

**Current implementation**: Frontend periodic polling

```javascript
// Frontend polling implementation
setInterval(async () => {
    const response = await fetch('/api/explore/progress');
    const data = await response.json();
    updateUI(data);
}, 500);  // Poll every 500ms
```

**Pros**: Simple implementation, good compatibility
**Cons**: Latency, invalid requests, server load

### 6.2 WebSocket Solution (Future)

**Protocol design**:

```javascript
// WebSocket connection
const ws = new WebSocket('ws://localhost:5000/ws/explore/123');

// Server push
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    switch(data.type) {
        case 'progress':
            updateProgress(data.current, data.total);
            break;
        case 'screenshot':
            updateScreenshot(data.image);
            break;
        case 'node_found':
            addNodeToList(data.node);
            break;
    }
};
```

## 7. Key Interfaces

### 7.1 Main Pages

| Page | Route | Function |
|------|-------|----------|
| Connection Status | `/` | Device connection, status display |
| Command Studio | `/command_studio` | Send commands, view results |
| Map Builder | `/map_builder` | Auto map building, progress monitoring |
| Map Viewer | `/map_viewer` | Map visualization, editing |
| Route Executor | `/cortex_route` | Task submission, execution monitoring |

### 7.2 API Categories

**Device Connection API**
- `/api/device/connect` - Connect device
- `/api/device/disconnect` - Disconnect device
- `/api/device/status` - Get status

**Command Execution API**
- `/api/command/tap` - Tap
- `/api/command/swipe` - Swipe
- `/api/command/input_text` - Input text

**Map Building API**
- `/api/explore/start` - Start map building
- `/api/explore/progress` - Get progress
- `/api/maps/list` - List maps

**Cortex Execution API**
- `/api/cortex/submit` - Submit task
- `/api/cortex/status/{task_id}` - Get status
- `/api/cortex/logs/{task_id}` - Get logs

## 8. Design Principles

### 8.1 Unified Entry Point
- All functions integrated in one web interface
- Unified navigation bar and status display
- Consistent user experience

### 8.2 Real-time Feedback
- Polling mechanism for task progress
- Real-time display of screenshots and logs
- Visual state machine flow

### 8.3 Module Decoupling
- Frontend communicates with backend via HTTP API
- Backend calls module core functions
- Modules are independent and easy to maintain

## 9. Code Structure

| File | Responsibility | Key Content |
|------|----------------|--------------|
| `app.py` | Flask backend service | API routes, device management |
| `main.js` | Frontend interaction logic | DOM operations, AJAX requests |
| `templates/*.html` | Page templates | UI for each function page |

## 10. Cross References
- `docs/en/lxb_link.md` - Device communication
- `docs/en/lxb_map_builder.md` - Map building
- `docs/en/lxb_cortex.md` - Automation execution
