package finanze.me.plugins

import android.util.Base64
import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.CapacitorPlugin
import java.io.ByteArrayOutputStream
import java.io.File
import java.nio.ByteBuffer
import java.security.SecureRandom
import java.util.zip.Deflater
import java.util.zip.Inflater
import javax.crypto.Cipher
import javax.crypto.Mac
import javax.crypto.SecretKeyFactory
import javax.crypto.spec.IvParameterSpec
import javax.crypto.spec.PBEKeySpec
import javax.crypto.spec.SecretKeySpec

interface BackupProcessorVersion {
    fun compile(rawData: ByteArray, password: String): ByteArray
    fun decompile(encryptedData: ByteArray, password: String): ByteArray
}

class BackupProcessorV1 : BackupProcessorVersion {
    companion object {
        private const val SALT = "finanze-backup-salt"
        private const val PBKDF2_ITERATIONS = 100000
        private const val KEY_LENGTH = 32
        private const val FERNET_VERSION: Byte = 0x80.toByte()
        private const val KEY_CACHE_LIMIT = 32
    }

    private val keyCache = object {
        private val cache = LinkedHashMap<String, ByteArray>(KEY_CACHE_LIMIT, 0.75f, true)

        @Synchronized
        fun get(password: String): ByteArray? = cache[password]

        @Synchronized
        fun put(password: String, key: ByteArray) {
            cache[password] = key
            if (cache.size > KEY_CACHE_LIMIT) {
                val iterator = cache.entries.iterator()
                if (iterator.hasNext()) {
                    iterator.next()
                    iterator.remove()
                }
            }
        }
    }

    override fun compile(rawData: ByteArray, password: String): ByteArray {
        val compressed = compressZlib(rawData, 9)
        val key = deriveKey(password)
        return fernetEncrypt(compressed, key)
    }

    override fun decompile(encryptedData: ByteArray, password: String): ByteArray {
        val key = deriveKey(password)
        val decrypted = fernetDecrypt(encryptedData, key)
        return decompressZlib(decrypted)
    }

    private fun deriveKey(password: String): ByteArray {
        keyCache.get(password)?.let { return it }
        val factory = SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256")
        val spec = PBEKeySpec(
            password.toCharArray(),
            SALT.toByteArray(Charsets.UTF_8),
            PBKDF2_ITERATIONS,
            KEY_LENGTH * 8
        )
        val derived = factory.generateSecret(spec).encoded
        keyCache.put(password, derived)
        return derived
    }

    private fun compressZlib(data: ByteArray, level: Int = 9): ByteArray {
        val deflater = Deflater(level)
        deflater.setInput(data)
        deflater.finish()

        val outputStream = ByteArrayOutputStream(data.size)
        val buffer = ByteArray(4096)

        while (!deflater.finished()) {
            val count = deflater.deflate(buffer)
            outputStream.write(buffer, 0, count)
        }
        deflater.end()
        outputStream.close()

        return outputStream.toByteArray()
    }

    private fun decompressZlib(data: ByteArray): ByteArray {
        val inflater = Inflater()
        inflater.setInput(data)

        val outputStream = ByteArrayOutputStream(data.size * 2)
        val buffer = ByteArray(4096)

        while (!inflater.finished()) {
            val count = inflater.inflate(buffer)
            outputStream.write(buffer, 0, count)
        }
        inflater.end()
        outputStream.close()

        return outputStream.toByteArray()
    }

    private fun fernetEncrypt(data: ByteArray, key: ByteArray): ByteArray {
        val signingKey = key.copyOfRange(0, 16)
        val encryptionKey = key.copyOfRange(16, 32)

        val iv = ByteArray(16)
        SecureRandom().nextBytes(iv)

        val timestamp = System.currentTimeMillis() / 1000
        val timestampBytes = ByteBuffer.allocate(8).putLong(timestamp).array()

        val cipher = Cipher.getInstance("AES/CBC/PKCS5Padding")
        cipher.init(Cipher.ENCRYPT_MODE, SecretKeySpec(encryptionKey, "AES"), IvParameterSpec(iv))
        val ciphertext = cipher.doFinal(data)

        val basicParts = ByteArrayOutputStream()
        basicParts.write(FERNET_VERSION.toInt())
        basicParts.write(timestampBytes)
        basicParts.write(iv)
        basicParts.write(ciphertext)
        val basicPartsBytes = basicParts.toByteArray()

        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(signingKey, "HmacSHA256"))
        val hmacResult = mac.doFinal(basicPartsBytes)

