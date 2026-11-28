import Capacitor
import Foundation
import Network

@objc(LoopbackCallbackPlugin)
public class LoopbackCallbackPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "LoopbackCallbackPlugin"
    public let jsName = "LoopbackCallback"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "start", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "stop", returnType: CAPPluginReturnPromise),
    ]

    private static let host = "127.0.0.1"
    private static let defaultPath = "/auth/callback"
    private static let defaultTimeoutMs = 10.0 * 60 * 1000
    private static let maxRequestBytes = 16 * 1024
    private static let successPage = """
        <!DOCTYPE html><html><head><meta charset="utf-8">\
        <meta name="viewport" content="width=device-width, initial-scale=1">\
        <title>Finanze</title></head>\
        <body style="font-family:-apple-system,sans-serif;text-align:center;padding:3rem 1.5rem">\
        <p>Sign-in complete. You can return to Finanze.</p></body></html>
        """
    private static let notFoundPage =
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\"><title>Finanze</title></head><body></body></html>"

    private let queue = DispatchQueue(label: "me.finanze.loopback-callback")
    private var listener: NWListener?
    private var timeoutWork: DispatchWorkItem?

    @objc func start(_ call: CAPPluginCall) {
        let path = call.getString("path") ?? Self.defaultPath
        guard path.hasPrefix("/") else {
            call.reject("Invalid callback path")
            return
        }
        let timeout = (call.getDouble("timeoutMs") ?? Self.defaultTimeoutMs) / 1000

        queue.async {
            self.stopListener()

            let parameters = NWParameters.tcp
            parameters.requiredLocalEndpoint = .hostPort(host: NWEndpoint.Host(Self.host), port: .any)
            parameters.allowLocalEndpointReuse = true

            let listener: NWListener
            do {
                listener = try NWListener(using: parameters)
            } catch {
                call.reject("Could not start the callback listener", nil, error)
                return
            }

            var settled = false
            listener.stateUpdateHandler = { [weak self, weak listener] state in
                guard let self, let listener else { return }
                switch state {
                case .ready:
                    guard !settled, let port = listener.port?.rawValue else { return }
                    settled = true
                    call.resolve(["port": Int(port), "url": "http://\(Self.host):\(port)\(path)"])
                case .failed(let error):
                    if !settled {
                        settled = true
                        call.reject("Could not start the callback listener", nil, error)
                    }
                    if self.listener === listener {
                        self.stopListener()
                    }
                default:
                    break
                }
            }
            listener.newConnectionHandler = { [weak self, weak listener] connection in
                guard let self, let port = listener?.port?.rawValue else {
                    connection.cancel()
                    return
                }
                connection.start(queue: self.queue)
                self.receive(connection, buffer: Data(), path: path, port: port)
            }

            let work = DispatchWorkItem { [weak self, weak listener] in
                guard let self, let listener, self.listener === listener else { return }
                self.stopListener()
                self.notifyListeners("timeout", data: [:])
            }
            self.listener = listener
            self.timeoutWork = work
            listener.start(queue: self.queue)
            self.queue.asyncAfter(deadline: .now() + timeout, execute: work)
        }
    }

    @objc func stop(_ call: CAPPluginCall) {
        queue.async {
            self.stopListener()
            call.resolve()
        }
    }

    deinit {
        listener?.cancel()
    }

    private func stopListener() {
        timeoutWork?.cancel()
        timeoutWork = nil
        listener?.cancel()
        listener = nil
    }

    private func receive(_ connection: NWConnection, buffer: Data, path: String, port: UInt16) {
        connection.receive(minimumIncompleteLength: 1, maximumLength: 4096) { [weak self] data, _, isComplete, error in
            guard let self else {
                connection.cancel()
                return
            }
            var received = buffer
            if let data {
                received.append(data)
            }
            let headersEnded = received.range(of: Data("\r\n\r\n".utf8)) != nil
            if !headersEnded && error == nil && !isComplete && received.count < Self.maxRequestBytes {
                self.receive(connection, buffer: received, path: path, port: port)
                return
            }

            if let target = Self.requestTarget(received),
               target.split(separator: "?", maxSplits: 1, omittingEmptySubsequences: false).first.map(String.init) == path {
                self.respond(connection, status: "200 OK", body: Self.successPage)
                self.notifyListeners("callback", data: ["url": "http://\(Self.host):\(port)\(target)"])
            } else {
                self.respond(connection, status: "404 Not Found", body: Self.notFoundPage)
            }
        }
    }

    private static func requestTarget(_ data: Data) -> String? {
        guard let text = String(data: data, encoding: .isoLatin1),
              let requestLine = text.components(separatedBy: "\r\n").first else {
            return nil
        }
        let parts = requestLine.split(separator: " ")
        guard parts.count >= 3, parts[0] == "GET", parts[1].hasPrefix("/") else {
            return nil
        }
        return String(parts[1])
    }

    private func respond(_ connection: NWConnection, status: String, body: String) {
        let content = Data(body.utf8)
        let head = "HTTP/1.1 \(status)\r\n" +
            "Content-Type: text/html; charset=utf-8\r\n" +
            "Content-Length: \(content.count)\r\n" +
            "Cache-Control: no-store\r\n" +
            "Connection: close\r\n\r\n"
        var response = Data(head.utf8)
        response.append(content)
        connection.send(content: response, completion: .contentProcessed { _ in
            connection.cancel()
        })
    }
}
