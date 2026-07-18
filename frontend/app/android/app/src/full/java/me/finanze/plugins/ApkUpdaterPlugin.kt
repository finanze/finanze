package me.finanze.plugins

import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings
import android.util.Log
import androidx.core.content.FileProvider
import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.CapacitorPlugin
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

@CapacitorPlugin(name = "ApkUpdater")
class ApkUpdaterPlugin : Plugin() {

    companion object {
        private const val TAG = "ApkUpdater"
        private const val DEFAULT_TIMEOUT = 60000
        private const val UPDATES_DIR = "updates"
        private const val MAX_REDIRECTS = 5
    }

    private fun getUpdatesDir(): File {
        val dir = File(context.cacheDir, UPDATES_DIR)
        if (!dir.exists()) {
            dir.mkdirs()
        }
        return dir
    }

    private fun openFollowingRedirects(
        urlString: String,
        timeout: Int,
    ): HttpURLConnection {
        var currentUrl = urlString
        var redirects = 0

        while (true) {
            val connection = (URL(currentUrl).openConnection() as HttpURLConnection).apply {
                requestMethod = "GET"
                connectTimeout = timeout
                readTimeout = timeout
                doInput = true
                useCaches = false
                instanceFollowRedirects = false
                setRequestProperty("Accept", "*/*")
            }

            val code = connection.responseCode
            Log.d(TAG, "GET $currentUrl -> $code")

            if (code in intArrayOf(301, 302, 303, 307, 308)) {
                val location = connection.getHeaderField("Location")
                connection.disconnect()
                if (location.isNullOrBlank() || redirects >= MAX_REDIRECTS) {
                    throw IOException("Too many redirects or missing Location header")
                }
                currentUrl = URL(URL(currentUrl), location).toString()
                redirects++
                continue
            }

            return connection
        }
    }

    @PluginMethod
    fun canInstall(call: PluginCall) {
        val granted = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            context.packageManager.canRequestPackageInstalls()
        } else {
            true
        }
        val result = JSObject()
        result.put("granted", granted)
        call.resolve(result)
    }

    @PluginMethod
    fun openInstallSettings(call: PluginCall) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val intent = Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES).apply {
                data = Uri.parse("package:${context.packageName}")
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            context.startActivity(intent)
        }
        call.resolve()
    }

    @PluginMethod
    fun download(call: PluginCall) {
        val url = call.getString("url")
        val fileName = call.getString("fileName")
        val timeout = call.getInt("timeout", DEFAULT_TIMEOUT) ?: DEFAULT_TIMEOUT
        val expectedSize = call.getDouble("expectedSize")?.toLong() ?: 0L

        if (url.isNullOrBlank() || fileName.isNullOrBlank()) {
            call.reject("Missing required parameters: url, fileName")
            return
        }

        bridge.execute {
            var connection: HttpURLConnection? = null
            var outputStream: FileOutputStream? = null

            try {
                val updatesDir = getUpdatesDir()
                val file = File(updatesDir, fileName)

                if (file.exists() && expectedSize > 0 && file.length() == expectedSize) {
                    Log.d(TAG, "APK already present (${file.length()} bytes), skipping download")
                    val cached = JSObject()
                    cached.put("path", file.absolutePath)
                    cached.put("size", file.length())
                    call.resolve(cached)
                    return@execute
                }

                if (file.exists()) {
                    file.delete()
                }

                Log.d(TAG, "Starting download: $url -> ${file.absolutePath}")
                connection = openFollowingRedirects(url, timeout)

                val responseCode = connection.responseCode
                if (responseCode !in 200..299) {
                    Log.e(TAG, "Download failed with status $responseCode")
                    call.reject("Download failed with status $responseCode")
                    return@execute
                }

                val total = connection.contentLengthLong
                Log.d(TAG, "Response $responseCode, contentLength=$total")
                val inputStream = connection.inputStream
                outputStream = FileOutputStream(file)

                val buffer = ByteArray(8192)
                var bytesRead: Int
                var downloaded = 0L
                var lastEmitted = 0L

                while (inputStream.read(buffer).also { bytesRead = it } != -1) {
                    outputStream.write(buffer, 0, bytesRead)
                    downloaded += bytesRead

                    if (downloaded - lastEmitted >= 65536 || (total > 0 && downloaded == total)) {
                        lastEmitted = downloaded
                        val progress = JSObject()
                        progress.put("downloaded", downloaded)
                        progress.put("total", total)
                        notifyListeners("downloadProgress", progress)
                    }
                }

                outputStream.flush()
                Log.d(TAG, "Download complete: $downloaded bytes")

                val result = JSObject()
                result.put("path", file.absolutePath)
                result.put("size", downloaded)
                call.resolve(result)

            } catch (e: Exception) {
                Log.e(TAG, "Download failed", e)
                call.reject("Download failed: ${e.message}", e)
            } finally {
                outputStream?.close()
                connection?.disconnect()
            }
        }
    }

    @PluginMethod
    fun install(call: PluginCall) {
        val path = call.getString("path")
        if (path.isNullOrBlank()) {
            call.reject("Missing required parameter: path")
            return
        }

        try {
            val file = File(path)
            if (!file.exists()) {
                call.reject("APK file does not exist: $path")
                return
            }

            val uri: Uri = FileProvider.getUriForFile(
                context,
                "${context.packageName}.fileprovider",
                file,
            )

            val intent = Intent(Intent.ACTION_VIEW).apply {
                setDataAndType(uri, "application/vnd.android.package-archive")
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            context.startActivity(intent)
            call.resolve()

        } catch (e: Exception) {
            call.reject("Install failed: ${e.message}", e)
        }
    }
}
