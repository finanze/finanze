package me.finanze.plugins

import android.graphics.Bitmap
import android.graphics.Color
import android.graphics.pdf.PdfRenderer
import android.os.ParcelFileDescriptor
import android.util.Base64
import com.getcapacitor.JSArray
import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.CapacitorPlugin
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.IOException
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sqrt

@CapacitorPlugin(name = "PdfRenderer")
class PdfRendererPlugin : Plugin() {

    companion object {
        private const val RENDER_DPI = 150.0
        private const val POINTS_PER_INCH = 72.0
        private const val PIXEL_MARGIN = 0.99
        private const val DEFAULT_MAX_PIXELS = 4_200_000
    }

    @PluginMethod
    fun renderPages(call: PluginCall) {
        val base64Data = call.getString("data")
        if (base64Data.isNullOrBlank()) {
            call.reject("Missing required parameter: data")
            return
        }
        val maxPages = max(call.getInt("maxPages", 10) ?: 10, 1)
        val maxPixels = (call.getInt("maxPixels", DEFAULT_MAX_PIXELS) ?: DEFAULT_MAX_PIXELS).toDouble()
        val quality = ((call.getDouble("quality") ?: 0.85) * 100).toInt().coerceIn(1, 100)

        bridge.execute {
            val file = File.createTempFile("render-", ".pdf", context.cacheDir)
            try {
                file.writeBytes(Base64.decode(base64Data, Base64.DEFAULT))
                val descriptor = ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY)
                val renderer = try {
                    PdfRenderer(descriptor)
                } catch (e: Exception) {
                    descriptor.close()
                    throw e
                }
                try {
                    val pages = JSArray()
                    for (index in 0 until min(renderer.pageCount, maxPages)) {
                        val page = renderer.openPage(index)
                        try {
                            pages.put(JSObject().put("data", renderPage(page, maxPixels, quality)))
                        } finally {
                            page.close()
                        }
                    }
                    call.resolve(JSObject().put("pages", pages).put("pageCount", renderer.pageCount))
                } finally {
                    renderer.close()
                }
            } catch (e: SecurityException) {
                call.reject("ENCRYPTED_PDF", e)
            } catch (e: IOException) {
                call.reject("INVALID_PDF", e)
            } catch (e: Exception) {
                call.reject("Failed to render PDF: ${e.message}", e)
            } finally {
                file.delete()
            }
        }
    }

    private fun renderPage(page: PdfRenderer.Page, maxPixels: Double, quality: Int): String {
        var scale = RENDER_DPI / POINTS_PER_INCH
        val pixels = page.width * page.height * scale * scale
        if (pixels > maxPixels) {
            scale *= sqrt(maxPixels / pixels) * PIXEL_MARGIN
        }
        val width = max(1, (page.width * scale).toInt())
        val height = max(1, (page.height * scale).toInt())
        val bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
        try {
            bitmap.eraseColor(Color.WHITE)
            page.render(bitmap, null, null, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY)
            val output = ByteArrayOutputStream()
            bitmap.compress(Bitmap.CompressFormat.JPEG, quality, output)
            return Base64.encodeToString(output.toByteArray(), Base64.NO_WRAP)
        } finally {
            bitmap.recycle()
        }
    }
}