        val result = ByteArrayOutputStream()
        result.write(basicPartsBytes)
        result.write(hmacResult)

        return result.toByteArray()
    }

    private fun fernetDecrypt(token: ByteArray, key: ByteArray): ByteArray {
        if (token.size < 57) {
            throw IllegalArgumentException("Invalid token length")
        }

        val signingKey = key.copyOfRange(0, 16)
        val encryptionKey = key.copyOfRange(16, 32)

        val version = token[0]
        if (version != FERNET_VERSION) {
            throw IllegalArgumentException("Invalid Fernet version")
        }

        val basicPartsEnd = token.size - 32
        val basicParts = token.copyOfRange(0, basicPartsEnd)
        val providedHmac = token.copyOfRange(basicPartsEnd, token.size)

        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(signingKey, "HmacSHA256"))
        val expectedHmac = mac.doFinal(basicParts)

        if (!expectedHmac.contentEquals(providedHmac)) {
            throw SecurityException("INVALID_CREDENTIALS")
        }

        val iv = token.copyOfRange(9, 25)
        val ciphertext = token.copyOfRange(25, basicPartsEnd)

        val cipher = Cipher.getInstance("AES/CBC/PKCS5Padding")
        cipher.init(Cipher.DECRYPT_MODE, SecretKeySpec(encryptionKey, "AES"), IvParameterSpec(iv))

        return cipher.doFinal(ciphertext)
    }
}

@CapacitorPlugin(name = "BackupProcessor")
class BackupProcessorPlugin : Plugin() {

    private val processors: Map<Int, BackupProcessorVersion> = mapOf(
        1 to BackupProcessorV1()
    )

    private fun getBackupDir(): File {
        val dir = File(context.filesDir, "backup_staging")
        if (!dir.exists()) {
            dir.mkdirs()
        }
        return dir
    }

    private fun getProcessor(version: Int): BackupProcessorVersion {
        return processors[version]
            ?: throw IllegalArgumentException("Unsupported backup protocol version: $version")
    }

    @PluginMethod
    fun compile(call: PluginCall) {
        val inputFileName = call.getString("inputFile")
        val outputFileName = call.getString("outputFile")
        val password = call.getString("password")
        val version = call.getInt("version", 1) ?: 1

        if (inputFileName.isNullOrBlank() || outputFileName.isNullOrBlank() || password.isNullOrBlank()) {
            call.reject("Missing required parameters: inputFile, outputFile, password")
            return
        }

        bridge.execute {
            try {
                val processor = getProcessor(version)
                val backupDir = getBackupDir()
                val inputFile = File(backupDir, inputFileName)
                val outputFile = File(backupDir, outputFileName)

                if (!inputFile.exists()) {
                    call.reject("Input file does not exist: $inputFileName")
                    return@execute
                }

                val rawData = inputFile.readBytes()
                val encrypted = processor.compile(rawData, password)
                outputFile.writeBytes(encrypted)
                inputFile.delete()

                val result = JSObject()
                result.put("size", encrypted.size)
                result.put("success", true)
                call.resolve(result)

            } catch (e: IllegalArgumentException) {
                call.reject(e.message, e)
            } catch (e: Exception) {
                call.reject("Compile failed: ${e.message}", e)
            }
        }
    }

