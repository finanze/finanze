import re
from datetime import date, datetime, time
from io import BytesIO
from typing import Any

import xlrd
from application.ports.file_rw_port import TableRWPort
from domain.dezimal import Dezimal
from domain.exception.exceptions import UnsupportedFileFormat
from domain.export import FileFormat
from domain.file_upload import FileUpload
from infrastructure.table.html_table_reader import read_html_tables
from infrastructure.table.spreadsheetml_reader import (
    is_spreadsheetml,
    read_spreadsheetml,
)
from infrastructure.table.text_decoding import decode_text, sniff_declared_charset

try:
    import pandas as pd

    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

try:
    from openpyxl import Workbook, load_workbook

    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

_OLE2_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_ZIP_SIGNATURE = b"PK\x03\x04"
_HTML_TABLE_TAG = re.compile(r"<table\b", re.IGNORECASE)


class XLSXFileTableAdapter(TableRWPort):
    async def convert(self, rows: list[list[str]], format: FileFormat) -> bytes:
        if format != FileFormat.XLSX:
            raise ValueError("XLSXFileTableAdapter only supports XLSX format")

        if not rows:
            raise ValueError("No rows provided for export")

        if HAS_PANDAS:
            return self._convert_with_pandas(rows)
        elif HAS_OPENPYXL:
            return self._convert_with_openpyxl(rows)
        else:
            raise RuntimeError(
                "Neither pandas nor openpyxl is available for XLSX export"
            )

    def _convert_with_pandas(self, rows: list[list[str]]) -> bytes:
        df = pd.DataFrame(rows)
        output = BytesIO()
        pd.DataFrame(df).to_excel(output, header=False, index=False)
        return output.getvalue()

    def _convert_with_openpyxl(self, rows: list[list[str]]) -> bytes:
        wb = Workbook()
        ws = wb.active
        for row in rows:
            ws.append(row)
        output = BytesIO()
        wb.save(output)
        return output.getvalue()

    async def parse(self, upload: FileUpload) -> list[list[Any]]:
        upload.data.seek(0)
        data = upload.data.read()

        if data.startswith(_OLE2_SIGNATURE):
            return _parse_xls(data)
        if data.startswith(_ZIP_SIGNATURE):
            return _parse_xlsx(data)
        return _parse_markup(data)


def _number(value: int | float) -> Dezimal:
    if isinstance(value, float) and value.is_integer():
        return Dezimal(int(value))
    return Dezimal(value)


def _xls_cell(cell: xlrd.sheet.Cell, datemode: int) -> Any:
    if cell.ctype == xlrd.XL_CELL_TEXT:
        return cell.value
    if cell.ctype == xlrd.XL_CELL_NUMBER:
        return _number(cell.value)
    if cell.ctype == xlrd.XL_CELL_DATE:
        try:
            return xlrd.xldate_as_datetime(cell.value, datemode)
        except (xlrd.xldate.XLDateError, ValueError, OverflowError):
            return _number(cell.value)
    if cell.ctype == xlrd.XL_CELL_BOOLEAN:
        return bool(cell.value)
    return ""


def _parse_xls(data: bytes) -> list[list[Any]]:
    try:
        book = xlrd.open_workbook(file_contents=data, on_demand=True)
    except Exception as e:
        raise UnsupportedFileFormat("Invalid XLS file") from e

    try:
        if book.nsheets == 0:
            return []
        sheet = book.sheet_by_index(0)
        return [
            [_xls_cell(cell, book.datemode) for cell in sheet.row(index)]
            for index in range(sheet.nrows)
        ]
    finally:
        book.release_resources()


def _xlsx_cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return _number(value)
    if isinstance(value, (datetime, date, str)):
        return value
    if isinstance(value, time):
        return value.isoformat()
    return str(value)


def _parse_xlsx(data: bytes) -> list[list[Any]]:
    if not HAS_OPENPYXL:
        raise RuntimeError("openpyxl is not available for XLSX parsing")

    try:
        wb = load_workbook(BytesIO(data), read_only=True, data_only=True)
    except Exception as e:
        raise UnsupportedFileFormat("Invalid XLSX file") from e

    try:
        ws = wb.active
        return [
            [_xlsx_cell(cell) for cell in row] for row in ws.iter_rows(values_only=True)
        ]
    finally:
        wb.close()


def _parse_markup(data: bytes) -> list[list[Any]]:
    text = decode_text(data, sniff_declared_charset(data))
    if not text.lstrip().startswith("<"):
        raise UnsupportedFileFormat("Unsupported spreadsheet file format")
    if is_spreadsheetml(text):
        return read_spreadsheetml(text)
    if _HTML_TABLE_TAG.search(text):
        return read_html_tables(text)
    raise UnsupportedFileFormat("Unsupported spreadsheet file format")
