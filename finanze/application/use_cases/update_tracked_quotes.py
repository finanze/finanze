import logging
from asyncio import Lock
from collections import defaultdict
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from dateutil.tz import tzlocal

from application.ports.exchange_rate_provider import ExchangeRateProvider
from application.ports.exchange_rate_storage import ExchangeRateStorage
from application.ports.instrument_info_provider import InstrumentInfoProvider
from application.ports.manual_position_data_port import ManualPositionDataPort
from application.ports.position_port import PositionPort
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.ports.virtual_import_registry import VirtualImportRegistry
from application.use_cases.manual_position_snapshot import (
    ManualPositionSnapshotWriter,
)
from domain.crypto import crypto_rate_key
from domain.dezimal import Dezimal
from domain.entity import Feature
from domain.exception.exceptions import ExecutionConflict
from domain.exchange_rate import ExchangeRates
from domain.global_position import (
    CryptoCurrencyPosition,
    DataSource,
    EquityType,
    FundType,
    GlobalPosition,
    ManualPositionData,
    ProductType,
)
from domain.instrument import InstrumentDataRequest, InstrumentInfo, InstrumentType
from domain.tracking import UpdateTrackedResult
from domain.use_cases.update_tracked_quotes import UpdateTrackedQuotes
from domain.virtual_data import VirtualDataSource

_TRACKABLE_PRODUCTS = (ProductType.STOCK_ETF, ProductType.FUND)


