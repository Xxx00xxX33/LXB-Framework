"""
LXB Auto Map Builder v5

基于 Node 驱动的 Android 应用自动建图系统

v5 新特性:
- 以 Node 为单位探索，不以页面为单位
- 每次从首页开始，按路径到达目标节点
- 不需要"返回"逻辑，不需要页面去重
- 记录：node → 目的地语义描述

主要组件:
- NodeExplorer: Node 驱动探索器 (v5 核心)
- NodeMapBuilder: Node 建图器
- NavigationMap: 导航地图

使用示例 (v5):
    from src.auto_map_builder import NodeMapBuilder, ExplorationConfig
    from src.auto_map_builder.vlm_engine import VLMConfig, set_config
    from src.lxb_link.client import LXBLinkClient

    # 配置 VLM API
    set_config(VLMConfig(
        api_base_url="https://api.example.com/v1",
        api_key="your-api-key",
        model_name="qwen-vl-plus"
    ))

    # 连接设备
    client = LXBLinkClient("192.168.1.100", 12345)
    client.connect()
    client.handshake()

    # 执行探索
    builder = NodeMapBuilder(client)
    result = builder.explore("com.example.app")

    # 保存导航图
    builder.save("./maps/app_nav.json")

兼容旧版本:
    from src.auto_map_builder import AutoMapBuilder  # v2
    from src.auto_map_builder import SemanticMapBuilder  # v3
    from src.auto_map_builder import CoordMapBuilder  # v4
"""

from .models import (
    ExplorationConfig,
    ExplorationResult,
    PageState,
    FusedNode,
    XMLNode,
    Transition,
    VLMDetection,
    VLMPageResult
)
from .vlm_engine import VLMEngine, VLMConfig, get_config, set_config
from .fusion_engine import FusionEngine, parse_xml_nodes
from .page_manager import PageManager
from .explorer import Explorer, ExplorationStatus
from .output_generator import OutputGenerator, generate_map_json

# v3 新模块
from .nav_graph import NavigationGraph, NavPage, NavAnchor, NavTransition, NodeLocator
from .semantic_analyzer import SemanticAnalyzer, SemanticAnalysisResult
from .semantic_explorer import SemanticExplorer, SemanticExplorationResult
from .path_planner import PathPlanner

# v3 SoM 模块
from .som_annotator import SoMAnnotator, AnnotatedNode, create_annotated_screenshot
from .som_analyzer import SoMAnalyzer, AnalysisResult as SoMAnalysisResult, Action, ActionType
from .som_explorer import SoMExplorer, SoMExplorationResult

# v5 Node 驱动模块
from .node_explorer import NodeExplorer, NavigationMap, NodeLocator as NodeLocatorV5, NodeTransition, NavNode


class NodeMapBuilder:
    """
    Node 驱动建图器 (v5 推荐)

    以 Node 为单位探索：
    - 每次从首页开始，按路径到达目标节点
    - 不需要"返回"逻辑
    - 不需要页面去重
    - 记录：node → 目的地语义描述
    """

    def __init__(self, client, config: ExplorationConfig = None, log_callback=None):
        self.client = client
        self.config = config or ExplorationConfig()
        self.log_callback = log_callback
        self._explorer: NodeExplorer = None
        self._result = None

    @property
    def status(self):
        if self._explorer:
            return self._explorer.status
        return ExplorationStatus.IDLE

    @property
    def nav_map(self) -> NavigationMap:
        if self._explorer:
            return self._explorer.nav_map
        return None

    def pause(self):
        if self._explorer:
            self._explorer.pause()

    def resume(self):
        if self._explorer:
            self._explorer.resume()

    def stop(self):
        if self._explorer:
            self._explorer.stop()

    def explore(self, package_name: str):
        self._explorer = NodeExplorer(self.client, self.config, self.log_callback)
        self._result = self._explorer.explore(package_name)
        return self._result

    def save(self, filepath: str = None):
        if not self._explorer or not self._explorer.nav_map:
            raise RuntimeError("请先执行 explore()")
        filepath = filepath or f"./maps/{self._result['package']}_nodes.json"
        self._explorer.nav_map.save(filepath)

    def get_realtime_state(self) -> dict:
        if self._explorer:
            return self._explorer.get_realtime_state()
        return {}


# v4 坐标驱动模块
from .coord_explorer import CoordExplorer


