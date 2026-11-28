import base64

import pytest

from domain.importing import AIImportFailed, ImportResultCode
from infrastructure.ai_import.capacitor_pdf_page_renderer import (
    CapacitorPdfPageRenderer,
)


@pytest.mark.asyncio
async def test_renders_pages_through_native_plugin(pdf_renderer_plugin):
    pdf_renderer_plugin.pages = [b"\xff\xd8\xff1", b"\xff\xd8\xff2"]

    pages = await CapacitorPdfPageRenderer().render(b"%PDF-1.4", 2, 1000)

    assert [page.data for page in pages] == pdf_renderer_plugin.pages
    assert all(page.mime_type == "image/jpeg" for page in pages)
    options = pdf_renderer_plugin.calls[0]
    assert base64.b64decode(options["data"]) == b"%PDF-1.4"
    assert options["maxPages"] == 2
    assert options["maxPixels"] == 1000


@pytest.mark.asyncio
@pytest.mark.parametrize("code", ["ENCRYPTED_PDF", "INVALID_PDF"])
async def test_native_pdf_errors_are_unsupported_files(pdf_renderer_plugin, code):
    pdf_renderer_plugin.error = RuntimeError(code)

    with pytest.raises(AIImportFailed) as error:
        await CapacitorPdfPageRenderer().render(b"%PDF-1.4", 2, 1000)

    assert error.value.code == ImportResultCode.UNSUPPORTED_FILE_FORMAT


@pytest.mark.asyncio
async def test_unexpected_failures_render_nothing(pdf_renderer_plugin):
    pdf_renderer_plugin.error = RuntimeError("bridge closed")

    assert await CapacitorPdfPageRenderer().render(b"%PDF-1.4", 2, 1000) == []
