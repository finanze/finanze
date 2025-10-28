import json
import logging
import os
from datetime import datetime
from typing import Any

from application.ports.exchange_rate_storage import ExchangeRateStorage
from dateutil.tz import tzlocal
from domain.dezimal import Dezimal
from domain.exchange_rate import ExchangeRates


class ExchangeRateFileStorage(ExchangeRateStorage):
    FILENAME = "rates.json"
    LAST_SAVED_KEY = "last_saved"
    RATES_KEY = "rates"

    def __init__(self, base_path: str):
        self._base_path = base_path
        os.makedirs(self._base_path, exist_ok=True)

        self._file_path = os.path.join(self._base_path, self.FILENAME)
        self._last_saved: datetime | None = None
        self._rates_cache: ExchangeRates = {}

        self._log = logging.getLogger(__name__)

        self._load()

    def _load(self):
        if not os.path.exists(self._file_path):
            return

        try:
            if os.path.getsize(self._file_path) == 0:
                return
            with open(self._file_path, "r") as f:
                data: dict[str, Any] = json.load(f)
            if not isinstance(data, dict):
                return
            last_saved_raw = data.get(self.LAST_SAVED_KEY)
            if isinstance(last_saved_raw, str):
                try:
                    self._last_saved = datetime.fromisoformat(last_saved_raw)
                except Exception:
                    self._log.warning("Malformed last_saved timestamp in rates.json")

            raw_rates = data.get(self.RATES_KEY, {})
            if isinstance(raw_rates, dict):
                parsed: ExchangeRates = {}
                for base, quotes in raw_rates.items():
                    if not isinstance(quotes, dict):
                        continue
                    parsed[base] = {}
                    for quote, val in quotes.items():
                        try:
                            parsed[base][quote] = Dezimal(str(val))
                        except Exception:
                            self._log.warning(
                                f"Skipping invalid rate {base}->{quote} value={val}"
                            )
                self._rates_cache = parsed
        except Exception as e:
            self._log.warning(f"Failed to load exchange rates from storage: {e}")

    def get(self) -> ExchangeRates:
        return self._rates_cache

    def save(self, exchange_rates: ExchangeRates):
        serializable: dict[str, dict[str, str]] = {}
        for base, quotes in exchange_rates.items():
            serializable[base] = {}
            for quote, dez in quotes.items():
                try:
                    serializable[base][quote] = str(dez)
                except Exception:
                    self._log.warning(
                        f"Unable to serialize rate {base}->{quote}: {dez}"
                    )

        self._last_saved = datetime.now(tzlocal())
        data = {
            self.LAST_SAVED_KEY: self._last_saved.isoformat(),
            self.RATES_KEY: serializable,
        }
        try:
            with open(self._file_path, "w") as f:
                json.dump(data, f, indent=2)
            self._rates_cache = exchange_rates
        except Exception as e:
            self._log.error(f"Failed to persist exchange rates: {e}")

    def get_last_saved(self) -> datetime | None:
        return self._last_saved