class CoordMapBuilder:
    """
    坐标驱动建图器 (v4 推荐)

    VLM 直接输出坐标 → 映射到 XML 节点 → 记录并点击
    - 简单直接，VLM 只做视觉决策
    - XML 只用于记录节点属性
    - 适应动态页面
    """

    def __init__(self, client, config: ExplorationConfig = None, log_callback=None):
        self.client = client
        self.config = config or ExplorationConfig()
        self.log_callback = log_callback
        self._explorer: CoordExplorer = None
        self._result = None

    @property
    def status(self):
        if self._explorer:
            return self._explorer.status
        return ExplorationStatus.IDLE

    @property
    def graph(self) -> NavigationGraph:
        if self._explorer:
            return self._explorer.graph
        return None

    def pause(self):
        if self._explorer:
            self._explorer.pause()

    def resume(self):
        if self._explorer:
            self._explorer.resume()

    def stop(self):
        if self._explorer:
            self._explorer.stop()

    def explore(self, package_name: str):
        self._explorer = CoordExplorer(self.client, self.config, self.log_callback)
        self._result = self._explorer.explore(package_name)
        return self._result

    def save(self, filepath: str = None):
        if not self._explorer or not self._explorer.graph:
            raise RuntimeError("请先执行 explore()")
        filepath = filepath or f"./maps/{self._result['package']}_nav.json"
        self._explorer.graph.save(filepath)

    def get_realtime_state(self) -> dict:
        if self._explorer:
            return self._explorer.get_realtime_state()
        return {}


class SoMMapBuilder:
    """
    SoM 建图器 (v3 推荐)

    基于 Set-of-Mark 标注的自动建图：
    - 截图标注编号，VLM 直接选择
    - 节点去重合并，避免重复点击
    - 结构化指令输出，精确可靠

    控制方法:
        - pause(): 暂停探索
        - resume(): 恢复探索
        - stop(): 终止探索
        - status: 获取当前状态
    """

    def __init__(
        self,
        client,
        config: ExplorationConfig = None,
        log_callback=None
    ):
        self.client = client
        self.config = config or ExplorationConfig()
        self.log_callback = log_callback

        self._explorer: SoMExplorer = None
        self._result: SoMExplorationResult = None
        self._planner: PathPlanner = None

    @property
    def status(self) -> ExplorationStatus:
        if self._explorer:
            return self._explorer.status
        return ExplorationStatus.IDLE

    @property
    def graph(self) -> NavigationGraph:
        """获取导航图"""
        if self._explorer:
            return self._explorer.graph
        return None

    def pause(self):
        if self._explorer:
            self._explorer.pause()

    def resume(self):
        if self._explorer:
            self._explorer.resume()

    def stop(self):
        if self._explorer:
            self._explorer.stop()

    def explore(self, package_name: str) -> SoMExplorationResult:
        """执行探索"""
        self._explorer = SoMExplorer(
            self.client,
            self.config,
            self.log_callback
        )
        self._result = self._explorer.explore(package_name)

        # 创建路径规划器
        self._planner = PathPlanner(
            self.client,
            self._explorer.graph,
            None,  # SoM 不需要 SemanticAnalyzer
            self.log_callback
        )

        return self._result

    def save(self, filepath: str = None):
        """保存导航图"""
        if not self._explorer or not self._explorer.graph:
            raise RuntimeError("请先执行 explore()")

        filepath = filepath or f"./maps/{self._result.package}_nav.json"
        self._explorer.graph.save(filepath)

    def load(self, filepath: str):
        """加载导航图"""
        graph = NavigationGraph.load(filepath)

        self._planner = PathPlanner(
            self.client,
            graph,
            None,
            self.log_callback
        )

        return graph

    def find_path(self, from_page: str, to_page: str):
        """查找路径"""
        if not self._planner:
            raise RuntimeError("请先执行 explore() 或 load()")
        return self._planner.find_path(from_page, to_page)

    def execute_path(self, path, verify: bool = False):
        """执行路径"""
        if not self._planner:
            raise RuntimeError("请先执行 explore() 或 load()")
        return self._planner.execute_path(path, verify_each_step=verify)

    def get_realtime_state(self) -> dict:
        """获取实时状态"""
        if self._explorer:
            return self._explorer.get_realtime_state()
        return {}


