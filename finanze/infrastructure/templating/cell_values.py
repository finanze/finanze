import re
import unicodedata
from datetime import date, datetime, time
from typing import Any, Iterable, Optional

from domain.currency_symbols import CURRENCY_SYMBOL_MAP
from domain.dezimal import Dezimal
from domain.export import NumberFormat

ISO_DATE_PATTERN = "ISO"

_DATE_PATTERNS = (
    ISO_DATE_PATTERN,
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%d/%m/%y",
    "%d-%m-%y",
    "%d.%m.%y",
    "%Y/%m/%d",
    "%Y.%m.%d",
    "%m/%d/%Y",
    "%m-%d-%Y",
    "%m.%d.%Y",
    "%m/%d/%y",
    "%m-%d-%y",
    "%m.%d.%y",
    "%Y%m%d",
)
_TIME_SUFFIXES = (" %H:%M:%S", " %H:%M")
_DATE_SAMPLE_LIMIT = 200

_SCIENTIFIC_NUMBER = re.compile(r"[+-]?\d+(\.\d+)?[eE][+-]?\d+")
_CURRENCY_AFFIX = re.compile(r"^[A-Za-z]{2,3}|[A-Za-z]{2,3}$")
_NUMBER_BODY = re.compile(r"[\d.,]*\d[\d.,]*")
_NUMBER_IGNORED_CHARS = ("'", "\u2019")

_UNAMBIGUOUS_SYMBOLS: dict[str, str] = {
    "€": "EUR",
    "£": "GBP",
    "₹": "INR",
    "₪": "ILS",
    "₩": "KRW",
    "₺": "TRY",
    "₴": "UAH",
    "₿": "BTC",
    "Ξ": "ETH",
    "Kč": "CZK",
    "zł": "PLN",
    "R$": "BRL",
}

_MONTH_TOKENS: dict[str, str] = {
    "ene": "01",
    "enero": "01",
    "jan": "01",
    "january": "01",
    "gen": "01",
    "gennaio": "01",
    "januar": "01",
    "janv": "01",
    "janvier": "01",
    "janeiro": "01",
    "feb": "02",
    "febrero": "02",
    "february": "02",
    "febbraio": "02",
    "februar": "02",
    "fev": "02",
    "fevr": "02",
    "fevrier": "02",
    "fevereiro": "02",
    "mar": "03",
    "marzo": "03",
    "march": "03",
    "marz": "03",
    "maerz": "03",
    "mars": "03",
    "marco": "03",
    "abr": "04",
    "abril": "04",
    "apr": "04",
    "april": "04",
    "aprile": "04",
    "avr": "04",
    "avril": "04",
    "may": "05",
    "mayo": "05",
    "mag": "05",
    "maggio": "05",
    "mai": "05",
    "maio": "05",
    "jun": "06",
    "junio": "06",
    "june": "06",
    "giu": "06",
    "giugno": "06",
    "juni": "06",
    "juin": "06",
    "junho": "06",
    "jul": "07",
    "julio": "07",
    "july": "07",
    "lug": "07",
    "luglio": "07",
    "juli": "07",
    "juil": "07",
    "juillet": "07",
    "julho": "07",
    "ago": "08",
    "agosto": "08",
    "aug": "08",
    "august": "08",
    "aout": "08",
    "sep": "09",
    "sept": "09",
    "septiembre": "09",
    "setiembre": "09",
    "september": "09",
    "set": "09",
    "settembre": "09",
    "septembre": "09",
    "setembro": "09",
    "oct": "10",
    "octubre": "10",
    "october": "10",
    "ott": "10",
    "ottobre": "10",
    "okt": "10",
    "oktober": "10",
    "octobre": "10",
    "out": "10",
    "outubro": "10",
    "nov": "11",
    "noviembre": "11",
    "november": "11",
    "novembre": "11",
    "novembro": "11",
    "dic": "12",
    "diciembre": "12",
    "dec": "12",
    "december": "12",
    "dez": "12",
    "dezember": "12",
    "decembre": "12",
    "dezembro": "12",
}

_DAY_MONTH_YEAR_TEXT_RE = re.compile(
    r"^(\d{1,2})(?:[\s./-]+(?:de|del)?[\s./-]*)([A-Za-zÀ-ÿ]+)\.?(?:[\s./-]+(?:de|del)?[\s./-]*)(\d{2}|\d{4})((?:\s+\d{1,2}:\d{2}(?::\d{2})?)?)$",
    re.IGNORECASE,
)
_MONTH_DAY_YEAR_TEXT_RE = re.compile(
    r"^([A-Za-zÀ-ÿ]+)\.?\s+(\d{1,2}),?\s+(\d{2}|\d{4})((?:\s+\d{1,2}:\d{2}(?::\d{2})?)?)$",
    re.IGNORECASE,
)


def is_empty_cell(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def cell_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        if value.tzinfo is None and value.time() == time():
            return value.date().isoformat()
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def display_row(row: list[Any]) -> list[str]:
    return [cell_text(value) for value in row]


def _number_body(value: str) -> tuple[str, bool]:
    text = "".join(
        ch
        for ch in value
        if not ch.isspace()
        and ch not in _NUMBER_IGNORED_CHARS
        and unicodedata.category(ch) != "Sc"
    )
    negative = False
    if len(text) > 2 and text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1]
    text = _CURRENCY_AFFIX.sub("", text)
    if text.startswith("+"):
        text = text[1:]
    elif text.startswith("-"):
        negative = not negative
        text = text[1:]
    elif text.endswith("-"):
        negative = not negative
        text = text[:-1]
    if not _NUMBER_BODY.fullmatch(text):
        raise ValueError(f"Invalid number: {value}")
    return text, negative


