import logging
from datetime import datetime, timedelta
from typing import Optional

from application.ports.public_keychain_loader import PublicKeychainLoader
from dateutil.tz import tzlocal

from application.ports.public_keychain_data_port import PublicKeychainDataPort
from application.ports.public_keychain_fetcher_port import PublicKeychainFetcherPort
from domain.public_keychain import PublicKeyEntry, PublicKeychain

REFRESH_INTERVAL_HOURS = 6


class PublicKeychainAdapter(PublicKeychainLoader):
    def __init__(
        self,
        data_port: PublicKeychainDataPort,
        fetcher_port: PublicKeychainFetcherPort,
    ):
        self._data_port = data_port
        self._fetcher_port = fetcher_port
        self._cache: dict[str, PublicKeyEntry] = {}
        self._last_refresh: Optional[datetime] = None
        self._log = logging.getLogger(__name__)

    async def load(self) -> PublicKeychain:
        await self._refresh_if_needed()
        return PublicKeychain(self._cache)

    async def _refresh_if_needed(self) -> None:
        if self._cache and self._last_refresh is not None:
            elapsed = datetime.now(tzlocal()) - self._last_refresh
            if elapsed < timedelta(hours=REFRESH_INTERVAL_HOURS):
                return

        stored = await self._data_port.retrieve()
        for entry in stored:
            self._cache[entry.key] = entry

        latest_updated_at = max((e.updated_at for e in stored), default=None)

        needs_remote_fetch = (
            not stored
            or latest_updated_at is None
            or (datetime.now(tzlocal()) - latest_updated_at)
            >= timedelta(hours=REFRESH_INTERVAL_HOURS)
        )

        if needs_remote_fetch:
            remote_entries = await self._fetcher_port.fetch()
            if remote_entries:
                await self._apply_remote_updates(remote_entries)

        self._last_refresh = datetime.now(tzlocal())

    async def _apply_remote_updates(self, remote_entries: list[PublicKeyEntry]) -> None:
        entries_to_save: list[PublicKeyEntry] = []

        for remote in remote_entries:
            local = self._cache.get(remote.key)
            if local is None or remote.version > local.version:
                self._cache[remote.key] = remote
                entries_to_save.append(remote)

        if entries_to_save:
            await self._data_port.save(entries_to_save)
