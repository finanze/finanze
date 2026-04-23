import hashlib
from datetime import datetime

from dateutil.tz import tzlocal

from domain.public_keychain import PublicKeyEntry, PublicKeychain


class TestPublicKeyEntryDecodeAlgo1:
    def test_decodes_value(self):
        entry = PublicKeyEntry(
            key="abc123",
            value="YzcmMDc8ImMXBrmuJcc",
            algo=1,
            version=1,
            updated_at=datetime.now(tzlocal()),
        )
        assert entry.decode() == "TEST_A"

    def test_decodes_alternative_encoding(self):
        entry = PublicKeyEntry(
            key="abc123",
            value="CV1MWl1WSAm84Xsv",
            algo=1,
            version=1,
            updated_at=datetime.now(tzlocal()),
        )
        assert entry.decode() == "TEST_A"

    def test_caches_decoded_value(self):
        entry = PublicKeyEntry(
            key="abc123",
            value="YzcmMDc8ImMXBrmuJcc",
            algo=1,
            version=1,
            updated_at=datetime.now(tzlocal()),
        )
        first_call = entry.decode()
        second_call = entry.decode()
        assert first_call == second_call == "TEST_A"
        assert entry._decoded is not None

    def test_decodes_longer_value(self):
        entry = PublicKeyEntry(
            key="abc123",
            value="VhcYGQIeEwQTDhcbBhoTVpijBUUKiUzD",
            algo=1,
            version=1,
            updated_at=datetime.now(tzlocal()),
        )
        assert entry.decode() == "ANOTHEREXAMPLE"

    def test_decodes_longer_value_alternative(self):
        entry = PublicKeyEntry(
            key="abc123",
            value="kdDf3sXZ1MPUydDcwd3UkYU",
            algo=1,
            version=1,
            updated_at=datetime.now(tzlocal()),
        )
        assert entry.decode() == "ANOTHEREXAMPLE"


class TestPublicKeyEntryUnsupportedAlgo:
    def test_raises_for_unknown_algo(self):
        entry = PublicKeyEntry(
            key="abc123",
            value="whatever",
            algo=99,
            version=1,
            updated_at=datetime.now(tzlocal()),
        )
        try:
            entry.decode()
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Unsupported algo" in str(e)


class TestPublicKeyEntryRealKeys:
    def test_decodes_myinvestor_skey(self):
        entry = PublicKeyEntry(
            key="test",
            value="b1kjCh0wCwQdLi4uLi4iHhggGxsrBxskJTUjFTY4Kxs5BTBZGyMaNgpvWg",
            algo=1,
            version=1,
            updated_at=datetime.now(tzlocal()),
        )
        decoded = entry.decode()
        assert decoded == "6Ler_dkrAAAAAMqwOttDhtKJZLzYWDtVj_6tLuYe"

    def test_decodes_sego_api_key(self):
        entry = PublicKeyEntry(
            key="test",
            value="88DBwsbEwMqVxMKQxsfKlsWSkcTEwMXLkJXCkcfDlpDL8w",
            algo=1,
            version=1,
            updated_at=datetime.now(tzlocal()),
        )
        decoded = entry.decode()
        assert decoded == "3215739f71c549e6ab77368cf1b40ec8"

    def test_decodes_urbanitae_encryption_key(self):
        entry = PublicKeyEntry(
            key="test",
            value="LxZieEh6YR5cY2FKHkUdTmgvrUnxetCymA",
            algo=1,
            version=1,
            updated_at=datetime.now(tzlocal()),
        )
        decoded = entry.decode()
        assert decoded == "9MWgUN1sLNe1j2aG"


class TestPublicKeychainGet:
    def test_returns_entry_by_human_key(self):
        hashed = hashlib.shake_128(b"MY_KEY").hexdigest(8)
        entry = PublicKeyEntry(
            key=hashed,
            value="YzcmMDc8ImMXBrmuJcc",
            algo=1,
            version=1,
            updated_at=datetime.now(tzlocal()),
        )
        keychain = PublicKeychain({hashed: entry})

        result = keychain.get("MY_KEY")

        assert result is not None
        assert result.value == "YzcmMDc8ImMXBrmuJcc"

    def test_returns_none_for_missing_key(self):
        keychain = PublicKeychain({})
        assert keychain.get("MISSING") is None

    def test_key_hash_is_shake_128_of_8_bytes(self):
        keychain = PublicKeychain({})
        result = keychain._key_hash("MY_KEY")
        expected = hashlib.shake_128(b"MY_KEY").hexdigest(8)
        assert result == expected

    def test_different_keys_produce_different_hashes(self):
        keychain = PublicKeychain({})
        assert keychain._key_hash("KEY_A") != keychain._key_hash("KEY_B")
