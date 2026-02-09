package me.finanze.plugins

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.util.Base64
import androidx.exifinterface.media.ExifInterface
import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.CapacitorPlugin
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import kotlin.math.max
import kotlin.math.sqrt

@CapacitorPlugin(name = "ImageProcessor")
class ImageProcessorPlugin : Plugin() {

    companion object {
        private const val MAX_IMAGE_PIXELS = 4_200_000
        private const val JPEG_QUALITY = 75
    }

    @PluginMethod
    fun processImage(call: PluginCall) {
        val base64Data = call.getString("data")
        val filename = call.getString("filename") ?: "image.jpg"
        val contentType = call.getString("contentType") ?: "image/jpeg"

        if (base64Data.isNullOrBlank()) {
            call.reject("Missing required parameter: data")
            return
        }

        bridge.execute {
            try {
                processImageInternal(base64Data, filename, contentType, call)
            } catch (e: Exception) {
                call.reject("Failed to process image: ${e.message}")
            }
        }
    }

    private fun processImageInternal(
        base64Data: String,
        filename: String,
        contentType: String,
        call: PluginCall
    ) {
        val imageBytes = Base64.decode(base64Data, Base64.DEFAULT)
        
        val orientation = getExifOrientation(imageBytes)
        
        val options = BitmapFactory.Options().apply {
            inJustDecodeBounds = true
        }
        BitmapFactory.decodeByteArray(imageBytes, 0, imageBytes.size, options)
        
        val originalWidth = options.outWidth
        val originalHeight = options.outHeight
        val pixels = originalWidth * originalHeight
        
        var sampleSize = 1
        if (pixels > MAX_IMAGE_PIXELS) {
            val scale = sqrt(MAX_IMAGE_PIXELS.toDouble() / pixels.toDouble())
            sampleSize = max(1, (1.0 / scale).toInt())
        }
        
        val decodeOptions = BitmapFactory.Options().apply {
            inSampleSize = sampleSize
        }
        
        var bitmap = BitmapFactory.decodeByteArray(imageBytes, 0, imageBytes.size, decodeOptions)
            ?: run {
                call.reject("Failed to decode image data")
                return
            }
        
        bitmap = applyExifOrientation(bitmap, orientation)
        
        val currentPixels = bitmap.width * bitmap.height
        if (currentPixels > MAX_IMAGE_PIXELS) {
            val scale = sqrt(MAX_IMAGE_PIXELS.toDouble() / currentPixels.toDouble())
            val newWidth = max(1, (bitmap.width * scale).toInt())
            val newHeight = max(1, (bitmap.height * scale).toInt())
            
            val resized = Bitmap.createScaledBitmap(bitmap, newWidth, newHeight, true)
            if (resized != bitmap) {
                bitmap.recycle()
                bitmap = resized
            }
        }
        
        val hasAlpha = bitmap.hasAlpha()
        val isPNG = contentType.lowercase().contains("png") || filename.lowercase().endsWith(".png")
        
        val outputStream = ByteArrayOutputStream()
        var outputFilename = filename
        var outputContentType = contentType
        
        if (isPNG && hasAlpha) {
            bitmap.compress(Bitmap.CompressFormat.PNG, 100, outputStream)
            outputContentType = "image/png"
            outputFilename = changeExtension(filename, "png")
        } else {
            bitmap.compress(Bitmap.CompressFormat.JPEG, JPEG_QUALITY, outputStream)
            outputContentType = "image/jpeg"
            outputFilename = changeExtension(filename, "jpg")
        }
        
        bitmap.recycle()
        
        val outputBytes = outputStream.toByteArray()
        val base64Output = Base64.encodeToString(outputBytes, Base64.NO_WRAP)
        
        val result = JSObject().apply {
            put("data", base64Output)
            put("filename", outputFilename)
            put("contentType", outputContentType)
            put("size", outputBytes.size)
        }
        
        call.resolve(result)
    }
    
    private fun getExifOrientation(imageBytes: ByteArray): Int {
        return try {
            val inputStream = ByteArrayInputStream(imageBytes)
            val exif = ExifInterface(inputStream)
            exif.getAttributeInt(
                ExifInterface.TAG_ORIENTATION,
                ExifInterface.ORIENTATION_NORMAL
            )
        } catch (e: Exception) {
            ExifInterface.ORIENTATION_NORMAL
        }
    }
    
    private fun applyExifOrientation(bitmap: Bitmap, orientation: Int): Bitmap {
        val matrix = Matrix()
        
        when (orientation) {
            ExifInterface.ORIENTATION_ROTATE_90 -> matrix.postRotate(90f)
            ExifInterface.ORIENTATION_ROTATE_180 -> matrix.postRotate(180f)
            ExifInterface.ORIENTATION_ROTATE_270 -> matrix.postRotate(270f)
            ExifInterface.ORIENTATION_FLIP_HORIZONTAL -> matrix.preScale(-1f, 1f)
            ExifInterface.ORIENTATION_FLIP_VERTICAL -> matrix.preScale(1f, -1f)
            ExifInterface.ORIENTATION_TRANSPOSE -> {
                matrix.postRotate(90f)
                matrix.preScale(-1f, 1f)
            }
            ExifInterface.ORIENTATION_TRANSVERSE -> {
                matrix.postRotate(270f)
                matrix.preScale(-1f, 1f)
            }
            else -> return bitmap
        }
        
        val rotated = Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
        if (rotated != bitmap) {
            bitmap.recycle()
        }
        return rotated
    }

    private fun changeExtension(filename: String, newExtension: String): String {
        val lastDot = filename.lastIndexOf('.')
        val nameWithoutExtension = if (lastDot > 0) filename.substring(0, lastDot) else filename
        return "$nameWithoutExtension.$newExtension"
    }
}
