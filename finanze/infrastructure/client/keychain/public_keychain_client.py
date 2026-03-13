import logging
from datetime import datetime

from aiocache import cached, Cache
from dateutil.tz import tzlocal

from application.ports.public_keychain_fetcher_port import PublicKeychainFetcherPort
from domain.public_keychain import PublicKeyEntry
from infrastructure.client.http.http_session import get_http_session

KEYCHAIN_URL = "https://features.api.finanze.me/keys"
CACHE_TTL = 21600


class PublicKeychainClient(PublicKeychainFetcherPort):
    def __init__(self):
        self._log = logging.getLogger(__name__)
        self._session = None

    def _get_session(self):
        if not self._session:
            self._session = get_http_session()
        return self._session

    @cached(cache=Cache.MEMORY, ttl=CACHE_TTL)
    async def fetch(self) -> list[PublicKeyEntry]:
        try:
            response = await self._get_session().get(KEYCHAIN_URL, timeout=2)
            data = await response.json()
        except Exception as e:
            self._log.error(
                "Failed to fetch public keychain (%s): %r", type(e).__name__, e
            )
            return []

        version = data.get("version", 0)
        algo = data.get("algo", 0)
        entries_map = data.get("entries", {})
        now = datetime.now(tzlocal())

        return [
            PublicKeyEntry(key=k, value=v, algo=algo, version=version, updated_at=now)
            for k, v in entries_map.items()
        ]
