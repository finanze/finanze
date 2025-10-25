import logging
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from decimal import Decimal
from threading import Lock

from application.ports.crypto_price_provider import CryptoPriceProvider
from application.ports.exchange_rate_provider import ExchangeRateProvider
from application.ports.metal_price_provider import MetalPriceProvider
from domain.commodity import COMMODITY_SYMBOLS
from domain.exchange_rate import ExchangeRates
from domain.global_position import (
    CRYPTO_SYMBOLS,
)
from domain.use_cases.get_exchange_rates import GetExchangeRates


def _to_decimal(value):
    try:
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))
    except Exception:
        return None


def _now() -> int:
    return int(time.time())


class GetExchangeRatesImpl(GetExchangeRates):
    SUPPORTED_CURRENCIES = ["EUR", "USD"]
    DEFAULT_TIMEOUT = 7
    CACHE_TTL_SECONDS = 300

    def __init__(
        self,
        exchange_rates_provider: ExchangeRateProvider,
        crypto_price_provider: CryptoPriceProvider,
        metal_price_provider: MetalPriceProvider,
    ):
        self._exchange_rates_provider = exchange_rates_provider
        self._crypto_price_provider = crypto_price_provider
        self._metal_price_provider = metal_price_provider

        self._fiat_matrix: ExchangeRates | None = None
        self._last_base_refresh_ts: int = 0

        self._lock = Lock()

        self._log = logging.getLogger(__name__)

    def execute(self, timeout: int = DEFAULT_TIMEOUT) -> ExchangeRates:
        with self._lock:
            return self._get_exchange_rates(timeout)

    def _needs_base_refresh(self) -> bool:
        if self._fiat_matrix is None:
            return True
        return (_now() - self._last_base_refresh_ts) >= self.CACHE_TTL_SECONDS

    def _normalize_matrix(self, matrix):
        for base, quotes in matrix.items():
            for quote, rate in list(quotes.items()):
                dec = _to_decimal(rate)
                if dec is None:
                    self._log.warning(f"Dropping non-numeric rate {base}->{quote}")
                    del quotes[quote]
                else:
                    quotes[quote] = dec
        return matrix

    def _init_empty_matrix(self):
        return {c: {} for c in self.SUPPORTED_CURRENCIES}

    def _consume_future(
        self,
        future,
        futures_map,
        commodity_rates,
        crypto_rates,
        refreshed_base,
    ):
        kind, meta = futures_map[future]
        if future.cancelled():
            return refreshed_base
        try:
            result = future.result()
            if kind == "base":
                if result is not None:
                    refreshed_base = self._normalize_matrix(result)
            elif kind == "commodity":
                commodity, symbol = meta
                if result is not None:
                    commodity_rates[commodity] = (result, symbol)
            elif kind == "crypto":
                crypto, symbol, base_currency = meta
                if base_currency not in crypto_rates:
                    crypto_rates[base_currency] = {}
                crypto_rates[base_currency][crypto] = (result, symbol)
        except Exception as e:
            if kind == "base":
                self._log.error(f"Failed base fiat matrix fetch: {e}")
            elif kind == "commodity":
                commodity, _ = meta
                self._log.error(f"Failed commodity price for {commodity}: {e}")
            else:
                crypto, _, base_currency = meta
                self._log.error(
                    f"Failed crypto price for {crypto} in {base_currency}: {e}"
                )
        return refreshed_base

    def _get_exchange_rates(self, timeout: int) -> ExchangeRates:
        refresh_base = self._needs_base_refresh()
        if not refresh_base:
            return self._fiat_matrix

        if self._fiat_matrix is None:
            self._last_base_refresh_ts = _now()
            self._fiat_matrix = self._init_empty_matrix()

        commodity_rates = {}
        crypto_rates = {}
        refreshed_base = None

        start_monotonic = time.monotonic()
        slice_timeout = 0.2
        executor = ThreadPoolExecutor(max_workers=8)
        try:
            futures = {}
            futures.update(self._schedule_base_matrix(executor, True, timeout))
            futures.update(self._schedule_commodity_rates(executor, timeout))
            futures.update(self._schedule_crypto_rates(executor, timeout))

            pending = set(futures.keys())

            while pending:
                elapsed = time.monotonic() - start_monotonic
                remaining_global = timeout - elapsed
                if remaining_global <= 0:
                    self._log.warning(
                        f"Global timeout ({timeout}s) reached; canceling {len(pending)} pending fetches."
                    )
                    for f in pending:
                        f.cancel()
                    break

                wait_slice = min(slice_timeout, remaining_global)
                done, _ = wait(pending, timeout=wait_slice, return_when=FIRST_COMPLETED)
                if not done:
                    continue

                for f in done:
                    pending.remove(f)
                    refreshed_base = self._consume_future(
                        f, futures, commodity_rates, crypto_rates, refreshed_base
                    )

        except Exception as e:
            self._log.error(f"Unexpected error during parallel fetch: {e}")
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        if refreshed_base is not None:
            for base, quotes in refreshed_base.items():
                if base not in self._fiat_matrix:
                    self._fiat_matrix[base] = {}
                for quote, rate in quotes.items():
                    self._fiat_matrix[base][quote] = rate
            self._last_base_refresh_ts = _now()

        self._apply_rates(commodity_rates, crypto_rates)
        return self._fiat_matrix

    def _schedule_base_matrix(self, executor, refresh_base: bool, timeout: int):
        if not refresh_base:
            return {}
        return {
            executor.submit(
                self._exchange_rates_provider.get_matrix, timeout=timeout
            ): ("base", None)
        }

    def _schedule_commodity_rates(self, executor, timeout: int):
        return {
            executor.submit(
                self._metal_price_provider.get_price, commodity, timeout=timeout
            ): ("commodity", (commodity, symbol))
            for commodity, symbol in COMMODITY_SYMBOLS.items()
        }

    def _schedule_crypto_rates(self, executor, timeout: int):
        return {
            executor.submit(
                self._crypto_price_provider.get_price,
                crypto,
                base_currency,
                timeout=timeout,
            ): ("crypto", (crypto, symbol, base_currency))
            for base_currency in self.SUPPORTED_CURRENCIES
            for crypto, symbol in CRYPTO_SYMBOLS.items()
        }

    def _apply_rates(self, commodity_rates, crypto_rates):
        if self._fiat_matrix is None:
            return
        for base_currency in self.SUPPORTED_CURRENCIES:
            self._apply_commodity_rates(base_currency, commodity_rates)
            self._apply_crypto_rates(base_currency, crypto_rates)

    def _apply_commodity_rates(self, base_currency, commodity_rates):
        if self._fiat_matrix is None:
            return

        for commodity, (rate_data, symbol) in commodity_rates.items():
            try:
                price_dec = _to_decimal(rate_data.price)
                if price_dec is None or price_dec == 0:
                    continue
                if base_currency != rate_data.currency:
                    base_to_rate_currency = self._fiat_matrix[base_currency].get(
                        rate_data.currency
                    )
                    base_to_rate_currency = _to_decimal(base_to_rate_currency)
                    if base_to_rate_currency is None or base_to_rate_currency == 0:
                        continue
                    rate = base_to_rate_currency / price_dec
                else:
                    rate = Decimal(1) / price_dec
                self._fiat_matrix[base_currency][symbol.upper()] = rate
            except Exception as e:
                self._log.error(
                    f"Failed to apply commodity {commodity} for {base_currency}: {e}"
                )

    def _apply_crypto_rates(self, base_currency, crypto_rates):
        if self._fiat_matrix is None:
            return
        if base_currency in crypto_rates:
            for crypto, (rate, symbol) in crypto_rates[base_currency].items():
                try:
                    rate_dec = _to_decimal(rate)
                    if rate_dec is None or rate_dec == 0:
                        continue
                    self._fiat_matrix[base_currency][symbol.upper()] = (
                        Decimal(1) / rate_dec
                    )
                except Exception as e:
                    self._log.error(
                        f"Failed to apply crypto {crypto} for {base_currency}: {e}"
                    )
