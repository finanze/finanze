#if CONNECTIONS
import Foundation
import Capacitor
import WebKit

@objc(LoginWebViewPlugin)
public class LoginWebViewPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "LoginWebViewPlugin"
    public let jsName = "LoginWebView"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "open", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "close", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "executeScript", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "getCookies", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "clearData", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "reload", returnType: CAPPluginReturnPromise),
    ]

    private var loginWebView: WKWebView?
    private var navController: UINavigationController?
    private var interceptUrlPatterns: [String] = []
    private var dataStore: WKWebsiteDataStore?

    // MARK: - Plugin Methods

    @objc func open(_ call: CAPPluginCall) {
        guard let urlString = call.getString("url"),
              let url = URL(string: urlString) else {
            call.reject("Missing or invalid url")
            return
        }

        let title = call.getString("title") ?? ""
        let clearSession = call.getBool("clearSession") ?? false
        let patterns = call.getArray("interceptUrlPatterns", String.self) ?? []
        let injectScript = call.getString("injectScript")

        self.interceptUrlPatterns = patterns

        DispatchQueue.main.async {
            self.createAndPresentWebView(
                url: url,
                title: title,
                clearSession: clearSession,
                injectScript: injectScript,
                call: call
            )
        }
    }

    @objc func close(_ call: CAPPluginCall) {
        DispatchQueue.main.async {
            self.dismissWebView()
            call.resolve()
        }
    }

    @objc func executeScript(_ call: CAPPluginCall) {
        guard let code = call.getString("code") else {
            call.reject("Missing code")
            return
        }

        DispatchQueue.main.async {
            guard let webView = self.loginWebView else {
                call.reject("WebView not open")
                return
            }

            webView.evaluateJavaScript(code) { result, error in
                if let error = error {
                    call.reject("Script error: \(error.localizedDescription)")
                    return
                }
                let resultString: String
                if let result = result {
                    if let str = result as? String {
                        resultString = str
                    } else {
                        resultString = String(describing: result)
                    }
                } else {
                    resultString = ""
                }
                call.resolve(["result": resultString])
            }
        }
    }

    @objc func getCookies(_ call: CAPPluginCall) {
        guard let urlString = call.getString("url"),
              let url = URL(string: urlString) else {
            call.reject("Missing url")
            return
        }

        DispatchQueue.main.async {
            let cookieStore = self.dataStore?.httpCookieStore ?? WKWebsiteDataStore.default().httpCookieStore

            cookieStore.getAllCookies { allCookies in
                let host = url.host?.lowercased() ?? ""
                let matching = allCookies.filter { cookie in
                    let domain = cookie.domain.lowercased()
                    if domain.hasPrefix(".") {
                        return host == String(domain.dropFirst()) || host.hasSuffix(domain)
                    }
                    return host == domain
                }

                var cookiesObj: [String: String] = [:]
                for cookie in matching {
                    cookiesObj[cookie.name] = cookie.value
                }

                let raw = matching.map { "\($0.name)=\($0.value)" }.joined(separator: "; ")
                call.resolve([
                    "cookies": cookiesObj,
                    "raw": raw
                ])
            }
        }
    }

    @objc func clearData(_ call: CAPPluginCall) {
        guard let dataStore = self.dataStore else {
            call.resolve()
            return
        }

        let types = WKWebsiteDataStore.allWebsiteDataTypes()
        dataStore.removeData(ofTypes: types, modifiedSince: .distantPast) {
            call.resolve()
        }
    }

    @objc func reload(_ call: CAPPluginCall) {
        DispatchQueue.main.async {
            self.loginWebView?.reload()
            call.resolve()
        }
    }

    // MARK: - WebView Creation

    private func createAndPresentWebView(
        url: URL,
        title: String,
        clearSession: Bool,
        injectScript: String?,
        call: CAPPluginCall
    ) {
        let config = WKWebViewConfiguration()

        if clearSession {
            dataStore = WKWebsiteDataStore.nonPersistent()
        } else {
            dataStore = WKWebsiteDataStore.default()
        }
        config.websiteDataStore = dataStore!

        // Register custom scheme handler for request interception
        let schemeHandler = LoginSchemeHandler(plugin: self)
        config.setURLSchemeHandler(schemeHandler, forURLScheme: "loginwebview-https")
        config.setURLSchemeHandler(schemeHandler, forURLScheme: "loginwebview-http")

        let userContentController = WKUserContentController()

        // Inject the interception bridge script at document start
        let bridgeScript = self.buildInterceptionScript()
        let script = WKUserScript(source: bridgeScript, injectionTime: .atDocumentStart, forMainFrameOnly: false)
        userContentController.addUserScript(script)

        // Inject custom user script if provided
        if let injectScript = injectScript, !injectScript.isEmpty {
            let customScript = WKUserScript(source: injectScript, injectionTime: .atDocumentStart, forMainFrameOnly: false)
            userContentController.addUserScript(customScript)
        }

        // Register message handler for JS→native communication
        userContentController.add(LeakAvoider(delegate: self), name: "loginWebView")

        config.userContentController = userContentController
        config.preferences.javaScriptCanOpenWindowsAutomatically = true

        let webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = self
        webView.allowsBackForwardNavigationGestures = true
        self.loginWebView = webView

        // Create view controller
        let vc = UIViewController()
        vc.view = webView

        // Navigation bar with title and close button
        let navController = UINavigationController(rootViewController: vc)
        vc.navigationItem.title = title
        vc.navigationItem.rightBarButtonItem = UIBarButtonItem(
            barButtonSystemItem: .done,
            target: self,
            action: #selector(closeTapped)
        )
        navController.modalPresentationStyle = .fullScreen
        self.navController = navController

        // Clear session data if requested, then load
        if clearSession {
            let types = WKWebsiteDataStore.allWebsiteDataTypes()
            dataStore!.removeData(ofTypes: types, modifiedSince: .distantPast) { [weak self] in
                self?.loginWebView?.load(URLRequest(url: url))
            }
        } else {
            webView.load(URLRequest(url: url))
        }

        // Present modally
        guard let presentingVC = self.bridge?.viewController else {
            call.reject("Cannot present WebView")
            return
        }

        presentingVC.present(navController, animated: true) {
            call.resolve()
        }
    }

    @objc private func closeTapped() {
        dismissWebView()
    }

    private func dismissWebView() {
        navController?.dismiss(animated: true) { [weak self] in
            self?.cleanup()
        }
        if navController?.presentingViewController == nil {
            cleanup()
        }
    }

    private func cleanup() {
        notifyListeners("closed", data: [:])
        loginWebView?.configuration.userContentController.removeAllUserScripts()
        loginWebView?.configuration.userContentController.removeScriptMessageHandler(forName: "loginWebView")
        loginWebView?.navigationDelegate = nil
        loginWebView = nil
        navController = nil
        interceptUrlPatterns = []
    }

    // MARK: - Interception Script

    private func buildInterceptionScript() -> String {
        return """
        (function() {
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
                    window.webkit.messageHandlers.loginWebView.postMessage(JSON.stringify({
                        type: 'request',
                        url: String(self._lwv_url || ''),
                        method: String(self._lwv_method || 'GET'),
                        headers: self._lwv_headers || {}
                    }));
                } catch(e) {}

                var origOnReady = self.onreadystatechange;
                self.onreadystatechange = function() {
                    if (self.readyState === 4) {
                        try {
                            window.webkit.messageHandlers.loginWebView.postMessage(JSON.stringify({
                                type: 'response',
                                url: String(self._lwv_url || ''),
                                statusCode: self.status,
                                body: self.responseText || ''
                            }));
                        } catch(e) {}
                    }
                    if (origOnReady) origOnReady.apply(self, arguments);
                };

                self.addEventListener('load', function() {
                    try {
                        window.webkit.messageHandlers.loginWebView.postMessage(JSON.stringify({
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
                    window.webkit.messageHandlers.loginWebView.postMessage(JSON.stringify({
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
                            window.webkit.messageHandlers.loginWebView.postMessage(JSON.stringify({
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
        """
    }

    // MARK: - URL Pattern Matching

    func matchesInterceptPattern(_ urlString: String) -> Bool {
        if interceptUrlPatterns.isEmpty { return false }
        for pattern in interceptUrlPatterns {
            if urlString.contains(pattern) {
                return true
            }
        }
        return false
    }
}

