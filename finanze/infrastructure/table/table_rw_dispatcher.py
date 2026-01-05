from application.ports.file_rw_port import TableRWPort
from domain.exception.exceptions import UnsupportedFileFormat
from domain.export import FileFormat
from domain.file_upload import FileUpload


def _infer_format(upload: FileUpload) -> FileFormat:
    if upload.filename.endswith(".csv") or upload.content_type == "text/csv":
        return FileFormat.CSV
    if upload.filename.endswith(".tsv") or upload.content_type in (
        "text/tab-separated-values",
        "text/tsv",
    ):
        return FileFormat.TSV
    if upload.filename.endswith(".xlsx") or upload.content_type in (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ):
        return FileFormat.XLSX
    raise UnsupportedFileFormat("Unsupported file format")


class TableRWDispatcher(TableRWPort):
    def __init__(self, adapters: dict[FileFormat, TableRWPort]):
        self._adapters = adapters

    async def convert(self, rows: list[list[str]], format: FileFormat) -> bytes:
        adapter = self._adapters.get(format)
        if not adapter:
            raise ValueError(f"No table adapter registered for format {format}")
        return await adapter.convert(rows, format)

    async def parse(self, upload: FileUpload) -> list[list[str]]:
        detected_format = _infer_format(upload)
        adapter = self._adapters.get(detected_format)
        if not adapter:
            raise UnsupportedFileFormat(
                f"No table adapter registered for format {detected_format}"
            )
        return await adapter.parse(upload)
