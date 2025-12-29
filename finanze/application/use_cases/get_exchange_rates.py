import logging
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime
from decimal import Decimal
from threading import Lock

from application.ports.crypto_price_provider import CryptoAssetInfoProvider
from application.ports.exchange_rate_provider import ExchangeRateProvider
from application.ports.exchange_rate_storage import ExchangeRateStorage
from application.ports.metal_price_provider import MetalPriceProvider
from application.ports.position_port import PositionPort
from dateutil.tz import tzlocal
from domain.commodity import COMMODITY_SYMBOLS
from domain.constants import SUPPORTED_CURRENCIES
from domain.dezimal import Dezimal
from domain.exchange_rate import ExchangeRates
from domain.global_position import PositionQueryRequest, ProductType
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
    BASE_CRYPTO_SYMBOLS = ["BTC", "ETH", "LTC", "TRX", "BNB", "USDT", "USDC"]
    DEFAULT_TIMEOUT = 7
    CACHE_TTL_SECONDS = 300
    STORAGE_REFRESH_SECONDS = 6 * 60 * 60

    def __init__(
        self,
        exchange_rates_provider: ExchangeRateProvider,
        crypto_asset_info_provider: CryptoAssetInfoProvider,
        metal_price_provider: MetalPriceProvider,
        exchange_rates_storage: ExchangeRateStorage,
        position_port: PositionPort,
    ):
        self._exchange_rates_provider = exchange_rates_provider
        self._crypto_asset_info_provider = crypto_asset_info_provider
        self._metal_price_provider = metal_price_provider
        self._exchange_rates_storage = exchange_rates_storage
        self._position_port = position_port

        stored = self._exchange_rates_storage.get()
        self._fiat_matrix: ExchangeRates | None = stored if stored else None

        self._last_base_refresh_ts: int = 0
        if stored:
            storage_update_date = self._exchange_rates_storage.get_last_saved()
            self._last_base_refresh_ts = int(storage_update_date.timestamp())

        self._lock = Lock()

        self._log = logging.getLogger(__name__)
        self._second_load = False

    def execute(self, initial_load: bool = False) -> ExchangeRates:
        with self._lock:
            return self._get_exchange_rates(initial_load)

    def _needs_base_refresh(self) -> bool:
        if self._fiat_matrix is None:
            return True
        return (_now() - self._last_base_refresh_ts) >= self.CACHE_TTL_SECONDS

    def _normalize_matrix(self, matrix):
        for base, quotes in matrix.items():
            invalid = []
            for quote, rate in quotes.items():
                dec = _to_decimal(rate)
                if dec is None:
                    self._log.warning(f"Dropping non-numeric rate {base}->{quote}")
                    invalid.append(quote)
                else:
                    quotes[quote] = rate if isinstance(rate, Dezimal) else Dezimal(dec)
            for k in invalid:
                del quotes[k]
        return matrix

    def _init_empty_matrix(self):
        return {c: {} for c in SUPPORTED_CURRENCIES}

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
                symbol, base_currency = meta
                if base_currency not in crypto_rates:
                    crypto_rates[base_currency] = {}
                crypto_rates[base_currency][symbol] = result
            elif kind == "crypto_batch":
                for symbol, fiat_map in result.items():
                    for fiat_iso, price in fiat_map.items():
                        if fiat_iso not in crypto_rates:
                            crypto_rates[fiat_iso] = {}
                        crypto_rates[fiat_iso][symbol] = price
        except Exception as e:
            if kind == "base":
                self._log.error(f"Failed base fiat matrix fetch: {e}")
            elif kind == "commodity":
                commodity, _ = meta
                self._log.error(f"Failed commodity price for {commodity}: {e}")
            elif kind == "crypto_batch":
                self._log.error(f"Failed batched crypto prices fetch: {e}")
            else:
                symbol, base_currency = meta
                self._log.error(
                    f"Failed crypto price for {symbol} in {base_currency}: {e}"
                )
        return refreshed_base

    def _get_exchange_rates(self, initial_load: bool) -> ExchangeRates:
        timeout = self.DEFAULT_TIMEOUT if not initial_load else 5

        refresh_base = self._needs_base_refresh()
        if not refresh_base and not self._second_load:
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
            if refresh_base:
                futures.update(self._schedule_base_matrix(executor, True, timeout))
                futures.update(self._schedule_commodity_rates(executor, timeout))
            futures.update(self._schedule_crypto_rates(executor, timeout, initial_load))

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
                    self._fiat_matrix[base][quote] = (
                        rate
                        if isinstance(rate, Dezimal)
                        else Dezimal(_to_decimal(rate))
                    )
            self._last_base_refresh_ts = _now()

        self._apply_rates(commodity_rates, crypto_rates)

        self._save_rates_to_storage(force=self._second_load)

        if self._second_load:
            self._second_load = False
        elif initial_load:
            self._second_load = True

        return self._fiat_matrix

    def _save_rates_to_storage(self, force: bool = False):
        try:
            if self._fiat_matrix:
                last_saved = self._exchange_rates_storage.get_last_saved()
                if (
                    force
                    or (last_saved is None)
                    or (
                        (datetime.now(tzlocal()) - last_saved).total_seconds()
                        >= self.STORAGE_REFRESH_SECONDS
                    )
                ):
                    self._log.debug("Saving exchange rates to storage.")
                    self._exchange_rates_storage.save(self._fiat_matrix)
        except Exception as e:
            self._log.error(f"Failed to persist refreshed exchange rates: {e}")

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

    def _get_position_crypto_currency_symbol_address(self) -> dict[str, str | None]:
        crypto_entity_positions = self._position_port.get_last_grouped_by_entity(
            PositionQueryRequest(products=[ProductType.CRYPTO])
        )
        asset_addresses = {}
        for position in crypto_entity_positions.values():
            if ProductType.CRYPTO not in position.products:
                continue
            for wallet in position.products[ProductType.CRYPTO].entries:
                for asset in wallet.assets:
                    asset_addresses[asset.symbol.upper()] = (
                        asset.contract_address.lower()
                        if asset.contract_address
                        else None
                    )

        return asset_addresses

    def _get_crypto_price_map(
        self,
        symbol_addresses: dict[str, str | None],
    ) -> dict[str, dict[str, Dezimal]]:
        price_map: dict[str, dict[str, Dezimal]] = {}

        addresses: dict[str, str] = {}
        non_address_symbols = []
        for symbol, address in symbol_addresses.items():
            if address is None:
                non_address_symbols.append(symbol)
            else:
                addresses[address.lower()] = symbol
        if non_address_symbols:
            price_map = self._crypto_asset_info_provider.get_multiple_prices_by_symbol(
                non_address_symbols, fiat_isos=SUPPORTED_CURRENCIES
            )

        if addresses:
            address_prices = self._crypto_asset_info_provider.get_prices_by_addresses(
                list(addresses.keys()), fiat_isos=SUPPORTED_CURRENCIES
            )
            for addr, fiat_prices in address_prices.items():
                contract_address = addr.lower()
                symbol = addresses[contract_address]
                price_map[symbol] = fiat_prices

        return price_map

    def _schedule_crypto_rates(self, executor, timeout: int, initial_load: bool):
        if initial_load:
            return {
                executor.submit(
                    self._crypto_asset_info_provider.get_price,
                    symbol,
                    base_currency,
                    timeout=timeout,
                ): ("crypto", (symbol, base_currency))
                for base_currency in SUPPORTED_CURRENCIES
                for symbol in self.BASE_CRYPTO_SYMBOLS
            }

        asset_symbol_addresses = self._get_position_crypto_currency_symbol_address()

        if not asset_symbol_addresses:
            return {}

        return {
            executor.submit(
                self._get_crypto_price_map,
                asset_symbol_addresses,
            ): ("crypto_batch", None)
        }

    def _apply_rates(self, commodity_rates, crypto_rates):
        if self._fiat_matrix is None:
            return
        for base_currency in SUPPORTED_CURRENCIES:
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
                self._fiat_matrix[base_currency][symbol.upper()] = Dezimal(rate)
            except Exception as e:
                self._log.error(
                    f"Failed to apply commodity {commodity} for {base_currency}: {e}"
                )

    def _apply_crypto_rates(self, base_currency, crypto_rates):
        if self._fiat_matrix is None:
            return
        if base_currency in crypto_rates:
            for symbol, rate in crypto_rates[base_currency].items():
                try:
                    rate_dec = _to_decimal(rate)
                    if rate_dec is None or rate_dec == 0:
                        continue
                    self._fiat_matrix[base_currency][symbol.upper()] = Dezimal(
                        Decimal(1) / rate_dec
                    )
                except Exception as e:
                    self._log.error(
                        f"Failed to apply crypto {symbol} for {base_currency}: {e}"
                    )
