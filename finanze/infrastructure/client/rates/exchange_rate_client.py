import logging
from datetime import datetime

import requests
from application.ports.exchange_rate_provider import ExchangeRateProvider
from cachetools import TTLCache, cached
from domain.dezimal import Dezimal
from domain.exchange_rate import ExchangeRates

AVAILABLE_CURRENCIES = ["EUR", "USD"]


def _parse_rates(rates: dict) -> dict:
    return {currency.upper(): Dezimal(rate) for currency, rate in rates.items()}


class ExchangeRateClient(ExchangeRateProvider):
    MATRIX_CACHE_TTL = 2 * 60 * 60
    TIMEOUT = 10

    BASE_URL = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1"
    CURRENCIES_URL = f"{BASE_URL}/currencies.min.json"
    DATE_FORMAT = "%Y-%m-%d"

    def __init__(self):
        self._rates = {}
        self._available_currencies = {}
        self._update_date = None
        self._log = logging.getLogger(__name__)

        self._load_rate_matrix(self.TIMEOUT)

    def get_available_currencies(self, **kwargs) -> dict[str, str]:
        if not self._available_currencies:
            timeout = kwargs.get("timeout", self.TIMEOUT)
            self._available_currencies = self._fetch_available_currencies(timeout)
        return self._available_currencies

    @cached(cache=TTLCache(maxsize=1, ttl=MATRIX_CACHE_TTL))
    def get_matrix(self, **kwargs) -> ExchangeRates:
        current_date = self._get_current_date()
        timeout = kwargs.get("timeout", self.TIMEOUT)
        if current_date != self._update_date:
            self._load_rate_matrix(timeout)
        return self._rates

    def _fetch_available_currencies(self, timeout: int) -> dict:
        return self._fetch(self.CURRENCIES_URL, timeout)

    def _fetch_rates(self, currency: str, timeout: int) -> dict:
        url = f"{self.BASE_URL}/currencies/{currency.lower()}.min.json"
        return self._fetch(url, timeout)

    def _fetch(self, url: str, timeout: int) -> dict:
        response = requests.get(url, timeout=timeout)
        if response.ok:
            return response.json()

        self._log.error("Error Response Body:" + response.text)
        response.raise_for_status()
        return {}

    def _get_current_date(self) -> str:
        return datetime.now().strftime(self.DATE_FORMAT)

    def _load_rate_matrix(self, timeout: int):
        for currency in AVAILABLE_CURRENCIES:
            result = self._fetch_rates(currency, timeout=timeout)
            self._update_date = datetime.strptime(result["date"], self.DATE_FORMAT)
            self._rates[currency] = _parse_rates(result[currency.lower()])
