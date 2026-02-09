import Foundation
import Capacitor
import CommonCrypto
import zlib

protocol BackupProcessorVersion {
    func compile(rawData: Data, password: String) throws -> Data
    func decompile(encryptedData: Data, password: String) throws -> Data
}

class BackupProcessorV1: BackupProcessorVersion {
    private let salt = "finanze-backup-salt"
    private let pbkdf2Iterations: UInt32 = 100000
    private let keyLength = 32
    private let fernetVersion: UInt8 = 0x80
    private let keyCache = NSCache<NSString, NSData>()
    
    func compile(rawData: Data, password: String) throws -> Data {
        // Use zlib-wrapped deflate (Android-compatible) for cross-platform backups.
        let compressed = try compressZlib(data: rawData)
        let key = try deriveKey(password: password)
        return try fernetEncrypt(data: compressed, key: key)
    }
    
    func decompile(encryptedData: Data, password: String) throws -> Data {
        let key = try deriveKey(password: password)
        let decrypted = try fernetDecrypt(token: encryptedData, key: key)
        return try decompressZlib(data: decrypted)
    }
    
    private func deriveKey(password: String) throws -> Data {
        if let cached = keyCache.object(forKey: password as NSString) {
            return Data(referencing: cached)
        }
        guard let passwordData = password.data(using: .utf8),
              let saltData = salt.data(using: .utf8) else {
            throw NSError(domain: "BackupProcessor", code: -1, userInfo: [NSLocalizedDescriptionKey: "Invalid password or salt"])
        }
        
        var derivedKey = Data(count: keyLength)
        let result = derivedKey.withUnsafeMutableBytes { derivedKeyBytes in
            passwordData.withUnsafeBytes { passwordBytes in
                saltData.withUnsafeBytes { saltBytes in
                    CCKeyDerivationPBKDF(
                        CCPBKDFAlgorithm(kCCPBKDF2),
                        passwordBytes.baseAddress?.assumingMemoryBound(to: Int8.self),
                        passwordData.count,
                        saltBytes.baseAddress?.assumingMemoryBound(to: UInt8.self),
                        saltData.count,
                        CCPseudoRandomAlgorithm(kCCPRFHmacAlgSHA256),
                        pbkdf2Iterations,
                        derivedKeyBytes.baseAddress?.assumingMemoryBound(to: UInt8.self),
                        keyLength
                    )
                }
            }
        }
        
        guard result == kCCSuccess else {
            throw NSError(domain: "BackupProcessor", code: -1, userInfo: [NSLocalizedDescriptionKey: "Key derivation failed"])
        }
        
        keyCache.setObject(derivedKey as NSData, forKey: password as NSString)
        return derivedKey
    }
    
    private func compressZlib(data: Data) throws -> Data {
        var stream = z_stream()
        var status: Int32

        // windowBits = 15 => zlib header/trailer (matches Android's Deflater defaults)
        status = deflateInit2_(
            &stream,
            Z_BEST_COMPRESSION,
            Z_DEFLATED,
            15,
            8,
            Z_DEFAULT_STRATEGY,
            ZLIB_VERSION,
            Int32(MemoryLayout<z_stream>.size)
        )
        guard status == Z_OK else {
            throw NSError(domain: "BackupProcessor", code: Int(status), userInfo: [NSLocalizedDescriptionKey: "Compression init failed"])
        }

        var compressed = Data(count: max(1024, data.count / 2))

        try data.withUnsafeBytes { inputBytes in
            stream.next_in = UnsafeMutablePointer<Bytef>(mutating: inputBytes.baseAddress?.assumingMemoryBound(to: Bytef.self))
            stream.avail_in = uInt(data.count)

            while true {
                if Int(stream.total_out) >= compressed.count {
                    compressed.count *= 2
                }

                let outputCount = compressed.count
                compressed.withUnsafeMutableBytes { outputBytes in
                    stream.next_out = outputBytes.baseAddress?.assumingMemoryBound(to: Bytef.self).advanced(by: Int(stream.total_out))
                    stream.avail_out = uInt(outputCount) - uInt(stream.total_out)
                    status = deflate(&stream, Z_FINISH)
                }

                if status == Z_STREAM_END {
                    break
                }
                if status == Z_OK || status == Z_BUF_ERROR {
                    continue
                }

                deflateEnd(&stream)
                throw NSError(domain: "BackupProcessor", code: Int(status), userInfo: [NSLocalizedDescriptionKey: "Compression failed"])
            }
        }

        deflateEnd(&stream)
        compressed.count = Int(stream.total_out)
        return compressed
    }

