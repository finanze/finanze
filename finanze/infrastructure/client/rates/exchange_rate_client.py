import logging
from datetime import datetime

from aiocache import cached
from aiocache.serializers import PickleSerializer
from application.ports.exchange_rate_provider import ExchangeRateProvider
from domain.dezimal import Dezimal
from domain.exchange_rate import ExchangeRates
from infrastructure.client.http.http_session import get_http_session

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
        self._session = get_http_session()

    async def get_available_currencies(self, **kwargs) -> dict[str, str]:
        if not self._available_currencies:
            request_timeout = kwargs.get("timeout", self.TIMEOUT)
            self._available_currencies = await self._fetch_available_currencies(
                request_timeout
            )
        return self._available_currencies

    @cached(
        ttl=MATRIX_CACHE_TTL,
        key_builder=lambda f, self, **kwargs: "exchange_rate_matrix",
        serializer=PickleSerializer(),
    )
    async def get_matrix(self, **kwargs) -> ExchangeRates:
        current_date = self._get_current_date()
        request_timeout = kwargs.get("timeout", self.TIMEOUT)
        if current_date != self._update_date:
            await self._load_rate_matrix(request_timeout)
        return self._rates

    async def _fetch_available_currencies(self, request_timeout: int) -> dict:
        return await self._fetch(self.CURRENCIES_URL, request_timeout)

    async def _fetch_rates(self, currency: str, request_timeout: int) -> dict:
        url = f"{self.BASE_URL}/currencies/{currency.lower()}.min.json"
        return await self._fetch(url, request_timeout)

    async def _fetch(self, url: str, request_timeout: int) -> dict:
        response = await self._session.get(url, timeout=request_timeout)
        if response.ok:
            return await response.json()

        body = await response.text()
        self._log.error("Error Response Body:" + body)
        response.raise_for_status()
        return {}

    def _get_current_date(self) -> str:
        return datetime.now().strftime(self.DATE_FORMAT)

    async def _load_rate_matrix(self, request_timeout: int):
        for currency in AVAILABLE_CURRENCIES:
            result = await self._fetch_rates(currency, request_timeout=request_timeout)
            self._update_date = datetime.strptime(result["date"], self.DATE_FORMAT)
            self._rates[currency] = _parse_rates(result[currency.lower()])
