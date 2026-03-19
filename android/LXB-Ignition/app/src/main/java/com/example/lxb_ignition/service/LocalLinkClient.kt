package com.example.lxb_ignition.service

import com.lxb.server.protocol.CommandIds
import com.lxb.server.protocol.FrameCodec
import java.io.BufferedInputStream
import java.io.BufferedOutputStream
import java.io.Closeable
import java.net.InetSocketAddress
import java.net.Socket
import java.net.SocketTimeoutException
import java.util.concurrent.atomic.AtomicInteger

/**
 * Minimal LXB-Link TCP client used by APK.
 *
 * Protocol model:
 * - one request frame -> one ACK frame
 * - no transport-layer retry/dedup on client side
 */
class LocalLinkClient(
    private val host: String,
    private val port: Int,
    private val defaultTimeoutMs: Int = 8000,
) : Closeable {

    companion object {
        // Keep sequence monotonic across all client instances in this process.
        private val GLOBAL_SEQ = AtomicInteger(1)
        private const val DEFAULT_PORT = 12345
    }

    private val targetPort: Int = if (port in 1..65535) port else DEFAULT_PORT

    private val socket: Socket = Socket().apply {
        connect(InetSocketAddress(host, targetPort), defaultTimeoutMs)
        soTimeout = defaultTimeoutMs
        tcpNoDelay = true
    }

    private val input = BufferedInputStream(socket.getInputStream())
    private val output = BufferedOutputStream(socket.getOutputStream())

    @Synchronized
    @Throws(Exception::class)
    fun handshake(timeoutMs: Int = 3000) {
        sendCommandRaw(CommandIds.CMD_HANDSHAKE, ByteArray(0), timeoutMs)
    }

    /**
     * Send one command and return the ACK payload.
     */
    @Synchronized
    @Throws(Exception::class)
    fun sendCommand(cmd: Byte, payload: ByteArray, timeoutMs: Int = defaultTimeoutMs): ByteArray {
        return sendCommandRaw(cmd, payload, timeoutMs)
    }

    @Throws(Exception::class)
    private fun sendCommandRaw(cmd: Byte, payload: ByteArray, timeoutMs: Int): ByteArray {
        val seq = nextSeq()
        val frame = FrameCodec.encode(seq, cmd, payload)

        socket.soTimeout = timeoutMs
        output.write(frame)
        output.flush()

        val respData = try {
            readFrame(timeoutMs)
        } catch (e: SocketTimeoutException) {
            throw RuntimeException("TCP recv timeout for cmd=0x${String.format("%02X", cmd)}", e)
        }

        val decoded = FrameCodec.decode(respData)

        val cmdInt = decoded.cmd.toInt() and 0xFF
        val ackInt = CommandIds.CMD_ACK.toInt() and 0xFF
        if (cmdInt != ackInt) {
            throw RuntimeException(
                "Unexpected cmd in response: 0x${String.format("%02X", decoded.cmd)} " +
                    "(expected ACK 0x${String.format("%02X", CommandIds.CMD_ACK)})"
            )
        }
        if (decoded.seq != seq) {
            throw RuntimeException("ACK seq mismatch: got ${decoded.seq}, expected $seq")
        }
        return decoded.payload
    }

    @Throws(Exception::class)
    private fun readFrame(timeoutMs: Int): ByteArray {
        socket.soTimeout = timeoutMs

        val header = ByteArray(FrameCodec.HEADER_SIZE)
        readFully(header, 0, FrameCodec.HEADER_SIZE)

        val payloadLength = ((header[8].toInt() and 0xFF) shl 8) or (header[9].toInt() and 0xFF)
        val totalLength = FrameCodec.HEADER_SIZE + payloadLength + FrameCodec.CRC_SIZE

        val frame = ByteArray(totalLength)
        System.arraycopy(header, 0, frame, 0, FrameCodec.HEADER_SIZE)
        readFully(frame, FrameCodec.HEADER_SIZE, payloadLength + FrameCodec.CRC_SIZE)
        return frame
    }

    @Throws(Exception::class)
    private fun readFully(buf: ByteArray, offset: Int, length: Int) {
        var read = 0
        while (read < length) {
            val n = input.read(buf, offset + read, length - read)
            if (n < 0) {
                throw RuntimeException("TCP socket closed while reading frame")
            }
            read += n
        }
    }

    private fun nextSeq(): Int {
        while (true) {
            val cur = GLOBAL_SEQ.get()
            val next = if (cur >= 0x7FFFFFF0) 1 else cur + 1
            if (GLOBAL_SEQ.compareAndSet(cur, next)) {
                return cur
            }
        }
    }

    override fun close() {
        try {
            socket.close()
        } catch (_: Exception) {
        }
    }
}
