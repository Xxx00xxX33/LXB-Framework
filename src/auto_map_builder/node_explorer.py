"""
LXB Auto Map Builder v5 - Node 驱动探索

核心思路：
1. 以 Node 为单位探索，不以页面为单位
2. 每次从首页开始，按路径到达目标节点
3. 不需要"返回"逻辑，不需要页面去重
4. 记录：node → 目的地语义描述

数据结构：
- NodeLocator: 节点定位器（resource_id, text, bounds）
- NodeTransition: 节点跳转记录（node → target_description）
- NavigationMap: 导航地图（所有节点的跳转关系）
"""

import json
import time
import base64
import hashlib
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Set, Callable
from enum import Enum
from io import BytesIO

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from .vlm_engine import VLMEngine
from .models import ExplorationConfig


class ExplorationStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    COMPLETED = "completed"


@dataclass
class NodeLocator:
    """节点定位器 - 用于定位和标识 UI 元素"""
    resource_id: Optional[str] = None
    text: Optional[str] = None
    content_desc: Optional[str] = None
    class_name: Optional[str] = None
    bounds: Optional[Tuple[int, int, int, int]] = None

    def unique_key(self) -> str:
        """生成唯一标识"""
        # 优先级：resource_id > text > content_desc > bounds
        if self.resource_id:
            # 只取 ID 部分
            rid = self.resource_id.split("/")[-1] if "/" in self.resource_id else self.resource_id
            return f"id:{rid}"
        if self.text and len(self.text) <= 20:
            return f"text:{self.text}"
        if self.content_desc and len(self.content_desc) <= 20:
            return f"desc:{self.content_desc}"
        if self.bounds:
            return f"bounds:{self.bounds}"
        return f"unknown:{id(self)}"

    def click_point(self) -> Optional[Tuple[int, int]]:
        """获取点击坐标（bounds 中心）"""
        if self.bounds and len(self.bounds) >= 4:
            return ((self.bounds[0] + self.bounds[2]) // 2,
                    (self.bounds[1] + self.bounds[3]) // 2)
        return None

    def to_dict(self) -> dict:
        d = {}
        if self.resource_id:
            d["resource_id"] = self.resource_id
        if self.text:
            d["text"] = self.text
        if self.content_desc:
            d["content_desc"] = self.content_desc
        if self.class_name:
            d["class_name"] = self.class_name
        if self.bounds:
            d["bounds"] = list(self.bounds)
        return d

    @staticmethod
    def from_dict(d: dict) -> "NodeLocator":
        return NodeLocator(
            resource_id=d.get("resource_id"),
            text=d.get("text"),
            content_desc=d.get("content_desc"),
            class_name=d.get("class_name"),
            bounds=tuple(d["bounds"]) if d.get("bounds") else None
        )

    def __hash__(self):
        return hash(self.unique_key())

    def __eq__(self, other):
        if not isinstance(other, NodeLocator):
            return False
        return self.unique_key() == other.unique_key()


@dataclass
class NodeTransition:
    """节点跳转记录"""
    node_key: str                           # 节点唯一标识
    locator: NodeLocator                    # 节点定位器
    path: List[NodeLocator]                 # 从首页到达的路径
    description: str                        # 节点描述（VLM 生成）
    role: str = "other"                     # 角色：bottom_tab, top_tab, back, search, menu, other
    target_description: str = ""            # 目的地页面描述
    target_nodes: List["NavNode"] = field(default_factory=list)  # 目的地的导航节点
    explored: bool = False                  # 是否已探索
    explore_time: float = 0.0               # 探索时间

    def to_dict(self) -> dict:
        return {
            "node_key": self.node_key,
            "locator": self.locator.to_dict(),
            "path": [p.to_dict() for p in self.path],
            "description": self.description,
            "role": self.role,
            "target_description": self.target_description,
            "target_nodes": [n.to_dict() for n in self.target_nodes],
            "explored": self.explored,
            "explore_time": self.explore_time
        }


@dataclass
class NavNode:
    """导航节点 - VLM 识别的可点击元素"""
    locator: NodeLocator
    description: str  # VLM 描述
    role: str = "other"  # bottom_tab, top_tab, back, search, menu, other

    def to_dict(self) -> dict:
        return {
            "locator": self.locator.to_dict(),
            "description": self.description,
            "role": self.role
        }

    @staticmethod
    def from_dict(d: dict) -> "NavNode":
        return NavNode(
            locator=NodeLocator.from_dict(d["locator"]),
            description=d.get("description", ""),
            role=d.get("role", "other")
        )


@dataclass
class ExploreTask:
    """探索任务"""
    locator: NodeLocator        # 要点击的节点
    path: List[NodeLocator]     # 从首页到达的路径
    description: str            # 节点描述
    depth: int = 0              # 深度
    role: str = "other"         # 角色


class NavigationMap:
    """
    导航地图 - 以 Node 为中心

    记录每个节点点击后去哪，不关心"页面"概念
    """

    def __init__(self):
        self.transitions: Dict[str, NodeTransition] = {}  # node_key → transition
        self.home_description: str = ""  # 首页描述

    def add_transition(self, transition: NodeTransition):
        """添加跳转记录"""
        self.transitions[transition.node_key] = transition

    def get_transition(self, node_key: str) -> Optional[NodeTransition]:
        """获取跳转记录"""
        return self.transitions.get(node_key)

    def is_explored(self, node_key: str) -> bool:
        """检查节点是否已探索"""
        trans = self.transitions.get(node_key)
        return trans is not None and trans.explored

    def get_stats(self) -> dict:
        """获取统计信息"""
        explored = sum(1 for t in self.transitions.values() if t.explored)
        return {
            "total_nodes": len(self.transitions),
            "explored_nodes": explored,
            "pending_nodes": len(self.transitions) - explored
        }

    def to_dict(self) -> dict:
        return {
            "home_description": self.home_description,
            "transitions": {k: v.to_dict() for k, v in self.transitions.items()}
        }

    def save(self, filepath: str):
        """保存到文件"""
        import os
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)