def extract_number_currency(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped:
        return None
    for symbol, code in _UNAMBIGUOUS_SYMBOLS.items():
        if symbol in stripped:
            try:
                _number_body(stripped)
                return code
            except ValueError:
                return None

    compact = "".join(
        ch
        for ch in stripped
        if not ch.isspace()
        and ch not in _NUMBER_IGNORED_CHARS
        and unicodedata.category(ch) != "Sc"
    )
    if len(compact) > 2 and compact.startswith("(") and compact.endswith(")"):
        compact = compact[1:-1]
    if compact.startswith(("+", "-")):
        compact = compact[1:]
    match = _CURRENCY_AFFIX.search(compact)
    if not match:
        return None
    candidate = match.group(0).upper()
    if len(candidate) != 3 or candidate not in CURRENCY_SYMBOL_MAP:
        return None
    try:
        _number_body(stripped)
    except ValueError:
        return None
    return candidate


def parse_number(value: Any, number_format: NumberFormat) -> Dezimal:
    if isinstance(value, Dezimal):
        return value
    if isinstance(value, bool):
        raise ValueError(f"Invalid number: {value}")
    if not isinstance(value, str):
        return Dezimal(value)

    text = value.strip()
    if _SCIENTIFIC_NUMBER.fullmatch(text):
        return Dezimal(text)

    body, negative = _number_body(text)
    if number_format == NumberFormat.EUROPEAN:
        body = body.replace(".", "").replace(",", ".")
    else:
        body = body.replace(",", "")

    number = Dezimal(body)
    return -number if negative and number != 0 else number


def _decimal_separator_hint(value: str) -> Optional[NumberFormat]:
    try:
        body, _ = _number_body(value.strip())
    except ValueError:
        return None

    last_dot = body.rfind(".")
    last_comma = body.rfind(",")
    if last_dot >= 0 and last_comma >= 0:
        return NumberFormat.EUROPEAN if last_comma > last_dot else NumberFormat.ENGLISH

    separator = "." if last_dot >= 0 else "," if last_comma >= 0 else None
    if separator is None:
        return None

    parts = body.split(separator)
    decimal_format = NumberFormat.ENGLISH if separator == "." else NumberFormat.EUROPEAN
    thousands_format = (
        NumberFormat.EUROPEAN if separator == "." else NumberFormat.ENGLISH
    )
    if len(parts) > 2:
        return thousands_format

    integer, fraction = parts
    if len(fraction) == 3 and 0 < len(integer) <= 3 and integer != "0":
        return None
    return decimal_format


def infer_number_format(values: Iterable[Any]) -> Optional[NumberFormat]:
    hints = {
        _decimal_separator_hint(value) for value in values if isinstance(value, str)
    }
    hints.discard(None)
    return hints.pop() if len(hints) == 1 else None


def _strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value).casefold()
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def normalize_textual_date(value: str) -> str:
    text = " ".join(value.split())
    if not any(ch.isalpha() for ch in text if ch not in "TZtz"):
        return text

    match = _DAY_MONTH_YEAR_TEXT_RE.match(text)
    if match:
        day, month_raw, year, time_part = match.groups()
        month = _MONTH_TOKENS.get(_strip_accents(month_raw))
        if month is not None:
            return f"{int(day):02d}/{month}/{year}{time_part}"

    match = _MONTH_DAY_YEAR_TEXT_RE.match(text)
    if match:
        month_raw, day, year, time_part = match.groups()
        month = _MONTH_TOKENS.get(_strip_accents(month_raw))
        if month is not None:
            return f"{month}/{int(day):02d}/{year}{time_part}"

    return text


def parse_datetime(value: str, date_format: Optional[str]) -> datetime:
    if date_format is None:
        normalized = normalize_textual_date(value)
        return datetime.fromisoformat(normalized)
    return datetime.strptime(value, date_format)


def parse_with_date_pattern(value: str, pattern: str) -> datetime:
    text = normalize_textual_date(value)
    if pattern == ISO_DATE_PATTERN:
        return datetime.fromisoformat(text)
    if ":" not in text:
        return datetime.strptime(text, pattern)
    for suffix in _TIME_SUFFIXES:
        try:
            return datetime.strptime(text, pattern + suffix)
        except ValueError:
            continue
    raise ValueError(f"Invalid date: {value}")


def _pattern_applies(pattern: str, value: str) -> bool:
    if pattern == ISO_DATE_PATTERN:
        return True
    if pattern == "%Y%m%d":
        return value[:8].isdigit()
    return pattern[2] in value


def detect_date_pattern(values: Iterable[Any]) -> Optional[str]:
    samples = []
    for value in values:
        if isinstance(value, str) and value.strip():
            samples.append(normalize_textual_date(value))
            if len(samples) >= _DATE_SAMPLE_LIMIT:
                break
    if not samples:
        return None

    best_pattern = None
    best_count = 0
    for pattern in _DATE_PATTERNS:
        count = 0
        for sample in samples:
            if not _pattern_applies(pattern, sample):
                continue
            try:
                parse_with_date_pattern(sample, pattern)
                count += 1
            except ValueError:
                continue
        if count > best_count:
            best_pattern = pattern
            best_count = count
            if count == len(samples):
                break
    return best_pattern
