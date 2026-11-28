import re
from collections import Counter
from datetime import datetime, time
from typing import Optional

from domain.dezimal import Dezimal
from domain.export import NumberFormat
from domain.template_fields import TemplateFieldType
from domain.transactions import TxType
from infrastructure.ai_import.import_schema import BALANCE_FIELD, REF_FIELD
from infrastructure.templating.cell_values import (
    decimal_separator_hint,
    detect_date_pattern,
    parse_number,
    parse_with_date_pattern,
)

NUMBER_TYPES = {TemplateFieldType.DECIMAL, TemplateFieldType.INTEGER}
DATE_TYPES = {TemplateFieldType.DATE, TemplateFieldType.DATETIME}
IBAN_FIELD = "iban"
IBAN_SHAPE = re.compile(r"[A-Z]{2}\d{2}[A-Z0-9]{10,30}")
INFLOW_CONFLICTS = {TxType.OUTFLOW.value, TxType.FEE.value}
OUTFLOW_CONFLICTS = {TxType.INFLOW.value}

ExtractedRow = dict[str, str]


def cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).strip()


# Ambiguous values like "3.000" follow the separator style of the rest of the response
def canonical_numbers(values: list[str]) -> list[str]:
    hints = [decimal_separator_hint(value) if value else None for value in values]
    counts = Counter(hint for hint in hints if hint is not None)
    majority = counts.most_common(1)[0][0] if counts else NumberFormat.ENGLISH
    result = []
    for value, hint in zip(values, hints):
        if not value:
            result.append(value)
            continue
        try:
            result.append(str(parse_number(value, hint or majority)))
        except ValueError:
            result.append(value)
    return result


def _is_iso(value: str) -> bool:
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return False
    return True


def canonical_dates(values: list[str]) -> list[str]:
    pending = [bool(value) and not _is_iso(value) for value in values]
    pattern = detect_date_pattern(
        [value for value, todo in zip(values, pending) if todo]
    )
    if pattern is None:
        return values
    result = []
    for value, todo in zip(values, pending):
        if not todo:
            result.append(value)
            continue
        try:
            parsed = parse_with_date_pattern(value, pattern)
        except ValueError:
            result.append(value)
            continue
        result.append(
            parsed.date().isoformat() if parsed.time() == time() else parsed.isoformat()
        )
    return result


def _iban(value: str) -> str:
    compact = "".join(value.split()).upper()
    return compact if IBAN_SHAPE.fullmatch(compact) else ""


# Each model response is normalized on its own, as formats can differ between pages
def normalize_response(
    raw_rows: list[dict], types: dict[str, TemplateFieldType]
) -> list[ExtractedRow]:
    rows = []
    for raw in raw_rows:
        row = {name: cell(raw.get(name)) for name in types}
        if any(value for name, value in row.items() if name != BALANCE_FIELD):
            rows.append(row)
    for name, kind in types.items():
        if kind in NUMBER_TYPES:
            convert = canonical_numbers
        elif kind in DATE_TYPES:
            convert = canonical_dates
        else:
            continue
        for row, value in zip(rows, convert([row[name] for row in rows])):
            row[name] = value
    for row in rows:
        if row.get(IBAN_FIELD):
            row[IBAN_FIELD] = _iban(row[IBAN_FIELD])
    return rows


def _number(value: Optional[str]) -> Optional[Dezimal]:
    try:
        return Dezimal(value) if value else None
    except ValueError:
        return None


def _balance_signs(
    amounts: list[Optional[Dezimal]], balances: list[Optional[Dezimal]]
) -> dict[int, int]:
    forward: dict[int, int] = {}
    backward: dict[int, int] = {}
    for index in range(1, len(amounts)):
        previous, current = balances[index - 1], balances[index]
        if previous is None or current is None or current == previous:
            continue
        delta = current - previous
        sign = 1 if delta > 0 else -1
        if amounts[index] is not None and abs(amounts[index]) == abs(delta):
            forward[index] = sign
        if amounts[index - 1] is not None and abs(amounts[index - 1]) == abs(delta):
            backward[index - 1] = -sign
    # Newest-first statements chain balances backwards, the orientation with more matches wins
    if len(forward) > len(backward):
        return forward
    if len(backward) > len(forward):
        return backward
    return {}


# Running balances printed on the rows settle the direction when the model read it wrong
def apply_balance_directions(rows: list[ExtractedRow]):
    amounts = [_number(row.get("amount")) for row in rows]
    balances = [_number(row.get(BALANCE_FIELD)) for row in rows]
    for index, sign in _balance_signs(amounts, balances).items():
        row = rows[index]
        amount = abs(amounts[index])
        row["amount"] = str(amount if sign > 0 else -amount)
        conflicts = INFLOW_CONFLICTS if sign > 0 else OUTFLOW_CONFLICTS
        if row.get("type", "").upper() in conflicts:
            row["type"] = ""


def drop_shared_refs(rows: list[ExtractedRow]):
    contents: dict[str, set[tuple]] = {}
    for row in rows:
        ref = row.get(REF_FIELD)
        if ref:
            contents.setdefault(ref, set()).add(
                (row.get("date"), row.get("amount"), row.get("name"))
            )
    shared = {ref for ref, values in contents.items() if len(values) > 1}
    for row in rows:
        if row.get(REF_FIELD) in shared:
            row[REF_FIELD] = ""
