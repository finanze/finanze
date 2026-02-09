import logging
from asyncio import Lock
from dataclasses import asdict
from datetime import datetime
from uuid import uuid4

from application.mixins.atomic_use_case import AtomicUCMixin
from application.ports.exchange_rate_provider import ExchangeRateProvider
from application.ports.last_fetches_port import LastFetchesPort
from application.ports.metal_price_provider import MetalPriceProvider
from application.ports.position_port import PositionPort
from application.ports.transaction_handler_port import TransactionHandlerPort
from dateutil.tz import tzlocal
from domain.commodity import (
    WEIGHT_CONVERSIONS,
    CommodityRegister,
    UpdateCommodityPosition,
)
from domain.dezimal import Dezimal
from domain.entity import Feature
from domain.exception.exceptions import ExecutionConflict
from domain.fetch_record import DataSource, FetchRecord
from domain.global_position import Commodities, Commodity, GlobalPosition, ProductType
from domain.native_entities import COMMODITIES
from domain.use_cases.save_commodities import SaveCommodities


class SaveCommoditiesImpl(AtomicUCMixin, SaveCommodities):
    def __init__(
        self,
        position_port: PositionPort,
        exchange_rates_provider: ExchangeRateProvider,
        metal_price_provider: MetalPriceProvider,
        last_fetches_port: LastFetchesPort,
        transaction_handler_port: TransactionHandlerPort,
    ):
        AtomicUCMixin.__init__(self, transaction_handler_port)

        self._position_port = position_port
        self._exchange_rates_provider = exchange_rates_provider
        self._metal_price_provider = metal_price_provider
        self._last_fetches_port = last_fetches_port

        self._lock = Lock()

        self._log = logging.getLogger(__name__)

    async def execute(self, commodity_position: UpdateCommodityPosition):
        if self._lock.locked():
            raise ExecutionConflict()

        async with self._lock:
            now = datetime.now(tzlocal())
            await self._position_port.delete_position_for_date(
                COMMODITIES.id, now.date(), source=DataSource.REAL
            )

            fiat_matrix = await self._exchange_rates_provider.get_matrix()
            commodity_entries = [
                await self._map_commodity(entry, fiat_matrix)
                for entry in commodity_position.registers
            ]
            products = {ProductType.COMMODITY: Commodities(commodity_entries)}
            position = GlobalPosition(
                id=uuid4(),
                entity=COMMODITIES,
                products=products,
            )

            await self._position_port.save(position)
            await self._last_fetches_port.save(
                [
                    FetchRecord(
                        entity_id=COMMODITIES.id, date=now, feature=Feature.POSITION
                    )
                ]
            )

    async def _map_commodity(
        self, commodity_register: CommodityRegister, fiat_matrix
    ) -> Commodity:
        commodity_register_dict = asdict(commodity_register)

        currency = commodity_register.currency or "EUR"
        commodity_register_dict["currency"] = currency

        initial_investment = commodity_register.initial_investment
        avg_buy_price = commodity_register.average_buy_price
        if initial_investment:
            commodity_register_dict["average_buy_price"] = round(
                commodity_register.initial_investment / commodity_register.amount, 4
            )
            commodity_register_dict["initial_investment"] = round(initial_investment, 2)
        elif avg_buy_price:
            commodity_register_dict["initial_investment"] = round(
                commodity_register.amount * commodity_register.average_buy_price, 2
            )
            commodity_register_dict["average_buy_price"] = round(avg_buy_price, 4)

        exchange_rate = await self._metal_price_provider.get_price(
            commodity_register.type
        )
        if exchange_rate is None:
            commodity_register_dict["market_value"] = initial_investment or Dezimal("0")
            return Commodity(**commodity_register_dict, id=uuid4())

        amount = commodity_register.amount
        if exchange_rate.unit != commodity_register.unit:
            conversion_factor = WEIGHT_CONVERSIONS[exchange_rate.unit][
                commodity_register.unit
            ]
            amount = amount / conversion_factor

        rate = exchange_rate.price
        if exchange_rate.currency != currency:
            fiat_rate = fiat_matrix[exchange_rate.currency][currency]
            rate = rate * fiat_rate

        commodity_register_dict["market_value"] = round(amount * rate, 2)

        return Commodity(**commodity_register_dict, id=uuid4())
