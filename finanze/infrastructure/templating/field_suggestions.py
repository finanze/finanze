import re
from datetime import date
from typing import Any, Optional

from domain.currency_symbols import CURRENCY_SYMBOL_MAP
from domain.export import NumberFormat
from domain.importing import SuggestedTemplateField, TemplateFieldsSuggestion
from domain.template import missing_required_template_fields
from domain.template_fields import TemplateField, TemplateFieldType
from domain.template_header_aliases import header_alias_score
from domain.transactions import normalize_iban
from infrastructure.templating.cell_values import (
    _UNAMBIGUOUS_SYMBOLS,
    cell_text,
    detect_date_pattern,
    extract_number_currency,
    infer_number_format,
    is_empty_cell,
    parse_number,
    parse_with_date_pattern,
)

HEADER_SCAN_ROWS = 50
SAMPLE_SIZE = 20

_NUMBER_TYPES = (TemplateFieldType.DECIMAL, TemplateFieldType.INTEGER)
_DATE_TYPES = (TemplateFieldType.DATE, TemplateFieldType.DATETIME)

_ISIN_PATTERN = re.compile(r"[A-Z]{2}[A-Z0-9]{9}\d")
_IBAN_PATTERN = re.compile(r"[A-Z]{2}\d{2}[A-Z0-9]{10,30}")
_BOOLEAN_VALUES = {"true", "false", "1", "0", "yes", "no"}
_BRACKETED_ISO_RE = re.compile(r"[\(\[\{]\s*([A-Za-z]{3})\s*[\)\]\}]")
_LABELED_CURRENCY_RE = re.compile(
    r"\b(?:divisa|moneda|currency|ccy|valuta|w[aä]hrung|devise|moeda)\s*[:=-]?\s*([A-Za-z]{3})\b",
    re.IGNORECASE,
)
_PREAMBLE_ISO_RE = re.compile(
    r"\b(EUR|USD|GBP|CHF|JPY|CAD|AUD|SEK|NOK|DKK|PLN|CZK|HUF|RON|BGN|BRL|MXN|CNY|HKD|SGD|NZD|KRW|INR|ILS|ZAR)\b"
)


def _is_number(value: Any) -> bool:
    try:
        parse_number(value, NumberFormat.ENGLISH)
        return True
    except (ValueError, TypeError):
        return False


def _is_date(value: Any, pattern: Optional[str]) -> bool:
    if isinstance(value, date):
        return True
    if pattern is None or not isinstance(value, str):
        return False
    try:
        parse_with_date_pattern(value, pattern)
        return True
    except ValueError:
        return False


def _is_iban(value: Any) -> bool:
    normalized = normalize_iban(cell_text(value))
    return normalized is not None and _IBAN_PATTERN.fullmatch(normalized) is not None


def _matching_count(field: TemplateField, samples: list[Any]) -> int:
    field_type = field.type
    if field_type in _NUMBER_TYPES:
        return sum(1 for value in samples if _is_number(value))
    if field_type in _DATE_TYPES:
        pattern = detect_date_pattern(samples)
        return sum(1 for value in samples if _is_date(value, pattern))
    if field_type == TemplateFieldType.CURRENCY:
        return sum(
            1
            for value in samples
            if cell_text(value).strip().upper() in CURRENCY_SYMBOL_MAP
        )
    if field_type == TemplateFieldType.ENUM:
        values = {item.value for item in field.enum} if field.enum else set()
        return sum(1 for value in samples if cell_text(value).strip().upper() in values)
    if field_type == TemplateFieldType.BOOLEAN:
        return sum(
            1
            for value in samples
            if isinstance(value, bool)
            or cell_text(value).strip().lower() in _BOOLEAN_VALUES
        )
    if field.field == "isin":
        return sum(
            1
            for value in samples
            if _ISIN_PATTERN.fullmatch(cell_text(value).strip().upper())
        )
    if field.field == "iban":
        return sum(1 for value in samples if _is_iban(value))
    return len(samples)


def _matched_fields(row: list[Any], fields: list[TemplateField]) -> set[str]:
    matched = set()
    for value in row:
        if is_empty_cell(value):
            continue
        text = cell_text(value)
        for field in fields:
            if header_alias_score(field.field, text) is not None:
                matched.add(field.field)
    return matched


def _find_header_row(
    table: list[list[Any]], fields: list[TemplateField]
) -> Optional[int]:
    first_index = None
    best_index = None
    best_count = 1
    scanned = 0
    for index, row in enumerate(table):
        if all(is_empty_cell(value) for value in row):
            continue
        if first_index is None:
            first_index = index
        count = len(_matched_fields(row, fields))
        if count > best_count:
            best_index = index
            best_count = count
        scanned += 1
        if scanned >= HEADER_SCAN_ROWS:
            break
    return best_index if best_index is not None else first_index


def _column_samples(rows: list[list[Any]], column: int) -> list[Any]:
    samples = []
    for row in rows:
        if column < len(row) and not is_empty_cell(row[column]):
            samples.append(row[column])
            if len(samples) >= SAMPLE_SIZE:
                break
    return samples


def _column_values(rows: list[list[Any]], column: int) -> list[Any]:
    return [
        row[column]
        for row in rows
        if column < len(row) and not is_empty_cell(row[column])
    ]


