import Foundation
import Capacitor
import PDFKit
import UIKit

@objc(PdfRendererPlugin)
public class PdfRendererPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "PdfRendererPlugin"
    public let jsName = "PdfRenderer"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "renderPages", returnType: CAPPluginReturnPromise),
    ]

    private let renderDpi: CGFloat = 150
    private let pointsPerInch: CGFloat = 72
    private let pixelMargin: CGFloat = 0.99

    @objc func renderPages(_ call: CAPPluginCall) {
        guard let base64Data = call.getString("data"),
              let pdfData = Data(base64Encoded: base64Data) else {
            call.reject("Missing required parameter: data")
            return
        }

        let maxPages = max(call.getInt("maxPages") ?? 10, 1)
        let maxPixels = CGFloat(call.getInt("maxPixels") ?? 4_200_000)
        let quality = CGFloat(call.getDouble("quality") ?? 0.85)

        DispatchQueue.global(qos: .userInitiated).async {
            guard let document = PDFDocument(data: pdfData) else {
                call.reject("INVALID_PDF")
                return
            }
            if document.isLocked {
                call.reject("ENCRYPTED_PDF")
                return
            }

            var pages: [[String: Any]] = []
            for index in 0..<min(document.pageCount, maxPages) {
                autoreleasepool {
                    guard let page = document.page(at: index),
                          let jpeg = self.render(page, maxPixels: maxPixels, quality: quality) else {
                        return
                    }
                    pages.append(["data": jpeg.base64EncodedString()])
                }
            }
            call.resolve(["pages": pages, "pageCount": document.pageCount])
        }
    }

    private func render(_ page: PDFPage, maxPixels: CGFloat, quality: CGFloat) -> Data? {
        let bounds = page.bounds(for: .mediaBox)
        guard bounds.width > 0, bounds.height > 0 else { return nil }

        var scale = renderDpi / pointsPerInch
        let pixels = bounds.width * bounds.height * scale * scale
        if pixels > maxPixels {
            scale *= sqrt(maxPixels / pixels) * pixelMargin
        }
        let size = CGSize(
            width: max(1, floor(bounds.width * scale)),
            height: max(1, floor(bounds.height * scale))
        )

        let format = UIGraphicsImageRendererFormat()
        format.scale = 1
        format.opaque = true
        let image = UIGraphicsImageRenderer(size: size, format: format).image { context in
            UIColor.white.setFill()
            context.fill(CGRect(origin: .zero, size: size))
            let cgContext = context.cgContext
            cgContext.translateBy(x: 0, y: size.height)
            cgContext.scaleBy(x: scale, y: -scale)
            cgContext.translateBy(x: -bounds.minX, y: -bounds.minY)
            page.draw(with: .mediaBox, to: cgContext)
        }
        return image.jpegData(compressionQuality: quality)
    }
}
