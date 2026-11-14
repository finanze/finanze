import re
from datetime import datetime
from typing import Any, Optional
from xml.etree import ElementTree

from domain.dezimal import Dezimal
from domain.exception.exceptions import UnsupportedFileFormat

SPREADSHEETML_NAMESPACE = "urn:schemas-microsoft-com:office:spreadsheet"

_NS = f"{{{SPREADSHEETML_NAMESPACE}}}"
_FORBIDDEN_DECLARATIONS = re.compile(r"<!\s*(DOCTYPE|ENTITY)", re.IGNORECASE)
_WORKBOOK_TAG = re.compile(r"<(\w+:)?Workbook\b")
_DETECTION_CHARS = 8192
_MAX_PADDING = 1000


def is_spreadsheetml(text: str) -> bool:
    head = text[:_DETECTION_CHARS]
    return SPREADSHEETML_NAMESPACE in head and bool(_WORKBOOK_TAG.search(head))


def _index(element: ElementTree.Element) -> Optional[int]:
    raw = element.get(f"{_NS}Index")
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _span(element: ElementTree.Element) -> int:
    try:
        return min(max(int(element.get(f"{_NS}MergeAcross", "0")), 0), _MAX_PADDING)
    except ValueError:
        return 0


def _cell_value(cell: ElementTree.Element) -> Any:
    data = cell.find(f"{_NS}Data")
    if data is None:
        return ""
    text = "".join(data.itertext()).strip()
    if not text:
        return ""
    data_type = data.get(f"{_NS}Type")
    try:
        if data_type == "Number":
            return Dezimal(text)
        if data_type == "DateTime":
            return datetime.fromisoformat(text)
        if data_type == "Boolean":
            return text == "1"
    except ValueError:
        return text
    return text


def _padding(current_length: int, index: Optional[int]) -> int:
    if index is None:
        return 0
    return max(0, min(index - 1 - current_length, _MAX_PADDING))


def read_spreadsheetml(text: str) -> list[list[Any]]:
    if _FORBIDDEN_DECLARATIONS.search(text):
        raise UnsupportedFileFormat("XML declarations are not allowed")
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as e:
        raise UnsupportedFileFormat("Invalid SpreadsheetML file") from e

    worksheet = root.find(f"{_NS}Worksheet")
    table = worksheet.find(f"{_NS}Table") if worksheet is not None else None
    if table is None:
        return []

    rows: list[list[Any]] = []
    for row in table.findall(f"{_NS}Row"):
        rows.extend([] for _ in range(_padding(len(rows), _index(row))))
        values: list[Any] = []
        for cell in row.findall(f"{_NS}Cell"):
            values.extend([""] * _padding(len(values), _index(cell)))
            values.append(_cell_value(cell))
            values.extend([""] * _span(cell))
        rows.append(values)
    return rows
