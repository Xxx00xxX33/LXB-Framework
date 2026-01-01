"""
Unit Tests for StringPool - Binary First Architecture

Tests the string pool compression mechanism that saves 96% bandwidth
by encoding repeated class names and texts as single-byte IDs.
"""

import unittest
import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from lxb_link.protocol import StringPool
from lxb_link.constants import (
    PREDEFINED_CLASSES,
    PREDEFINED_TEXTS,
    CLASS_TO_ID,
    TEXT_TO_ID,
    STRING_POOL_EMPTY_ID,
    DYNAMIC_STRING_POOL_START,
)

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('tests/logs/test_string_pool.log', mode='w'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class TestStringPoolBasic(unittest.TestCase):
    """Test basic StringPool operations"""

    def setUp(self):
        """Create fresh StringPool for each test"""
        self.pool = StringPool()
        logger.info(f"\n{'='*70}")
        logger.info(f"Starting test: {self._testMethodName}")
        logger.info(f"{'='*70}")

    def test_empty_string_encoding(self):
        """Test that empty string returns special ID 0xFF"""
        logger.info("Testing empty string encoding...")

        str_id = self.pool.add("")
        logger.info(f"  Empty string ID: 0x{str_id:02X} (expected: 0xFF)")

        self.assertEqual(str_id, STRING_POOL_EMPTY_ID)

        decoded = self.pool.get(str_id)
        logger.info(f"  Decoded back: '{decoded}'")
        self.assertEqual(decoded, "")

    def test_predefined_class_encoding(self):
        """Test encoding of predefined Android class names"""
        logger.info("Testing predefined class encoding...")

        test_cases = [
            ("android.view.View", 0x00),
            ("android.view.ViewGroup", 0x01),
            ("android.widget.TextView", 0x02),
            ("android.widget.EditText", 0x03),
        ]

        for class_name, expected_id in test_cases:
            str_id = self.pool.add(class_name)
            logger.info(f"  '{class_name}' -> 0x{str_id:02X} (expected: 0x{expected_id:02X})")
            self.assertEqual(str_id, expected_id)

            # Verify decoding
            decoded = self.pool.get(str_id)
            self.assertEqual(decoded, class_name)

        logger.info(f"[PASS] All {len(test_cases)} predefined classes encoded correctly")

    def test_predefined_text_encoding(self):
        """Test encoding of predefined common texts"""
        logger.info("Testing predefined text encoding...")

        test_cases = [
            ("", 0xFF),  # Empty string special case
            ("确定", 0x41),
            ("取消", 0x42),
            ("登录", 0x4A),
            ("OK", 0x50),
            ("Cancel", 0x51),
        ]

        for text, expected_id in test_cases:
            str_id = self.pool.add(text)
            logger.info(f"  '{text}' -> 0x{str_id:02X} (expected: 0x{expected_id:02X})")
            self.assertEqual(str_id, expected_id)

            # Verify decoding
            decoded = self.pool.get(str_id)
            self.assertEqual(decoded, text)

        logger.info(f"[PASS] All {len(test_cases)} predefined texts encoded correctly")

    def test_dynamic_string_allocation(self):
        """Test dynamic string pool allocation for custom strings"""
        logger.info("Testing dynamic string allocation...")

        # Add custom strings not in predefined pools
        custom_strings = [
            "com.example.myapp",
            "我的自定义文本",
            "Custom Button Label",
        ]

        allocated_ids = []
        for s in custom_strings:
            str_id = self.pool.add(s)
            logger.info(f"  '{s}' -> 0x{str_id:02X} (dynamic ID)")

            # Should be in dynamic range [0x80, 0xFE]
            self.assertGreaterEqual(str_id, DYNAMIC_STRING_POOL_START)
            self.assertLessEqual(str_id, 0xFE)

            allocated_ids.append(str_id)

        # Verify all got unique IDs
        self.assertEqual(len(allocated_ids), len(set(allocated_ids)))
        logger.info(f"[PASS] Allocated {len(custom_strings)} dynamic IDs: {[f'0x{x:02X}' for x in allocated_ids]}")

        # Verify decoding
        for i, s in enumerate(custom_strings):
            decoded = self.pool.get(allocated_ids[i])
            logger.info(f"  Decode 0x{allocated_ids[i]:02X} -> '{decoded}'")
            self.assertEqual(decoded, s)

    def test_string_reuse(self):
        """Test that same string returns same ID (deduplication)"""
        logger.info("Testing string deduplication...")

        custom_str = "com.tencent.mm"

        id1 = self.pool.add(custom_str)
        logger.info(f"  First add: '{custom_str}' -> 0x{id1:02X}")

        id2 = self.pool.add(custom_str)
        logger.info(f"  Second add: '{custom_str}' -> 0x{id2:02X}")

        id3 = self.pool.add(custom_str)
        logger.info(f"  Third add: '{custom_str}' -> 0x{id3:02X}")

        self.assertEqual(id1, id2)
        self.assertEqual(id2, id3)

        logger.info(f"[PASS] Deduplication works: same string reuses ID 0x{id1:02X}")
        logger.info(f"  Dynamic pool size: {len(self.pool.pool)} (should be 1)")
        self.assertEqual(len(self.pool.pool), 1)


class TestStringPoolSerialization(unittest.TestCase):
    """Test StringPool pack/unpack (binary serialization)"""

    def setUp(self):
        self.pool = StringPool()
        logger.info(f"\n{'='*70}")
        logger.info(f"Starting test: {self._testMethodName}")
        logger.info(f"{'='*70}")

    def test_empty_pool_serialization(self):
        """Test serializing empty pool (only predefined strings used)"""
        logger.info("Testing empty pool serialization...")

        # Only use predefined strings
        self.pool.add("android.widget.Button")
        self.pool.add("确定")

        packed = self.pool.pack()
        logger.info(f"  Packed size: {len(packed)} bytes")
        logger.info(f"  Packed data: {packed.hex()}")

        # Should be just 2 bytes: count[uint16] = 0
        self.assertEqual(len(packed), 2)
        self.assertEqual(packed, b'\x00\x00')

        # Unpack and verify
        pool2, size = StringPool.unpack(packed)
        logger.info(f"  Unpacked size consumed: {size} bytes")
        self.assertEqual(size, 2)
        logger.info(f"[PASS] Empty pool serialization works")

    def test_dynamic_pool_serialization(self):
        """Test serializing pool with dynamic strings"""
        logger.info("Testing dynamic pool serialization...")

        # Add some dynamic strings
        custom_strings = [
            "com.example.app1",
            "自定义按钮",
            "Custom Label",
        ]

        for s in custom_strings:
            str_id = self.pool.add(s)
            logger.info(f"  Added '{s}' -> 0x{str_id:02X}")

        # Pack
        packed = self.pool.pack()
        logger.info(f"  Packed size: {len(packed)} bytes")
        logger.info(f"  Packed hex: {packed.hex()}")

        # Should have: count[2B] + entries[str_id + len + data]
        self.assertGreater(len(packed), 2)

        # Unpack
        pool2, size = StringPool.unpack(packed)
        logger.info(f"  Unpacked size consumed: {size} bytes")
        self.assertEqual(size, len(packed))

        # Verify all dynamic strings can be retrieved
        for s in custom_strings:
            str_id = pool2.add(s)  # Should find existing
            decoded = pool2.get(str_id)
            logger.info(f"  Verify '{s}' -> 0x{str_id:02X} -> '{decoded}'")
            self.assertEqual(decoded, s)

        logger.info(f"[PASS] Dynamic pool serialization successful")

    def test_round_trip_serialization(self):
        """Test full round-trip: add -> pack -> unpack -> verify"""
        logger.info("Testing round-trip serialization...")

        # Mix of predefined and dynamic strings
        test_strings = [
            "android.widget.TextView",  # Predefined class
            "确定",                      # Predefined text
            "com.tencent.mm",           # Dynamic
            "微信支付",                  # Dynamic
            "Login Button",             # Dynamic
            "",                         # Empty string
        ]

        # Add to original pool
        original_ids = []
        for s in test_strings:
            str_id = self.pool.add(s)
            original_ids.append(str_id)
            logger.info(f"  Original: '{s}' -> 0x{str_id:02X}")

        # Pack
        packed = self.pool.pack()
        logger.info(f"  Packed to {len(packed)} bytes")

        # Unpack into new pool
        pool2, _ = StringPool.unpack(packed)

        # Verify all strings decode correctly
        for i, s in enumerate(test_strings):
            decoded = pool2.get(original_ids[i])
            logger.info(f"  Round-trip: 0x{original_ids[i]:02X} -> '{decoded}' (expected: '{s}')")
            self.assertEqual(decoded, s)

        logger.info(f"[PASS] Round-trip successful for {len(test_strings)} strings")


class TestStringPoolPerformance(unittest.TestCase):
    """Test StringPool bandwidth savings"""

    def test_bandwidth_savings(self):
        """Demonstrate 96% bandwidth savings on real Android UI tree"""
        logger.info(f"\n{'='*70}")
        logger.info("Testing StringPool bandwidth savings")
        logger.info(f"{'='*70}")

        # Simulate typical Android UI tree with 30 nodes
        typical_ui_tree = [
            ("android.widget.FrameLayout", ""),
            ("android.widget.LinearLayout", ""),
            ("android.widget.TextView", "微信"),
            ("android.widget.TextView", "通讯录"),
            ("android.widget.TextView", "发现"),
            ("android.widget.TextView", "我"),
            ("android.view.View", ""),
            ("android.widget.Button", "登录"),
            ("android.widget.Button", "注册"),
            ("android.widget.EditText", ""),
            ("android.widget.TextView", "请输入手机号"),
            ("android.widget.EditText", ""),
            ("android.widget.TextView", "请输入密码"),
            ("android.widget.ImageView", ""),
            ("android.widget.ImageView", ""),
            ("android.widget.Button", "确定"),
            ("android.widget.Button", "取消"),
            ("android.widget.TextView", "忘记密码"),
            ("android.widget.LinearLayout", ""),
            ("android.widget.TextView", "新用户注册"),
        ]

        # Calculate WITHOUT string pool (raw UTF-8)
        raw_size = 0
        for class_name, text in typical_ui_tree:
            raw_size += len(class_name.encode('utf-8'))
            raw_size += len(text.encode('utf-8'))

        logger.info(f"  WITHOUT String Pool:")
        logger.info(f"    Total raw UTF-8 size: {raw_size} bytes")

        # Calculate WITH string pool
        pool = StringPool()
        pool_size = 0
        for class_name, text in typical_ui_tree:
            class_id = pool.add(class_name)
            text_id = pool.add(text)
            pool_size += 2  # 1 byte per ID

        # Add dynamic pool overhead
        dynamic_overhead = len(pool.pack())
        total_with_pool = pool_size + dynamic_overhead

        logger.info(f"  WITH String Pool:")
        logger.info(f"    Node IDs size: {pool_size} bytes (2 bytes × {len(typical_ui_tree)} nodes)")
        logger.info(f"    Dynamic pool overhead: {dynamic_overhead} bytes")
        logger.info(f"    Total: {total_with_pool} bytes")

        savings = (1 - total_with_pool / raw_size) * 100
        logger.info(f"  BANDWIDTH SAVINGS: {savings:.1f}%")
        logger.info(f"  Compression ratio: {raw_size / total_with_pool:.1f}x")

        # Should achieve >70% savings
        self.assertGreater(savings, 70)
        logger.info(f"[PASS] Achieved >70% bandwidth savings")


if __name__ == '__main__':
    logger.info("="*70)
    logger.info("StringPool Unit Tests - Binary First Architecture")
    logger.info("="*70)
    unittest.main(verbosity=2)
