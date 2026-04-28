#if CONNECTIONS
import Foundation
import Capacitor

// Lazy-load Tlsclient.framework via dlopen to avoid Go runtime
// initialization at app launch (which blocks the main thread).
// The framework is a dynamic library built from Go c-archive + clang -shared.
private class TlsclientBridge {
    static let shared = TlsclientBridge()

    // C signatures from //export:
    //   char* TlsRequest(char* requestJSON, char** errOut)
    //   void TlsDestroySession(char* sessionID)
    //   void TlsFreeString(char* s)
    typealias RequestFn = @convention(c) (UnsafePointer<CChar>?, UnsafeMutablePointer<UnsafeMutablePointer<CChar>?>?) -> UnsafeMutablePointer<CChar>?
    typealias DestroyFn = @convention(c) (UnsafePointer<CChar>?) -> Void
    typealias FreeFn = @convention(c) (UnsafeMutablePointer<CChar>?) -> Void

    private var handle: UnsafeMutableRawPointer?
    private var _request: RequestFn?
    private var _destroy: DestroyFn?
    private var _free: FreeFn?

    private let queue = DispatchQueue(label: "tlsclient.init", qos: .userInitiated)
    private var loaded = false
    private var loadError: String?

    func ensureLoaded() -> (Bool, String?) {
        if loaded { return (true, nil) }
        return queue.sync {
            if loaded { return (true, nil) }

            guard let h = dlopen("@rpath/Tlsclient.framework/Tlsclient", RTLD_NOW) else {
                let err = String(cString: dlerror())
                loadError = "dlopen failed: \(err)"
                NSLog("TlsHttpPlugin: %@", loadError!)
                return (false, loadError)
            }
            handle = h

            guard let reqSym = dlsym(h, "TlsRequest"),
                  let destroySym = dlsym(h, "TlsDestroySession"),
                  let freeSym = dlsym(h, "TlsFreeString") else {
                loadError = "dlsym failed for one or more symbols"
                NSLog("TlsHttpPlugin: %@", loadError!)
                dlclose(h)
                handle = nil
                return (false, loadError)
            }

            _request = unsafeBitCast(reqSym, to: RequestFn.self)
            _destroy = unsafeBitCast(destroySym, to: DestroyFn.self)
            _free = unsafeBitCast(freeSym, to: FreeFn.self)

            loaded = true
            NSLog("TlsHttpPlugin: framework loaded successfully")
            return (true, nil)
        }
    }

    func request(_ json: String) -> (String?, Error?) {
        let (ok, err) = ensureLoaded()
        guard ok, let fn = _request, let freeFn = _free else {
            return (nil, NSError(domain: "TlsHttp", code: -1,
                                 userInfo: [NSLocalizedDescriptionKey: "Tlsclient not loaded: \(err ?? "unknown")"]))
        }

        var errPtr: UnsafeMutablePointer<CChar>? = nil
        let resultPtr = fn(json, &errPtr)

        if let errPtr = errPtr {
            let errStr = String(cString: errPtr)
            freeFn(errPtr)
            return (nil, NSError(domain: "TlsHttp", code: -2,
                                 userInfo: [NSLocalizedDescriptionKey: errStr]))
        }

        guard let resultPtr = resultPtr else {
            return (nil, NSError(domain: "TlsHttp", code: -3,
                                 userInfo: [NSLocalizedDescriptionKey: "Nil response"]))
        }

        let result = String(cString: resultPtr)
        freeFn(resultPtr)
        return (result, nil)
    }

    func destroySession(_ sessionId: String) {
        let (ok, _) = ensureLoaded()
        guard ok, let fn = _destroy else { return }
        fn(sessionId)
    }
}

@objc(TlsHttpPlugin)
public class TlsHttpPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "TlsHttpPlugin"
    public let jsName = "TlsHttp"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "request", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "destroySession", returnType: CAPPluginReturnPromise),
    ]

    @objc func request(_ call: CAPPluginCall) {
        guard let url = call.getString("url"),
              let method = call.getString("method") else {
            call.reject("Missing url or method")
            return
        }

        let sessionId = call.getString("sessionId") ?? "default"
        let headers = call.getObject("headers") ?? [:]
        let data = call.getString("data")
        let profile = call.getString("profile") ?? ""
        let forceHttp1 = call.getBool("forceHttp1") ?? false
        let disableHttp3 = call.getBool("disableHttp3") ?? false

        var requestDict: [String: Any] = [
            "sessionId": sessionId,
            "method": method,
            "url": url,
            "headers": headers,
        ]
        if let data = data {
            requestDict["body"] = data
        }
        if !profile.isEmpty {
            requestDict["profile"] = profile
        }
        if forceHttp1 {
            requestDict["forceHttp1"] = true
        }
        if disableHttp3 {
            requestDict["disableHttp3"] = true
        }

        guard let requestData = try? JSONSerialization.data(withJSONObject: requestDict),
              let requestJSON = String(data: requestData, encoding: .utf8) else {
            call.reject("Failed to serialize request")
            return
        }

        DispatchQueue.global(qos: .userInitiated).async {
            let (responseJSON, error) = TlsclientBridge.shared.request(requestJSON)

            if let error = error {
                call.reject("TLS request failed: \(error.localizedDescription)")
                return
            }

            guard let responseJSON = responseJSON,
                  let responseData = responseJSON.data(using: .utf8),
                  let response = try? JSONSerialization.jsonObject(with: responseData) as? [String: Any] else {
                call.reject("Failed to parse TLS client response")
                return
            }

            call.resolve([
                "status": response["status"] as? Int ?? 0,
                "headers": response["headers"] as? [String: Any] ?? [:],
                "data": response["data"] as? String ?? "",
            ])
        }
    }

    @objc func destroySession(_ call: CAPPluginCall) {
        let sessionId = call.getString("sessionId") ?? "default"
        DispatchQueue.global(qos: .userInitiated).async {
            TlsclientBridge.shared.destroySession(sessionId)
            call.resolve()
        }
    }
}
#endif
