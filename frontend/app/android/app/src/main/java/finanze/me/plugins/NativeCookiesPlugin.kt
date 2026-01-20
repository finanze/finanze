package finanze.me.plugins

import android.webkit.CookieManager
import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.CapacitorPlugin

@CapacitorPlugin(name = "NativeCookies")
class NativeCookiesPlugin : Plugin() {

    @PluginMethod
    fun getAllCookies(call: PluginCall) {
        val url = call.getString("url")
        if (url.isNullOrBlank()) {
            call.reject("Missing url")
            return
        }

        try {
            val cookieManager = CookieManager.getInstance()
            val cookieString = cookieManager.getCookie(url)

            val result = JSObject()
            val cookies = JSObject()

            if (!cookieString.isNullOrBlank()) {
                val pairs = cookieString.split(";")
                for (pair in pairs) {
                    val trimmed = pair.trim()
                    val eqIndex = trimmed.indexOf('=')
                    if (eqIndex > 0) {
                        val name = trimmed.substring(0, eqIndex).trim()
                        val value = trimmed.substring(eqIndex + 1).trim()
                        cookies.put(name, value)
                    }
                }
            }

            result.put("cookies", cookies)
            result.put("raw", cookieString ?: "")
            call.resolve(result)
        } catch (e: Exception) {
            call.reject("Failed to get cookies: ${e.message}", e)
        }
    }

    @PluginMethod
    fun getCookie(call: PluginCall) {
        val url = call.getString("url")
        val name = call.getString("name")

        if (url.isNullOrBlank()) {
            call.reject("Missing url")
            return
        }
        if (name.isNullOrBlank()) {
            call.reject("Missing name")
            return
        }

        try {
            val cookieManager = CookieManager.getInstance()
            val cookieString = cookieManager.getCookie(url)

            var value: String? = null
            if (!cookieString.isNullOrBlank()) {
                val pairs = cookieString.split(";")
                for (pair in pairs) {
                    val trimmed = pair.trim()
                    val eqIndex = trimmed.indexOf('=')
                    if (eqIndex > 0) {
                        val cookieName = trimmed.substring(0, eqIndex).trim()
                        if (cookieName == name) {
                            value = trimmed.substring(eqIndex + 1).trim()
                            break
                        }
                    }
                }
            }

            val result = JSObject()
            if (value != null) {
                result.put("value", value)
            }
            call.resolve(result)
        } catch (e: Exception) {
            call.reject("Failed to get cookie: ${e.message}", e)
        }
    }
}
