import asyncio
import logging
import time
from datetime import datetime
from decimal import Decimal
from typing import Awaitable, Callable, TypeVar

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


T = TypeVar("T")
JobResult = TypeVar("JobResult")


JobMeta = tuple[str, object]
JobFactory = Callable[[], Awaitable[object]]
JobDef = tuple[JobFactory, JobMeta]
JobOutcome = tuple[str, object, object | None, BaseException | None]


async def _default_port_call_runner(coro: Awaitable[T]) -> T:
    return await coro


async def _default_job_scheduler(
    jobs: list[JobDef], timeout: float
) -> list[JobOutcome]:
    start_monotonic = time.monotonic()
    slice_timeout = 0.2

    tasks_map: dict[asyncio.Task, JobMeta] = {}
    for job_factory, meta in jobs:
        tasks_map[asyncio.create_task(job_factory())] = meta

    pending = set(tasks_map.keys())
    outcomes: list[JobOutcome] = []

    while pending:
        elapsed = time.monotonic() - start_monotonic
        remaining_global = timeout - elapsed
        if remaining_global <= 0:
            for f in pending:
                f.cancel()
            break

        wait_slice = min(slice_timeout, remaining_global)
        done, pending = await asyncio.wait(
            pending, timeout=wait_slice, return_when=asyncio.FIRST_COMPLETED
        )
        if not done:
            continue

        for future in done:
            kind, meta = tasks_map[future]
            if future.cancelled():
                outcomes.append((kind, meta, None, asyncio.CancelledError()))
                continue
            try:
                outcomes.append((kind, meta, future.result(), None))
            except BaseException as e:
                outcomes.append((kind, meta, None, e))

    return outcomes


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
        port_call_runner: Callable[[Awaitable[T]], Awaitable[T]] | None = None,
        job_scheduler: (
            Callable[[list[JobDef], float], Awaitable[list[JobOutcome]]] | None
        ) = None,
    ):
        self._exchange_rates_provider = exchange_rates_provider
        self._crypto_asset_info_provider = crypto_asset_info_provider
        self._metal_price_provider = metal_price_provider
        self._exchange_rates_storage = exchange_rates_storage
        self._position_port = position_port

        self._port_call_runner = port_call_runner or _default_port_call_runner
        self._job_scheduler = job_scheduler or _default_job_scheduler

        self._fiat_matrix: ExchangeRates | None = None
        self._last_base_refresh_ts: int = 0

        self._lock = asyncio.Lock()
        self._log = logging.getLogger(__name__)
        self._second_load = False

    async def execute(self, initial_load: bool = False) -> ExchangeRates:
        async with self._lock:
            return await self._get_exchange_rates(initial_load)

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
        self, future, futures_map, commodity_rates, crypto_rates, refreshed_base
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
                crypto_rates.setdefault(base_currency, {})[symbol] = result
            elif kind == "crypto_batch":
                for symbol, fiat_map in result.items():
                    for fiat_iso, price in fiat_map.items():
                        crypto_rates.setdefault(fiat_iso, {})[symbol] = price
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

    def _consume_outcome(
        self,
        kind: str,
        meta: object,
        result: object | None,
        error: BaseException | None,
        commodity_rates,
        crypto_rates,
        refreshed_base,
    ):
        try:
            if error is not None:
                raise error

            if kind == "base":
                if result is not None:
                    refreshed_base = self._normalize_matrix(result)
            elif kind == "commodity":
                commodity, symbol = meta
                if result is not None:
                    commodity_rates[commodity] = (result, symbol)
            elif kind == "crypto":
                symbol, base_currency = meta
                crypto_rates.setdefault(base_currency, {})[symbol] = result
            elif kind == "crypto_batch":
                for symbol, fiat_map in result.items():
                    for fiat_iso, price in fiat_map.items():
                        crypto_rates.setdefault(fiat_iso, {})[symbol] = price
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

    async def _get_exchange_rates(self, initial_load: bool) -> ExchangeRates:
        timeout = self.DEFAULT_TIMEOUT if not initial_load else 5

        if self._fiat_matrix is None:
            stored = await self._exchange_rates_storage.get()
            if stored:
                self._fiat_matrix = stored
                storage_update_date = (
                    await self._exchange_rates_storage.get_last_saved()
                )
                if storage_update_date:
                    self._last_base_refresh_ts = int(storage_update_date.timestamp())

        refresh_base = self._needs_base_refresh()
        if not refresh_base and not self._second_load:
            return self._fiat_matrix

        if self._fiat_matrix is None:
            self._last_base_refresh_ts = _now()
            self._fiat_matrix = self._init_empty_matrix()

        commodity_rates = {}
        crypto_rates = {}
        refreshed_base = None

        try:
            jobs: list[JobDef] = []
            if refresh_base:
                jobs.extend(self._schedule_base_matrix(timeout))
                jobs.extend(self._schedule_commodity_rates(timeout))

            jobs.extend(await self._schedule_crypto_rates(timeout, initial_load))

            outcomes = await self._job_scheduler(jobs, timeout)
            for kind, meta, result, error in outcomes:
                refreshed_base = self._consume_outcome(
                    kind,
                    meta,
                    result,
                    error,
                    commodity_rates,
                    crypto_rates,
                    refreshed_base,
                )

        except Exception as e:
            self._log.error(f"Unexpected error during parallel fetch: {e}")

        if refreshed_base is not None:
            for base, quotes in refreshed_base.items():
                self._fiat_matrix.setdefault(base, {})
                for quote, rate in quotes.items():
                    self._fiat_matrix[base][quote] = (
                        rate
                        if isinstance(rate, Dezimal)
                        else Dezimal(_to_decimal(rate))
                    )
            self._last_base_refresh_ts = _now()

        self._apply_rates(commodity_rates, crypto_rates)
        await self._save_rates_to_storage(force=self._second_load)

        if self._second_load:
            self._second_load = False
        elif initial_load:
            self._second_load = True

        return self._fiat_matrix

    async def _save_rates_to_storage(self, force: bool = False):
        try:
            if self._fiat_matrix:
                last_saved = await self._exchange_rates_storage.get_last_saved()
                if (
                    force
                    or (last_saved is None)
                    or (
                        (datetime.now(tzlocal()) - last_saved).total_seconds()
                        >= self.STORAGE_REFRESH_SECONDS
                    )
                ):
                    self._log.debug("Saving exchange rates to storage.")
                    await self._exchange_rates_storage.save(self._fiat_matrix)
        except Exception as e:
            self._log.error(f"Failed to persist refreshed exchange rates: {e}")

    def _schedule_base_matrix(self, timeout: int):
        async def _run():
            return await self._port_call_runner(
                self._exchange_rates_provider.get_matrix(timeout=timeout)
            )

        return [(_run, ("base", None))]

    def _schedule_commodity_rates(self, timeout: int):
        items = []
        for commodity, symbol in COMMODITY_SYMBOLS.items():

            async def _run(c=commodity):
                return await self._port_call_runner(
                    self._metal_price_provider.get_price(c, timeout=timeout)
                )

            items.append((_run, ("commodity", (commodity, symbol))))

        return items

    async def _get_position_crypto_currency_symbol_address(
        self,
    ) -> dict[str, str | None]:
        crypto_entity_positions = await self._position_port.get_last_grouped_by_entity(
            PositionQueryRequest(products=[ProductType.CRYPTO])
        )
        asset_addresses: dict[str, str | None] = {}
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

    async def _get_crypto_price_map(
        self, symbol_addresses: dict[str, str | None]
    ) -> dict[str, dict[str, Dezimal]]:
        price_map: dict[str, dict[str, Dezimal]] = {}

        addresses: dict[str, str] = {}
        non_address_symbols: list[str] = []
        for symbol, address in symbol_addresses.items():
            if address is None:
                non_address_symbols.append(symbol)
            else:
                addresses[address.lower()] = symbol

        if non_address_symbols:
            price_map = (
                await self._crypto_asset_info_provider.get_multiple_prices_by_symbol(
                    non_address_symbols, fiat_isos=SUPPORTED_CURRENCIES
                )
            )

        if addresses:
            address_prices = (
                await self._crypto_asset_info_provider.get_prices_by_addresses(
                    list(addresses.keys()), fiat_isos=SUPPORTED_CURRENCIES
                )
            )
            for addr, fiat_prices in address_prices.items():
                symbol = addresses[addr.lower()]
                price_map[symbol] = fiat_prices

        return price_map

    async def _schedule_crypto_rates(self, timeout: int, initial_load: bool):
        if initial_load:
            tasks = []
            for base_currency in SUPPORTED_CURRENCIES:
                for symbol in self.BASE_CRYPTO_SYMBOLS:

                    async def _run(sym=symbol, base=base_currency):
                        return await self._port_call_runner(
                            self._crypto_asset_info_provider.get_price(
                                sym, base, timeout=timeout
                            )
                        )

                    tasks.append((_run, ("crypto", (symbol, base_currency))))
            return tasks

        asset_symbol_addresses = (
            await self._get_position_crypto_currency_symbol_address()
        )
        if not asset_symbol_addresses:
            return []

        async def _run_batch():
            return await self._get_crypto_price_map(asset_symbol_addresses)

        return [(_run_batch, ("crypto_batch", None))]

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
