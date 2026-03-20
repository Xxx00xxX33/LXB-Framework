package com.lxb.server.protocol;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.zip.CRC32;

/**
 * LXB-Link frame codec.
 *
 * Protocol versions:
 * - v1 (0x01): len is uint16, header size = 10
 * - v2 (0x02): len is uint32, header size = 12
 *
 * Encoding always uses v2 now.
 * Decoding supports both v1 and v2 for compatibility.
 */
public class FrameCodec {

    public static final short MAGIC = (short) 0xAA55;

    public static final byte VERSION_V1 = 0x01;
    public static final byte VERSION_V2 = 0x02;
    public static final byte VERSION = VERSION_V2;

    public static final int HEADER_SIZE_V1 = 10; // magic2 + ver1 + seq4 + cmd1 + len2
    public static final int HEADER_SIZE_V2 = 12; // magic2 + ver1 + seq4 + cmd1 + len4
    public static final int HEADER_SIZE = HEADER_SIZE_V2;

    public static final int CRC_SIZE = 4;
    public static final int MIN_FRAME_SIZE = HEADER_SIZE_V1 + CRC_SIZE;

    public static final int MAX_PAYLOAD_SIZE_V1 = 65535;
    // Keep bounded for memory safety.
    public static final int MAX_PAYLOAD_SIZE_V2 = 16 * 1024 * 1024;
    public static final int MAX_PAYLOAD_SIZE = MAX_PAYLOAD_SIZE_V2;

    private static int computeHeaderSizeByVersion(byte version) throws ProtocolException {
        if (version == VERSION_V1) return HEADER_SIZE_V1;
        if (version == VERSION_V2) return HEADER_SIZE_V2;
        throw new ProtocolException(
                "Unsupported version: 0x" + String.format("%02X", version)
        );
    }

    public static int headerSizeForVersion(byte version) throws ProtocolException {
        return computeHeaderSizeByVersion(version);
    }

    public static int parsePayloadLengthFromHeader(byte[] header) throws ProtocolException {
        if (header == null || header.length < HEADER_SIZE_V1) {
            throw new ProtocolException("Header too short");
        }
        ByteBuffer hb = ByteBuffer.wrap(header).order(ByteOrder.BIG_ENDIAN);
        short magic = hb.getShort();
        if (magic != MAGIC) {
            throw new ProtocolException("Invalid magic in header");
        }
        byte version = hb.get();
        int headerSize = computeHeaderSizeByVersion(version);
        if (header.length < headerSize) {
            throw new ProtocolException("Header length mismatch for version");
        }
        hb.getInt(); // seq
        hb.get();    // cmd
        long payloadLen = (version == VERSION_V2)
                ? (hb.getInt() & 0xFFFFFFFFL)
                : (hb.getShort() & 0xFFFFL);
        if (payloadLen < 0 || payloadLen > Integer.MAX_VALUE) {
            throw new ProtocolException("Payload length out of int range: " + payloadLen);
        }
        int payloadLenInt = (int) payloadLen;
        int maxAllowed = (version == VERSION_V2) ? MAX_PAYLOAD_SIZE_V2 : MAX_PAYLOAD_SIZE_V1;
        if (payloadLenInt > maxAllowed) {
            throw new ProtocolException(
                    "Payload too large: " + payloadLenInt + " (max " + maxAllowed + ")"
            );
        }
        return payloadLenInt;
    }

    public static byte[] encode(int seq, byte cmd, byte[] payload) {
        if (payload == null) {
            payload = new byte[0];
        }
        if (payload.length > MAX_PAYLOAD_SIZE_V2) {
            throw new IllegalArgumentException(
                    "Payload too large for v2 frame: " + payload.length +
                            " (max " + MAX_PAYLOAD_SIZE_V2 + ")"
            );
        }

        int headerSize = HEADER_SIZE_V2;
        int frameSize = headerSize + payload.length + CRC_SIZE;
        ByteBuffer buffer = ByteBuffer.allocate(frameSize).order(ByteOrder.BIG_ENDIAN);

        buffer.putShort(MAGIC);
        buffer.put(VERSION_V2);
        buffer.putInt(seq);
        buffer.put(cmd);
        buffer.putInt(payload.length);
        buffer.put(payload);

        CRC32 crc32 = new CRC32();
        crc32.update(buffer.array(), 0, headerSize + payload.length);
        buffer.putInt((int) crc32.getValue());

        return buffer.array();
    }

