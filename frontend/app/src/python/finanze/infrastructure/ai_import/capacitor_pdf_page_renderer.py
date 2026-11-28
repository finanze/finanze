import base64
import logging

import js
from pyodide.ffi import to_js

from application.ports.pdf_page_renderer import PdfPageRenderer
from domain.ai import AIAttachment
from domain.importing import AIImportFailed, ImportResultCode

JPEG_QUALITY = 0.85
PDF_ERRORS = {"ENCRYPTED_PDF": "Encrypted PDF", "INVALID_PDF": "Unreadable PDF"}


class CapacitorPdfPageRenderer(PdfPageRenderer):
    def __init__(self):
        self._log = logging.getLogger(__name__)

    async def render(
        self, pdf: bytes, max_pages: int, max_pixels: int
    ) -> list[AIAttachment]:
        plugin = getattr(js.window, "PdfRenderer", None)
        if plugin is None:
            return []
        options = {
            "data": base64.b64encode(pdf).decode("ascii"),
            "maxPages": max_pages,
            "maxPixels": max_pixels,
            "quality": JPEG_QUALITY,
        }
        try:
            result = await plugin.renderPages(to_js(options, create_pyproxies=False))
        except Exception as e:
            message = str(e)
            for code, detail in PDF_ERRORS.items():
                if code in message:
                    raise AIImportFailed(
                        ImportResultCode.UNSUPPORTED_FILE_FORMAT, detail
                    ) from e
            self._log.warning(f"PDF page rendering failed: {e}")
            return []

        result_py = result.to_py() if hasattr(result, "to_py") else result
        return [
            AIAttachment(
                mime_type="image/jpeg",
                data=base64.b64decode(page["data"]),
                name=f"page-{index + 1}.jpg",
            )
            for index, page in enumerate(result_py.get("pages") or [])
            if page.get("data")
        ]