    private func decompressZlib(data: Data) throws -> Data {
        // zlib wrapper (matches Android's Deflater defaults)
        return try decompressZlib(data: data, windowBits: 15)
    }

    private func decompressZlib(data: Data, windowBits: Int32) throws -> Data {
        var stream = z_stream()
        var status: Int32

        status = inflateInit2_(&stream, windowBits, ZLIB_VERSION, Int32(MemoryLayout<z_stream>.size))
        guard status == Z_OK else {
            throw NSError(domain: "BackupProcessor", code: Int(status), userInfo: [NSLocalizedDescriptionKey: "Decompression init failed"])
        }

        var decompressed = Data(count: max(1024, data.count * 4))

        let result: Data = try data.withUnsafeBytes { inputBytes in
            stream.next_in = UnsafeMutablePointer<Bytef>(mutating: inputBytes.baseAddress?.assumingMemoryBound(to: Bytef.self))
            stream.avail_in = uInt(data.count)

            while true {
                if Int(stream.total_out) >= decompressed.count {
                    decompressed.count *= 2
                }

                let outputCount = decompressed.count
                decompressed.withUnsafeMutableBytes { outputBytes in
                    stream.next_out = outputBytes.baseAddress?.assumingMemoryBound(to: Bytef.self).advanced(by: Int(stream.total_out))
                    stream.avail_out = uInt(outputCount) - uInt(stream.total_out)
                    status = inflate(&stream, Z_NO_FLUSH)
                }

                if status == Z_STREAM_END {
                    break
                }
                if status == Z_OK {
                    continue
                }
                if status == Z_BUF_ERROR {
                    // Need more output space.
                    if stream.avail_out == 0 {
                        decompressed.count *= 2
                        continue
                    }
                }

                inflateEnd(&stream)
                throw NSError(domain: "BackupProcessor", code: Int(status), userInfo: [NSLocalizedDescriptionKey: "Decompression failed"])
            }

            return decompressed
        }

        let totalOut = Int(stream.total_out)
        inflateEnd(&stream)
        var final = result
        final.count = totalOut
        return final
    }
    
    private func fernetEncrypt(data: Data, key: Data) throws -> Data {
        let signingKey = key.prefix(16)
        let encryptionKey = key.suffix(16)
        
        var iv = Data(count: 16)
        let result = iv.withUnsafeMutableBytes { ivBytes in
            SecRandomCopyBytes(kSecRandomDefault, 16, ivBytes.baseAddress!)
        }
        guard result == errSecSuccess else {
            throw NSError(domain: "BackupProcessor", code: -1, userInfo: [NSLocalizedDescriptionKey: "IV generation failed"])
        }
        
        let timestamp = UInt64(Date().timeIntervalSince1970)
        var timestampBytes = Data(count: 8)
        timestampBytes.withUnsafeMutableBytes { ptr in
            ptr.storeBytes(of: timestamp.bigEndian, as: UInt64.self)
        }
        
        let ciphertext = try aesEncrypt(data: data, key: encryptionKey, iv: iv)
        
        var basicParts = Data()
        basicParts.append(fernetVersion)
        basicParts.append(timestampBytes)
        basicParts.append(iv)
        basicParts.append(ciphertext)
        
        let hmac = try computeHMAC(data: basicParts, key: signingKey)
        
        var result_ = basicParts
        result_.append(hmac)
        return result_
    }
    
    private func fernetDecrypt(token: Data, key: Data) throws -> Data {
        guard token.count >= 57 else {
            throw NSError(domain: "BackupProcessor", code: -1, userInfo: [NSLocalizedDescriptionKey: "Invalid token length"])
        }
        
        let signingKey = key.prefix(16)
        let encryptionKey = key.suffix(16)
        
        guard token[0] == fernetVersion else {
            throw NSError(domain: "BackupProcessor", code: -1, userInfo: [NSLocalizedDescriptionKey: "Invalid Fernet version"])
        }
        
        let basicPartsEnd = token.count - 32
        let basicParts = token.prefix(basicPartsEnd)
        let providedHmac = token.suffix(32)
        
        let expectedHmac = try computeHMAC(data: Data(basicParts), key: signingKey)
        
        guard expectedHmac == Data(providedHmac) else {
            throw NSError(domain: "BackupProcessor", code: -1, userInfo: [NSLocalizedDescriptionKey: "INVALID_CREDENTIALS"])
        }
        
        let iv = token[9..<25]
        let ciphertext = token[25..<basicPartsEnd]
        
        return try aesDecrypt(data: Data(ciphertext), key: encryptionKey, iv: Data(iv))
    }
    
