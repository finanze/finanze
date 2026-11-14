import asyncio
from io import BytesIO
from math import sqrt

import pypdfium2 as pdfium
from application.ports.pdf_page_renderer import PdfPageRenderer
from domain.ai import AIAttachment

RENDER_DPI = 150
POINTS_PER_INCH = 72
JPEG_QUALITY = 85
PIXEL_MARGIN = 0.99


def _render(pdf: bytes, max_pages: int, max_pixels: int) -> list[AIAttachment]:
    document = pdfium.PdfDocument(pdf)
    try:
        pages = []
        for index in range(min(len(document), max_pages)):
            page = document[index]
            try:
                width, height = page.get_size()
                scale = RENDER_DPI / POINTS_PER_INCH
                pixels = width * height * scale * scale
                if pixels > max_pixels:
                    scale *= sqrt(max_pixels / pixels) * PIXEL_MARGIN
                bitmap = page.render(scale=scale)
                image = bitmap.to_pil()
                out = BytesIO()
                image.convert("RGB").save(out, format="JPEG", quality=JPEG_QUALITY)
                pages.append(
                    AIAttachment(
                        mime_type="image/jpeg",
                        data=out.getvalue(),
                        name=f"page-{index + 1}.jpg",
                    )
                )
            finally:
                page.close()
        return pages
    finally:
        document.close()


class PdfiumPageRenderer(PdfPageRenderer):
    async def render(
        self, pdf: bytes, max_pages: int, max_pixels: int
    ) -> list[AIAttachment]:
        return await asyncio.to_thread(_render, pdf, max_pages, max_pixels)
