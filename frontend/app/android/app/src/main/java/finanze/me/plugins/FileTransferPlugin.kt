package finanze.me.plugins

import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.CapacitorPlugin
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.net.HttpURLConnection
import java.net.URL

@CapacitorPlugin(name = "FileTransfer")
class FileTransferPlugin : Plugin() {

    companion object {
        private const val DEFAULT_TIMEOUT = 60000
    }

    private fun getBackupDir(): File {
        val dir = File(context.filesDir, "backup_staging")
        if (!dir.exists()) {
            dir.mkdirs()
        }
        return dir
    }

    @PluginMethod
    fun upload(call: PluginCall) {
        val url = call.getString("url")
        val fileName = call.getString("fileName")
        val method = call.getString("method", "PUT") ?: "PUT"
        val headers: JSObject = call.getObject("headers") ?: JSObject()
        val timeout = call.getInt("timeout", DEFAULT_TIMEOUT) ?: DEFAULT_TIMEOUT

        if (url.isNullOrBlank() || fileName.isNullOrBlank()) {
            call.reject("Missing required parameters: url, fileName")
            return
        }

        bridge.execute {
            var connection: HttpURLConnection? = null
            var inputStream: FileInputStream? = null

            try {
                val backupDir = getBackupDir()
                val file = File(backupDir, fileName)

                if (!file.exists()) {
                    call.reject("File does not exist: $fileName")
                    return@execute
                }

                val fileSize = file.length()

                connection = (URL(url).openConnection() as HttpURLConnection).apply {
                    requestMethod = method
                    connectTimeout = timeout
                    readTimeout = timeout
                    doOutput = true
                    doInput = true
                    useCaches = false
                    setFixedLengthStreamingMode(fileSize)
                }

                headers.keys().forEach { key ->
                    val value = headers.getString(key)
                    if (value != null && key.lowercase() != "content-length") {
                        connection.setRequestProperty(key, value)
                    }
                }
                connection.setRequestProperty("Content-Length", fileSize.toString())

                inputStream = FileInputStream(file)
                val outputStream = connection.outputStream

                val buffer = ByteArray(8192)
                var bytesRead: Int

                while (inputStream.read(buffer).also { bytesRead = it } != -1) {
                    outputStream.write(buffer, 0, bytesRead)
                }

                outputStream.flush()
                outputStream.close()

                val responseCode = connection.responseCode

                val result = JSObject()
                result.put("status", responseCode)
                result.put("success", responseCode in 200..299)

                if (responseCode in 200..299) {
                    file.delete()
                    call.resolve(result)
                } else {
                    val errorBody = try {
                        connection.errorStream?.bufferedReader()?.readText() ?: ""
                    } catch (e: Exception) {
                        ""
                    }
                    result.put("error", errorBody)
                    call.reject(
                        "Upload failed with status $responseCode",
                        null as Exception?,
                        result
                    )
                }

            } catch (e: Exception) {
                call.reject("Upload failed: ${e.message}", e)
            } finally {
                inputStream?.close()
                connection?.disconnect()
            }
        }
    }

    @PluginMethod
    fun download(call: PluginCall) {
        val url = call.getString("url")
        val fileName = call.getString("fileName")
        val timeout = call.getInt("timeout", DEFAULT_TIMEOUT) ?: DEFAULT_TIMEOUT

        if (url.isNullOrBlank() || fileName.isNullOrBlank()) {
            call.reject("Missing required parameters: url, fileName")
            return
        }

        bridge.execute {
            var connection: HttpURLConnection? = null
            var outputStream: FileOutputStream? = null

            try {
                val backupDir = getBackupDir()
                val file = File(backupDir, fileName)

                connection = (URL(url).openConnection() as HttpURLConnection).apply {
                    requestMethod = "GET"
                    connectTimeout = timeout
                    readTimeout = timeout
                    doInput = true
                    useCaches = false
                }

                val responseCode = connection.responseCode

                if (responseCode == 429) {
                    call.reject("TOO_MANY_REQUESTS")
                    return@execute
                }

                if (responseCode !in 200..299) {
                    call.reject("Download failed with status $responseCode")
                    return@execute
                }

                val inputStream = connection.inputStream
                outputStream = FileOutputStream(file)

                val buffer = ByteArray(8192)
                var bytesRead: Int
                var totalBytes = 0L

                while (inputStream.read(buffer).also { bytesRead = it } != -1) {
                    outputStream.write(buffer, 0, bytesRead)
                    totalBytes += bytesRead
                }

                outputStream.flush()

                val result = JSObject()
                result.put("status", responseCode)
                result.put("size", totalBytes)
                result.put("success", true)
                call.resolve(result)

            } catch (e: Exception) {
                call.reject("Download failed: ${e.message}", e)
            } finally {
                outputStream?.close()
                connection?.disconnect()
            }
        }
    }
}
