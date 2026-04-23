import json
import logging
from datetime import datetime

from application.ports.exchange_rate_storage import ExchangeRateStorage
from domain.exchange_rate import ExchangeRates
from domain.dezimal import Dezimal

import js


class PreferenceExchangeRateStorage(ExchangeRateStorage):
    KEY_RATES = "exchange_rates_data"
    LAST_SAVED_KEY = "last_saved"
    RATES_KEY = "rates"

    def __init__(self):
        self._log = logging.getLogger(__name__)
        self._last_saved: datetime | None = None
        self._rates_cache: ExchangeRates = {}

    async def initialize(self):
        await self._load()

    async def _load(self):
        try:
            val = await js.jsBridge.preferences.get(self.KEY_RATES)
            if not val:
                return

            data = json.loads(val)
            last_saved_raw = data.get(self.LAST_SAVED_KEY)
            if last_saved_raw:
                try:
                    self._last_saved = datetime.fromisoformat(last_saved_raw)
                except Exception:
                    pass

            raw_rates = data.get(self.RATES_KEY, {})
            if isinstance(raw_rates, dict):
                parsed: ExchangeRates = {}
                for base, quotes in raw_rates.items():
                    if not isinstance(quotes, dict):
                        continue
                    parsed[base] = {}
                    for quote, val in quotes.items():
                        parsed[base][quote] = Dezimal(str(val))
                self._rates_cache = parsed
        except Exception as e:
            self._log.warning(f"Failed to load rates from prefs: {e}")

    async def get(self) -> ExchangeRates:
        return self._rates_cache

    async def get_last_saved(self) -> datetime | None:
        return self._last_saved

    async def save(self, exchange_rates: ExchangeRates):
        await self._save(exchange_rates)

    async def _save(self, exchange_rates: ExchangeRates):
        serializable = {}
        for base, quotes in exchange_rates.items():
            serializable[base] = {}
            for quote, dez in quotes.items():
                serializable[base][quote] = str(dez)

        self._last_saved = datetime.now().astimezone()
        data = {
            self.LAST_SAVED_KEY: self._last_saved.isoformat(),
            self.RATES_KEY: serializable,
        }
        try:
            await js.jsBridge.preferences.set(self.KEY_RATES, json.dumps(data))
            self._rates_cache = exchange_rates
        except Exception as e:
            self._log.exception(f"Failed to save rates to prefs: {e}")
