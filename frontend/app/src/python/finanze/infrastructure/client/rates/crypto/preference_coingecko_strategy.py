import json
import logging
from datetime import datetime
from typing import Any, List, Dict, Optional
from infrastructure.client.rates.crypto.coingecko_cache_strategy import (
    CoinGeckoCacheStrategy,
)
import js


class PreferenceCoinGeckoCacheStrategy(CoinGeckoCacheStrategy):
    KEY_COINS = "coingecko_coins"
    KEY_PLATFORMS = "coingecko_platforms"

    def __init__(self):
        self._log = logging.getLogger(__name__)

    async def load_coin_list(
        self,
    ) -> tuple[Optional[List[Dict[str, Any]]], Optional[datetime]]:
        try:
            val = await js.jsBridge.preferences.get(self.KEY_COINS)
            if not val:
                return None, None

            data = json.loads(val)
            last_updated_raw = data.get("last_updated")
            last_updated = None
            if last_updated_raw:
                last_updated = datetime.fromisoformat(last_updated_raw)
            return data.get("result"), last_updated
        except Exception as e:
            self._log.warning(f"Failed to load coin list from prefs: {e}")
            return None, None

    async def save_coin_list(self, data: List[Dict[str, Any]], last_updated: datetime):
        try:
            payload = {"last_updated": last_updated.isoformat(), "result": data}
            await js.jsBridge.preferences.set(self.KEY_COINS, json.dumps(payload))
        except Exception as e:
            self._log.warning(f"Failed to save coin list to prefs: {e}")

    async def load_platforms(
        self,
    ) -> tuple[Optional[List[Dict[str, Any]]], Optional[datetime]]:
        try:
            val = await js.jsBridge.preferences.get(self.KEY_PLATFORMS)
            if not val:
                return None, None

            data = json.loads(val)
            last_updated_raw = data.get("last_updated")
            last_updated = None
            if last_updated_raw:
                last_updated = datetime.fromisoformat(last_updated_raw)
            return data.get("result"), last_updated
        except Exception as e:
            self._log.warning(f"Failed to load platforms from prefs: {e}")
            return None, None

    async def save_platforms(self, data: List[Dict[str, Any]], last_updated: datetime):
        try:
            payload = {"last_updated": last_updated.isoformat(), "result": data}
            await js.jsBridge.preferences.set(self.KEY_PLATFORMS, json.dumps(payload))
        except Exception as e:
            self._log.warning(f"Failed to save platforms to prefs: {e}")
