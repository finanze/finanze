from io import BytesIO

import pypdfium2 as pdfium
import pytest
from domain.ai import AIAttachment
from domain.importing import AIImportFailed, ImportResultCode
from infrastructure.ai_import.pdfium_page_renderer import PdfiumPageRenderer
from infrastructure.ai_import.pillow_image_normalizer import PillowImageNormalizer
from PIL import Image


def _image(size, mode="RGB", fmt="PNG") -> bytes:
    out = BytesIO()
    Image.new(mode, size, "white").save(out, format=fmt)
    return out.getvalue()


def _pdf(pages: int) -> bytes:
    document = pdfium.PdfDocument.new()
    for _ in range(pages):
        document.new_page(612, 792)
    out = BytesIO()
    document.save(out)
    return out.getvalue()


class TestPillowImageNormalizer:
    @pytest.mark.asyncio
    async def test_small_supported_images_pass_through(self):
        image = AIAttachment(mime_type="image/png", data=_image((100, 100)))
        assert await PillowImageNormalizer().normalize(image, 10_000, 10**6) is image

    @pytest.mark.asyncio
    async def test_large_images_are_downscaled_to_jpeg(self):
        image = AIAttachment(mime_type="image/png", data=_image((400, 300)))
        result = await PillowImageNormalizer().normalize(image, 30_000, 10**6)
        assert result.mime_type == "image/jpeg"
        with Image.open(BytesIO(result.data)) as decoded:
            assert decoded.width * decoded.height <= 30_000

    @pytest.mark.asyncio
    async def test_transparent_images_stay_png(self):
        data = _image((400, 300), mode="RGBA")
        image = AIAttachment(mime_type="image/png", data=data)
        result = await PillowImageNormalizer().normalize(image, 30_000, 10**6)
        assert result.mime_type == "image/png"

    @pytest.mark.asyncio
    async def test_unsupported_formats_are_converted(self):
        image = AIAttachment(mime_type="image/bmp", data=_image((10, 10), fmt="BMP"))
        result = await PillowImageNormalizer().normalize(image, 10_000, 10**6)
        assert result.mime_type == "image/jpeg"

    @pytest.mark.asyncio
    async def test_unreadable_images_fail(self):
        image = AIAttachment(mime_type="image/heic", data=b"garbage")
        with pytest.raises(AIImportFailed) as error:
            await PillowImageNormalizer().normalize(image, 10_000, 10**6)
        assert error.value.code == ImportResultCode.UNSUPPORTED_FILE_FORMAT


class TestPdfiumPageRenderer:
    @pytest.mark.asyncio
    async def test_renders_limited_pages_within_pixel_budget(self):
        pages = await PdfiumPageRenderer().render(_pdf(3), 2, 500_000)
        assert len(pages) == 2
        assert all(page.mime_type == "image/jpeg" for page in pages)
        with Image.open(BytesIO(pages[0].data)) as decoded:
            assert decoded.width * decoded.height <= 500_000
