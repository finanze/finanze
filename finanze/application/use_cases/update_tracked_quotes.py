import logging
from asyncio import Lock
from typing import Optional
from uuid import UUID

from application.ports.exchange_rate_provider import ExchangeRateProvider
from application.ports.instrument_info_provider import InstrumentInfoProvider
from application.ports.manual_position_data_port import ManualPositionDataPort
from application.ports.position_port import PositionPort
from domain.dezimal import Dezimal
from domain.exception.exceptions import ExecutionConflict
from domain.global_position import EquityType, FundType, ProductType
from domain.instrument import InstrumentDataRequest, InstrumentInfo, InstrumentType
from domain.use_cases.update_tracked_quotes import UpdateTrackedQuotes


class UpdateTrackedQuotesImpl(UpdateTrackedQuotes):
    def __init__(
        self,
        position_port: PositionPort,
        manual_position_data_port: ManualPositionDataPort,
        instrument_info_provider: InstrumentInfoProvider,
        exchange_rate_provider: ExchangeRateProvider,
    ):
        self._position_port = position_port
        self._manual_position_data_port = manual_position_data_port
        self._instrument_info_provider = instrument_info_provider
        self._exchange_rate_provider = exchange_rate_provider

        self._lock = Lock()
        self._log = logging.getLogger(__name__)

    async def execute(self):
        if self._lock.locked():
            raise ExecutionConflict()

        async with self._lock:
            trackable_entries = await self._manual_position_data_port.get_trackable()
            if not trackable_entries:
                return

            self._log.info(
                "Updating tracked quotes for %d entries", len(trackable_entries)
            )

            fiat_matrix = await self._exchange_rate_provider.get_matrix()

            for mpd in trackable_entries:
                try:
                    await self._update_entry_quote(
                        entry_id=mpd.entry_id,
                        product_type=mpd.product_type,
                        tracker_key=mpd.data.tracker_key if mpd.data else None,
                        fiat_matrix=fiat_matrix,
                    )
                except Exception:
                    self._log.exception(
                        "Failed updating tracked quote for entry %s", mpd.entry_id
                    )
                    continue

    async def _resolve_entry_info(
        self, entry_id: UUID, product_type: ProductType
    ) -> Optional[tuple[Dezimal, str, InstrumentType]]:
        if product_type == ProductType.STOCK_ETF:
            stock = await self._position_port.get_stock_detail(entry_id)
            if not stock:
                return None
            inst_type = (
                InstrumentType.STOCK
                if stock.type == EquityType.STOCK
                else InstrumentType.ETF
            )
            return stock.shares, stock.currency, inst_type

        if product_type == ProductType.FUND:
            fund = await self._position_port.get_fund_detail(entry_id)
            if not fund:
                return None
            if fund.type != FundType.MUTUAL_FUND:
                return None
            return fund.shares, fund.currency, InstrumentType.MUTUAL_FUND

        return None

    async def _fetch_instrument_info(
        self, tracker_key: str, instrument_type: InstrumentType
    ) -> Optional[InstrumentInfo]:
        req = InstrumentDataRequest(type=instrument_type, ticker=tracker_key)
        return await self._instrument_info_provider.get_info(req)

    def _convert_price_currency(
        self,
        price: Dezimal,
        info_currency: Optional[str],
        target_currency: str,
        fiat_matrix,
    ) -> Optional[Dezimal]:
        if not info_currency or info_currency == target_currency:
            return price

        try:
            exchange_rate: Dezimal = fiat_matrix[target_currency][info_currency]
            return price / exchange_rate
        except KeyError:
            if price is None:
                self._log.error(
                    "Missing fiat conversion rate from %s to %s",
                    info_currency,
                    target_currency,
                )
            return None

    async def _update_entry_quote(
        self,
        entry_id: UUID,
        product_type: ProductType,
        tracker_key: Optional[str],
        fiat_matrix,
    ):
        if not tracker_key:
            return

        resolved = await self._resolve_entry_info(entry_id, product_type)
        if not resolved:
            return

        shares, currency, instrument_type = resolved
        info = await self._fetch_instrument_info(tracker_key, instrument_type)
        if not (info and info.price):
            return

        price = self._convert_price_currency(
            info.price, info.currency, currency, fiat_matrix
        )

        market_value = round(shares * price, 4)

        await self._position_port.update_market_value(
            entry_id, product_type, market_value
        )
