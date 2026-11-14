import secrets
import time
from typing import Callable, Optional

from application.ports.import_preview_store import ImportPreviewStore
from domain.importing import ImportPreview

PREVIEW_TTL_SECONDS = 30 * 60
MAX_PREVIEWS = 8


class MemoryImportPreviewStore(ImportPreviewStore):
    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._previews: dict[str, tuple[float, ImportPreview]] = {}

    def save(self, preview: ImportPreview) -> str:
        self._evict_expired()
        while len(self._previews) >= MAX_PREVIEWS:
            self._previews.pop(next(iter(self._previews)))
        token = secrets.token_urlsafe(24)
        self._previews[token] = (self._clock() + PREVIEW_TTL_SECONDS, preview)
        return token

    def take(self, token: str) -> Optional[ImportPreview]:
        self._evict_expired()
        stored = self._previews.pop(token, None)
        return stored[1] if stored else None

    def clear(self):
        self._previews.clear()

    def _evict_expired(self):
        now = self._clock()
        for token in [
            t for t, (expires, _) in self._previews.items() if expires <= now
        ]:
            del self._previews[token]
