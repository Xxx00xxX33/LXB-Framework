package com.example.lxb_ignition.service

import com.lxb.server.protocol.CommandIds
import com.lxb.server.protocol.FrameCodec
import java.io.Closeable
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.SocketTimeoutException
import java.util.concurrent.atomic.AtomicInteger

/**
 * Minimal LXB-Link client implementation running inside the APK.
 *
 * It talks to lxb-core Main UDP server on localhost using the same FrameCodec
 * as Python client, but with a simplified reliability model:
 *  - one request -> one ACK frame
 *  - no retries / no multi-channel scheduling
 *
 * This is enough for triggering end-side Cortex FSM from the APK.
 */
class LocalLinkClient(
    private val host: String,
    private val port: Int,
    private val defaultTimeoutMs: Int = 8000,
) : Closeable {

    companion object {
        // Keep sequence monotonic across all client instances in this process.
        private val GLOBAL_SEQ = AtomicInteger(1)
    }

    private val socket: DatagramSocket = DatagramSocket().apply {
        soTimeout = defaultTimeoutMs
    }

    @Synchronized
    @Throws(Exception::class)
    fun handshake(timeoutMs: Int = 3000) {
        sendCommandRaw(CommandIds.CMD_HANDSHAKE, ByteArray(0), timeoutMs)
    }

    /**
     * Send one command and return the ACK payload.
     *
     * @param cmd CommandIds.CMD_*
     * @param payload Command payload (binary)
     * @param timeoutMs Receive timeout in milliseconds.
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

        val address = InetAddress.getByName(host)
        val packet = DatagramPacket(frame, frame.size, address, port)

        socket.soTimeout = timeoutMs
        socket.send(packet)

        val buf = ByteArray(64 * 1024)
        val respPacket = DatagramPacket(buf, buf.size)
        try {
            socket.receive(respPacket)
        } catch (e: SocketTimeoutException) {
            throw RuntimeException("UDP recv timeout for cmd=0x${String.format("%02X", cmd)}", e)
        }

        val respData = respPacket.data.copyOf(respPacket.length)
        val decoded = FrameCodec.decode(respData)

        val cmdInt = decoded.cmd.toInt() and 0xFF
        val ackInt = CommandIds.CMD_ACK.toInt() and 0xFF
        if (cmdInt != ackInt) {
            throw RuntimeException(
                "Unexpected cmd in response: 0x${String.format("%02X", decoded.cmd)} (expected ACK 0x${String.format("%02X", CommandIds.CMD_ACK)})"
            )
        }
        if (decoded.seq != seq) {
            throw RuntimeException("ACK seq mismatch: got ${decoded.seq}, expected $seq")
        }
        return decoded.payload
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
        socket.close()
    }
}
