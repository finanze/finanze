import Foundation
import Capacitor

@objc(FileTransferPlugin)
public class FileTransferPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "FileTransferPlugin"
    public let jsName = "FileTransfer"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "upload", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "download", returnType: CAPPluginReturnPromise),
    ]
    
    private let defaultTimeout: TimeInterval = 60
    
    private func getBackupDir() -> URL {
        let documentsDir = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first!
        let backupDir = documentsDir.appendingPathComponent("backup_staging")
        try? FileManager.default.createDirectory(at: backupDir, withIntermediateDirectories: true)
        return backupDir
    }
    
    @objc func upload(_ call: CAPPluginCall) {
        guard let urlString = call.getString("url"),
              let url = URL(string: urlString),
              let fileName = call.getString("fileName") else {
            call.reject("Missing required parameters: url, fileName")
            return
        }
        
        let method = call.getString("method") ?? "PUT"
        let headers = call.getObject("headers") ?? [:]
        let timeout = TimeInterval(call.getInt("timeout") ?? Int(defaultTimeout * 1000)) / 1000
        
        DispatchQueue.global(qos: .userInitiated).async {
            let backupDir = self.getBackupDir()
            let file = backupDir.appendingPathComponent(fileName)
            
            guard FileManager.default.fileExists(atPath: file.path) else {
                call.reject("File does not exist: \(fileName)")
                return
            }
            
            guard let fileData = try? Data(contentsOf: file) else {
                call.reject("Failed to read file: \(fileName)")
                return
            }
            
            var request = URLRequest(url: url)
            request.httpMethod = method
            request.timeoutInterval = timeout
            
            for (key, value) in headers {
                if let stringValue = value as? String, key.lowercased() != "content-length" {
                    request.setValue(stringValue, forHTTPHeaderField: key)
                }
            }
            request.setValue(String(fileData.count), forHTTPHeaderField: "Content-Length")
            request.httpBody = fileData
            
            let task = URLSession.shared.dataTask(with: request) { _, response, error in
                if let error = error {
                    call.reject("Upload failed: \(error.localizedDescription)")
                    return
                }
                
                guard let httpResponse = response as? HTTPURLResponse else {
                    call.reject("Invalid response")
                    return
                }
                
                let statusCode = httpResponse.statusCode
                
                if statusCode == 429 {
                    call.reject("TOO_MANY_REQUESTS")
                    return
                }
                
                if statusCode >= 200 && statusCode < 300 {
                    try? FileManager.default.removeItem(at: file)
                    call.resolve([
                        "status": statusCode,
                        "success": true
                    ])
                } else {
                    call.reject("Upload failed with status \(statusCode)")
                }
            }
            
            task.resume()
        }
    }
    
    @objc func download(_ call: CAPPluginCall) {
        guard let urlString = call.getString("url"),
              let url = URL(string: urlString),
              let fileName = call.getString("fileName") else {
            call.reject("Missing required parameters: url, fileName")
            return
        }
        
        let timeout = TimeInterval(call.getInt("timeout") ?? Int(defaultTimeout * 1000)) / 1000
        
        DispatchQueue.global(qos: .userInitiated).async {
            var request = URLRequest(url: url)
            request.httpMethod = "GET"
            request.timeoutInterval = timeout
            
            let task = URLSession.shared.dataTask(with: request) { data, response, error in
                if let error = error {
                    call.reject("Download failed: \(error.localizedDescription)")
                    return
                }
                
                guard let httpResponse = response as? HTTPURLResponse else {
                    call.reject("Invalid response")
                    return
                }
                
                let statusCode = httpResponse.statusCode
                
                if statusCode == 429 {
                    call.reject("TOO_MANY_REQUESTS")
                    return
                }
                
                if statusCode < 200 || statusCode >= 300 {
                    call.reject("Download failed with status \(statusCode)")
                    return
                }
                
                guard let data = data else {
                    call.reject("No data received")
                    return
                }
                
                let backupDir = self.getBackupDir()
                let file = backupDir.appendingPathComponent(fileName)
                
                do {
                    try data.write(to: file)
                    call.resolve([
                        "status": statusCode,
                        "size": data.count,
                        "success": true
                    ])
                } catch {
                    call.reject("Failed to write file: \(error.localizedDescription)")
                }
            }
            
            task.resume()
        }
    }
}
