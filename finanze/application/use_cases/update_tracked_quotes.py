import logging
from asyncio import Lock
from collections import defaultdict
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from dateutil.tz import tzlocal

from application.ports.exchange_rate_provider import ExchangeRateProvider
from application.ports.instrument_info_provider import InstrumentInfoProvider
from application.ports.manual_position_data_port import ManualPositionDataPort
from application.ports.position_port import PositionPort
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.use_cases.manual_position_snapshot import (
    ManualPositionSnapshotWriter,
)
from domain.dezimal import Dezimal
from domain.exception.exceptions import ExecutionConflict
from domain.global_position import (
    DataSource,
    EquityType,
    FundType,
    GlobalPosition,
    ManualPositionData,
    ProductType,
)
from domain.instrument import InstrumentDataRequest, InstrumentInfo, InstrumentType
from domain.use_cases.update_tracked_quotes import UpdateTrackedQuotes

_TRACKABLE_PRODUCTS = (ProductType.STOCK_ETF, ProductType.FUND)


class UpdateTrackedQuotesImpl(UpdateTrackedQuotes):
    def __init__(
        self,
        position_port: PositionPort,
        manual_position_data_port: ManualPositionDataPort,
        instrument_info_provider: InstrumentInfoProvider,
        exchange_rate_provider: ExchangeRateProvider,
        snapshot_writer: ManualPositionSnapshotWriter,
        transaction_handler_port: TransactionHandlerPort,
    ):
        self._position_port = position_port
        self._manual_position_data_port = manual_position_data_port
        self._instrument_info_provider = instrument_info_provider
        self._exchange_rate_provider = exchange_rate_provider
        self._snapshot_writer = snapshot_writer
        self._transaction_handler_port = transaction_handler_port

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

            grouped: dict[UUID, list[ManualPositionData]] = defaultdict(list)
            for mpd in trackable_entries:
                grouped[mpd.global_position_id].append(mpd)

            for global_position_id, entries in grouped.items():
                try:
                    await self._refresh_position(
                        global_position_id, entries, fiat_matrix
                    )
                except Exception:
                    self._log.exception(
                        "Failed updating tracked quotes for position %s",
                        global_position_id,
                    )
                    continue

    async def _refresh_position(
        self,
        global_position_id: UUID,
        entries: list[ManualPositionData],
        fiat_matrix,
    ):
        position = await self._position_port.get_by_id(global_position_id)
        if not position:
            return

        changed = await self._apply_quote_updates(position, entries, fiat_matrix)
        if not changed:
            return

        position.id = uuid4()
        position.date = datetime.now(tzlocal())
        position.source = DataSource.MANUAL

        async with self._transaction_handler_port.start():
            await self._snapshot_writer.write(position.entity, position)

    async def _apply_quote_updates(
        self,
        position: GlobalPosition,
        entries: list[ManualPositionData],
        fiat_matrix,
    ) -> bool:
        tracker_by_entry: dict[UUID, Optional[str]] = {
            mpd.entry_id: (mpd.data.tracker_key if mpd.data else None)
            for mpd in entries
        }

        changed = False
        for product_type in _TRACKABLE_PRODUCTS:
            container = position.products.get(product_type)
            if not (container and getattr(container, "entries", None)):
                continue

            for entry in container.entries:
                tracker_key = tracker_by_entry.get(entry.id)
                new_value = await self._compute_market_value(
                    entry, product_type, tracker_key, fiat_matrix
                )
                if new_value is None:
                    continue
                if new_value != entry.market_value:
                    entry.market_value = new_value
                    changed = True

        return changed

    async def _compute_market_value(
        self,
        entry,
        product_type: ProductType,
        tracker_key: Optional[str],
        fiat_matrix,
    ) -> Optional[Dezimal]:
        if not tracker_key:
            return None

        instrument_type = self._instrument_type_for(entry, product_type)
        if instrument_type is None:
            return None

        info = await self._fetch_instrument_info(tracker_key, instrument_type)
        if not (info and info.price):
            return None

        price = self._convert_price_currency(
            info.price, info.currency, entry.currency, fiat_matrix
        )
        if price is None:
            return None

        return round(entry.shares * price, 4)

    @staticmethod
    def _instrument_type_for(
        entry, product_type: ProductType
    ) -> Optional[InstrumentType]:
        if product_type == ProductType.STOCK_ETF:
            return (
                InstrumentType.STOCK
                if entry.type == EquityType.STOCK
                else InstrumentType.ETF
            )

        if product_type == ProductType.FUND:
            if entry.type != FundType.MUTUAL_FUND:
                return None
            return InstrumentType.MUTUAL_FUND

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
            self._log.error(
                "Missing fiat conversion rate from %s to %s",
                info_currency,
                target_currency,
            )
            return None