    public static DecodedFrame decode(byte[] data) throws ProtocolException, CRCException {
        if (data == null || data.length < MIN_FRAME_SIZE) {
            throw new ProtocolException(
                    "Frame too short: " + (data == null ? 0 : data.length) +
                            " bytes (minimum " + MIN_FRAME_SIZE + ")"
            );
        }

        ByteBuffer pre = ByteBuffer.wrap(data).order(ByteOrder.BIG_ENDIAN);
        short magic = pre.getShort();
        if (magic != MAGIC) {
            throw new ProtocolException("Invalid magic: 0x" + String.format("%04X", magic & 0xFFFF));
        }
        byte version = pre.get();
        int headerSize = computeHeaderSizeByVersion(version);

        if (data.length < headerSize + CRC_SIZE) {
            throw new ProtocolException("Frame too short for header version");
        }

        ByteBuffer buffer = ByteBuffer.wrap(data).order(ByteOrder.BIG_ENDIAN);
        short magic2 = buffer.getShort();
        if (magic2 != MAGIC) {
            throw new ProtocolException("Invalid magic while decoding");
        }

        byte ver = buffer.get();
        int seq = buffer.getInt();
        byte cmd = buffer.get();

        long payloadLenLong = (ver == VERSION_V2)
                ? (buffer.getInt() & 0xFFFFFFFFL)
                : (buffer.getShort() & 0xFFFFL);

        if (payloadLenLong < 0 || payloadLenLong > Integer.MAX_VALUE) {
            throw new ProtocolException("Payload length out of range: " + payloadLenLong);
        }
        int payloadLength = (int) payloadLenLong;

        int maxAllowed = (ver == VERSION_V2) ? MAX_PAYLOAD_SIZE_V2 : MAX_PAYLOAD_SIZE_V1;
        if (payloadLength > maxAllowed) {
            throw new ProtocolException(
                    "Payload too large: " + payloadLength + " (max " + maxAllowed + ")"
            );
        }

        long expectedSizeLong = (long) headerSize + (long) payloadLength + (long) CRC_SIZE;
        if (expectedSizeLong > data.length) {
            throw new ProtocolException(
                    "Frame truncated: expected " + expectedSizeLong + " bytes, got " + data.length
            );
        }

        byte[] payload = new byte[payloadLength];
        buffer.get(payload);

        int receivedCRC = buffer.getInt();
        CRC32 crc32 = new CRC32();
        crc32.update(data, 0, headerSize + payloadLength);
        int calculatedCRC = (int) crc32.getValue();

        if (receivedCRC != calculatedCRC) {
            throw new CRCException(String.format(
                    "CRC mismatch: calculated=0x%08X, received=0x%08X",
                    calculatedCRC, receivedCRC
            ));
        }

        return new DecodedFrame(ver, seq, cmd, payload);
    }

    public static boolean validateMagic(byte[] data) {
        if (data == null || data.length < 2) return false;
        ByteBuffer buffer = ByteBuffer.wrap(data, 0, 2).order(ByteOrder.BIG_ENDIAN);
        return buffer.getShort() == MAGIC;
    }

    public static FrameInfo getFrameInfo(byte[] data) throws ProtocolException {
        if (data == null || data.length < HEADER_SIZE_V1) {
            throw new ProtocolException("Data too short for frame header");
        }

        ByteBuffer pre = ByteBuffer.wrap(data).order(ByteOrder.BIG_ENDIAN);
        short magic = pre.getShort();
        byte version = pre.get();
        int headerSize = computeHeaderSizeByVersion(version);
        if (data.length < headerSize) {
            throw new ProtocolException("Data too short for full header version");
        }

        ByteBuffer buffer = ByteBuffer.wrap(data).order(ByteOrder.BIG_ENDIAN);

        FrameInfo info = new FrameInfo();
        info.magic = buffer.getShort();
        info.version = buffer.get();
        info.seq = buffer.getInt();
        info.cmd = buffer.get();
        info.payloadLength = (info.version == VERSION_V2)
                ? buffer.getInt()
                : (buffer.getShort() & 0xFFFF);

        return info;
    }

    public static byte[] encodeAck(int seq, byte[] responsePayload) {
        return encode(seq, (byte) 0x02, responsePayload);
    }

    public static byte[] encodeSimpleAck(int seq, boolean success) {
        return encode(seq, (byte) 0x02, new byte[]{(byte) (success ? 0x01 : 0x00)});
    }

    public static class DecodedFrame {
        public final byte version;
        public final int seq;
        public final byte cmd;
        public final byte[] payload;

        public DecodedFrame(byte version, int seq, byte cmd, byte[] payload) {
            this.version = version;
            this.seq = seq;
            this.cmd = cmd;
            this.payload = payload;
        }

        @Override
        public String toString() {
            return String.format("Frame[ver=0x%02X, seq=%d, cmd=0x%02X, len=%d]",
                    version, seq, cmd & 0xFF, payload.length);
        }
    }

    public static class FrameInfo {
        public short magic;
        public byte version;
        public int seq;
        public byte cmd;
        public int payloadLength;

        @Override
        public String toString() {
            return String.format(
                    "FrameInfo[magic=0x%04X, ver=0x%02X, seq=%d, cmd=0x%02X, len=%d]",
                    magic & 0xFFFF, version, seq, cmd & 0xFF, payloadLength
            );
        }
    }

    public static class ProtocolException extends Exception {
        public ProtocolException(String message) {
            super(message);
        }
    }

    public static class CRCException extends Exception {
        public CRCException(String message) {
            super(message);
        }
    }
}
