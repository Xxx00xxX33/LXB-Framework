"""
Unit Tests for Sense Layer - AI Agent Perception Commands

Tests the Binary First encoding/decoding for:
- GET_ACTIVITY: Query current foreground Activity
- FIND_NODE: Computation offloading for UI element search
- DUMP_HIERARCHY: Binary UI tree with string pool compression
"""

import unittest
import sys
import logging
import struct
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from lxb_link.protocol import ProtocolFrame, StringPool
from lxb_link.constants import (
    CMD_GET_ACTIVITY,
    CMD_FIND_NODE,
    CMD_DUMP_HIERARCHY,
    MATCH_EXACT_TEXT,
    MATCH_CONTAINS_TEXT,
    MATCH_RESOURCE_ID,
    RETURN_COORDS,
    RETURN_BOUNDS,
    HIERARCHY_FORMAT_BINARY,
    HIERARCHY_COMPRESS_ZLIB,
)

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('tests/logs/test_sense_layer.log', mode='w'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class TestGetActivity(unittest.TestCase):
    """Test GET_ACTIVITY command pack/unpack"""

    def test_pack_get_activity(self):
        """Test packing GET_ACTIVITY command (no payload)"""
        logger.info(f"\n{'='*70}")
        logger.info("Testing GET_ACTIVITY pack")
        logger.info(f"{'='*70}")

        seq = 0x12345678
        frame = ProtocolFrame.pack_get_activity(seq)

        logger.info(f"  Sequence: 0x{seq:08X}")
        logger.info(f"  Frame size: {len(frame)} bytes")
        logger.info(f"  Frame hex: {frame.hex()}")

        # Unpack to verify structure
        seq_out, cmd, payload = ProtocolFrame.unpack(frame)

        logger.info(f"  Unpacked seq: 0x{seq_out:08X}")
        logger.info(f"  Unpacked cmd: 0x{cmd:02X} (GET_ACTIVITY = 0x{CMD_GET_ACTIVITY:02X})")
        logger.info(f"  Payload length: {len(payload)} bytes")

        self.assertEqual(seq_out, seq)
        self.assertEqual(cmd, CMD_GET_ACTIVITY)
        self.assertEqual(len(payload), 0)

        logger.info("[PASS] GET_ACTIVITY pack successful")

    def test_unpack_get_activity_response(self):
        """Test unpacking GET_ACTIVITY response"""
        logger.info(f"\n{'='*70}")
        logger.info("Testing GET_ACTIVITY unpack response")
        logger.info(f"{'='*70}")

        # Simulate device response
        package_name = "com.tencent.mm"
        activity_name = ".ui.LauncherUI"

        package_bytes = package_name.encode('utf-8')
        activity_bytes = activity_name.encode('utf-8')

        # Pack response: success[1B] + pkg_len[2B] + pkg + act_len[2B] + act
        payload = struct.pack('<BH', 1, len(package_bytes))
        payload += package_bytes
        payload += struct.pack('<H', len(activity_bytes))
        payload += activity_bytes

        logger.info(f"  Simulated payload size: {len(payload)} bytes")
        logger.info(f"  Payload hex: {payload.hex()}")

        # Unpack
        success, pkg, act = ProtocolFrame.unpack_get_activity_response(payload)

        logger.info(f"  Success: {success}")
        logger.info(f"  Package: {pkg}")
        logger.info(f"  Activity: {act}")

        self.assertTrue(success)
        self.assertEqual(pkg, package_name)
        self.assertEqual(act, activity_name)

        logger.info("[PASS] GET_ACTIVITY unpack successful")


class TestFindNode(unittest.TestCase):
    """Test FIND_NODE command pack/unpack"""

    def test_pack_find_node_text_search(self):
        """Test packing FIND_NODE for text search"""
        logger.info(f"\n{'='*70}")
        logger.info("Testing FIND_NODE pack (text search)")
        logger.info(f"{'='*70}")

        seq = 0x100
        query = "登录"
        match_type = MATCH_CONTAINS_TEXT
        return_mode = RETURN_COORDS

        frame = ProtocolFrame.pack_find_node(
            seq, match_type, return_mode, query,
            multi_match=False, timeout_ms=3000
        )

        logger.info(f"  Query: '{query}'")
        logger.info(f"  Match type: {match_type} (CONTAINS_TEXT)")
        logger.info(f"  Return mode: {return_mode} (COORDS)")
        logger.info(f"  Frame size: {len(frame)} bytes")

        # Unpack frame
        seq_out, cmd, payload = ProtocolFrame.unpack(frame)

        logger.info(f"  Unpacked seq: 0x{seq_out:08X}")
        logger.info(f"  Unpacked cmd: 0x{cmd:02X}")
        logger.info(f"  Payload size: {len(payload)} bytes")
        logger.info(f"  Payload hex: {payload.hex()}")

        # Verify payload structure
        match_type_out, return_mode_out, multi_match_out, timeout_out, query_len = \
            struct.unpack('<BBBHH', payload[:7])

        logger.info(f"  Decoded match_type: {match_type_out}")
        logger.info(f"  Decoded return_mode: {return_mode_out}")
        logger.info(f"  Decoded multi_match: {multi_match_out}")
        logger.info(f"  Decoded timeout: {timeout_out}ms")
        logger.info(f"  Decoded query_len: {query_len}")

        query_out = payload[7:7+query_len].decode('utf-8')
        logger.info(f"  Decoded query: '{query_out}'")

        self.assertEqual(query_out, query)
        self.assertEqual(match_type_out, match_type)
        self.assertEqual(return_mode_out, return_mode)

        logger.info("[PASS] FIND_NODE pack successful")

    def test_unpack_find_node_coords_response(self):
        """Test unpacking FIND_NODE response (RETURN_COORDS)"""
        logger.info(f"\n{'='*70}")
        logger.info("Testing FIND_NODE unpack (COORDS mode)")
        logger.info(f"{'='*70}")

        # Simulate device finding 2 nodes
        coords = [(540, 960), (540, 1200)]

        # Pack response: status[1B] + count[1B] + coords[]
        payload = struct.pack('<BB', 1, len(coords))  # status=1 (success), count=2
        for x, y in coords:
            payload += struct.pack('<HH', x, y)

        logger.info(f"  Simulated payload size: {len(payload)} bytes")
        logger.info(f"  Payload hex: {payload.hex()}")

        # Unpack
        status, results = ProtocolFrame.unpack_find_node_coords(payload)

        logger.info(f"  Status: {status} (1=success)")
        logger.info(f"  Found {len(results)} nodes:")
        for i, (x, y) in enumerate(results):
            logger.info(f"    Node {i}: ({x}, {y})")

        self.assertEqual(status, 1)
        self.assertEqual(len(results), 2)
        self.assertEqual(results, coords)

        logger.info("[PASS] FIND_NODE unpack (COORDS) successful")

    def test_unpack_find_node_bounds_response(self):
        """Test unpacking FIND_NODE response (RETURN_BOUNDS)"""
        logger.info(f"\n{'='*70}")
        logger.info("Testing FIND_NODE unpack (BOUNDS mode)")
        logger.info(f"{'='*70}")

        # Simulate device finding 1 node with bounds
        bounds = [(100, 500, 980, 650)]

        # Pack response: status[1B] + count[1B] + bounds[]
        payload = struct.pack('<BB', 1, len(bounds))
        for left, top, right, bottom in bounds:
            payload += struct.pack('<HHHH', left, top, right, bottom)

        logger.info(f"  Simulated payload size: {len(payload)} bytes")
        logger.info(f"  Payload hex: {payload.hex()}")

        # Unpack
        status, results = ProtocolFrame.unpack_find_node_bounds(payload)

        logger.info(f"  Status: {status}")
        logger.info(f"  Found {len(results)} nodes:")
        for i, (l, t, r, b) in enumerate(results):
            logger.info(f"    Node {i}: bounds=({l}, {t}, {r}, {b}), size={r-l}x{b-t}")

        self.assertEqual(status, 1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results, bounds)

        logger.info("[PASS] FIND_NODE unpack (BOUNDS) successful")

    def test_find_node_not_found(self):
        """Test FIND_NODE when node is not found"""
        logger.info(f"\n{'='*70}")
        logger.info("Testing FIND_NODE not found case")
        logger.info(f"{'='*70}")

        # Pack response: status=0 (not found), count=0
        payload = struct.pack('<BB', 0, 0)

        logger.info(f"  Payload: {payload.hex()}")

        status, results = ProtocolFrame.unpack_find_node_coords(payload)

        logger.info(f"  Status: {status} (0=not found)")
        logger.info(f"  Results: {results}")

        self.assertEqual(status, 0)
        self.assertEqual(len(results), 0)

        logger.info("[PASS] FIND_NODE not found case handled correctly")


class TestDumpHierarchy(unittest.TestCase):
    """Test DUMP_HIERARCHY command pack/unpack"""

    def test_pack_dump_hierarchy(self):
        """Test packing DUMP_HIERARCHY command"""
        logger.info(f"\n{'='*70}")
        logger.info("Testing DUMP_HIERARCHY pack")
        logger.info(f"{'='*70}")

        seq = 0x200
        format = HIERARCHY_FORMAT_BINARY
        compress = HIERARCHY_COMPRESS_ZLIB
        max_depth = 8

        frame = ProtocolFrame.pack_dump_hierarchy(seq, format, compress, max_depth)

        logger.info(f"  Format: {format} (BINARY)")
        logger.info(f"  Compress: {compress} (ZLIB)")
        logger.info(f"  Max depth: {max_depth}")
        logger.info(f"  Frame size: {len(frame)} bytes")

        # Unpack frame
        seq_out, cmd, payload = ProtocolFrame.unpack(frame)

        logger.info(f"  Unpacked cmd: 0x{cmd:02X} (DUMP_HIERARCHY = 0x{CMD_DUMP_HIERARCHY:02X})")
        logger.info(f"  Payload hex: {payload.hex()}")

        # Verify payload: format[1B] + compress[1B] + max_depth[2B]
        format_out, compress_out, max_depth_out = struct.unpack('<BBH', payload)

        logger.info(f"  Decoded format: {format_out}")
        logger.info(f"  Decoded compress: {compress_out}")
        logger.info(f"  Decoded max_depth: {max_depth_out}")

        self.assertEqual(format_out, format)
        self.assertEqual(compress_out, compress)
        self.assertEqual(max_depth_out, max_depth)

        logger.info("[PASS] DUMP_HIERARCHY pack successful")

    def test_pack_unpack_hierarchy_binary(self):
        """Test binary hierarchy pack/unpack with string pool"""
        logger.info(f"\n{'='*70}")
        logger.info("Testing DUMP_HIERARCHY binary pack/unpack")
        logger.info(f"{'='*70}")

        # Create simple UI tree
        nodes = [
            {
                'parent_index': None,
                'child_count': 2,
                'class': 'android.widget.FrameLayout',
                'bounds': [0, 0, 1080, 1920],
                'text': '',
                'resource_id': '',
                'content_desc': '',
                'clickable': False,
                'visible': True,
                'enabled': True,
                'focused': False,
                'scrollable': False,
                'editable': False,
                'checkable': False,
                'checked': False,
            },
            {
                'parent_index': 0,
                'child_count': 0,
                'class': 'android.widget.TextView',
                'bounds': [100, 200, 980, 300],
                'text': '登录',
                'resource_id': 'com.example:id/login_text',
                'content_desc': '登录按钮',
                'clickable': True,
                'visible': True,
                'enabled': True,
                'focused': False,
                'scrollable': False,
                'editable': False,
                'checkable': False,
                'checked': False,
            },
            {
                'parent_index': 0,
                'child_count': 0,
                'class': 'android.widget.Button',
                'bounds': [100, 400, 980, 550],
                'text': '确定',
                'resource_id': 'com.example:id/confirm_btn',
                'content_desc': '',
                'clickable': True,
                'visible': True,
                'enabled': True,
                'focused': False,
                'scrollable': False,
                'editable': False,
                'checkable': False,
                'checked': False,
            },
        ]

        logger.info(f"  Created {len(nodes)} nodes")
        for i, node in enumerate(nodes):
            logger.info(f"    Node {i}: {node['class']} text='{node['text']}'")

        # Pack to binary
        pool = StringPool()
        packed = ProtocolFrame.pack_hierarchy_binary(nodes, pool)

        logger.info(f"  Packed size: {len(packed)} bytes")
        logger.info(f"  Packed hex (first 64 bytes): {packed[:64].hex()}")

        # Unpack
        hierarchy, pool_out = ProtocolFrame.unpack_dump_hierarchy_binary(packed)

        logger.info(f"  Unpacked version: {hierarchy['version']}")
        logger.info(f"  Unpacked node_count: {hierarchy['node_count']}")
        logger.info(f"  String pool dynamic entries: {len(pool_out.pool)}")

        # Verify nodes
        self.assertEqual(hierarchy['node_count'], len(nodes))

        for i, node_out in enumerate(hierarchy['nodes']):
            logger.info(f"  Node {i}:")
            logger.info(f"    Class: {node_out['class']}")
            logger.info(f"    Text: '{node_out['text']}'")
            logger.info(f"    Resource ID: {node_out['resource_id']}")
            logger.info(f"    Bounds: {node_out['bounds']}")
            logger.info(f"    Clickable: {node_out['clickable']}")

            # Verify against original
            self.assertEqual(node_out['class'], nodes[i]['class'])
            self.assertEqual(node_out['text'], nodes[i]['text'])
            self.assertEqual(node_out['resource_id'], nodes[i]['resource_id'])
            self.assertEqual(node_out['bounds'], nodes[i]['bounds'])
            self.assertEqual(node_out['clickable'], nodes[i]['clickable'])

        logger.info("[PASS] DUMP_HIERARCHY binary pack/unpack successful")

    def test_hierarchy_bandwidth_savings(self):
        """Demonstrate 90% bandwidth savings vs JSON"""
        logger.info(f"\n{'='*70}")
        logger.info("Testing DUMP_HIERARCHY bandwidth savings")
        logger.info(f"{'='*70}")

        # Create realistic UI tree (10 nodes)
        nodes = []
        for i in range(10):
            nodes.append({
                'parent_index': None if i == 0 else 0,
                'child_count': 9 if i == 0 else 0,
                'class': 'android.widget.TextView',
                'bounds': [0, i*100, 1080, (i+1)*100],
                'text': '确定',
                'resource_id': 'com.example:id/text',
                'content_desc': '',
                'clickable': True,
                'visible': True,
                'enabled': True,
                'focused': False,
                'scrollable': False,
                'editable': False,
                'checkable': False,
                'checked': False,
            })

        # Calculate JSON size (approximate)
        import json
        json_str = json.dumps({'nodes': nodes}, ensure_ascii=False)
        json_size = len(json_str.encode('utf-8'))

        logger.info(f"  JSON encoding size: {json_size} bytes")

        # Pack with binary + string pool
        packed = ProtocolFrame.pack_hierarchy_binary(nodes)
        binary_size = len(packed)

        logger.info(f"  Binary encoding size: {binary_size} bytes")

        savings = (1 - binary_size / json_size) * 100
        logger.info(f"  BANDWIDTH SAVINGS: {savings:.1f}%")
        logger.info(f"  Compression ratio: {json_size / binary_size:.1f}x")

        # Should achieve >80% savings
        self.assertGreater(savings, 80)
        logger.info("[PASS] Achieved >80% bandwidth savings vs JSON")


if __name__ == '__main__':
    logger.info("="*70)
    logger.info("Sense Layer Unit Tests - Binary First Architecture")
    logger.info("="*70)
    unittest.main(verbosity=2)