    private func aesEncrypt(data: Data, key: Data, iv: Data) throws -> Data {
        let bufferSize = data.count + kCCBlockSizeAES128
        var buffer = Data(count: bufferSize)
        var numBytesEncrypted: size_t = 0
        
        let status = buffer.withUnsafeMutableBytes { bufferBytes in
            data.withUnsafeBytes { dataBytes in
                key.withUnsafeBytes { keyBytes in
                    iv.withUnsafeBytes { ivBytes in
                        CCCrypt(
                            CCOperation(kCCEncrypt),
                            CCAlgorithm(kCCAlgorithmAES),
                            CCOptions(kCCOptionPKCS7Padding),
                            keyBytes.baseAddress, key.count,
                            ivBytes.baseAddress,
                            dataBytes.baseAddress, data.count,
                            bufferBytes.baseAddress, bufferSize,
                            &numBytesEncrypted
                        )
                    }
                }
            }
        }
        
        guard status == kCCSuccess else {
            throw NSError(domain: "BackupProcessor", code: Int(status), userInfo: [NSLocalizedDescriptionKey: "Encryption failed"])
        }
        
        buffer.count = numBytesEncrypted
        return buffer
    }
    
    private func aesDecrypt(data: Data, key: Data, iv: Data) throws -> Data {
        let bufferSize = data.count + kCCBlockSizeAES128
        var buffer = Data(count: bufferSize)
        var numBytesDecrypted: size_t = 0
        
        let status = buffer.withUnsafeMutableBytes { bufferBytes in
            data.withUnsafeBytes { dataBytes in
                key.withUnsafeBytes { keyBytes in
                    iv.withUnsafeBytes { ivBytes in
                        CCCrypt(
                            CCOperation(kCCDecrypt),
                            CCAlgorithm(kCCAlgorithmAES),
                            CCOptions(kCCOptionPKCS7Padding),
                            keyBytes.baseAddress, key.count,
                            ivBytes.baseAddress,
                            dataBytes.baseAddress, data.count,
                            bufferBytes.baseAddress, bufferSize,
                            &numBytesDecrypted
                        )
                    }
                }
            }
        }
        
        guard status == kCCSuccess else {
            throw NSError(domain: "BackupProcessor", code: Int(status), userInfo: [NSLocalizedDescriptionKey: "Decryption failed"])
        }
        
        buffer.count = numBytesDecrypted
        return buffer
    }
    
    private func computeHMAC(data: Data, key: Data) throws -> Data {
        var hmac = Data(count: Int(CC_SHA256_DIGEST_LENGTH))
        
        hmac.withUnsafeMutableBytes { hmacBytes in
            data.withUnsafeBytes { dataBytes in
                key.withUnsafeBytes { keyBytes in
                    CCHmac(
                        CCHmacAlgorithm(kCCHmacAlgSHA256),
                        keyBytes.baseAddress, key.count,
                        dataBytes.baseAddress, data.count,
                        hmacBytes.baseAddress
                    )
                }
            }
        }
        
        return hmac
    }
}