class UpdateTrackedQuotesImpl(UpdateTrackedQuotes):
    def __init__(
        self,
        position_port: PositionPort,
        manual_position_data_port: ManualPositionDataPort,
        instrument_info_provider: InstrumentInfoProvider,
        exchange_rate_provider: ExchangeRateProvider,
        exchange_rate_storage: ExchangeRateStorage,
        virtual_import_registry: VirtualImportRegistry,
        snapshot_writer: ManualPositionSnapshotWriter,
        transaction_handler_port: TransactionHandlerPort,
    ):
        self._position_port = position_port
        self._manual_position_data_port = manual_position_data_port
        self._instrument_info_provider = instrument_info_provider
        self._exchange_rate_provider = exchange_rate_provider
        self._exchange_rate_storage = exchange_rate_storage
        self._virtual_import_registry = virtual_import_registry
        self._snapshot_writer = snapshot_writer
        self._transaction_handler_port = transaction_handler_port

        self._lock = Lock()
        self._log = logging.getLogger(__name__)

    async def execute(self):
        if self._lock.locked():
            raise ExecutionConflict()

        async with self._lock:
            trackable_entries = await self._manual_position_data_port.get_trackable()
            grouped: dict[UUID, list[ManualPositionData]] = defaultdict(list)
            for mpd in trackable_entries:
                grouped[mpd.global_position_id].append(mpd)

            crypto_position_ids = await self._get_manual_crypto_position_ids()

            if not grouped and not crypto_position_ids:
                return UpdateTrackedResult(had_tracked=False)

            fund_entries = sum(
                1 for mpd in trackable_entries if mpd.product_type == ProductType.FUND
            )
            stock_etf_entries = sum(
                1
                for mpd in trackable_entries
                if mpd.product_type == ProductType.STOCK_ETF
            )
            crypto_entries = await self._count_manual_crypto_entries(
                crypto_position_ids
            )

            self._log.info(
                "Updating tracked quotes for %d instrument positions "
                "(%d funds, %d stocks/etfs) and %d crypto positions (%d entries)",
                len(grouped),
                fund_entries,
                stock_etf_entries,
                len(crypto_position_ids),
                crypto_entries,
            )

            fiat_matrix = (
                await self._exchange_rate_provider.get_matrix() if grouped else None
            )
            crypto_matrix = (
                await self._exchange_rate_storage.get() if crypto_position_ids else None
            )

            changed_entities: set[UUID] = set()
            changed_entries = 0
            refresh_ids = set(grouped.keys()) | crypto_position_ids
            for global_position_id in refresh_ids:
                position_entries = grouped.get(global_position_id, [])
                is_crypto = global_position_id in crypto_position_ids
                try:
                    result = await self._refresh_position(
                        global_position_id,
                        position_entries,
                        fiat_matrix,
                        crypto_matrix if is_crypto else None,
                    )
                    if result is not None:
                        entity_id, entry_count = result
                        changed_entities.add(entity_id)
                        changed_entries += entry_count
                except Exception:
                    tracker_keys = [
                        mpd.data.tracker_key
                        for mpd in position_entries
                        if mpd.data and mpd.data.tracker_key
                    ]
                    self._log.exception(
                        "Failed updating tracked quotes for position %s "
                        "(crypto=%s, %d tracked entries, trackers=%s)",
                        global_position_id,
                        is_crypto,
                        len(position_entries),
                        tracker_keys,
                    )
                    continue

            self._log.info(
                "Finished updating tracked quotes: had_tracked=%s, "
                "%d changed entities, %d changed entries",
                True,
                len(changed_entities),
                changed_entries,
            )

            return UpdateTrackedResult(
                had_tracked=True, changed_entities=list(changed_entities)
            )

    async def _get_manual_crypto_position_ids(self) -> set[UUID]:
        records = await self._virtual_import_registry.get_last_import_records(
            VirtualDataSource.MANUAL
        )
        candidate_ids = {
            record.global_position_id
            for record in records
            if record.feature == Feature.POSITION and record.global_position_id
        }
        if not candidate_ids:
            return set()
        return await self._position_port.get_manual_crypto_position_ids(
            list(candidate_ids)
        )

    async def _count_manual_crypto_entries(self, crypto_position_ids: set[UUID]) -> int:
        count = 0
        for global_position_id in crypto_position_ids:
            position = await self._position_port.get_by_id(global_position_id)
            if not position:
                continue
            container = position.products.get(ProductType.CRYPTO)
            if not (container and getattr(container, "entries", None)):
                continue
            for wallet in container.entries:
                if wallet.id is not None:
                    continue
                count += sum(
                    1 for asset in wallet.assets if asset.source == DataSource.MANUAL
                )
        return count

    async def _refresh_position(
        self,
        global_position_id: UUID,
        entries: list[ManualPositionData],
        fiat_matrix,
        crypto_matrix: Optional[ExchangeRates],
    ) -> Optional[tuple[UUID, int]]:
        position = await self._position_port.get_by_id(global_position_id)
        if not position:
            return None

        changed_entries = 0
        if entries:
            changed_entries += await self._apply_quote_updates(
                position, entries, fiat_matrix
            )
        if crypto_matrix is not None:
            changed_entries += self._apply_crypto_updates(position, crypto_matrix)
        if not changed_entries:
            return None

        position.id = uuid4()
        position.date = datetime.now(tzlocal())
        position.source = DataSource.MANUAL

        async with self._transaction_handler_port.start():
            await self._snapshot_writer.write(position.entity, position)

        return position.entity.id, changed_entries

    def _apply_crypto_updates(
        self,
        position: GlobalPosition,
        crypto_matrix: ExchangeRates,
    ) -> int:
        container = position.products.get(ProductType.CRYPTO)
        if not (container and getattr(container, "entries", None)):
            return 0

        changed = 0
        for wallet in container.entries:
            if wallet.id is not None:
                continue
            for asset in wallet.assets:
                if asset.source != DataSource.MANUAL:
                    continue
                new_value = self._compute_crypto_market_value(asset, crypto_matrix)
                if new_value is None:
                    continue
                if new_value != asset.market_value:
                    asset.market_value = new_value
                    changed += 1

        return changed

    @staticmethod
    def _compute_crypto_market_value(
        asset: CryptoCurrencyPosition,
        crypto_matrix: ExchangeRates,
    ) -> Optional[Dezimal]:
        if not asset.currency or asset.amount is None:
            return None
        rates = crypto_matrix.get(asset.currency)
        if not rates:
            return None
        rate_key = crypto_rate_key(asset.type, asset.symbol, asset.contract_address)
        if rate_key is None:
            return None
        rate = rates.get(rate_key)
        if rate is None or rate == 0:
            return None
        price = Dezimal(1) / rate
        return round(asset.amount * price, 2)

    async def _apply_quote_updates(
        self,
        position: GlobalPosition,
        entries: list[ManualPositionData],
        fiat_matrix,
    ) -> int:
        tracker_by_entry: dict[UUID, Optional[str]] = {
            mpd.entry_id: (mpd.data.tracker_key if mpd.data else None)
            for mpd in entries
        }

        changed = 0
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
                    changed += 1

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
