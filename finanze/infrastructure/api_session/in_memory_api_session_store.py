import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

from application.ports.api_session_port import ApiSessionPort
from dateutil.tz import tzlocal


def _now() -> datetime:
    return datetime.now(tzlocal())


class InMemoryApiSessionStore(ApiSessionPort):
    def __init__(self, remember_ttl: Optional[timedelta] = None):
        self._remember_ttl = remember_ttl
        self._digests: dict[str, Optional[datetime]] = {}

    def create(self, remember: bool = False) -> str:
        token = secrets.token_urlsafe(32)
        expires_at = (
            _now() + self._remember_ttl if remember and self._remember_ttl else None
        )
        self._digests[self._digest(token)] = expires_at
        return token

    def is_valid(self, token: Optional[str]) -> bool:
        if not token:
            return False
        digest = self._digest(token)
        if digest not in self._digests:
            return False
        expires_at = self._digests[digest]
        if expires_at is not None and _now() >= expires_at:
            del self._digests[digest]
            return False
        return True

    def revoke_all(self):
        self._digests.clear()

    @staticmethod
    def _digest(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