class SemanticMapBuilder:
    """
    语义建图器 (v3)

    基于 VLM 语义 ID 的自动建图，支持：
    - 语义级别页面去重
    - 精确跳转路径记录
    - 快速路径规划

    控制方法:
        - pause(): 暂停探索
        - resume(): 恢复探索
        - stop(): 终止探索
        - status: 获取当前状态
    """

    def __init__(
        self,
        client,
        config: ExplorationConfig = None,
        log_callback=None
    ):
        self.client = client
        self.config = config or ExplorationConfig()
        self.log_callback = log_callback

        self._explorer: SemanticExplorer = None
        self._result: SemanticExplorationResult = None
        self._planner: PathPlanner = None

    @property
    def status(self) -> ExplorationStatus:
        if self._explorer:
            return self._explorer.status
        return ExplorationStatus.IDLE

    @property
    def graph(self) -> NavigationGraph:
        """获取导航图"""
        if self._explorer:
            return self._explorer.graph
        return None

    def pause(self):
        if self._explorer:
            self._explorer.pause()

    def resume(self):
        if self._explorer:
            self._explorer.resume()

    def stop(self):
        if self._explorer:
            self._explorer.stop()

    def explore(self, package_name: str) -> SemanticExplorationResult:
        """执行探索"""
        self._explorer = SemanticExplorer(
            self.client,
            self.config,
            self.log_callback
        )
        self._result = self._explorer.explore(package_name)

        # 创建路径规划器
        self._planner = PathPlanner(
            self.client,
            self._explorer.graph,
            self._explorer.analyzer,
            self.log_callback
        )

        return self._result

    def save(self, filepath: str = None):
        """保存导航图"""
        if not self._explorer or not self._explorer.graph:
            raise RuntimeError("请先执行 explore()")

        filepath = filepath or f"./maps/{self._result.package}_nav.json"
        self._explorer.graph.save(filepath)

    def load(self, filepath: str):
        """加载导航图"""
        graph = NavigationGraph.load(filepath)

        # 创建路径规划器
        vlm_config = get_config()
        vlm_engine = VLMEngine(vlm_config)
        analyzer = SemanticAnalyzer(vlm_engine)

        self._planner = PathPlanner(
            self.client,
            graph,
            analyzer,
            self.log_callback
        )

        return graph

    def find_path(self, from_page: str, to_page: str):
        """查找路径"""
        if not self._planner:
            raise RuntimeError("请先执行 explore() 或 load()")
        return self._planner.find_path(from_page, to_page)

    def execute_path(self, path, verify: bool = False):
        """执行路径"""
        if not self._planner:
            raise RuntimeError("请先执行 explore() 或 load()")
        return self._planner.execute_path(path, verify_each_step=verify)

    def navigate_to(self, target_page: str, verify: bool = True):
        """导航到目标页面 (从首页开始)"""
        if not self._planner:
            raise RuntimeError("请先执行 explore() 或 load()")

        package = self._result.package if self._result else None
        return self._planner.navigate_from_home(target_page, package_name=package)

    def get_realtime_state(self) -> dict:
        """获取实时状态"""
        if self._explorer:
            return self._explorer.get_realtime_state()
        return {}


# v2 兼容
class AutoMapBuilder:
    """
    自动建图器 (v2 兼容)

    封装了完整的探索流程，提供简洁的 API
    """

    def __init__(
        self,
        client,
        config: ExplorationConfig = None,
        log_callback=None
    ):
        self.client = client
        self.config = config or ExplorationConfig()
        self.log_callback = log_callback

        self._explorer: Explorer = None
        self._result = None

    @property
    def status(self) -> ExplorationStatus:
        if self._explorer:
            return self._explorer.status
        return ExplorationStatus.IDLE

    def pause(self):
        if self._explorer:
            self._explorer.pause()
        else:
            raise RuntimeError("探索未开始")

    def resume(self):
        if self._explorer:
            self._explorer.resume()
        else:
            raise RuntimeError("探索未开始")

    def stop(self):
        if self._explorer:
            self._explorer.stop()
        else:
            raise RuntimeError("探索未开始")

    def explore(self, package_name: str) -> ExplorationResult:
        self._explorer = Explorer(
            self.client,
            self.config,
            self.log_callback
        )
        self._result = self._explorer.explore(package_name)
        return self._result

    def save(self, output_dir: str = None):
        if not self._result:
            raise RuntimeError("请先执行 explore() 方法")

        output_dir = output_dir or self.config.output_dir
        generator = OutputGenerator(output_dir)
        generator.save(self._result, self.config.save_screenshots)

    def get_result(self) -> ExplorationResult:
        return self._result

    def generate_overview_json(self) -> dict:
        if not self._result:
            raise RuntimeError("请先执行 explore() 方法")
        return generate_map_json(self._result)


__all__ = [
    # v5 Node 驱动 (推荐)
    "NodeMapBuilder",
    "NodeExplorer",
    "NavigationMap",
    "NodeTransition",
    "NavNode",

    # v4 坐标驱动
    "CoordMapBuilder",
    "CoordExplorer",

    # v3 SoM
    "SoMMapBuilder",
    "SoMExplorer",
    "SoMExplorationResult",
    "SoMAnnotator",
    "SoMAnalyzer",
    "AnnotatedNode",
    "Action",
    "ActionType",

    # v3 语义版
    "SemanticMapBuilder",
    "SemanticExplorer",
    "SemanticExplorationResult",
    "SemanticAnalyzer",
    "SemanticAnalysisResult",

    # v3 通用组件
    "NavigationGraph",
    "NavPage",
    "NavAnchor",
    "NavTransition",
    "NodeLocator",
    "PathPlanner",

    # v2 兼容
    "AutoMapBuilder",
    "Explorer",
    "ExplorationStatus",

    # 配置和结果
    "ExplorationConfig",
    "ExplorationResult",

    # 数据结构
    "PageState",
    "FusedNode",
    "XMLNode",
    "Transition",
    "VLMDetection",
    "VLMPageResult",

    # VLM
    "VLMEngine",
    "VLMConfig",
    "get_config",
    "set_config",

    # 其他组件
    "FusionEngine",
    "PageManager",
    "OutputGenerator",

    # 工具函数
    "parse_xml_nodes",
    "generate_map_json",
    "create_annotated_screenshot"
]
