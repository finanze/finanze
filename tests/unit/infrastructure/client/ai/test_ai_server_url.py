import httpx
import pytest
from domain.exception.exceptions import AIProviderErrorCode
from infrastructure.client.ai.server_url import (
    api_base_url,
    normalize_server_url,
    server_root_url,
    unreachable,
)


class TestNormalizeServerUrl:
    @pytest.mark.parametrize(
        "url, expected",
        [
            ("http://localhost:8080", "http://localhost:8080"),
            ("  HTTP://localhost:8080/  ", "http://localhost:8080"),
            ("https://ai.example.com/api/v1/", "https://ai.example.com/api/v1"),
            ("http://[::1]:11434", "http://[::1]:11434"),
        ],
    )
    def test_normalizes_valid_urls(self, url, expected):
        assert normalize_server_url(url) == expected

    @pytest.mark.parametrize(
        "url",
        [
            None,
            "",
            "localhost:8080",
            "ftp://localhost",
            "file:///etc/passwd",
            "http://",
            "http://user:pass@localhost:8080",
            "http://localhost:8080/?key=1",
            "http://localhost:8080/#frag",
            "http://localhost:99999",
            "http://localhost:abc",
        ],
    )
    def test_rejects_invalid_urls(self, url):
        with pytest.raises(ValueError):
            normalize_server_url(url)


class TestApiBaseUrl:
    def test_appends_version_when_no_path(self):
        assert api_base_url("http://localhost:1234/") == "http://localhost:1234/v1"

    def test_keeps_explicit_path(self):
        assert api_base_url("https://host/openai/v1") == "https://host/openai/v1"
        assert api_base_url("https://host/custom") == "https://host/custom"


class TestServerRootUrl:
    def test_strips_version_suffix(self):
        assert server_root_url("http://localhost:8080/v1/") == "http://localhost:8080"

    def test_keeps_other_paths(self):
        assert server_root_url("http://host/llama") == "http://host/llama"


def test_unreachable_maps_to_unavailable():
    error = unreachable("Custom endpoint", httpx.ConnectError("refused"))
    assert error.code == AIProviderErrorCode.UNAVAILABLE
    assert error.details == "Custom endpoint unreachable (ConnectError)"
