import re
from typing import Any

REDACTED = "[redacted]"
MAX_STRING_LENGTH = 500
MAX_COLLECTION_ITEMS = 50

_DENY_KEY_PARTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "auth",
    "cookie",
    "credential",
    "api_key",
    "apikey",
    "private_key",
    "privatekey",
    "mnemonic",
    "seed",
    "xpub",
    "xprv",
    "iban",
    "account_number",
    "card",
    "cvv",
    "email",
    "phone",
    "address",
    "ssn",
    "pin",
    "otp",
    "signature",
    "jwt",
    "bearer",
    "session",
)

_IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b")
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_LONG_HEX_RE = re.compile(r"\b(?:0x)?[0-9a-fA-F]{26,}\b")
_BEARER_RE = re.compile(r"(?i)\b(?:bearer|basic)\s+[A-Za-z0-9._\-+/=]+")


def is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in _DENY_KEY_PARTS)


def scrub_text(text: str) -> str:
    scrubbed = _BEARER_RE.sub(REDACTED, text)
    scrubbed = _IBAN_RE.sub(REDACTED, scrubbed)
    scrubbed = _EMAIL_RE.sub(REDACTED, scrubbed)
    scrubbed = _LONG_HEX_RE.sub(REDACTED, scrubbed)

    if len(scrubbed) > MAX_STRING_LENGTH:
        scrubbed = scrubbed[:MAX_STRING_LENGTH] + "..."

    return scrubbed


def scrub(value: Any, key: str | None = None) -> Any:
    if key is not None and is_sensitive_key(key):
        return REDACTED

    if isinstance(value, str):
        return scrub_text(value)

    if isinstance(value, dict):
        return {k: scrub(v, str(k)) for k, v in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [scrub(v) for v in list(value)[:MAX_COLLECTION_ITEMS]]

    if isinstance(value, (int, float, bool)) or value is None:
        return value

    return scrub_text(str(value))