// MARK: - WKNavigationDelegate

extension LoginWebViewPlugin: WKNavigationDelegate {
    public func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        let url = webView.url?.absoluteString ?? ""
        notifyListeners("pageLoaded", data: ["url": url])
    }

    public func webView(
        _ webView: WKWebView,
        decidePolicyFor navigationAction: WKNavigationAction,
        decisionHandler: @escaping (WKNavigationActionPolicy) -> Void
    ) {
        if let url = navigationAction.request.url?.absoluteString, matchesInterceptPattern(url) {
            var headers: [String: String] = [:]
            if let allHeaders = navigationAction.request.allHTTPHeaderFields {
                headers = allHeaders
            }
            notifyListeners("requestIntercepted", data: [
                "url": url,
                "method": navigationAction.request.httpMethod ?? "GET",
                "headers": headers
            ])
        }
        decisionHandler(.allow)
    }

    public func webView(
        _ webView: WKWebView,
        decidePolicyFor navigationResponse: WKNavigationResponse,
        decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void
    ) {
        if let httpResponse = navigationResponse.response as? HTTPURLResponse,
           let url = httpResponse.url?.absoluteString,
           matchesInterceptPattern(url) {
            var headers: [String: String] = [:]
            for (key, value) in httpResponse.allHeaderFields {
                headers[String(describing: key)] = String(describing: value)
            }
            notifyListeners("responseIntercepted", data: [
                "url": url,
                "statusCode": httpResponse.statusCode,
                "headers": headers
            ])
        }
        decisionHandler(.allow)
    }
}

