from io import BytesIO
from unittest.mock import AsyncMock

import pytest

from domain.exception.exceptions import UnsupportedFileFormat
from domain.export import FileFormat
from domain.file_upload import FileUpload
from infrastructure.table.table_rw_dispatcher import TableRWDispatcher


def _dispatcher():
    adapters = {file_format: AsyncMock() for file_format in FileFormat}
    for file_format, adapter in adapters.items():
        adapter.parse = AsyncMock(return_value=[[file_format.value]])
    return TableRWDispatcher(adapters)


def _upload(filename, content_type, body=b""):
    return FileUpload(
        filename=filename,
        content_type=content_type,
        content_length=len(body),
        data=BytesIO(body),
    )


class TestTableRWDispatcherParse:
    @pytest.mark.parametrize(
        "filename,content_type,body,expected",
        [
            ("movements.CSV", "application/octet-stream", b"", FileFormat.CSV),
            ("movements.tsv", "text/csv", b"", FileFormat.TSV),
            ("movements.xlsx", "", b"", FileFormat.XLSX),
            ("movements.xls", "application/octet-stream", b"", FileFormat.XLSX),
            ("movements.xls.xls", "", b"", FileFormat.XLSX),
            ("movements.html", "application/octet-stream", b"", FileFormat.HTML),
            ("movements.HTM", "", b"", FileFormat.HTML),
            ("movements.pdf", "application/octet-stream", b"", FileFormat.PDF),
            ("movements", "application/vnd.ms-excel", b"", FileFormat.XLSX),
            ("movements", "text/csv; charset=utf-8", b"", FileFormat.CSV),
            ("movements", "text/tab-separated-values", b"", FileFormat.TSV),
            ("movements", "text/html; charset=iso-8859-1", b"", FileFormat.HTML),
            ("movements", "application/pdf", b"", FileFormat.PDF),
            ("download", "application/octet-stream", b"%PDF-1.5\n...", FileFormat.PDF),
            (
                "download",
                "application/octet-stream",
                b"<!DOCTYPE html><table>",
                FileFormat.HTML,
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_routes_by_extension_then_content_type_then_magic(
        self, filename, content_type, body, expected
    ):
        rows = await _dispatcher().parse(_upload(filename, content_type, body))

        assert rows == [[expected.value]]

    @pytest.mark.asyncio
    async def test_rejects_unknown_files(self):
        with pytest.raises(UnsupportedFileFormat):
            await _dispatcher().parse(_upload("movements.zip", "application/zip"))
