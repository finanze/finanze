import logging
import os
from typing import Optional

from infrastructure.client.rates.crypto.crypto_dataset_store import (
    DATASET_FILENAMES,
    CryptoDatasetStore,
)


class FileCryptoDatasetStore(CryptoDatasetStore):
    def __init__(self, app_dir: str):
        self._app_dir = app_dir
        self._log = logging.getLogger(__name__)

    def _path(self, key: str) -> Optional[str]:
        filename = DATASET_FILENAMES.get(key)
        if not filename:
            return None
        return os.path.join(self._app_dir, filename)

    async def load(self, key: str) -> Optional[str]:
        path = self._path(key)
        if not path or not os.path.exists(path):
            return None
        try:
            if os.path.getsize(path) == 0:
                return None
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            self._log.warning(f"Failed to read crypto dataset file {path}: {e}")
            return None

    async def save(self, key: str, raw_text: str) -> None:
        path = self._path(key)
        if not path:
            return
        tmp_path = f"{path}.tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(raw_text)
            os.replace(tmp_path, path)
        except Exception as e:
            self._log.warning(f"Failed to persist crypto dataset file {path}: {e}")
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
