import csv
from io import StringIO, TextIOWrapper

from application.ports.file_rw_port import TableRWPort
from domain.export import FileFormat
from domain.file_upload import FileUpload
from domain.exception.exceptions import UnsupportedFileFormat


def _delimiter_for_format(export_format: FileFormat) -> str:
    if export_format == FileFormat.CSV:
        return ","
    elif export_format == FileFormat.TSV:
        return "\t"
    else:
        raise ValueError(f"Unsupported export format: {export_format}")


def _delimiter_from_upload(upload: FileUpload) -> str:
    if upload.content_type in ("text/tab-separated-values", "text/tsv"):
        return "\t"
    if upload.content_type == "text/csv" or upload.filename.endswith(".csv"):
        return ","
    if upload.filename.endswith(".tsv"):
        return "\t"
    raise UnsupportedFileFormat("Unsupported CSV/TSV file format")


class CSVFileTableAdapter(TableRWPort):
    def convert(self, rows: list[list[str]], format: FileFormat) -> bytes:
        if not rows:
            raise ValueError("No rows provided for export")

        delimiter = _delimiter_for_format(format)

        output = StringIO()
        writer = csv.writer(output, delimiter=delimiter)
        for row in rows:
            writer.writerow(row)

        data_str = output.getvalue()
        return data_str.encode("utf-8")

    def parse(self, upload: FileUpload) -> list[list[str]]:
        delimiter = _delimiter_from_upload(upload)
        upload.data.seek(0)
        stream = TextIOWrapper(upload.data, encoding="utf-8")
        reader = csv.reader(stream, delimiter=delimiter)
        return list(reader)
