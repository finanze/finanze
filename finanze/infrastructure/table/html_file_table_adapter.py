import re
from typing import Any

from application.ports.file_rw_port import TableRWPort
from domain.exception.exceptions import NoTableFound
from domain.export import FileFormat
from domain.file_upload import FileUpload
from infrastructure.table.html_table_reader import read_html_tables
from infrastructure.table.text_decoding import decode_text, sniff_declared_charset

_HTML_TABLE_TAG = re.compile(r"<table\b", re.IGNORECASE)


class HTMLFileTableAdapter(TableRWPort):
    async def convert(self, rows: list[list[str]], format: FileFormat) -> bytes:
        raise ValueError("HTMLFileTableAdapter does not support export")

    async def parse(self, upload: FileUpload) -> list[list[Any]]:
        upload.data.seek(0)
        data = upload.data.read()
        text = decode_text(data, sniff_declared_charset(data))
        if not _HTML_TABLE_TAG.search(text):
            raise NoTableFound("No HTML table found")
        rows = read_html_tables(text)
        if not rows:
            raise NoTableFound("No HTML table rows found")
        return rows
