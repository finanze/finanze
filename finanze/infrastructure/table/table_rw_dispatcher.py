import re
from typing import Any

from application.ports.file_rw_port import TableRWPort
from domain.exception.exceptions import UnsupportedFileFormat
from domain.export import FileFormat
from domain.file_upload import FileUpload

_TSV_CONTENT_TYPES = ("text/tab-separated-values", "text/tsv")
_EXCEL_CONTENT_TYPES = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
)
_HTML_CONTENT_TYPES = ("text/html", "application/xhtml+xml")
_PDF_CONTENT_TYPES = ("application/pdf", "application/x-pdf")
_OLE2_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_ZIP_SIGNATURE = b"PK\x03\x04"
_HTML_SNIFF_RE = re.compile(
    rb"^\s*(?:<!doctype\s+html|<html\b|<table\b)", re.IGNORECASE
)


def _sniff_stream(upload: FileUpload) -> FileFormat | None:
    if upload.data is None:
        return None
    try:
        upload.data.seek(0)
        head = upload.data.read(512)
        upload.data.seek(0)
    except Exception:
        return None
    if not head:
        return None
    if b"%PDF-" in head:
        return FileFormat.PDF
    if head.startswith((_OLE2_SIGNATURE, _ZIP_SIGNATURE)):
        return FileFormat.XLSX
    if _HTML_SNIFF_RE.search(head):
        return FileFormat.HTML
    return None


def _infer_format(upload: FileUpload) -> FileFormat:
    filename = (upload.filename or "").lower()
    if filename.endswith(".csv"):
        return FileFormat.CSV
    if filename.endswith(".tsv"):
        return FileFormat.TSV
    if filename.endswith((".xlsx", ".xls")):
        return FileFormat.XLSX
    if filename.endswith((".html", ".htm", ".xhtml")):
        return FileFormat.HTML
    if filename.endswith(".pdf"):
        return FileFormat.PDF

    content_type = (upload.content_type or "").split(";", 1)[0].strip().lower()
    if content_type == "text/csv":
        return FileFormat.CSV
    if content_type in _TSV_CONTENT_TYPES:
        return FileFormat.TSV
    if content_type in _EXCEL_CONTENT_TYPES:
        return FileFormat.XLSX
    if content_type in _HTML_CONTENT_TYPES:
        return FileFormat.HTML
    if content_type in _PDF_CONTENT_TYPES:
        return FileFormat.PDF

    sniffed = _sniff_stream(upload)
    if sniffed is not None:
        return sniffed

    raise UnsupportedFileFormat("Unsupported file format")


class TableRWDispatcher(TableRWPort):
    def __init__(self, adapters: dict[FileFormat, TableRWPort]):
        self._adapters = adapters

    async def convert(self, rows: list[list[str]], format: FileFormat) -> bytes:
        adapter = self._adapters.get(format)
        if not adapter:
            raise ValueError(f"No table adapter registered for format {format}")
        return await adapter.convert(rows, format)

    async def parse(self, upload: FileUpload) -> list[list[Any]]:
        detected_format = _infer_format(upload)
        adapter = self._adapters.get(detected_format)
        if not adapter:
            raise UnsupportedFileFormat(
                f"No table adapter registered for format {detected_format}"
            )
        return await adapter.parse(upload)
