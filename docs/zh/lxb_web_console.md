# LXB-WebConsole

## 1. Scope
LXB-WebConsole 是统一的 Web 调试入口，提供连接管理、命令调试、地图构建、地图查看和 Cortex 执行的界面。

## 2. Architecture
代码目录：`web_console/`

```
web_console/
├── app.py                 # Flask 后端服务
├── templates/             # HTML 模板
│   ├── index.html         # 连接状态页
│   ├── command_studio.html
│   ├── map_builder.html
│   ├── map_viewer.html
│   └── cortex_route.html
└── static/
    └── js/
        └── main.js        # 前端交互逻辑
```

### 模块关系

```
Web Browser (用户界面)
       │
       v
Flask Backend (app.py)
       │
       ├──> LXB-Link (设备通信)
       ├──> LXB-Cortex (自动化执行)
       └──> LXB-MapBuilder (地图构建)
```

## 3. Core Flow

### 3.1 连接管理流程

```
用户输入设备信息 (IP + 端口)
       │
       v
创建 LXBLinkClient 实例
       │
       v
握手验证 (handshake)
       │
       v
获取设备信息并显示
```

### 3.2 命令调试流程

```
用户选择命令类型 (TAP/SWIPE/INPUT/...)
       │
       v
前端表单填充参数
       │
       v
POST /api/command/execute
       │
       v
后端执行命令
       │
       v
前端显示结果
```

### 3.3 地图构建流程

```
用户配置建图参数
       │
       v
启动 NodeMapBuilder
       │
       v
实时进度推送
       │
       v
前端更新 UI (进度、截图、节点)
       │
       v
完成并保存地图 JSON
```

### 3.4 Cortex 执行流程

```
用户输入任务描述
       │
       v
选择或上传地图
       │
       v
创建 CortexFSMEngine
       │
       v
实时日志推送 (FSM 状态、路由轨迹)
       │
       v
前端可视化展示
```

## 4. Screen Mirroring Implementation (屏幕镜像实现)

### 4.1 传输协议

**方案**：**HTTP 分片传输** (非 MJPEG，非 WebSocket)

**原因**：
- HTTP 兼容性好，无需额外协议协商
- 分片传输处理大图（避免 2MB 限制）
- 选择性重传机制提高可靠性

### 4.2 协议流程

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

### 4.3 参数配置

| 参数 | 值 | 说明 |
|------|---|------|
| 分片大小 | 32KB | 平衡传输效率与丢包影响 |
| 压缩格式 | JPEG | 图像压缩 |
| JPEG 质量 | 85 | 视觉质量与文件大小平衡 |
| 超时时间 | 2s | 单次分片接收超时 |
| 最大重试 | 3 | 缺失分片重传次数 |

### 4.4 性能指标

| 指标 | 值 |
|------|---|
| 分片数量 | ~30-60 (1080×2400 JPEG) |
| 完整传输时间 | 200-500ms (局域网) |
| 帧率 | 2-5 FPS (受网络/压缩影响) |
| 带宽占用 | 500KB - 2MB per frame |

### 4.5 代码实现

```python
# Server-Pull 模型
def request_screenshot_fragmented(self):
    """
    请求分片截图传输
    """
    # Step 1: 发送 IMG_REQ
    seq_req = self._next_seq()
    req_frame = ProtocolFrame.pack(seq_req, CMD_IMG_REQ, b'')
    self._send_frame(req_frame)

    # Step 2: 接收 IMG_META
    img_id, total_size, num_chunks = self._wait_for_img_meta()

    # Step 3: 接收所有分片 (burst mode)
    chunks = self._receive_chunks_with_retries(img_id, num_chunks)

    # Step 4: 发送 IMG_FIN + 等待 ACK
    self._send_img_fin_with_ack(img_id)

    # Step 5: 组装完整图像
    return b''.join(chunks)
```

## 5. Concurrency Model (并发模型)

### 5.1 任务队列设计

**当前实现**：**单线程顺序执行**

```python
# Flask 单线程处理
@app.route('/api/command/execute', methods=['POST'])
def execute_command():
    # 阻塞执行，直到命令完成
    result = client.tap(x, y)
    return jsonify(result)
```

### 5.2 并发控制

**全局锁**：确保同一设备的命令顺序执行

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

### 5.3 未来扩展：异步任务队列

**可选方案**：

1. **Celery + Redis**：
   - 优点：成熟的任务队列，支持分布式
   - 缺点：增加部署复杂度

2. **asyncio + aiohttp**：
   - 优点：原生异步，无需额外依赖
   - 缺点：需重构现有同步代码

3. **Python Queue + ThreadPool**：
   - 优点：简单，无需额外服务
   - 缺点：单机限制

## 6. Real-time Progress Push (实时进度推送)

### 6.1 轮询机制

**当前实现**：前端定时轮询

```javascript
// 前端轮询实现
setInterval(async () => {
    const response = await fetch('/api/explore/progress');
    const data = await response.json();
    updateUI(data);
}, 500);  // 每 500ms 轮询一次
```

**优点**：实现简单，兼容性好
**缺点**：延迟、无效请求、服务器负载

### 6.2 WebSocket 方案（未来）

**协议设计**：

```javascript
// WebSocket 连接
const ws = new WebSocket('ws://localhost:5000/ws/explore/123');

// 服务端推送
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

### 7.1 主要页面

| 页面 | 路由 | 功能 |
|------|------|------|
| 连接状态 | `/` | 设备连接、状态显示 |
| 命令调试 | `/command_studio` | 发送命令、查看结果 |
| 地图构建 | `/map_builder` | 自动建图、进度监控 |
| 地图查看 | `/map_viewer` | 地图可视化、编辑 |
| 路由执行 | `/cortex_route` | 任务提交、执行监控 |

### 7.2 API 分类

**设备连接 API**
- `/api/device/connect` - 连接设备
- `/api/device/disconnect` - 断开连接
- `/api/device/status` - 获取状态

**命令执行 API**
- `/api/command/tap` - 点击
- `/api/command/swipe` - 滑动
- `/api/command/input_text` - 输入文本

**地图构建 API**
- `/api/explore/start` - 开始建图
- `/api/explore/progress` - 获取进度
- `/api/maps/list` - 列出地图

**Cortex 执行 API**
- `/api/cortex/submit` - 提交任务
- `/api/cortex/status/{task_id}` - 获取状态
- `/api/cortex/logs/{task_id}` - 获取日志

## 8. Design Principles

### 8.1 统一入口
- 所有功能集成在一个 Web 界面
- 统一的导航栏和状态显示
- 一致的用户体验

### 8.2 实时反馈
- 轮询机制获取任务进度
- 实时显示截图和日志
- 可视化状态机流转

### 8.3 模块解耦
- 前端通过 HTTP API 与后端通信
- 后端调用各模块核心功能
- 模块间独立，易于维护

## 9. Code Structure

| 文件 | 职责 | 关键内容 |
|------|------|----------|
| `app.py` | Flask 后端服务 | API 路由、设备管理 |
| `main.js` | 前端交互逻辑 | DOM 操作、AJAX 请求 |
| `templates/*.html` | 页面模板 | 各功能页面 UI |

## 10. Cross References
- `docs/zh/lxb_link.md` - 设备通信
- `docs/zh/lxb_map_builder.md` - 地图构建
- `docs/zh/lxb_cortex.md` - 自动化执行
