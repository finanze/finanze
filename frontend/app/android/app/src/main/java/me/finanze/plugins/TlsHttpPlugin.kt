package me.finanze.plugins

import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.CapacitorPlugin
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import org.json.JSONObject
import mobile.Mobile

@CapacitorPlugin(name = "TlsHttp")
class TlsHttpPlugin : Plugin() {

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    @PluginMethod
    fun request(call: PluginCall) {
        val url = call.getString("url")
        val method = call.getString("method")
        if (url.isNullOrBlank() || method.isNullOrBlank()) {
            call.reject("Missing url or method")
            return
        }

        val sessionId = call.getString("sessionId") ?: "default"
        val headers = call.getObject("headers") ?: JSObject()
        val data = call.getString("data")
        val profile = call.getString("profile")

        val requestObj = JSONObject().apply {
            put("sessionId", sessionId)
            put("method", method)
            put("url", url)
            val headersObj = JSONObject()
            for (key in headers.keys()) {
                headersObj.put(key, headers.getString(key))
            }
            put("headers", headersObj)
            if (data != null) {
                put("body", data)
            }
            if (!profile.isNullOrBlank()) {
                put("profile", profile)
            }
            if (call.getBoolean("forceHttp1") == true) {
                put("forceHttp1", true)
            }
            if (call.getBoolean("disableHttp3") == true) {
                put("disableHttp3", true)
            }
        }

        scope.launch {
            try {
                val responseJSON = Mobile.request(requestObj.toString())
                val response = JSONObject(responseJSON)

                val result = JSObject().apply {
                    put("status", response.optInt("status", 0))

                    val respHeaders = response.optJSONObject("headers")
                    val headersResult = JSObject()
                    if (respHeaders != null) {
                        val keys = respHeaders.keys()
                        while (keys.hasNext()) {
                            val key = keys.next()
                            headersResult.put(key, respHeaders.getString(key))
                        }
                    }
                    put("headers", headersResult)
                    put("data", response.optString("data", ""))
                }

                call.resolve(result)
            } catch (e: Exception) {
                call.reject("TLS request failed: ${e.message}", e)
            }
        }
    }

    @PluginMethod
    fun destroySession(call: PluginCall) {
        val sessionId = call.getString("sessionId") ?: "default"
        try {
            Mobile.destroySession(sessionId)
        } catch (_: Exception) {}
        call.resolve()
    }
}