def _detect_formats(
    rows: list[list[Any]], assigned: dict[int, TemplateField]
) -> tuple[Optional[NumberFormat], Optional[str]]:
    number_values = []
    date_format = None
    for column in sorted(assigned):
        field_type = assigned[column].type
        if field_type in _NUMBER_TYPES:
            number_values.extend(_column_values(rows, column))
        elif field_type in _DATE_TYPES and date_format is None:
            date_format = detect_date_pattern(_column_values(rows, column))
    return infer_number_format(number_values), date_format


def _header_currency_hint(header: str) -> Optional[str]:
    for symbol, code in _UNAMBIGUOUS_SYMBOLS.items():
        if symbol in header:
            return code
    for match in _BRACKETED_ISO_RE.findall(header):
        upper = match.upper()
        if upper in CURRENCY_SYMBOL_MAP:
            return upper
    return None


def _detect_currency(
    table: list[list[Any]],
    header_index: int,
    header_row: list[Any],
    data_rows: list[list[Any]],
    assigned: dict[int, TemplateField],
) -> Optional[str]:
    for column, field in assigned.items():
        if field.type == TemplateFieldType.CURRENCY:
            codes = {
                cell_text(val).strip().upper()
                for val in _column_samples(data_rows, column)
                if cell_text(val).strip().upper() in CURRENCY_SYMBOL_MAP
            }
            return codes.pop() if len(codes) == 1 else None

    header_codes = {
        code
        for column, field in assigned.items()
        if field.type in _NUMBER_TYPES and column < len(header_row)
        for code in (_header_currency_hint(cell_text(header_row[column])),)
        if code is not None
    }
    if len(header_codes) == 1:
        return header_codes.pop()

    value_codes = {
        code
        for column, field in assigned.items()
        if field.type in _NUMBER_TYPES
        for sample in _column_samples(data_rows, column)
        for code in (extract_number_currency(sample),)
        if code is not None
    }
    if len(value_codes) == 1:
        return value_codes.pop()

    preamble_labeled = set()
    preamble_iso = set()
    for row in table[:header_index]:
        line = " ".join(cell_text(c).strip() for c in row if not is_empty_cell(c))
        if not line:
            continue
        for match in _LABELED_CURRENCY_RE.findall(line):
            upper = match.upper()
            if upper in CURRENCY_SYMBOL_MAP:
                preamble_labeled.add(upper)
        for match in _PREAMBLE_ISO_RE.findall(line):
            preamble_iso.add(match)
        if "€" in line:
            preamble_iso.add("EUR")
    if len(preamble_labeled) == 1:
        return preamble_labeled.pop()
    if len(preamble_iso) == 1:
        return preamble_iso.pop()
    return None


def suggest_template_fields(
    table: list[list[Any]], fields: list[TemplateField]
) -> TemplateFieldsSuggestion:
    header_index = _find_header_row(table, fields)
    if header_index is None:
        return TemplateFieldsSuggestion(
            headers=[],
            fields=[],
            missing_required_fields=missing_required_template_fields(fields, set()),
        )

    header_row = table[header_index]
    data_rows = [
        row
        for row in table[header_index + 1 :]
        if not all(is_empty_cell(value) for value in row)
    ]

    headers = []
    candidates = []
    for column, value in enumerate(header_row):
        header = cell_text(value).strip()
        if not header:
            continue
        headers.append(header)
        for field in fields:
            score = header_alias_score(field.field, header)
            if score is None:
                continue
            priority = 0 if field.required or field.or_requires else 1
            candidates.append(((priority, *score, column), field, column))

    candidates.sort(key=lambda candidate: candidate[0])
    samples_by_column: dict[int, list[Any]] = {}
    assigned_fields = set()
    assigned: dict[int, TemplateField] = {}
    for _, field, column in candidates:
        if field.field in assigned_fields or column in assigned:
            continue
        if data_rows:
            if column not in samples_by_column:
                samples_by_column[column] = _column_samples(data_rows, column)
            samples = samples_by_column[column]
            if not samples or _matching_count(field, samples) * 2 <= len(samples):
                continue
        assigned_fields.add(field.field)
        assigned[column] = field

    if "amount" not in assigned_fields and (
        ("amount_in" in assigned_fields) ^ ("amount_out" in assigned_fields)
    ):
        sibling = "amount_out" if "amount_in" in assigned_fields else "amount_in"
        for score_tuple, field, column in candidates:
            if (
                field.field == sibling
                and column not in assigned
                and score_tuple[2] == 0
                and not samples_by_column.get(
                    column, _column_samples(data_rows, column)
                )
            ):
                assigned_fields.add(sibling)
                assigned[column] = field
                break

    number_format, date_format = _detect_formats(data_rows, assigned)
    detected_currency = _detect_currency(
        table, header_index, header_row, data_rows, assigned
    )
    missing_required = missing_required_template_fields(fields, assigned_fields)
    return TemplateFieldsSuggestion(
        headers=headers,
        fields=[
            SuggestedTemplateField(
                field=assigned[column].field,
                name=cell_text(header_row[column]).strip(),
            )
            for column in sorted(assigned)
        ],
        number_format=number_format,
        date_format=date_format,
        detected_currency=detected_currency,
        missing_required_fields=missing_required,
    )
