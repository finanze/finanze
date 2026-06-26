import logging
from typing import Optional

import js

from infrastructure.client.rates.crypto.crypto_dataset_store import (
    DATASET_FILENAMES,
    CryptoDatasetStore,
)


class MobileCryptoDatasetStore(CryptoDatasetStore):
    CACHE_DIR = "crypto_cache"

    def __init__(self):
        self._log = logging.getLogger(__name__)
        self._dir_ready = False

    def _path(self, key: str) -> Optional[str]:
        filename = DATASET_FILENAMES.get(key)
        if not filename:
            return None
        return f"{self.CACHE_DIR}/{filename}"

    async def _ensure_dir(self) -> None:
        if self._dir_ready:
            return
        await js.jsBridge.filesystem.createDirectory(self.CACHE_DIR)
        self._dir_ready = True

    async def load(self, key: str) -> Optional[str]:
        path = self._path(key)
        if not path:
            return None
        try:
            exists = await js.jsBridge.filesystem.fileExists(path)
            if not exists:
                return None
            return await js.jsBridge.filesystem.readFile(path, False)
        except Exception as e:
            self._log.warning(f"Failed to read crypto dataset file {path}: {e}")
            return None

    async def save(self, key: str, raw_text: str) -> None:
        path = self._path(key)
        if not path:
            return
        try:
            await self._ensure_dir()
            await js.jsBridge.filesystem.writeFile(path, raw_text, False)
        except Exception as e:
            self._log.warning(f"Failed to persist crypto dataset file {path}: {e}")
