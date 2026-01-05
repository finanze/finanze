import Foundation
import Capacitor
import UIKit
import ImageIO

@objc(ImageProcessorPlugin)
public class ImageProcessorPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "ImageProcessorPlugin"
    public let jsName = "ImageProcessor"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "processImage", returnType: CAPPluginReturnPromise),
    ]
    
    private let maxImagePixels: Int = 4_200_000
    private let jpegQuality: CGFloat = 0.75
    
    @objc func processImage(_ call: CAPPluginCall) {
        guard let base64Data = call.getString("data") else {
            call.reject("Missing required parameter: data")
            return
        }
        
        let filename = call.getString("filename") ?? "image.jpg"
        let contentType = call.getString("contentType") ?? "image/jpeg"
        
        DispatchQueue.global(qos: .userInitiated).async {
            self.processImageInternal(
                base64Data: base64Data,
                filename: filename,
                contentType: contentType,
                call: call
            )
        }
    }
    
    private func processImageInternal(
        base64Data: String,
        filename: String,
        contentType: String,
        call: CAPPluginCall
    ) {
        guard let imageData = Data(base64Encoded: base64Data),
              var image = UIImage(data: imageData) else {
            call.reject("Failed to decode image data")
            return
        }
        
        image = fixImageOrientation(image)
        
        var processedImage = image
        
        let width = processedImage.size.width
        let height = processedImage.size.height
        let pixels = Int(width * height)
        
        if pixels > maxImagePixels && width > 0 && height > 0 {
            let scale = sqrt(Double(maxImagePixels) / Double(pixels))
            let newWidth = max(1, Int(width * scale))
            let newHeight = max(1, Int(height * scale))
            
            if let resizedImage = resizeImageHighQuality(processedImage, to: CGSize(width: newWidth, height: newHeight)) {
                processedImage = resizedImage
            }
        }
        
        let hasAlpha = imageHasAlpha(processedImage)
        let isPNG = contentType.lowercased().contains("png") || filename.lowercased().hasSuffix(".png")
        
        var outputData: Data?
        var outputFilename = filename
        var outputContentType = contentType
        
        if isPNG && hasAlpha {
            outputData = processedImage.pngData()
            outputContentType = "image/png"
            outputFilename = changeExtension(filename, to: "png")
        } else {
            outputData = encodeJPEGOptimized(processedImage, quality: jpegQuality)
            outputContentType = "image/jpeg"
            outputFilename = changeExtension(filename, to: "jpg")
        }
        
        guard let finalData = outputData else {
            call.reject("Failed to encode processed image")
            return
        }
        
        let base64Output = finalData.base64EncodedString()
        
        call.resolve([
            "data": base64Output,
            "filename": outputFilename,
            "contentType": outputContentType,
            "size": finalData.count
        ])
    }
    
    private func fixImageOrientation(_ image: UIImage) -> UIImage {
        if image.imageOrientation == .up {
            return image
        }
        
        UIGraphicsBeginImageContextWithOptions(image.size, false, image.scale)
        image.draw(in: CGRect(origin: .zero, size: image.size))
        let normalizedImage = UIGraphicsGetImageFromCurrentImageContext()
        UIGraphicsEndImageContext()
        
        return normalizedImage ?? image
    }
    
    private func resizeImageHighQuality(_ image: UIImage, to targetSize: CGSize) -> UIImage? {
        guard let cgImage = image.cgImage else { return nil }
        
        let context = CGContext(
            data: nil,
            width: Int(targetSize.width),
            height: Int(targetSize.height),
            bitsPerComponent: 8,
            bytesPerRow: 0,
            space: CGColorSpaceCreateDeviceRGB(),
            bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
        )
        
        context?.interpolationQuality = .high
        context?.draw(cgImage, in: CGRect(origin: .zero, size: targetSize))
        
        guard let resizedCGImage = context?.makeImage() else { return nil }
        return UIImage(cgImage: resizedCGImage)
    }
    
    private func encodeJPEGOptimized(_ image: UIImage, quality: CGFloat) -> Data? {
        guard let cgImage = image.cgImage else {
            return image.jpegData(compressionQuality: quality)
        }
        
        let data = NSMutableData()
        guard let destination = CGImageDestinationCreateWithData(data, "public.jpeg" as CFString, 1, nil) else {
            return image.jpegData(compressionQuality: quality)
        }
        
        let options: [CFString: Any] = [
            kCGImageDestinationLossyCompressionQuality: quality,
            kCGImageDestinationOptimizeColorForSharing: true
        ]
        
        CGImageDestinationAddImage(destination, cgImage, options as CFDictionary)
        
        guard CGImageDestinationFinalize(destination) else {
            return image.jpegData(compressionQuality: quality)
        }
        
        return data as Data
    }
    
    private func imageHasAlpha(_ image: UIImage) -> Bool {
        guard let cgImage = image.cgImage else { return false }
        
        let alphaInfo = cgImage.alphaInfo
        return alphaInfo == .first ||
               alphaInfo == .last ||
               alphaInfo == .premultipliedFirst ||
               alphaInfo == .premultipliedLast ||
               alphaInfo == .alphaOnly
    }
    
    private func changeExtension(_ filename: String, to newExtension: String) -> String {
        let url = URL(fileURLWithPath: filename)
        let nameWithoutExtension = url.deletingPathExtension().lastPathComponent
        return "\(nameWithoutExtension).\(newExtension)"
    }
}
