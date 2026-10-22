from urllib.parse import urlsplit, urlunsplit

import httpx
from domain.exception.exceptions import AIProviderError, AIProviderErrorCode

ALLOWED_SCHEMES = ("http", "https")
API_VERSION_PATH = "/v1"
TRANSPORT_ERRORS = (httpx.HTTPError, httpx.InvalidURL)


def normalize_server_url(url: str | None) -> str:
    parts = urlsplit((url or "").strip())
    scheme = parts.scheme.lower()
    if scheme not in ALLOWED_SCHEMES or not parts.hostname:
        raise ValueError("Invalid server URL")
    if parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError("Invalid server URL")
    _ = parts.port
    return urlunsplit((scheme, parts.netloc, parts.path.rstrip("/"), "", ""))


def api_base_url(url: str | None) -> str:
    base = normalize_server_url(url)
    if not urlsplit(base).path:
        base += API_VERSION_PATH
    return base


def server_root_url(url: str | None) -> str:
    root = normalize_server_url(url)
    if root.endswith(API_VERSION_PATH):
        root = root[: -len(API_VERSION_PATH)]
    return root


def unreachable(provider_name: str, error: Exception) -> AIProviderError:
    return AIProviderError(
        AIProviderErrorCode.UNAVAILABLE,
        f"{provider_name} unreachable ({type(error).__name__})",
    )
