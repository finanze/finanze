package me.finanze.plugins

import android.annotation.SuppressLint
import android.app.Dialog
import android.graphics.Bitmap
import android.os.Handler
import android.os.Looper
import android.view.ViewGroup
import android.webkit.CookieManager
import android.webkit.JavascriptInterface
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebStorage
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.ImageButton
import android.widget.LinearLayout
import android.widget.TextView
import androidx.appcompat.widget.Toolbar
import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.CapacitorPlugin
import org.json.JSONObject

@CapacitorPlugin(name = "LoginWebView")
class LoginWebViewPlugin : Plugin() {

    private var webView: WebView? = null
    private var dialog: Dialog? = null
    private var interceptUrlPatterns: List<String> = emptyList()
    private val mainHandler = Handler(Looper.getMainLooper())

    // MARK: - Plugin Methods

    @PluginMethod
    fun open(call: PluginCall) {
        val url = call.getString("url")
        if (url.isNullOrBlank()) {
            call.reject("Missing or invalid url")
            return
        }

        val title = call.getString("title") ?: ""
        val clearSession = call.getBoolean("clearSession") ?: false
        val patterns = call.getArray("interceptUrlPatterns")
        interceptUrlPatterns = if (patterns != null) {
            (0 until patterns.length()).mapNotNull { patterns.getString(it) }
        } else {
            emptyList()
        }
        val injectScript = call.getString("injectScript")

        mainHandler.post {
            createAndShowWebView(url, title, clearSession, injectScript, call)
        }
    }

    @PluginMethod
    fun close(call: PluginCall) {
        mainHandler.post {
            dismissWebView()
            call.resolve()
        }
    }

    @PluginMethod
    fun executeScript(call: PluginCall) {
        val code = call.getString("code")
        if (code.isNullOrBlank()) {
            call.reject("Missing code")
            return
        }

        mainHandler.post {
            val wv = webView
            if (wv == null) {
                call.reject("WebView not open")
                return@post
            }

            wv.evaluateJavascript(code) { value ->
                val result = JSObject()
                // Android returns JSON-encoded string, strip outer quotes if it's a string
                val cleaned = if (value != null && value.startsWith("\"") && value.endsWith("\"")) {
                    value.substring(1, value.length - 1)
                        .replace("\\\"", "\"")
                        .replace("\\\\", "\\")
                } else {
                    value ?: ""
                }
                result.put("result", cleaned)
                call.resolve(result)
            }
        }
    }

    @PluginMethod
    fun getCookies(call: PluginCall) {
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
    fun clearData(call: PluginCall) {
        mainHandler.post {
            try {
                CookieManager.getInstance().removeAllCookies(null)
                WebStorage.getInstance().deleteAllData()
                webView?.clearCache(true)
                webView?.clearHistory()
                call.resolve()
            } catch (e: Exception) {
                call.reject("Failed to clear data: ${e.message}", e)
            }
        }
    }

    @PluginMethod
    fun reload(call: PluginCall) {
        mainHandler.post {
            webView?.reload()
            call.resolve()
        }
    }

    // MARK: - WebView Creation

    @SuppressLint("SetJavaScriptEnabled")
    private fun createAndShowWebView(
        url: String,
        title: String,
        clearSession: Boolean,
        injectScript: String?,
        call: PluginCall
    ) {
        val activity = this.activity ?: run {
            call.reject("Activity not available")
            return
        }

        // Create dialog
        val dlg = Dialog(activity, android.R.style.Theme_DeviceDefault_Light_NoActionBar_Fullscreen)
        dialog = dlg

        // Root layout
        val rootLayout = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            layoutParams = ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
        }

        // Toolbar
        val toolbar = Toolbar(activity).apply {
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            )
            setBackgroundColor(0xFFF5F5F5.toInt())
            val titleView = TextView(activity).apply {
                text = title
                textSize = 18f
                setTextColor(0xFF333333.toInt())
            }
            addView(titleView)

            val closeBtn = ImageButton(activity).apply {
                setImageResource(android.R.drawable.ic_menu_close_clear_cancel)
                setBackgroundColor(0x00000000)
                setOnClickListener { dismissWebView() }
            }
            addView(closeBtn)
        }
        rootLayout.addView(toolbar)

