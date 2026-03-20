import hashlib
from datetime import datetime, timedelta
from typing import Optional

import pytest
from dateutil.tz import tzlocal

from application.ports.public_keychain_data_port import PublicKeychainDataPort
from application.ports.public_keychain_fetcher_port import PublicKeychainFetcherPort
from domain.public_keychain import PublicKeyEntry
from infrastructure.keychain.public_keychain_adapter import PublicKeychainAdapter


def _hash(name: str) -> str:
    return hashlib.shake_128(name.encode("utf-8")).hexdigest(8)


def _entry(
    key: str,
    value: str,
    algo: int = 1,
    version: int = 1,
    updated_at: Optional[datetime] = None,
):
    return PublicKeyEntry(
        key=key,
        value=value,
        algo=algo,
        version=version,
        updated_at=updated_at or datetime.now(tzlocal()),
    )


class MockDataPort(PublicKeychainDataPort):
    def __init__(self, entries: list[PublicKeyEntry] = None):
        self.entries: list[PublicKeyEntry] = entries or []
        self.save_calls: list[list[PublicKeyEntry]] = []

    async def save(self, entries: list[PublicKeyEntry]) -> None:
        self.save_calls.append(entries)
        for e in entries:
            found = False
            for i, existing in enumerate(self.entries):
                if existing.key == e.key:
                    self.entries[i] = e
                    found = True
                    break
            if not found:
                self.entries.append(e)

    async def retrieve(self) -> list[PublicKeyEntry]:
        return list(self.entries)


class MockFetcherPort(PublicKeychainFetcherPort):
    def __init__(self, entries: list[PublicKeyEntry] = None):
        self.entries: list[PublicKeyEntry] = entries or []
        self.fetch_count = 0

    async def fetch(self) -> list[PublicKeyEntry]:
        self.fetch_count += 1
        return list(self.entries)


class TestLoadWithEmptyState:
    @pytest.mark.asyncio
    async def test_fetches_remote_when_no_local_data(self):
        hashed = _hash("MYI_SKEY")
        fetcher = MockFetcherPort([_entry(hashed, "encoded_value")])
        data = MockDataPort()
        adapter = PublicKeychainAdapter(data, fetcher)

        keychain = await adapter.load()
        result = keychain.get("MYI_SKEY")

        assert result is not None
        assert result.value == "encoded_value"
        assert fetcher.fetch_count == 1
        assert len(data.save_calls) == 1


class TestLoadWithFreshLocalData:
    @pytest.mark.asyncio
    async def test_does_not_fetch_remote_when_local_is_fresh(self):
        hashed = _hash("MYI_SKEY")
        now = datetime.now(tzlocal())
        data = MockDataPort([_entry(hashed, "local_value", updated_at=now)])
        fetcher = MockFetcherPort([_entry(hashed, "remote_value")])
        adapter = PublicKeychainAdapter(data, fetcher)

        keychain = await adapter.load()
        result = keychain.get("MYI_SKEY")

        assert result.value == "local_value"
        assert fetcher.fetch_count == 0


class TestLoadWithStaleLocalData:
    @pytest.mark.asyncio
    async def test_fetches_remote_when_local_is_stale(self):
        hashed = _hash("MYI_SKEY")
        old = datetime.now(tzlocal()) - timedelta(hours=7)
        data = MockDataPort([_entry(hashed, "old_value", version=1, updated_at=old)])
        fetcher = MockFetcherPort([_entry(hashed, "new_value", version=2)])
        adapter = PublicKeychainAdapter(data, fetcher)

        keychain = await adapter.load()
        result = keychain.get("MYI_SKEY")

        assert result.value == "new_value"
        assert result.version == 2
        assert fetcher.fetch_count == 1


class TestLoadDoesNotUpdateWhenSameVersion:
    @pytest.mark.asyncio
    async def test_keeps_local_when_remote_version_not_newer(self):
        hashed = _hash("MYI_SKEY")
        old = datetime.now(tzlocal()) - timedelta(hours=7)
        data = MockDataPort([_entry(hashed, "local_value", version=2, updated_at=old)])
        fetcher = MockFetcherPort([_entry(hashed, "remote_value", version=2)])
        adapter = PublicKeychainAdapter(data, fetcher)

        keychain = await adapter.load()
        result = keychain.get("MYI_SKEY")

        assert result.value == "local_value"
        assert len(data.save_calls) == 0


class TestLoadMissingKey:
    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_key(self):
        fetcher = MockFetcherPort([])
        data = MockDataPort()
        adapter = PublicKeychainAdapter(data, fetcher)

        keychain = await adapter.load()
        result = keychain.get("UNKNOWN_KEY")

        assert result is None


class TestCacheAvoidsDuplicateRefresh:
    @pytest.mark.asyncio
    async def test_second_load_uses_cache(self):
        hashed = _hash("MYI_SKEY")
        fetcher = MockFetcherPort([_entry(hashed, "val")])
        data = MockDataPort()
        adapter = PublicKeychainAdapter(data, fetcher)

        await adapter.load()
        await adapter.load()

        assert fetcher.fetch_count == 1
