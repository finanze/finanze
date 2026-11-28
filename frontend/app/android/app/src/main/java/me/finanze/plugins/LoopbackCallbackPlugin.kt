package me.finanze.plugins

import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.CapacitorPlugin
import java.io.BufferedReader
import java.io.IOException
import java.io.InputStreamReader
import java.net.InetAddress
import java.net.ServerSocket
import java.net.Socket
import java.net.SocketTimeoutException
import java.nio.charset.StandardCharsets

@CapacitorPlugin(name = "LoopbackCallback")
class LoopbackCallbackPlugin : Plugin() {

    private val lock = Any()
    private var server: ServerSocket? = null

    @PluginMethod
    fun start(call: PluginCall) {
        val path = call.getString("path") ?: DEFAULT_PATH
        if (!path.startsWith("/")) {
            call.reject("Invalid callback path")
            return
        }
        val timeoutMs = (call.getInt("timeoutMs") ?: DEFAULT_TIMEOUT_MS).toLong()

        stopServer()
        val socket = try {
            ServerSocket(0, BACKLOG, InetAddress.getByName(HOST))
        } catch (e: IOException) {
            call.reject("Could not start the callback listener", e)
            return
        }
        val port = socket.localPort
        val deadline = System.currentTimeMillis() + timeoutMs
        synchronized(lock) { server = socket }
        Thread({ serve(socket, path, port, deadline) }, "LoopbackCallback").apply {
            isDaemon = true
            start()
        }

        val result = JSObject()
        result.put("port", port)
        result.put("url", "http://$HOST:$port$path")
        call.resolve(result)
    }

    @PluginMethod
    fun stop(call: PluginCall) {
        stopServer()
        call.resolve()
    }

    override fun handleOnDestroy() {
        stopServer()
    }

    private fun serve(socket: ServerSocket, path: String, port: Int, deadline: Long) {
        try {
            while (!socket.isClosed) {
                val remaining = deadline - System.currentTimeMillis()
                if (remaining <= 0) {
                    if (release(socket)) {
                        notifyListeners("timeout", JSObject())
                    }
                    return
                }
                socket.soTimeout = remaining.coerceAtMost(Int.MAX_VALUE.toLong()).toInt()
                val client = try {
                    socket.accept()
                } catch (e: SocketTimeoutException) {
                    continue
                }
                client.use { handle(it, path, port) }
            }
        } catch (e: IOException) {
            release(socket)
        }
    }

    private fun handle(client: Socket, path: String, port: Int) {
        client.soTimeout = READ_TIMEOUT_MS
        val target = try {
            readTarget(client)
        } catch (e: IOException) {
            null
        }
        if (target != null && target.substringBefore('?') == path) {
            respond(client, "200 OK", SUCCESS_PAGE)
            val data = JSObject()
            data.put("url", "http://$HOST:$port$target")
            notifyListeners("callback", data)
        } else {
            respond(client, "404 Not Found", NOT_FOUND_PAGE)
        }
    }

    private fun readTarget(client: Socket): String? {
        val reader = BufferedReader(
            InputStreamReader(client.getInputStream(), StandardCharsets.ISO_8859_1)
        )
        val requestLine = reader.readLine() ?: return null
        var headers = 0
        while (headers < MAX_HEADER_LINES) {
            val line = reader.readLine()
            if (line.isNullOrEmpty()) break
            headers++
        }
        val parts = requestLine.split(" ")
        if (parts.size < 3 || parts[0] != "GET" || !parts[1].startsWith("/")) {
            return null
        }
        return parts[1]
    }

    private fun respond(client: Socket, status: String, body: String) {
        val content = body.toByteArray(StandardCharsets.UTF_8)
        val head = "HTTP/1.1 $status\r\n" +
            "Content-Type: text/html; charset=utf-8\r\n" +
            "Content-Length: ${content.size}\r\n" +
            "Cache-Control: no-store\r\n" +
            "Connection: close\r\n\r\n"
        try {
            val output = client.getOutputStream()
            output.write(head.toByteArray(StandardCharsets.ISO_8859_1))
            output.write(content)
            output.flush()
        } catch (e: IOException) {
            // the browser may close the connection before reading the page
        }
    }

    private fun release(socket: ServerSocket): Boolean {
        synchronized(lock) {
            if (server !== socket) return false
            server = null
        }
        closeQuietly(socket)
        return true
    }

    private fun stopServer() {
        val socket = synchronized(lock) {
            val current = server
            server = null
            current
        }
        socket?.let { closeQuietly(it) }
    }

    private fun closeQuietly(socket: ServerSocket) {
        try {
            socket.close()
        } catch (e: IOException) {
            // already closed
        }
    }

    companion object {
        private const val HOST = "127.0.0.1"
        private const val DEFAULT_PATH = "/auth/callback"
        private const val DEFAULT_TIMEOUT_MS = 10 * 60 * 1000
        private const val BACKLOG = 8
        private const val READ_TIMEOUT_MS = 5000
        private const val MAX_HEADER_LINES = 100
        private const val SUCCESS_PAGE =
            "<!DOCTYPE html><html><head><meta charset=\"utf-8\">" +
                "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">" +
                "<title>Finanze</title></head>" +
                "<body style=\"font-family:-apple-system,Roboto,sans-serif;text-align:center;padding:3rem 1.5rem\">" +
                "<p>Sign-in complete. You can return to Finanze.</p></body></html>"
        private const val NOT_FOUND_PAGE =
            "<!DOCTYPE html><html><head><meta charset=\"utf-8\"><title>Finanze</title></head>" +
                "<body></body></html>"
    }
}
