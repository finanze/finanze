import hashlib
import secrets
from typing import Optional

from application.ports.api_session_port import ApiSessionPort


class InMemoryApiSessionStore(ApiSessionPort):
    def __init__(self):
        self._digests: set[str] = set()

    def create(self) -> str:
        token = secrets.token_urlsafe(32)
        self._digests.add(self._digest(token))
        return token

    def is_valid(self, token: Optional[str]) -> bool:
        if not token:
            return False
        return self._digest(token) in self._digests

    def revoke_all(self):
        self._digests.clear()

    @staticmethod
    def _digest(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
