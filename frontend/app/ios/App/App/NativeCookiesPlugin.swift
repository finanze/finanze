import Foundation
import Capacitor
import WebKit

@objc(NativeCookiesPlugin)
public class NativeCookiesPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "NativeCookiesPlugin"
    public let jsName = "NativeCookies"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "getAllCookies", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "getCookie", returnType: CAPPluginReturnPromise),
    ]

    private func cookieStore() -> WKHTTPCookieStore {
        if let webView = bridge?.webView {
            return webView.configuration.websiteDataStore.httpCookieStore
        }
        return WKWebsiteDataStore.default().httpCookieStore
    }

    private func cookiesFor(url: URL, from cookies: [HTTPCookie]) -> [HTTPCookie] {
        guard let host = url.host?.lowercased(), !host.isEmpty else {
            return []
        }

        return cookies.filter { cookie in
            let domain = cookie.domain.lowercased()
            if domain.hasPrefix(".") {
                return host == String(domain.dropFirst()) || host.hasSuffix(domain)
            }
            return host == domain
        }
    }

    private func buildCookieHeader(_ cookies: [HTTPCookie]) -> String {
        return cookies.map { "\($0.name)=\($0.value)" }.joined(separator: "; ")
    }

    @objc func getAllCookies(_ call: CAPPluginCall) {
        guard let urlString = call.getString("url"),
              let url = URL(string: urlString) else {
            call.reject("Missing url")
            return
        }

        cookieStore().getAllCookies { allCookies in
            let matching = self.cookiesFor(url: url, from: allCookies)

            var cookiesObj: [String: String] = [:]
            for cookie in matching {
                cookiesObj[cookie.name] = cookie.value
            }

            call.resolve([
                "cookies": cookiesObj,
                "raw": self.buildCookieHeader(matching)
            ])
        }
    }

    @objc func getCookie(_ call: CAPPluginCall) {
        guard let urlString = call.getString("url"),
              let url = URL(string: urlString) else {
            call.reject("Missing url")
            return
        }
        guard let name = call.getString("name"), !name.isEmpty else {
            call.reject("Missing name")
            return
        }

        cookieStore().getAllCookies { allCookies in
            let matching = self.cookiesFor(url: url, from: allCookies)
            if let cookie = matching.first(where: { $0.name == name }) {
                call.resolve(["value": cookie.value])
            } else {
                call.resolve([:])
            }
        }
    }
}