        // WebView
        val wv = WebView(activity).apply {
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                0,
                1f
            )
        }

        val settings = wv.settings
        settings.javaScriptEnabled = true
        settings.domStorageEnabled = true
        settings.databaseEnabled = true
        settings.cacheMode = WebSettings.LOAD_DEFAULT
        settings.mixedContentMode = WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE
        settings.userAgentString = settings.userAgentString.replace("; wv", "")

        // Add JS interface for message passing
        wv.addJavascriptInterface(LoginWebViewJSInterface(this), "loginWebViewNative")

        // Build the interception bridge script
        val bridgeScript = buildInterceptionScript()
        val fullInjectScript = if (!injectScript.isNullOrBlank()) {
            "$bridgeScript\n$injectScript"
        } else {
            bridgeScript
        }

        wv.webViewClient = object : WebViewClient() {
            override fun shouldInterceptRequest(
                view: WebView?,
                request: WebResourceRequest?
            ): WebResourceResponse? {
                request?.let { req ->
                    val reqUrl = req.url.toString()
                    if (matchesInterceptPattern(reqUrl)) {
                        val headers = JSObject()
                        for ((key, value) in req.requestHeaders) {
                            headers.put(key, value)
                        }
                        val data = JSObject().apply {
                            put("url", reqUrl)
                            put("method", req.method)
                            put("headers", headers)
                        }
                        notifyListeners("requestIntercepted", data)
                    }
                }
                return super.shouldInterceptRequest(view, request)
            }

            override fun onPageFinished(view: WebView?, url: String?) {
                super.onPageFinished(view, url)
                // Inject the interception script after each page load
                view?.evaluateJavascript(fullInjectScript, null)

                val data = JSObject().apply {
                    put("url", url ?: "")
                }
                notifyListeners("pageLoaded", data)
            }
        }

        wv.webChromeClient = WebChromeClient()

        webView = wv
        rootLayout.addView(wv)

        dlg.setContentView(rootLayout)
        dlg.setOnDismissListener {
            cleanup()
        }

        // Clear session data if needed
        if (clearSession) {
            CookieManager.getInstance().removeAllCookies {
                WebStorage.getInstance().deleteAllData()
                wv.clearCache(true)
                wv.clearHistory()
                wv.loadUrl(url)
            }
        } else {
            wv.loadUrl(url)
        }

        dlg.show()
        call.resolve()
    }

    private fun dismissWebView() {
        dialog?.dismiss()
    }

    private fun cleanup() {
        val data = JSObject()
        notifyListeners("closed", data)

        webView?.removeJavascriptInterface("loginWebViewNative")
        webView?.destroy()
        webView = null
        dialog = null
        interceptUrlPatterns = emptyList()
    }

    // MARK: - Interception Script

    private fun buildInterceptionScript(): String {
        return """
        (function() {
            if (window._lwvInjected) return;
            window._lwvInjected = true;

            var _origOpen = XMLHttpRequest.prototype.open;
            var _origSend = XMLHttpRequest.prototype.send;
            var _origSetHeader = XMLHttpRequest.prototype.setRequestHeader;

            XMLHttpRequest.prototype.open = function(method, url) {
                this._lwv_url = url;
                this._lwv_method = method;
                this._lwv_headers = {};
                return _origOpen.apply(this, arguments);
            };

            XMLHttpRequest.prototype.setRequestHeader = function(name, value) {
                if (this._lwv_headers) {
                    this._lwv_headers[name] = value;
                }
                return _origSetHeader.apply(this, arguments);
            };

            XMLHttpRequest.prototype.send = function() {
                var self = this;
                try {
                    loginWebViewNative.postMessage(JSON.stringify({
                        type: 'request',
                        url: String(self._lwv_url || ''),
                        method: String(self._lwv_method || 'GET'),
                        headers: self._lwv_headers || {}
                    }));
                } catch(e) {}

                self.addEventListener('load', function() {
                    try {
                        loginWebViewNative.postMessage(JSON.stringify({
                            type: 'response',
                            url: String(self._lwv_url || ''),
                            statusCode: self.status,
                            body: self.responseText || ''
                        }));
                    } catch(e) {}
                });

                return _origSend.apply(this, arguments);
            };

            var _origFetch = window.fetch;
            function extractHeaders(src) {
                var h = {};
                if (!src) return h;
                if (src instanceof Headers) {
                    src.forEach(function(v, k) { h[k] = v; });
                } else if (typeof src === 'object' && !(src instanceof Array)) {
                    for (var k in src) {
                        if (src.hasOwnProperty(k)) h[k] = String(src[k]);
                    }
                }
                return h;
            }
            window.fetch = function(input, init) {
                var isRequest = (typeof Request !== 'undefined' && input instanceof Request);
                var url = (typeof input === 'string') ? input : (input && input.url ? input.url : '');
                var method = (init && init.method) || (isRequest ? input.method : '') || 'GET';
                var headers = {};
                if (init && init.headers) {
                    headers = extractHeaders(init.headers);
                } else if (isRequest && input.headers) {
                    headers = extractHeaders(input.headers);
                }
                try {
                    loginWebViewNative.postMessage(JSON.stringify({
                        type: 'request',
                        url: String(url),
                        method: String(method),
                        headers: headers
                    }));
                } catch(e) {}

                return _origFetch.apply(this, arguments).then(function(response) {
                    var cloned = response.clone();
                    cloned.text().then(function(body) {
                        try {
                            loginWebViewNative.postMessage(JSON.stringify({
                                type: 'response',
                                url: String(url),
                                statusCode: response.status,
                                body: body
                            }));
                        } catch(e) {}
                    }).catch(function() {});
                    return response;
                });
            };
        })();
        """.trimIndent()
    }

    // MARK: - URL Pattern Matching

    private fun matchesInterceptPattern(urlString: String): Boolean {
        if (interceptUrlPatterns.isEmpty()) return false
        return interceptUrlPatterns.any { urlString.contains(it) }
    }

    // MARK: - JS→Native message handler

    fun handleJsMessage(message: String) {
        try {
            val json = JSONObject(message)
            val type = json.getString("type")
            val urlString = json.optString("url", "")

            if (!matchesInterceptPattern(urlString)) return

            if (type == "request") {
                val headers = JSObject()
                val jsonHeaders = json.optJSONObject("headers")
                if (jsonHeaders != null) {
                    val keys = jsonHeaders.keys()
                    while (keys.hasNext()) {
                        val key = keys.next()
                        headers.put(key, jsonHeaders.getString(key))
                    }
                }
                val data = JSObject().apply {
                    put("url", urlString)
                    put("method", json.optString("method", "GET"))
                    put("headers", headers)
                }
                notifyListeners("requestIntercepted", data)
            } else if (type == "response") {
                val data = JSObject().apply {
                    put("url", urlString)
                    put("statusCode", json.optInt("statusCode", 0))
                    put("headers", JSObject())
                    put("body", json.optString("body", ""))
                }
                notifyListeners("responseIntercepted", data)
            }
        } catch (_: Exception) {
            // Ignore malformed messages
        }
    }
}

// JS interface for Android WebView
private class LoginWebViewJSInterface(private val plugin: LoginWebViewPlugin) {
    @JavascriptInterface
    fun postMessage(message: String) {
        plugin.handleJsMessage(message)
    }
}