// MARK: - WKScriptMessageHandler (via LeakAvoider)

extension LoginWebViewPlugin: WKScriptMessageHandler {
    public func userContentController(
        _ userContentController: WKUserContentController,
        didReceive message: WKScriptMessage
    ) {
        guard message.name == "loginWebView",
              let body = message.body as? String,
              let data = body.data(using: .utf8),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let type = json["type"] as? String else {
            return
        }

        let urlString = json["url"] as? String ?? ""

        guard matchesInterceptPattern(urlString) else { return }

        if type == "request" {
            let method = json["method"] as? String ?? "GET"
            let headers = json["headers"] as? [String: String] ?? [:]
            notifyListeners("requestIntercepted", data: [
                "url": urlString,
                "method": method,
                "headers": headers
            ])
        } else if type == "response" {
            let statusCode = json["statusCode"] as? Int ?? 0
            let responseBody = json["body"] as? String ?? ""
            notifyListeners("responseIntercepted", data: [
                "url": urlString,
                "statusCode": statusCode,
                "headers": [:] as [String: String],
                "body": responseBody
            ])
        }
    }
}

// MARK: - LeakAvoider (prevents retain cycle between WKUserContentController and plugin)

private class LeakAvoider: NSObject, WKScriptMessageHandler {
    weak var delegate: WKScriptMessageHandler?

    init(delegate: WKScriptMessageHandler) {
        self.delegate = delegate
        super.init()
    }

    func userContentController(
        _ userContentController: WKUserContentController,
        didReceive message: WKScriptMessage
    ) {
        delegate?.userContentController(userContentController, didReceive: message)
    }
}

// MARK: - LoginSchemeHandler (for native request observation)

private class LoginSchemeHandler: NSObject, WKURLSchemeHandler {
    weak var plugin: LoginWebViewPlugin?

    init(plugin: LoginWebViewPlugin) {
        self.plugin = plugin
        super.init()
    }

    func webView(_ webView: WKWebView, start urlSchemeTask: WKURLSchemeTask) {
        // This scheme handler is registered but not actively used for proxying.
        // Request interception is handled via JS injection + WKNavigationDelegate.
        urlSchemeTask.didFailWithError(NSError(domain: "LoginWebView", code: -1, userInfo: nil))
    }

    func webView(_ webView: WKWebView, stop urlSchemeTask: WKURLSchemeTask) {
        // No-op
    }
}
#endif