    @PluginMethod
    fun decompile(call: PluginCall) {
        val inputFileName = call.getString("inputFile")
        val outputFileName = call.getString("outputFile")
        val password = call.getString("password")
        val version = call.getInt("version", 1) ?: 1

        if (inputFileName.isNullOrBlank() || outputFileName.isNullOrBlank() || password.isNullOrBlank()) {
            call.reject("Missing required parameters: inputFile, outputFile, password")
            return
        }

        bridge.execute {
            try {
                val processor = getProcessor(version)
                val backupDir = getBackupDir()
                val inputFile = File(backupDir, inputFileName)
                val outputFile = File(backupDir, outputFileName)

                if (!inputFile.exists()) {
                    call.reject("Input file does not exist: $inputFileName")
                    return@execute
                }

                val encryptedData = inputFile.readBytes()
                val decompressed = processor.decompile(encryptedData, password)
                outputFile.writeBytes(decompressed)
                inputFile.delete()

                val result = JSObject()
                result.put("size", decompressed.size)
                result.put("success", true)
                call.resolve(result)

            } catch (e: SecurityException) {
                call.reject("INVALID_CREDENTIALS", e)
            } catch (e: IllegalArgumentException) {
                call.reject(e.message, e)
            } catch (e: Exception) {
                call.reject("Decompile failed: ${e.message}", e)
            }
        }
    }

    @PluginMethod
    fun writeFile(call: PluginCall) {
        val fileName = call.getString("fileName")
        val dataB64 = call.getString("data")

        if (fileName.isNullOrBlank() || dataB64.isNullOrBlank()) {
            call.reject("Missing required parameters: fileName, data")
            return
        }

        bridge.execute {
            try {
                val backupDir = getBackupDir()
                val file = File(backupDir, fileName)
                val data = Base64.decode(dataB64, Base64.NO_WRAP)
                file.writeBytes(data)

                val result = JSObject()
                result.put("size", data.size)
                result.put("success", true)
                call.resolve(result)

            } catch (e: Exception) {
                call.reject("Write failed: ${e.message}", e)
            }
        }
    }

    @PluginMethod
    fun readFile(call: PluginCall) {
        val fileName = call.getString("fileName")

        if (fileName.isNullOrBlank()) {
            call.reject("Missing required parameter: fileName")
            return
        }

        bridge.execute {
            try {
                val backupDir = getBackupDir()
                val file = File(backupDir, fileName)

                if (!file.exists()) {
                    call.reject("File does not exist: $fileName")
                    return@execute
                }

                val data = file.readBytes()
                val dataB64 = Base64.encodeToString(data, Base64.NO_WRAP)

                val result = JSObject()
                result.put("data", dataB64)
                result.put("size", data.size)
                result.put("success", true)
                call.resolve(result)

            } catch (e: Exception) {
                call.reject("Read failed: ${e.message}", e)
            }
        }
    }

    @PluginMethod
    fun deleteFile(call: PluginCall) {
        val fileName = call.getString("fileName")

        if (fileName.isNullOrBlank()) {
            call.reject("Missing required parameter: fileName")
            return
        }

        try {
            val backupDir = getBackupDir()
            val file = File(backupDir, fileName)

            if (file.exists()) {
                file.delete()
            }

            val result = JSObject()
            result.put("success", true)
            call.resolve(result)

        } catch (e: Exception) {
            call.reject("Delete failed: ${e.message}", e)
        }
    }

    @PluginMethod
    fun getFilePath(call: PluginCall) {
        val fileName = call.getString("fileName")

        if (fileName.isNullOrBlank()) {
            call.reject("Missing required parameter: fileName")
            return
        }

        try {
            val backupDir = getBackupDir()
            val file = File(backupDir, fileName)

            val result = JSObject()
            result.put("path", file.absolutePath)
            result.put("exists", file.exists())
            call.resolve(result)

        } catch (e: Exception) {
            call.reject("GetFilePath failed: ${e.message}", e)
        }
    }

    @PluginMethod
    fun cleanup(call: PluginCall) {
        try {
            val backupDir = getBackupDir()
            backupDir.listFiles()?.forEach { it.delete() }

            val result = JSObject()
            result.put("success", true)
            call.resolve(result)

        } catch (e: Exception) {
            call.reject("Cleanup failed: ${e.message}", e)
        }
    }
}
