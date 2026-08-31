import pytest

from infrastructure.telemetry.scrubbing import (
    MAX_STRING_LENGTH,
    REDACTED,
    is_sensitive_key,
    scrub,
    scrub_text,
)


class TestIsSensitiveKey:
    @pytest.mark.parametrize(
        "key",
        [
            "password",
            "userPassword",
            "access_token",
            "Authorization",
            "iban",
            "account_number",
            "mnemonic",
            "private_key",
            "email",
            "cookie",
        ],
    )
    def test_detects_sensitive_keys(self, key):
        assert is_sensitive_key(key)

    @pytest.mark.parametrize("key", ["entity", "amount", "route", "http_method"])
    def test_allows_safe_keys(self, key):
        assert not is_sensitive_key(key)


class TestScrubText:
    def test_redacts_iban(self):
        assert "ES9121000418450200051332" not in scrub_text(
            "Transfer to ES9121000418450200051332 failed"
        )

    def test_redacts_email(self):
        assert scrub_text("user john.doe@mail.com failed") == f"user {REDACTED} failed"

    def test_redacts_bearer_token(self):
        assert scrub_text("Authorization: Bearer abc.def.ghi") == (
            f"Authorization: {REDACTED}"
        )

    def test_redacts_long_hex_values(self):
        address = "0x71c7656ec7ab88b098defb751b7401b5f6d8976f"
        assert address not in scrub_text(f"wallet {address} not found")

    def test_truncates_long_values(self):
        result = scrub_text("z" * (MAX_STRING_LENGTH + 100))
        assert len(result) == MAX_STRING_LENGTH + 3
        assert result.endswith("...")

    def test_keeps_harmless_text(self):
        assert scrub_text("entity not found") == "entity not found"


class TestScrub:
    def test_redacts_nested_sensitive_keys(self):
        data = {"user": {"password": "hunter2", "name": "bob"}}

        assert scrub(data) == {"user": {"password": REDACTED, "name": "bob"}}

    def test_scrubs_values_inside_lists(self):
        data = {"messages": ["contact a@b.com"]}

        assert scrub(data) == {"messages": [f"contact {REDACTED}"]}

    def test_keeps_primitives(self):
        assert scrub({"count": 3, "ok": True, "missing": None}) == {
            "count": 3,
            "ok": True,
            "missing": None,
        }

    def test_limits_collection_size(self):
        assert len(scrub(list(range(200)))) == 50

    def test_stringifies_unknown_objects(self):
        class Custom:
            def __str__(self):
                return "custom value"

        assert scrub(Custom()) == "custom value"
