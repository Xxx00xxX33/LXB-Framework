"""
Unit Tests for Input Extension Layer - Advanced Input Commands

Tests the Binary First encoding/decoding for:
- INPUT_TEXT: Multi-method text input with pure UTF-8 encoding (NO JSON)
- KEY_EVENT: Physical key events (HOME, BACK, ENTER, etc.)
"""

import unittest
import sys
import logging
import struct
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from lxb_link.protocol import ProtocolFrame
from lxb_link.constants import (
    CMD_INPUT_TEXT,
    CMD_KEY_EVENT,
    INPUT_METHOD_ADB,
    INPUT_METHOD_CLIPBOARD,
    INPUT_METHOD_ACCESSIBILITY,
    INPUT_FLAG_CLEAR_FIRST,
    INPUT_FLAG_PRESS_ENTER,
    INPUT_FLAG_HIDE_KEYBOARD,
    KEY_HOME,
    KEY_BACK,
    KEY_ENTER,
    KEY_DELETE,
)

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('tests/logs/test_input_extension.log', mode='w'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class TestInputText(unittest.TestCase):
    """Test INPUT_TEXT command pack/unpack"""

    def test_pack_input_text_basic(self):
        """Test packing INPUT_TEXT with basic parameters"""
        logger.info(f"\n{'='*70}")
        logger.info("Testing INPUT_TEXT pack (basic)")
        logger.info(f"{'='*70}")

        seq = 0x100
        text = "Hello World"
        method = INPUT_METHOD_CLIPBOARD

        frame = ProtocolFrame.pack_input_text(seq, text, method)

        logger.info(f"  Text: '{text}'")
        logger.info(f"  Method: {method} (CLIPBOARD)")
        logger.info(f"  Frame size: {len(frame)} bytes")

        # Unpack frame
        seq_out, cmd, payload = ProtocolFrame.unpack(frame)

        logger.info(f"  Unpacked cmd: 0x{cmd:02X} (INPUT_TEXT = 0x{CMD_INPUT_TEXT:02X})")
        logger.info(f"  Payload size: {len(payload)} bytes")
        logger.info(f"  Payload hex: {payload.hex()}")

        # Verify payload structure: method[1B] + flags[1B] + target_x[2B] +
        #                            target_y[2B] + delay_ms[2B] + text_len[2B] + text[]
        method_out, flags, target_x, target_y, delay_ms, text_len = \
            struct.unpack('<BBHHHH', payload[:10])

        text_bytes = payload[10:10+text_len]
        text_out = text_bytes.decode('utf-8')

        logger.info(f"  Decoded method: {method_out}")
        logger.info(f"  Decoded flags: 0x{flags:02X}")
        logger.info(f"  Decoded target: ({target_x}, {target_y})")
        logger.info(f"  Decoded delay: {delay_ms}ms")
        logger.info(f"  Decoded text_len: {text_len}")
        logger.info(f"  Decoded text: '{text_out}'")

        self.assertEqual(method_out, method)
        self.assertEqual(text_out, text)
        self.assertEqual(flags, 0)  # No flags set

        logger.info("[PASS] INPUT_TEXT basic pack successful")

    def test_pack_input_text_chinese(self):
        """Test INPUT_TEXT with Chinese text (UTF-8 encoding)"""
        logger.info(f"\n{'='*70}")
        logger.info("Testing INPUT_TEXT pack (Chinese UTF-8)")
        logger.info(f"{'='*70}")

        seq = 0x101
        text = "微信支付密码"
        method = INPUT_METHOD_CLIPBOARD

        frame = ProtocolFrame.pack_input_text(seq, text, method)

        logger.info(f"  Text: '{text}'")
        logger.info(f"  Text bytes: {text.encode('utf-8').hex()}")
        logger.info(f"  Frame size: {len(frame)} bytes")

        # Unpack
        seq_out, cmd, payload = ProtocolFrame.unpack(frame)

        method_out, flags, target_x, target_y, delay_ms, text_len = \
            struct.unpack('<BBHHHH', payload[:10])

        text_out = payload[10:10+text_len].decode('utf-8')

        logger.info(f"  Decoded text: '{text_out}'")
        logger.info(f"  UTF-8 match: {text_out == text}")

        self.assertEqual(text_out, text)

        logger.info("[PASS] INPUT_TEXT Chinese UTF-8 encoding successful")

    def test_pack_input_text_with_flags(self):
        """Test INPUT_TEXT with multiple flags set"""
        logger.info(f"\n{'='*70}")
        logger.info("Testing INPUT_TEXT pack (with flags)")
        logger.info(f"{'='*70}")

        seq = 0x102
        text = "username@example.com"
        method = INPUT_METHOD_ADB

        frame = ProtocolFrame.pack_input_text(
            seq, text, method,
            clear_first=True,
            press_enter=True,
            hide_keyboard=True,
            target_x=500,
            target_y=800,
            delay_ms=50
        )

        logger.info(f"  Text: '{text}'")
        logger.info(f"  Method: {method} (ADB)")
        logger.info(f"  Flags: CLEAR_FIRST | PRESS_ENTER | HIDE_KEYBOARD")
        logger.info(f"  Target: (500, 800)")
        logger.info(f"  Delay: 50ms")

        # Unpack
        seq_out, cmd, payload = ProtocolFrame.unpack(frame)

        method_out, flags, target_x, target_y, delay_ms, text_len = \
            struct.unpack('<BBHHHH', payload[:10])

        logger.info(f"  Decoded flags: 0x{flags:02X}")
        logger.info(f"    CLEAR_FIRST: {bool(flags & INPUT_FLAG_CLEAR_FIRST)}")
        logger.info(f"    PRESS_ENTER: {bool(flags & INPUT_FLAG_PRESS_ENTER)}")
        logger.info(f"    HIDE_KEYBOARD: {bool(flags & INPUT_FLAG_HIDE_KEYBOARD)}")
        logger.info(f"  Decoded target: ({target_x}, {target_y})")
        logger.info(f"  Decoded delay: {delay_ms}ms")

        # Verify flags
        self.assertTrue(flags & INPUT_FLAG_CLEAR_FIRST)
        self.assertTrue(flags & INPUT_FLAG_PRESS_ENTER)
        self.assertTrue(flags & INPUT_FLAG_HIDE_KEYBOARD)
        self.assertEqual(target_x, 500)
        self.assertEqual(target_y, 800)
        self.assertEqual(delay_ms, 50)

        logger.info("[PASS] INPUT_TEXT flags encoding successful")

    def test_unpack_input_text_response(self):
        """Test unpacking INPUT_TEXT response"""
        logger.info(f"\n{'='*70}")
        logger.info("Testing INPUT_TEXT unpack response")
        logger.info(f"{'='*70}")

        # Simulate device response: status[1B] + actual_method[1B]
        status = 1  # Success
        actual_method = INPUT_METHOD_CLIPBOARD

        payload = struct.pack('<BB', status, actual_method)

        logger.info(f"  Simulated payload: {payload.hex()}")

        # Unpack
        status_out, method_out = ProtocolFrame.unpack_input_text_response(payload)

        logger.info(f"  Status: {status_out} (1=success)")
        logger.info(f"  Actual method: {method_out} (CLIPBOARD)")

        self.assertEqual(status_out, status)
        self.assertEqual(method_out, actual_method)

        logger.info("[PASS] INPUT_TEXT unpack response successful")

    def test_input_text_empty_string(self):
        """Test INPUT_TEXT with empty string (edge case)"""
        logger.info(f"\n{'='*70}")
        logger.info("Testing INPUT_TEXT with empty string")
        logger.info(f"{'='*70}")

        seq = 0x103
        text = ""

        frame = ProtocolFrame.pack_input_text(seq, text)

        logger.info(f"  Text: '{text}' (empty)")
        logger.info(f"  Frame size: {len(frame)} bytes")

        # Unpack
        seq_out, cmd, payload = ProtocolFrame.unpack(frame)

        method_out, flags, target_x, target_y, delay_ms, text_len = \
            struct.unpack('<BBHHHH', payload[:10])

        logger.info(f"  Decoded text_len: {text_len}")

        self.assertEqual(text_len, 0)

        logger.info("[PASS] INPUT_TEXT empty string handled correctly")


class TestKeyEvent(unittest.TestCase):
    """Test KEY_EVENT command pack/unpack"""

    def test_pack_key_event_back(self):
        """Test packing KEY_EVENT for BACK button"""
        logger.info(f"\n{'='*70}")
        logger.info("Testing KEY_EVENT pack (BACK button)")
        logger.info(f"{'='*70}")

        seq = 0x200
        keycode = KEY_BACK
        action = 2  # Click (down + up)

        frame = ProtocolFrame.pack_key_event(seq, keycode, action)

        logger.info(f"  Keycode: {keycode} (KEY_BACK)")
        logger.info(f"  Action: {action} (CLICK)")
        logger.info(f"  Frame size: {len(frame)} bytes")

        # Unpack frame
        seq_out, cmd, payload = ProtocolFrame.unpack(frame)

        logger.info(f"  Unpacked cmd: 0x{cmd:02X} (KEY_EVENT = 0x{CMD_KEY_EVENT:02X})")
        logger.info(f"  Payload size: {len(payload)} bytes (expected: 6)")
        logger.info(f"  Payload hex: {payload.hex()}")

        # Verify payload: keycode[1B] + action[1B] + meta_state[4B]
        self.assertEqual(len(payload), 6)

        keycode_out, action_out, meta_state = struct.unpack('<BBI', payload)

        logger.info(f"  Decoded keycode: {keycode_out}")
        logger.info(f"  Decoded action: {action_out}")
        logger.info(f"  Decoded meta_state: 0x{meta_state:08X}")

        self.assertEqual(keycode_out, keycode)
        self.assertEqual(action_out, action)
        self.assertEqual(meta_state, 0)

        logger.info("[PASS] KEY_EVENT BACK pack successful")

    def test_pack_key_event_home(self):
        """Test packing KEY_EVENT for HOME button"""
        logger.info(f"\n{'='*70}")
        logger.info("Testing KEY_EVENT pack (HOME button)")
        logger.info(f"{'='*70}")

        seq = 0x201
        keycode = KEY_HOME

        frame = ProtocolFrame.pack_key_event(seq, keycode)

        logger.info(f"  Keycode: {keycode} (KEY_HOME)")

        # Unpack
        seq_out, cmd, payload = ProtocolFrame.unpack(frame)

        keycode_out, action_out, meta_state = struct.unpack('<BBI', payload)

        logger.info(f"  Decoded keycode: {keycode_out}")
        logger.info(f"  Decoded action: {action_out} (default: 2)")

        self.assertEqual(keycode_out, KEY_HOME)
        self.assertEqual(action_out, 2)  # Default action

        logger.info("[PASS] KEY_EVENT HOME pack successful")

    def test_pack_key_event_enter(self):
        """Test packing KEY_EVENT for ENTER key"""
        logger.info(f"\n{'='*70}")
        logger.info("Testing KEY_EVENT pack (ENTER key)")
        logger.info(f"{'='*70}")

        seq = 0x202
        keycode = KEY_ENTER

        frame = ProtocolFrame.pack_key_event(seq, keycode)

        # Unpack
        seq_out, cmd, payload = ProtocolFrame.unpack(frame)

        keycode_out, action_out, meta_state = struct.unpack('<BBI', payload)

        logger.info(f"  Keycode: {keycode_out} (KEY_ENTER = {KEY_ENTER})")

        self.assertEqual(keycode_out, KEY_ENTER)

        logger.info("[PASS] KEY_EVENT ENTER pack successful")

    def test_pack_key_event_delete(self):
        """Test packing KEY_EVENT for DELETE key"""
        logger.info(f"\n{'='*70}")
        logger.info("Testing KEY_EVENT pack (DELETE key)")
        logger.info(f"{'='*70}")

        seq = 0x203
        keycode = KEY_DELETE

        frame = ProtocolFrame.pack_key_event(seq, keycode)

        # Unpack
        seq_out, cmd, payload = ProtocolFrame.unpack(frame)

        keycode_out, action_out, meta_state = struct.unpack('<BBI', payload)

        logger.info(f"  Keycode: {keycode_out} (KEY_DELETE = {KEY_DELETE})")

        self.assertEqual(keycode_out, KEY_DELETE)

        logger.info("[PASS] KEY_EVENT DELETE pack successful")

    def test_pack_key_event_with_meta(self):
        """Test packing KEY_EVENT with meta state (Shift/Ctrl/Alt)"""
        logger.info(f"\n{'='*70}")
        logger.info("Testing KEY_EVENT with meta state")
        logger.info(f"{'='*70}")

        seq = 0x204
        keycode = 29  # 'A' key
        action = 2
        meta_state = 0x00000001  # SHIFT pressed

        frame = ProtocolFrame.pack_key_event(seq, keycode, action, meta_state)

        logger.info(f"  Keycode: {keycode}")
        logger.info(f"  Meta state: 0x{meta_state:08X} (SHIFT)")

        # Unpack
        seq_out, cmd, payload = ProtocolFrame.unpack(frame)

        keycode_out, action_out, meta_out = struct.unpack('<BBI', payload)

        logger.info(f"  Decoded meta_state: 0x{meta_out:08X}")

        self.assertEqual(meta_out, meta_state)

        logger.info("[PASS] KEY_EVENT meta state encoding successful")

    def test_unpack_key_event(self):
        """Test unpacking KEY_EVENT payload"""
        logger.info(f"\n{'='*70}")
        logger.info("Testing KEY_EVENT unpack")
        logger.info(f"{'='*70}")

        # Simulate payload: keycode[1B] + action[1B] + meta_state[4B]
        keycode = KEY_BACK
        action = 0  # Key down
        meta_state = 0

        payload = struct.pack('<BBI', keycode, action, meta_state)

        logger.info(f"  Simulated payload: {payload.hex()}")

        # Unpack
        keycode_out, action_out, meta_out = ProtocolFrame.unpack_key_event(payload)

        logger.info(f"  Decoded keycode: {keycode_out}")
        logger.info(f"  Decoded action: {action_out}")
        logger.info(f"  Decoded meta_state: {meta_out}")

        self.assertEqual(keycode_out, keycode)
        self.assertEqual(action_out, action)
        self.assertEqual(meta_out, meta_state)

        logger.info("[PASS] KEY_EVENT unpack successful")


class TestInputExtensionIntegration(unittest.TestCase):
    """Integration tests for Input Extension commands"""

    def test_input_text_workflow(self):
        """Test complete INPUT_TEXT workflow: pack -> simulate response -> unpack"""
        logger.info(f"\n{'='*70}")
        logger.info("Testing INPUT_TEXT workflow integration")
        logger.info(f"{'='*70}")

        # Step 1: Client packs INPUT_TEXT command
        seq = 0x300
        text = "alice@example.com"
        method = INPUT_METHOD_CLIPBOARD

        request_frame = ProtocolFrame.pack_input_text(
            seq, text, method,
            clear_first=True,
            press_enter=True
        )

        logger.info(f"Step 1: Client packs INPUT_TEXT")
        logger.info(f"  Text: '{text}'")
        logger.info(f"  Method: {method} (CLIPBOARD)")
        logger.info(f"  Request size: {len(request_frame)} bytes")

        # Step 2: Verify request structure
        seq_out, cmd, payload = ProtocolFrame.unpack(request_frame)
        logger.info(f"Step 2: Verify request")
        logger.info(f"  Command: 0x{cmd:02X}")
        logger.info(f"  Payload size: {len(payload)} bytes")

        # Step 3: Simulate device response
        status = 1  # Success
        actual_method = INPUT_METHOD_CLIPBOARD
        response_payload = struct.pack('<BB', status, actual_method)

        logger.info(f"Step 3: Device responds")
        logger.info(f"  Status: {status} (success)")
        logger.info(f"  Actual method: {actual_method}")

        # Step 4: Client unpacks response
        status_out, method_out = ProtocolFrame.unpack_input_text_response(response_payload)

        logger.info(f"Step 4: Client unpacks response")
        logger.info(f"  Status: {status_out}")
        logger.info(f"  Method used: {method_out}")

        self.assertEqual(status_out, 1)
        self.assertEqual(method_out, INPUT_METHOD_CLIPBOARD)

        logger.info("[PASS] INPUT_TEXT workflow successful")

    def test_key_event_sequence(self):
        """Test KEY_EVENT sequence (BACK -> HOME -> ENTER)"""
        logger.info(f"\n{'='*70}")
        logger.info("Testing KEY_EVENT sequence")
        logger.info(f"{'='*70}")

        keys = [
            (KEY_BACK, "BACK"),
            (KEY_HOME, "HOME"),
            (KEY_ENTER, "ENTER"),
        ]

        for i, (keycode, name) in enumerate(keys):
            seq = 0x400 + i
            frame = ProtocolFrame.pack_key_event(seq, keycode)

            seq_out, cmd, payload = ProtocolFrame.unpack(frame)
            keycode_out, action_out, meta_out = ProtocolFrame.unpack_key_event(payload)

            logger.info(f"  Key {i+1}: {name} (keycode={keycode_out}, action={action_out})")

            self.assertEqual(keycode_out, keycode)

        logger.info("[PASS] KEY_EVENT sequence successful")


if __name__ == '__main__':
    logger.info("="*70)
    logger.info("Input Extension Unit Tests - Binary First Architecture")
    logger.info("="*70)
    unittest.main(verbosity=2)
