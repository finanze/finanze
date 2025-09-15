import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from application.ports.crypto_price_provider import CryptoPriceProvider
from application.ports.exchange_rate_provider import ExchangeRateProvider
from application.ports.metal_price_provider import MetalPriceProvider
from cachetools import TTLCache, cached
from domain.commodity import COMMODITY_SYMBOLS
from domain.exchange_rate import ExchangeRates
from domain.global_position import (
    CRYPTO_SYMBOLS,
)
from domain.use_cases.get_exchange_rates import GetExchangeRates


class GetExchangeRatesImpl(GetExchangeRates):
    SUPPORTED_CURRENCIES = ["EUR", "USD"]

    def __init__(
        self,
        exchange_rates_provider: ExchangeRateProvider,
        crypto_price_provider: CryptoPriceProvider,
        metal_price_provider: MetalPriceProvider,
    ):
        self._exchange_rates_provider = exchange_rates_provider
        self._crypto_price_provider = crypto_price_provider
        self._metal_price_provider = metal_price_provider
        self._log = logging.getLogger(__name__)

    @cached(TTLCache(maxsize=1, ttl=600))
    def execute(self) -> ExchangeRates:
        fiat_matrix = self._exchange_rates_provider.get_matrix()

        commodity_rates, crypto_rates = self._fetch_all_rates_parallel()
        self._apply_rates_to_matrix(fiat_matrix, commodity_rates, crypto_rates)

        return fiat_matrix

    def _fetch_all_rates_parallel(self):
        with ThreadPoolExecutor(max_workers=8) as executor:
            commodity_futures = self._submit_commodity_tasks(executor)
            crypto_futures = self._submit_crypto_tasks(executor)

            commodity_rates = self._collect_commodity_results(commodity_futures)
            crypto_rates = self._collect_crypto_results(crypto_futures)

        return commodity_rates, crypto_rates

    def _submit_commodity_tasks(self, executor):
        return {
            executor.submit(self._metal_price_provider.get_price, commodity): (
                commodity,
                symbol,
            )
            for commodity, symbol in COMMODITY_SYMBOLS.items()
        }

    def _submit_crypto_tasks(self, executor):
        return {
            executor.submit(
                self._crypto_price_provider.get_price, crypto, base_currency
            ): (crypto, symbol, base_currency)
            for base_currency in self.SUPPORTED_CURRENCIES
            for crypto, symbol in CRYPTO_SYMBOLS.items()
        }

    def _collect_commodity_results(self, commodity_futures):
        commodity_rates = {}
        for future in as_completed(commodity_futures):
            commodity, symbol = commodity_futures[future]
            try:
                rate_data = future.result()
                if rate_data is None:
                    continue
                commodity_rates[commodity] = (rate_data, symbol)
            except Exception as e:
                self._log.error(f"Failed to fetch commodity price for {commodity}: {e}")
        return commodity_rates

    def _collect_crypto_results(self, crypto_futures):
        crypto_rates = {}
        for future in as_completed(crypto_futures):
            crypto, symbol, base_currency = crypto_futures[future]
            try:
                rate = future.result()
                if base_currency not in crypto_rates:
                    crypto_rates[base_currency] = {}
                crypto_rates[base_currency][crypto] = (rate, symbol)
            except Exception as e:
                self._log.error(
                    f"Failed to fetch crypto price for {crypto} in {base_currency}: {e}"
                )
        return crypto_rates

    def _apply_rates_to_matrix(self, fiat_matrix, commodity_rates, crypto_rates):
        for base_currency in self.SUPPORTED_CURRENCIES:
            self._apply_commodity_rates(fiat_matrix, base_currency, commodity_rates)
            self._apply_crypto_rates(fiat_matrix, base_currency, crypto_rates)

    def _apply_commodity_rates(self, fiat_matrix, base_currency, commodity_rates):
        for commodity, (rate_data, symbol) in commodity_rates.items():
            if base_currency != rate_data.currency:
                rate = fiat_matrix[base_currency][rate_data.currency] / rate_data.price
            else:
                rate = 1 / rate_data.price
            fiat_matrix[base_currency][symbol.upper()] = rate

    def _apply_crypto_rates(self, fiat_matrix, base_currency, crypto_rates):
        if base_currency in crypto_rates:
            for crypto, (rate, symbol) in crypto_rates[base_currency].items():
                fiat_matrix[base_currency][symbol.upper()] = 1 / rate
