import json
import os
import logging
from datetime import datetime
from typing import Any, List, Dict, Optional
from infrastructure.client.rates.crypto.coingecko_cache_strategy import (
    CoinGeckoCacheStrategy,
)


class FileCoinGeckoCacheStrategy(CoinGeckoCacheStrategy):
    CACHE_FILENAME = "coingecko.json"

    def __init__(self, app_dir: str):
        self._cache_file_path = os.path.join(app_dir, self.CACHE_FILENAME)
        self._log = logging.getLogger(__name__)

    def _read_cache_file(self) -> Dict[str, Any]:
        if not os.path.exists(self._cache_file_path):
            return {}
        try:
            if os.path.getsize(self._cache_file_path) == 0:
                return {}
            with open(self._cache_file_path, "r") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception as e:
            self._log.warning(f"Failed to read cache file: {e}")
            return {}

    def _write_cache_file(self, data: Dict[str, Any]):
        try:
            with open(self._cache_file_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self._log.exception(f"Failed to persist cache file: {e}")

    async def load_coin_list(
        self,
    ) -> tuple[Optional[List[Dict[str, Any]]], Optional[datetime]]:
        data = self._read_cache_file()
        coins_data = data.get("coins", {})
        if not isinstance(coins_data, dict):
            return None, None

        last_updated_raw = coins_data.get("last_updated")
        last_updated = None
        if isinstance(last_updated_raw, str):
            try:
                last_updated = datetime.fromisoformat(last_updated_raw)
            except Exception:
                pass

        result = coins_data.get("result")
        if isinstance(result, list):
            return result, last_updated
        return None, None

    async def save_coin_list(self, data: List[Dict[str, Any]], last_updated: datetime):
        full_data = self._read_cache_file()
        full_data["coins"] = {"last_updated": last_updated.isoformat(), "result": data}
        self._write_cache_file(full_data)

    async def load_platforms(
        self,
    ) -> tuple[Optional[List[Dict[str, Any]]], Optional[datetime]]:
        data = self._read_cache_file()
        platforms_data = data.get("platforms", {})
        if not isinstance(platforms_data, dict):
            return None, None

        last_updated_raw = platforms_data.get("last_updated")
        last_updated = None
        if isinstance(last_updated_raw, str):
            try:
                last_updated = datetime.fromisoformat(last_updated_raw)
            except Exception:
                pass

        result = platforms_data.get("result")
        if isinstance(result, list):
            return result, last_updated
        return None, None

    async def save_platforms(self, data: List[Dict[str, Any]], last_updated: datetime):
        full_data = self._read_cache_file()
        full_data["platforms"] = {
            "last_updated": last_updated.isoformat(),
            "result": data,
        }
        self._write_cache_file(full_data)
