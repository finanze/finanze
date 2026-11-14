import csv
from collections import Counter
from io import StringIO
from itertools import islice

from application.ports.file_rw_port import TableRWPort
from domain.export import FileFormat
from domain.file_upload import FileUpload
from domain.exception.exceptions import UnsupportedFileFormat
from infrastructure.table.text_decoding import decode_text

_TSV_CONTENT_TYPES = ("text/tab-separated-values", "text/tsv")
_DELIMITER_CANDIDATES = (",", ";", "\t", "|")
_DELIMITER_SAMPLE_ROWS = 100


def _delimiter_for_format(export_format: FileFormat) -> str:
    if export_format == FileFormat.CSV:
        return ","
    elif export_format == FileFormat.TSV:
        return "\t"
    else:
        raise ValueError(f"Unsupported export format: {export_format}")


def _is_tsv(upload: FileUpload) -> bool:
    return (upload.filename or "").lower().endswith(
        ".tsv"
    ) or upload.content_type in _TSV_CONTENT_TYPES


def _detect_delimiter(text: str) -> str:
    best_delimiter = _DELIMITER_CANDIDATES[0]
    best_score = 0
    for delimiter in _DELIMITER_CANDIDATES:
        reader = csv.reader(StringIO(text, newline=""), delimiter=delimiter)
        column_counts = Counter(
            len(row) for row in islice(reader, _DELIMITER_SAMPLE_ROWS) if len(row) > 1
        )
        if not column_counts:
            continue
        columns, frequency = column_counts.most_common(1)[0]
        score = columns * frequency
        if score > best_score:
            best_delimiter = delimiter
            best_score = score
    return best_delimiter


class CSVFileTableAdapter(TableRWPort):
    async def convert(self, rows: list[list[str]], format: FileFormat) -> bytes:
        if not rows:
            raise ValueError("No rows provided for export")

        delimiter = _delimiter_for_format(format)

        output = StringIO()
        writer = csv.writer(output, delimiter=delimiter)
        for row in rows:
            writer.writerow(row)

        data_str = output.getvalue()
        return data_str.encode("utf-8-sig")

    async def parse(self, upload: FileUpload) -> list[list[str]]:
        upload.data.seek(0)
        text = decode_text(upload.data.read())
        try:
            delimiter = "\t" if _is_tsv(upload) else _detect_delimiter(text)
            return list(csv.reader(StringIO(text, newline=""), delimiter=delimiter))
        except csv.Error as e:
            raise UnsupportedFileFormat("Invalid CSV/TSV file") from e