class NodeExplorer:
    """
    Node 驱动探索器

    核心逻辑：
    1. 分析首页，获取导航节点
    2. 每个节点作为独立任务
    3. 每次从首页开始，按路径到达，点击目标节点
    4. 记录目的地描述，发现新节点加入队列
    """

    _PROMPT_ANALYZE = '''分析这个 Android App 页面截图。

**屏幕分辨率: {width} x {height} 像素**

## 任务
1. 描述页面功能定位
2. 列出页面内的功能（自然语言）
3. 找出**页面跳转入口**和**输入框**

## 输出格式
```
PAGE|{{"type":"页面类型","purpose":"核心功能","features":"页面内有什么功能"}}
NAV|x|y|名称|类型
```

## 页面类型
首页/列表页/详情页/个人中心/设置页/搜索页/登录页/其他

## NAV 类型（只识别这4种）
- `tab`: 底部/顶部导航Tab（切换App主要模块）
- `jump`: 跳转入口（点击后进入新页面，如：搜索、设置、个人主页）
- `back`: 返回按钮
- `input`: 输入框/搜索框

## 严格排除（不要输出NAV）
- 页面内操作按钮（排序、筛选、收藏、分享、点赞）
- 列表项、卡片、商品
- 活动、广告、运营入口
- 不会跳转到新页面的任何按钮

**判断标准：点击后会跳转到一个完全不同的页面吗？**
- 是 → 输出 NAV
- 否 → 写在 features 里

## 示例
```
PAGE|{{"type":"首页","purpose":"浏览推荐内容","features":"下拉刷新、内容卡片、排序筛选"}}
NAV|{ex1_x}|{ex1_y}|首页|tab
NAV|{ex2_x}|{ex2_y}|消息|tab
NAV|{ex3_x}|{ex3_y}|我的|tab
NAV|540|80|搜索|jump
```

现在分析（只输出会跳转页面的入口）：'''

    def __init__(
        self,
        client,
        config: Optional[ExplorationConfig] = None,
        log_callback: Optional[Callable] = None
    ):
        self.client = client
        self.config = config or ExplorationConfig()
        self.log = log_callback or (lambda l, m, d=None: print(f"[{l}] {m}"))

        from .vlm_engine import get_config
        vlm_config = get_config()
        self.vlm = VLMEngine(vlm_config)

        self.nav_map = NavigationMap()
        self.pending_tasks: deque = deque()
        self.explored_keys: Set[str] = set()

        self._status = ExplorationStatus.IDLE
        self._status_lock = threading.Lock()
        self._pause_event = threading.Event()
        self._pause_event.set()

        self._screen_width = 1080
        self._screen_height = 2400

        self._stats = {
            "total_actions": 0,
            "start_time": 0.0
        }

        self._realtime = {
            "current_node": None,
            "current_screenshot": None,
            "last_action": None
        }
        self._realtime_lock = threading.Lock()

    @property
    def status(self) -> ExplorationStatus:
        with self._status_lock:
            return self._status

    @status.setter
    def status(self, value: ExplorationStatus):
        with self._status_lock:
            self._status = value

    def pause(self):
        if self._status == ExplorationStatus.RUNNING:
            self._pause_event.clear()
            self.status = ExplorationStatus.PAUSED

    def resume(self):
        if self._status == ExplorationStatus.PAUSED:
            self.status = ExplorationStatus.RUNNING
            self._pause_event.set()

    def stop(self):
        if self._status in (ExplorationStatus.RUNNING, ExplorationStatus.PAUSED):
            self.status = ExplorationStatus.STOPPING
            self._pause_event.set()

    def _check_control(self) -> bool:
        if self._status == ExplorationStatus.STOPPING:
            return False
        if self._status == ExplorationStatus.PAUSED:
            self._pause_event.wait()
        return self._status != ExplorationStatus.STOPPING

    def get_realtime_state(self) -> dict:
        with self._realtime_lock:
            state = self._realtime.copy()
            state["status"] = self._status.value
            stats = self.nav_map.get_stats()
            state["stats"] = {
                **stats,
                "total_actions": self._stats["total_actions"],
                "queue_size": len(self.pending_tasks),
                "elapsed": time.time() - self._stats["start_time"] if self._stats["start_time"] else 0
            }

            # 构建拓扑图数据（兼容前端）
            graph_nodes = []
            edges = []
            seen_targets = set()

            # 首页作为根节点
            if self.nav_map.home_description:
                graph_nodes.append({
                    "id": "home",
                    "type": "首页",
                    "desc": self.nav_map.home_description[:50]
                })

            # 遍历所有已探索的节点
            for node_key, trans in self.nav_map.transitions.items():
                if trans.explored and trans.target_description:
                    # 目标页面作为节点
                    target_id = trans.target_description[:30]
                    if target_id not in seen_targets:
                        seen_targets.add(target_id)
                        graph_nodes.append({
                            "id": target_id,
                            "type": "页面",
                            "desc": trans.target_description[:50]
                        })

                    # 边：从首页/上级页面 → 目标页面
                    from_id = "home" if not trans.path else trans.path[-1].unique_key()[:30]
                    edges.append({
                        "from": from_id,
                        "to": target_id,
                        "label": trans.description[:20]
                    })

            state["graph"] = {
                "nodes": graph_nodes,
                "edges": edges
            }

            # Node 列表（显示所有节点及其探索状态）
            node_list = []
            for node_key, trans in self.nav_map.transitions.items():
                node_list.append({
                    "node_key": node_key,
                    "description": trans.description,
                    "explored": trans.explored,
                    "target_description": trans.target_description[:50] if trans.target_description else "",
                    "depth": len(trans.path),
                    "role": trans.role,
                    "locator": {
                        "resource_id": trans.locator.resource_id,
                        "text": trans.locator.text,
                        "bounds": trans.locator.bounds
                    } if trans.locator else None
                })

            # 按探索状态排序：未探索的在前
            node_list.sort(key=lambda x: (x["explored"], x["depth"]))
            state["node_list"] = node_list

            return state

    # === 设备操作 ===

    def _get_screen_size(self):
        try:
            ok, w, h, _ = self.client.get_screen_size()
            if ok:
                self._screen_width, self._screen_height = w, h
                self.log("debug", f"获取屏幕尺寸成功: {w}x{h}")
            else:
                self.log("warn", "获取屏幕尺寸失败")
        except Exception as e:
            self.log("error", f"获取屏幕尺寸异常: {e}")

    def _screenshot(self) -> Optional[bytes]:
        try:
            data = self.client.request_screenshot()
            # 检查截图实际尺寸
            if data and HAS_PIL:
                from PIL import Image
                img = Image.open(BytesIO(data))
                img_w, img_h = img.size
                if img_w != self._screen_width or img_h != self._screen_height:
                    self.log("warn", f"截图尺寸 ({img_w}x{img_h}) != 屏幕尺寸 ({self._screen_width}x{self._screen_height})")
                    # 更新为截图的实际尺寸（VLM 看到的是截图）
                    self._screen_width, self._screen_height = img_w, img_h
            return data
        except Exception as e:
            self.log("error", f"截图失败: {e}")
            return None

    def _dump_actions(self) -> List[Dict]:
        try:
            return self.client.dump_actions().get("nodes", [])
        except:
            return []

    def _tap(self, x: int, y: int):
        self.client.tap(x, y)
        self._stats["total_actions"] += 1
        time.sleep(self.config.action_delay_ms / 1000)

    def _back(self):
        """按返回键"""
        self.client.key_event(4)
        time.sleep(0.5)

    def _launch_app(self, package: str):
        """启动应用"""
        try:
            self.log("debug", f"launch_app: {package}")
            self.client.launch_app(package, clear_task=True)
            time.sleep(2)
        except Exception as e:
            self.log("error", f"启动应用异常: {e}")

    def _go_home(self, package: str):
        """
        回到首页

        策略：先尝试 Back 键，如果退出了 App 再 launch
        """
        # 检查当前是否在目标 App
        try:
            ok, current_pkg, _ = self.client.get_activity()
            if ok and current_pkg == package:
                # 在目标 App 内，尝试用 Back 键回首页
                for _ in range(5):
                    self._back()
                    ok, pkg, _ = self.client.get_activity()
                    if not ok or pkg != package:
                        # 退出了 App，重新 launch
                        break
                else:
                    # Back 了 5 次还在 App 内，可能已经在首页了
                    return
        except:
            pass

        # launch App
        self.client.launch_app(package, clear_task=True)
        time.sleep(2)

    def _is_nav_anchor(self, xml_node: Dict) -> bool:
        """
        判断节点是否是导航锚点（而不是列表项）

        导航锚点特征：
        - 位置在顶部或底部（导航栏区域）
        - 不包含列表项关键词
        """
        bounds = xml_node.get("bounds", [0, 0, 0, 0])
        if len(bounds) < 4:
            return False

        y_center = (bounds[1] + bounds[3]) // 2
        h = self._screen_height

        # 1. 位置检查：在顶部 20% 或底部 20%（放宽范围）
        is_top = y_center < h * 0.20
        is_bottom = y_center > h * 0.80

        # 2. resource_id 检查：排除列表项
        res_id = xml_node.get("resource_id", "").lower()
        class_name = xml_node.get("class_name", "").lower()

        # 列表项关键词（排除）
        list_keywords = ["item", "cell", "row", "entry", "holder"]
        is_list_item = any(kw in res_id or kw in class_name for kw in list_keywords)

        # 如果在导航区域，且不是列表项，就是锚点
        if (is_top or is_bottom) and not is_list_item:
            return True

        # 如果有明确的导航关键词，也认为是锚点
        nav_keywords = ["tab", "nav", "menu", "bar", "bottom", "home", "search"]
        is_nav = any(kw in res_id for kw in nav_keywords)
        if is_nav and not is_list_item:
            return True

        return False

    def _is_input_field(self, xml_node: Dict) -> bool:
        """判断是否是输入框"""
        class_name = xml_node.get("class_name", "").lower()
        res_id = xml_node.get("resource_id", "").lower()

        # EditText 类
        if "edittext" in class_name or "edit" in class_name:
            return True

        # 搜索框
        if "search" in res_id and ("input" in res_id or "edit" in res_id or "box" in res_id):
            return True

        # focusable + editable
        if xml_node.get("editable", False):
            return True

        return False

    # === VLM 分析 ===

    def _analyze_page(self, screenshot: bytes) -> Tuple[str, List[NavNode]]:
        """
        分析页面（支持并发推理）

        Returns:
            (页面描述, 导航节点列表)
        """
        try:
            w, h = self._screen_width, self._screen_height
            prompt = self._PROMPT_ANALYZE.format(
                width=w,
                height=h,
                bottom_y=int(h * 0.85),
                top_y=int(h * 0.15),
                # 示例坐标（基于实际分辨率）
                ex1_x=int(w * 0.125),  # 底部导航第1个
                ex1_y=int(h * 0.95),
                ex2_x=int(w * 0.375),  # 底部导航第2个
                ex2_y=int(h * 0.95),
                ex3_x=int(w * 0.2),    # 顶部Tab
                ex3_y=int(h * 0.06)
            )

            # 检查是否启用并发推理
            if self.vlm.config.concurrent_enabled:
                return self._analyze_page_concurrent(screenshot, prompt)
            else:
                response = self.vlm._call_api(screenshot, prompt)
                self.log("debug", f"VLM 响应:\n{response[:500]}")
                return self._parse_response(response)
        except Exception as e:
            self.log("error", f"VLM 分析失败: {e}")
            return "", []

    def _analyze_page_concurrent(self, screenshot: bytes, prompt: str) -> Tuple[str, List[NavNode]]:
        """
        并发推理分析页面

        多次调用 VLM，聚合结果，提高准确性
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading

        num_requests = self.vlm.config.concurrent_requests
        threshold = self.vlm.config.occurrence_threshold

        self.log("info", f"  并发推理: {num_requests} 次, 阈值 {threshold}")

        results = []
        lock = threading.Lock()

        def single_call(idx: int):
            try:
                response = self.vlm._call_api(screenshot, prompt)
                desc, nodes = self._parse_response(response)
                with lock:
                    results.append((desc, nodes))
                return True
            except Exception as e:
                self.log("debug", f"  并发推理 #{idx+1} 失败: {e}")
                return False

        # 并发执行
        with ThreadPoolExecutor(max_workers=min(num_requests, 10)) as executor:
            futures = [executor.submit(single_call, i) for i in range(num_requests)]
            for future in as_completed(futures):
                future.result()

        if not results:
            return "", []

        # 聚合描述（取最常见的）
        descriptions = [r[0] for r in results if r[0]]
        if descriptions:
            final_desc = max(set(descriptions), key=descriptions.count)
        else:
            final_desc = ""

        # 聚合导航节点（按坐标分组，出现次数 >= threshold 的保留）
        all_nodes = []
        for _, nodes in results:
            all_nodes.extend(nodes)

        aggregated_nodes = self._aggregate_nav_nodes(all_nodes, threshold)

        self.log("info", f"  并发结果: {len(results)}/{num_requests} 成功, 聚合 {len(aggregated_nodes)} 个节点")

        return final_desc, aggregated_nodes

    def _aggregate_nav_nodes(self, nodes: List[NavNode], threshold: int) -> List[NavNode]:
        """
        聚合多次推理的导航节点

        按坐标分组，出现次数 >= threshold 的保留
        """
        if not nodes:
            return []

        # 按坐标分组（允许 50 像素误差）
        groups = []
        used = set()

        for i, node in enumerate(nodes):
            if i in used:
                continue

            if not node.locator.bounds:
                continue

            x1, y1 = node.locator.bounds[0], node.locator.bounds[1]
            group = [node]
            used.add(i)

            for j, other in enumerate(nodes):
                if j in used or not other.locator.bounds:
                    continue

                x2, y2 = other.locator.bounds[0], other.locator.bounds[1]
                # 距离小于 50 像素认为是同一个节点
                if abs(x1 - x2) < 50 and abs(y1 - y2) < 50:
                    group.append(other)
                    used.add(j)

            groups.append(group)

        # 过滤并聚合
        aggregated = []
        for group in groups:
            if len(group) < threshold:
                continue  # 出现次数不足，认为是噪声

            # 取平均坐标
            avg_x = sum(n.locator.bounds[0] for n in group) // len(group)
            avg_y = sum(n.locator.bounds[1] for n in group) // len(group)

            # 取最常见的描述
            descriptions = [n.description for n in group]
            most_common_desc = max(set(descriptions), key=descriptions.count)

            # 取最常见的角色
            roles = [n.role for n in group]
            most_common_role = max(set(roles), key=roles.count)

            aggregated.append(NavNode(
                locator=NodeLocator(bounds=(avg_x, avg_y, avg_x, avg_y)),
                description=most_common_desc,
                role=most_common_role
            ))

        return aggregated

    def _parse_response(self, response: str) -> Tuple[str, List[NavNode]]:
        """解析 VLM 响应"""
        description = ""
        nav_nodes = []

        for line in response.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("```"):
                continue

            # 新格式: PAGE|{"type":"...", "purpose":"...", "features":"..."}
            if line.startswith("PAGE|"):
                parts = line.split("|", 1)
                if len(parts) >= 2:
                    json_str = parts[1].strip()
                    try:
                        page_info = json.loads(json_str)
                        # 格式化为简洁描述
                        page_type = page_info.get("type", "未知")
                        purpose = page_info.get("purpose", "")
                        features = page_info.get("features", "")
                        description = f"[{page_type}] {purpose}"
                        if features:
                            description += f" | 功能: {features}"
                    except json.JSONDecodeError:
                        # JSON 解析失败，直接用原文
                        description = json_str

            # 兼容旧格式: DESC|页面描述
            elif line.startswith("DESC|"):
                parts = line.split("|", 1)
                if len(parts) >= 2:
                    description = parts[1].strip()

            elif line.startswith("NAV|"):
                parts = line.split("|")
                if len(parts) >= 4:
                    try:
                        x = int(parts[1].strip())
                        y = int(parts[2].strip())
                        desc = parts[3].strip()
                        nav_type = parts[4].strip() if len(parts) >= 5 else "other"

                        # 映射新类型到旧角色（兼容）
                        role_map = {
                            "tab": "bottom_tab",
                            "jump": "jump",
                            "back": "back",
                            "input": "input",
                            # 兼容旧格式
                            "bottom_tab": "bottom_tab",
                            "top_tab": "top_tab",
                            "search": "jump",
                            "menu": "jump",
                        }
                        role = role_map.get(nav_type, "other")

                        # 创建 locator（暂时只有坐标，后面会匹配 XML）
                        locator = NodeLocator(bounds=(x, y, x, y))
                        nav_nodes.append(NavNode(locator=locator, description=desc, role=role))
                    except ValueError:
                        continue

        return description, nav_nodes

    def _match_xml_node(self, vlm_x: int, vlm_y: int, vlm_desc: str, xml_nodes: List[Dict]) -> Optional[Dict]:
        """
        用 VLM 坐标和描述匹配 XML 节点

        策略（优先级从高到低）：
        1. 文本完全匹配 + 在同一行（y 坐标接近）
        2. 文本包含匹配 + 在同一行
        3. 坐标在 bounds 内
        4. 距离最近
        """
        # 筛选候选节点：导航锚点 + 输入框
        candidates_pool = []
        for node in xml_nodes:
            bounds = node.get("bounds", [0, 0, 0, 0])
            if len(bounds) < 4:
                continue

            # 导航锚点（需要 clickable）
            if node.get("clickable", False) and self._is_nav_anchor(node):
                candidates_pool.append(node)
            # 输入框
            elif self._is_input_field(node):
                candidates_pool.append(node)

        if not candidates_pool:
            return None

        vlm_desc_lower = vlm_desc.lower().strip()

        # 策略1: 文本完全匹配 + y 坐标接近（同一行）
        for node in candidates_pool:
            text = (node.get("text") or node.get("content_desc") or "").lower().strip()
            if text and text == vlm_desc_lower:
                bounds = node.get("bounds")
                center_y = (bounds[1] + bounds[3]) // 2
                if abs(center_y - vlm_y) < 150:  # 同一行
                    self.log("debug", f"      匹配策略1: 文本完全匹配「{text}」")
                    return node

        # 策略2: 文本包含匹配 + y 坐标接近
        for node in candidates_pool:
            text = (node.get("text") or node.get("content_desc") or "").lower().strip()
            if text and (vlm_desc_lower in text or text in vlm_desc_lower):
                bounds = node.get("bounds")
                center_y = (bounds[1] + bounds[3]) // 2
                if abs(center_y - vlm_y) < 150:
                    self.log("debug", f"      匹配策略2: 文本包含匹配「{text}」")
                    return node

        # 策略3: 坐标在 bounds 内
        for node in candidates_pool:
            bounds = node.get("bounds")
            x1, y1, x2, y2 = bounds
            if x1 <= vlm_x <= x2 and y1 <= vlm_y <= y2:
                text = node.get("text") or node.get("content_desc") or ""
                self.log("debug", f"      匹配策略3: 坐标在bounds内「{text}」")
                return node

        # 策略4: 距离最近（限制在 200 像素内）
        candidates = []
        for node in candidates_pool:
            bounds = node.get("bounds")
            center_x = (bounds[0] + bounds[2]) // 2
            center_y = (bounds[1] + bounds[3]) // 2
            dist = ((vlm_x - center_x) ** 2 + (vlm_y - center_y) ** 2) ** 0.5
            if dist < 200:
                candidates.append((dist, node))

        if candidates:
            candidates.sort(key=lambda x: x[0])
            best_dist, best_node = candidates[0]
            text = best_node.get("text") or best_node.get("content_desc") or ""
            self.log("debug", f"      匹配策略4: 距离最近 {best_dist:.0f}px「{text}」")
            return best_node

        return None

    def _create_locator_from_xml(self, xml_node: Dict) -> NodeLocator:
        """从 XML 节点创建 Locator"""
        return NodeLocator(
            resource_id=xml_node.get("resource_id"),
            text=xml_node.get("text"),
            content_desc=xml_node.get("content_desc"),
            class_name=xml_node.get("class_name"),
            bounds=tuple(xml_node.get("bounds", [0, 0, 0, 0]))
        )

    # 垃圾功能关键词（运营塞进来的无用入口）
    _JUNK_KEYWORDS = [
        # 活动运营
        "活动", "福利", "红包", "抽奖", "签到", "任务", "积分", "金币",
        "领取", "免费", "特惠", "优惠", "促销", "限时", "新人", "首单",
        # 会员相关
        "vip", "会员", "开通", "升级", "特权", "尊享",
        # 游戏/娱乐
        "游戏", "小游戏", "游戏中心", "直播", "短视频",
        # 第三方服务
        "小程序", "服务", "生活服务", "本地服务",
        # 广告
        "广告", "推广", "赞助", "热门活动",
        # 其他垃圾
        "皮肤", "主题", "装扮", "表情", "贴纸",
    ]

    def _is_junk_entry(self, description: str) -> bool:
        """判断是否是垃圾功能入口"""
        desc_lower = description.lower()
        for kw in self._JUNK_KEYWORDS:
            if kw in desc_lower:
                return True
        return False

    def _enrich_nav_nodes(self, nav_nodes: List[NavNode], xml_nodes: List[Dict]) -> List[NavNode]:
        """
        用 XML 信息丰富导航节点

        只保留能匹配到 clickable 且是导航锚点的 XML 节点
        """
        enriched = []

        # 先过滤掉垃圾功能
        filtered_nodes = []
        for nav in nav_nodes:
            if self._is_junk_entry(nav.description):
                self.log("debug", f"    ✗ 过滤垃圾功能: {nav.description}")
            else:
                filtered_nodes.append(nav)

        self.log("debug", f"  VLM 节点: {len(nav_nodes)} 个, 过滤后: {len(filtered_nodes)} 个")

        # 统计并打印导航锚点
        nav_anchors = [n for n in xml_nodes if n.get("clickable", False) and self._is_nav_anchor(n)]
        self.log("debug", f"  XML 中有 {len(nav_anchors)} 个导航锚点:")
        for anchor in nav_anchors:
            bounds = anchor.get("bounds", [0, 0, 0, 0])
            center_x = (bounds[0] + bounds[2]) // 2
            center_y = (bounds[1] + bounds[3]) // 2
            text = anchor.get("text") or anchor.get("content_desc") or anchor.get("resource_id", "")[:20]
            self.log("debug", f"    - [{text}] 中心({center_x},{center_y})")

        for nav in filtered_nodes:
            # 获取 VLM 坐标
            if nav.locator.bounds:
                vlm_x, vlm_y = nav.locator.bounds[0], nav.locator.bounds[1]
            else:
                continue

            # 匹配 XML 节点（优先文本匹配，其次坐标匹配）
            xml_node = self._match_xml_node(vlm_x, vlm_y, nav.description, xml_nodes)
            if xml_node:
                xml_text = xml_node.get("text") or xml_node.get("content_desc") or ""
                # 用 XML 信息更新 locator
                nav.locator = self._create_locator_from_xml(xml_node)
                new_center = nav.locator.click_point()
                self.log("info", f"    ✓ VLM「{nav.description}」({vlm_x},{vlm_y}) → XML「{xml_text}」{new_center}")
                enriched.append(nav)
            else:
                # 没匹配到，打印原因
                self.log("debug", f"    ✗ {nav.description}: VLM({vlm_x},{vlm_y}) 未匹配到导航锚点")

        self.log("info", f"  匹配结果: {len(enriched)}/{len(nav_nodes)} 个节点")
        return enriched

    # === 可视化 ===

    def _mark_point(self, screenshot: bytes, x: int, y: int, label: str = "") -> bytes:
        """在截图上标记点击位置"""
        if not HAS_PIL:
            return screenshot

        try:
            img = Image.open(BytesIO(screenshot))
            draw = ImageDraw.Draw(img)

            size = 30
            color = (255, 0, 0)
            width = 3

            draw.line([(x - size, y), (x + size, y)], fill=color, width=width)
            draw.line([(x, y - size), (x, y + size)], fill=color, width=width)
            draw.ellipse([(x - size//2, y - size//2), (x + size//2, y + size//2)],
                        outline=color, width=width)

            if label:
                try:
                    font = ImageFont.truetype("arial.ttf", 24)
                except:
                    font = ImageFont.load_default()
                draw.text((x + size, y - 12), label, fill=color, font=font)

            output = BytesIO()
            img.save(output, format='PNG')
            return output.getvalue()
        except:
            return screenshot

    # === 探索逻辑 ===

    def explore(self, package_name: str) -> dict:
        """执行探索"""
        self.status = ExplorationStatus.RUNNING
        self._stats["start_time"] = time.time()

        self.log("info", "=" * 50)
        self.log("info", f"[v5] Node 驱动探索: {package_name}")
        self.log("info", "=" * 50)

        self.nav_map = NavigationMap()
        self.pending_tasks = deque()
        self.explored_keys = set()

        try:
            self._get_screen_size()
            self.log("info", f"屏幕: {self._screen_width}x{self._screen_height}")

            # 启动应用
            self.log("info", f"启动应用: {package_name}")
            self._launch_app(package_name)

            if not self._check_control():
                return self._build_result(package_name)

            # 分析首页
            self.log("info", "分析首页...")
            screenshot = self._screenshot()
            if not screenshot:
                self.status = ExplorationStatus.STOPPED
                return self._build_result(package_name)

            xml_nodes = self._dump_actions()
            home_desc, home_nav_nodes = self._analyze_page(screenshot)

            # 用 XML 丰富导航节点
            home_nav_nodes = self._enrich_nav_nodes(home_nav_nodes, xml_nodes)

            self.nav_map.home_description = home_desc
            self.log("info", f"首页: {home_desc}")
            self.log("info", f"导航节点: {len(home_nav_nodes)} 个")

            for nav in home_nav_nodes:
                self.log("info", f"  - {nav.description} [{nav.role}] {nav.locator.unique_key()}")

            # 首页节点加入队列
            for nav in home_nav_nodes:
                task = ExploreTask(
                    locator=nav.locator,
                    path=[],
                    description=nav.description,
                    depth=0,
                    role=nav.role
                )
                self.pending_tasks.append(task)

                # 预注册到 nav_map
                trans = NodeTransition(
                    node_key=nav.locator.unique_key(),
                    locator=nav.locator,
                    path=[],
                    description=nav.description,
                    role=nav.role
                )
                self.nav_map.add_transition(trans)

            # 主循环：探索每个节点
            task_count = 0
            while self.pending_tasks:
                if not self._check_control():
                    break

                if self._stats["total_actions"] >= self.config.max_pages * 10:
                    self.log("info", "达到最大动作数")
                    break

                elapsed = time.time() - self._stats["start_time"]
                if elapsed >= self.config.max_time_seconds:
                    self.log("info", "达到时间限制")
                    break

                task = self.pending_tasks.popleft()
                node_key = task.locator.unique_key()

                # 检查是否已探索
                if node_key in self.explored_keys:
                    continue

                # 深度限制
                if task.depth >= self.config.max_depth:
                    self.log("debug", f"跳过深度超限: {task.description}")
                    continue

                task_count += 1
                self.explored_keys.add(node_key)

                self.log("info", "")
                self.log("info", f"━━━ [{task_count}] {task.description} (深度{task.depth}) ━━━")
                self.log("info", f"  路径: {' → '.join([p.unique_key()[:20] for p in task.path]) or '首页'}")

                # 回到首页（优先用 Back，避免 launch 导致卡死）
                self._go_home(package_name)

                # 按路径到达
                if task.path:
                    self.log("info", f"  重放路径 ({len(task.path)} 步)...")
                    for i, step in enumerate(task.path):
                        click_point = step.click_point()
                        if click_point:
                            self.log("debug", f"    步骤 {i+1}: 点击 {click_point}")
                            self._tap(*click_point)
                        else:
                            self.log("warn", f"    步骤 {i+1}: 无法获取点击坐标")

                # 点击目标节点
                click_point = task.locator.click_point()
                if not click_point:
                    self.log("warn", f"  无法获取点击坐标，跳过")
                    continue

                # 打印详细的点击信息
                self.log("info", f"  点击 ({click_point[0]}, {click_point[1]}) - {task.description}")
                if task.locator.bounds:
                    self.log("debug", f"    bounds: {task.locator.bounds}")
                if task.locator.resource_id:
                    self.log("debug", f"    resource_id: {task.locator.resource_id}")
                if task.locator.text:
                    self.log("debug", f"    text: {task.locator.text}")

                # 截图并标记（点击前）
                screenshot = self._screenshot()
                if screenshot:
                    marked = self._mark_point(screenshot, click_point[0], click_point[1], task.description)
                    with self._realtime_lock:
                        self._realtime["current_screenshot"] = base64.b64encode(marked).decode()
                        self._realtime["current_node"] = task.description

                # 执行点击
                self._tap(*click_point)

                # 等待页面响应（增加等待时间）
                time.sleep(0.8)
                new_screenshot = self._screenshot()
                if not new_screenshot:
                    continue

                new_xml = self._dump_actions()
                new_desc, new_nav_nodes = self._analyze_page(new_screenshot)
                new_nav_nodes = self._enrich_nav_nodes(new_nav_nodes, new_xml)

                self.log("info", f"  → {new_desc}")
                self.log("info", f"    发现 {len(new_nav_nodes)} 个导航节点")

                # 更新 transition
                trans = self.nav_map.get_transition(node_key)
                if trans:
                    trans.target_description = new_desc
                    trans.target_nodes = new_nav_nodes
                    trans.explored = True
                    trans.explore_time = time.time()

                # 新节点加入队列
                new_path = task.path + [task.locator]
                for nav in new_nav_nodes:
                    new_key = nav.locator.unique_key()
                    if new_key not in self.explored_keys:
                        new_task = ExploreTask(
                            locator=nav.locator,
                            path=new_path,
                            description=nav.description,
                            depth=task.depth + 1,
                            role=nav.role
                        )
                        self.pending_tasks.append(new_task)

                        # 预注册
                        if not self.nav_map.get_transition(new_key):
                            new_trans = NodeTransition(
                                node_key=new_key,
                                locator=nav.locator,
                                path=new_path,
                                description=nav.description,
                                role=nav.role
                            )
                            self.nav_map.add_transition(new_trans)

                with self._realtime_lock:
                    self._realtime["current_screenshot"] = base64.b64encode(new_screenshot).decode()
                    self._realtime["last_action"] = f"{task.description} → {new_desc}"

            # 完成
            elapsed = time.time() - self._stats["start_time"]
            stats = self.nav_map.get_stats()

            self.log("info", "")
            self.log("info", "=" * 50)
            self.log("info", "探索完成!")
            self.log("info", f"节点: {stats['total_nodes']}, 已探索: {stats['explored_nodes']}")
            self.log("info", f"动作: {self._stats['total_actions']}, 耗时: {elapsed:.1f}s")
            self.log("info", "=" * 50)

            self.status = ExplorationStatus.COMPLETED if self._status != ExplorationStatus.STOPPING else ExplorationStatus.STOPPED
            return self._build_result(package_name)

        except Exception as e:
            import traceback
            self.log("error", f"探索异常: {e}")
            self.log("debug", traceback.format_exc())
            self.status = ExplorationStatus.STOPPED
            return self._build_result(package_name)

    def _build_result(self, package: str) -> dict:
        """构建结果"""
        return {
            "package": package,
            "nav_map": self.nav_map,
            "exploration_time_seconds": time.time() - self._stats["start_time"],
            "total_actions": self._stats["total_actions"],
            **self.nav_map.get_stats()
        }
