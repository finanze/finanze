import codecs
import re
from typing import Optional

_DECLARED_CHARSET = re.compile(
    rb"""(?:charset|encoding)\s*=\s*["']?\s*([A-Za-z0-9_.:\-]+)""", re.IGNORECASE
)
_CHARSET_SNIFF_BYTES = 2048


def sniff_declared_charset(data: bytes) -> Optional[str]:
    match = _DECLARED_CHARSET.search(data[:_CHARSET_SNIFF_BYTES])
    return match.group(1).decode("ascii") if match else None


def decode_text(data: bytes, declared_charset: Optional[str] = None) -> str:
    if data.startswith(codecs.BOM_UTF8):
        return data[len(codecs.BOM_UTF8) :].decode("utf-8", errors="replace")
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return data.decode("utf-16", errors="replace")
    if declared_charset:
        try:
            return data.decode(declared_charset)
        except (LookupError, UnicodeDecodeError):
            pass
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")