@objc(BackupProcessorPlugin)
public class BackupProcessorPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "BackupProcessorPlugin"
    public let jsName = "BackupProcessor"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "compile", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "decompile", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "writeFile", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "readFile", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "deleteFile", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "getFilePath", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "cleanup", returnType: CAPPluginReturnPromise),
    ]
    
    private let processors: [Int: BackupProcessorVersion] = [
        1: BackupProcessorV1()
    ]
    
    private func getBackupDir() -> URL {
        let documentsDir = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first!
        let backupDir = documentsDir.appendingPathComponent("backup_staging")
        try? FileManager.default.createDirectory(at: backupDir, withIntermediateDirectories: true)
        return backupDir
    }
    
    private func getProcessor(version: Int) throws -> BackupProcessorVersion {
        guard let processor = processors[version] else {
            throw NSError(domain: "BackupProcessor", code: -1, userInfo: [NSLocalizedDescriptionKey: "Unsupported backup protocol version: \(version)"])
        }
        return processor
    }
    
    @objc func compile(_ call: CAPPluginCall) {
        guard let inputFileName = call.getString("inputFile"),
              let outputFileName = call.getString("outputFile"),
              let password = call.getString("password") else {
            call.reject("Missing required parameters: inputFile, outputFile, password")
            return
        }
        
        let version = call.getInt("version") ?? 1
        
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            guard let self = self else { return }
            
            do {
                let processor = try self.getProcessor(version: version)
                let backupDir = self.getBackupDir()
                let inputFile = backupDir.appendingPathComponent(inputFileName)
                let outputFile = backupDir.appendingPathComponent(outputFileName)
                
                guard FileManager.default.fileExists(atPath: inputFile.path) else {
                    call.reject("Input file does not exist: \(inputFileName)")
                    return
                }
                
                let rawData = try Data(contentsOf: inputFile)
                let encrypted = try processor.compile(rawData: rawData, password: password)
                try encrypted.write(to: outputFile)
                try? FileManager.default.removeItem(at: inputFile)
                
                call.resolve([
                    "size": encrypted.count,
                    "success": true
                ])
            } catch {
                call.reject("Compile failed: \(error.localizedDescription)")
            }
        }
    }
    
    @objc func decompile(_ call: CAPPluginCall) {
        guard let inputFileName = call.getString("inputFile"),
              let outputFileName = call.getString("outputFile"),
              let password = call.getString("password") else {
            call.reject("Missing required parameters: inputFile, outputFile, password")
            return
        }
        
        let version = call.getInt("version") ?? 1
        
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            guard let self = self else { return }
            
            do {
                let processor = try self.getProcessor(version: version)
                let backupDir = self.getBackupDir()
                let inputFile = backupDir.appendingPathComponent(inputFileName)
                let outputFile = backupDir.appendingPathComponent(outputFileName)
                
                guard FileManager.default.fileExists(atPath: inputFile.path) else {
                    call.reject("Input file does not exist: \(inputFileName)")
                    return
                }
                
                let encryptedData = try Data(contentsOf: inputFile)
                let decompressed = try processor.decompile(encryptedData: encryptedData, password: password)
                try decompressed.write(to: outputFile)
                try? FileManager.default.removeItem(at: inputFile)
                
                call.resolve([
                    "size": decompressed.count,
                    "success": true
                ])
            } catch let error as NSError {
                if error.localizedDescription.contains("INVALID_CREDENTIALS") {
                    call.reject("INVALID_CREDENTIALS")
                } else {
                    call.reject("Decompile failed: \(error.localizedDescription)")
                }
            }
        }
    }
    
    @objc func writeFile(_ call: CAPPluginCall) {
        guard let fileName = call.getString("fileName"),
              let dataB64 = call.getString("data"),
              let data = Data(base64Encoded: dataB64) else {
            call.reject("Missing required parameters: fileName, data")
            return
        }
        
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            guard let self = self else { return }
            
            do {
                let backupDir = self.getBackupDir()
                let file = backupDir.appendingPathComponent(fileName)
                try data.write(to: file)
                
                call.resolve([
                    "size": data.count,
                    "success": true
                ])
            } catch {
                call.reject("Write failed: \(error.localizedDescription)")
            }
        }
    }
    
    @objc func readFile(_ call: CAPPluginCall) {
        guard let fileName = call.getString("fileName") else {
            call.reject("Missing required parameter: fileName")
            return
        }
        
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            guard let self = self else { return }
            
            do {
                let backupDir = self.getBackupDir()
                let file = backupDir.appendingPathComponent(fileName)
                
                guard FileManager.default.fileExists(atPath: file.path) else {
                    call.reject("File does not exist: \(fileName)")
                    return
                }
                
                let data = try Data(contentsOf: file)
                let dataB64 = data.base64EncodedString()
                
                call.resolve([
                    "data": dataB64,
                    "size": data.count,
                    "success": true
                ])
            } catch {
                call.reject("Read failed: \(error.localizedDescription)")
            }
        }
    }
    
    @objc func deleteFile(_ call: CAPPluginCall) {
        guard let fileName = call.getString("fileName") else {
            call.reject("Missing required parameter: fileName")
            return
        }
        
        let backupDir = getBackupDir()
        let file = backupDir.appendingPathComponent(fileName)
        
        if FileManager.default.fileExists(atPath: file.path) {
            try? FileManager.default.removeItem(at: file)
        }
        
        call.resolve(["success": true])
    }
    
    @objc func getFilePath(_ call: CAPPluginCall) {
        guard let fileName = call.getString("fileName") else {
            call.reject("Missing required parameter: fileName")
            return
        }
        
        let backupDir = getBackupDir()
        let file = backupDir.appendingPathComponent(fileName)
        
        call.resolve([
            "path": file.path,
            "exists": FileManager.default.fileExists(atPath: file.path)
        ])
    }
    
    @objc func cleanup(_ call: CAPPluginCall) {
        let backupDir = getBackupDir()
        
        if let files = try? FileManager.default.contentsOfDirectory(at: backupDir, includingPropertiesForKeys: nil) {
            for file in files {
                try? FileManager.default.removeItem(at: file)
            }
        }
        
        call.resolve(["success": true])
    }
}
