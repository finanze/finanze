from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest

from application.use_cases.save_commodities import SaveCommoditiesImpl
from domain.commodity import (
    WEIGHT_CONVERSIONS,
    CommodityRegister,
    CommodityType,
    UpdateCommodityPosition,
    WeightUnit,
)
from domain.dezimal import Dezimal
from domain.exchange_rate import CommodityExchangeRate
from domain.global_position import ProductType
from domain.native_entities import COMMODITIES


def _build_use_case(
    position_port=None,
    exchange_rates_provider=None,
    metal_price_provider=None,
    last_fetches_port=None,
    transaction_handler_port=None,
):
    if position_port is None:
        position_port = AsyncMock()

    if exchange_rates_provider is None:
        exchange_rates_provider = AsyncMock()
        exchange_rates_provider.get_matrix = AsyncMock(return_value={})

    if metal_price_provider is None:
        metal_price_provider = AsyncMock()
        metal_price_provider.get_price = AsyncMock(return_value=None)

    if last_fetches_port is None:
        last_fetches_port = AsyncMock()

    if transaction_handler_port is None:
        transaction_handler_port = AsyncMock()

        @asynccontextmanager
        async def mock_tx():
            yield

        transaction_handler_port.start = mock_tx

    return SaveCommoditiesImpl(
        position_port=position_port,
        exchange_rates_provider=exchange_rates_provider,
        metal_price_provider=metal_price_provider,
        last_fetches_port=last_fetches_port,
        transaction_handler_port=transaction_handler_port,
    )


def _gold_register(
    amount=Dezimal("10"),
    unit=WeightUnit.GRAM,
    currency="EUR",
    initial_investment=None,
    average_buy_price=None,
) -> CommodityRegister:
    return CommodityRegister(
        name="Gold Bar",
        type=CommodityType.GOLD,
        amount=amount,
        unit=unit,
        currency=currency,
        initial_investment=initial_investment,
        average_buy_price=average_buy_price,
    )


def _gold_price(
    price=Dezimal("60"),
    unit=WeightUnit.GRAM,
    currency="EUR",
) -> CommodityExchangeRate:
    return CommodityExchangeRate(unit=unit, currency=currency, price=price)


# ---------------------------------------------------------------------------
# TestSaveCommodities
# ---------------------------------------------------------------------------


class TestSaveCommodities:
    @pytest.mark.asyncio
    async def test_saves_position_with_commodity_entries(self):
        metal_price_provider = AsyncMock()
        metal_price_provider.get_price = AsyncMock(
            return_value=_gold_price(
                price=Dezimal("50"), unit=WeightUnit.GRAM, currency="EUR"
            )
        )

        exchange_rates_provider = AsyncMock()
        exchange_rates_provider.get_matrix = AsyncMock(return_value={})

        position_port = AsyncMock()

        use_case = _build_use_case(
            position_port=position_port,
            exchange_rates_provider=exchange_rates_provider,
            metal_price_provider=metal_price_provider,
        )

        register = _gold_register(amount=Dezimal("5"), currency="EUR")
        request = UpdateCommodityPosition(registers=[register])

        await use_case.execute(request)

        position_port.save.assert_called_once()
        saved_position = position_port.save.call_args[0][0]
        commodities = saved_position.products[ProductType.COMMODITY]
        assert len(commodities.entries) == 1
        assert commodities.entries[0].market_value == Dezimal("250")

    @pytest.mark.asyncio
    async def test_defaults_currency_to_eur(self):
        metal_price_provider = AsyncMock()
        metal_price_provider.get_price = AsyncMock(
            return_value=_gold_price(
                price=Dezimal("60"), unit=WeightUnit.GRAM, currency="EUR"
            )
        )

        exchange_rates_provider = AsyncMock()
        exchange_rates_provider.get_matrix = AsyncMock(return_value={})

        position_port = AsyncMock()

        use_case = _build_use_case(
            position_port=position_port,
            exchange_rates_provider=exchange_rates_provider,
            metal_price_provider=metal_price_provider,
        )

        register = _gold_register(amount=Dezimal("1"), currency=None)
        request = UpdateCommodityPosition(registers=[register])

        await use_case.execute(request)

        saved_position = position_port.save.call_args[0][0]
        commodity = saved_position.products[ProductType.COMMODITY].entries[0]
        assert commodity.currency == "EUR"

    @pytest.mark.asyncio
    async def test_computes_market_value_from_metal_price(self):
        metal_price_provider = AsyncMock()
        metal_price_provider.get_price = AsyncMock(
            return_value=_gold_price(
                price=Dezimal("60"), unit=WeightUnit.GRAM, currency="EUR"
            )
        )

        exchange_rates_provider = AsyncMock()
        exchange_rates_provider.get_matrix = AsyncMock(return_value={})

        position_port = AsyncMock()

        use_case = _build_use_case(
            position_port=position_port,
            exchange_rates_provider=exchange_rates_provider,
            metal_price_provider=metal_price_provider,
        )

        register = _gold_register(
            amount=Dezimal("10"), unit=WeightUnit.GRAM, currency="EUR"
        )
        request = UpdateCommodityPosition(registers=[register])

        await use_case.execute(request)

        saved_position = position_port.save.call_args[0][0]
        commodity = saved_position.products[ProductType.COMMODITY].entries[0]
        assert commodity.market_value == Dezimal("600")

    @pytest.mark.asyncio
    async def test_converts_weight_unit(self):
        # Register is in TROY_OUNCE, metal price is per GRAM
        metal_price_provider = AsyncMock()
        metal_price_provider.get_price = AsyncMock(
            return_value=_gold_price(
                price=Dezimal("60"), unit=WeightUnit.GRAM, currency="EUR"
            )
        )

        exchange_rates_provider = AsyncMock()
        exchange_rates_provider.get_matrix = AsyncMock(return_value={})

        position_port = AsyncMock()

        use_case = _build_use_case(
            position_port=position_port,
            exchange_rates_provider=exchange_rates_provider,
            metal_price_provider=metal_price_provider,
        )

        register = _gold_register(
            amount=Dezimal("1"), unit=WeightUnit.TROY_OUNCE, currency="EUR"
        )
        request = UpdateCommodityPosition(registers=[register])

        await use_case.execute(request)

        # conversion_factor = WEIGHT_CONVERSIONS[GRAM][TROY_OUNCE] = 0.032150746568628
        # converted_amount = 1 / 0.032150746568628 = ~31.1034768
        # market_value = round(31.1034768 * 60, 2)
        conversion_factor = WEIGHT_CONVERSIONS[WeightUnit.GRAM][WeightUnit.TROY_OUNCE]
        converted_amount = Dezimal("1") / conversion_factor
        expected = round(converted_amount * Dezimal("60"), 2)

        saved_position = position_port.save.call_args[0][0]
        commodity = saved_position.products[ProductType.COMMODITY].entries[0]
        assert commodity.market_value == expected

    @pytest.mark.asyncio
    async def test_uses_initial_investment_when_no_price(self):
        metal_price_provider = AsyncMock()
        metal_price_provider.get_price = AsyncMock(return_value=None)

        exchange_rates_provider = AsyncMock()
        exchange_rates_provider.get_matrix = AsyncMock(return_value={})

        position_port = AsyncMock()

        use_case = _build_use_case(
            position_port=position_port,
            exchange_rates_provider=exchange_rates_provider,
            metal_price_provider=metal_price_provider,
        )

        register = _gold_register(
            amount=Dezimal("10"),
            currency="EUR",
            initial_investment=Dezimal("500"),
        )
        request = UpdateCommodityPosition(registers=[register])

        await use_case.execute(request)

        saved_position = position_port.save.call_args[0][0]
        commodity = saved_position.products[ProductType.COMMODITY].entries[0]
        assert commodity.market_value == Dezimal("500")


# ---------------------------------------------------------------------------
# TestCommodityDeleteBeforeSave
# ---------------------------------------------------------------------------


class TestCommodityDeleteBeforeSave:
    @pytest.mark.asyncio
    async def test_deletes_existing_position_before_saving(self):
        position_port = AsyncMock()

        call_order = []
        position_port.delete_position_for_date.side_effect = lambda *a, **kw: (
            call_order.append("delete")
        )

        async def save_side_effect(*a, **kw):
            call_order.append("save")

        position_port.save.side_effect = save_side_effect

        metal_price_provider = AsyncMock()
        metal_price_provider.get_price = AsyncMock(return_value=_gold_price())

        exchange_rates_provider = AsyncMock()
        exchange_rates_provider.get_matrix = AsyncMock(return_value={})

        use_case = _build_use_case(
            position_port=position_port,
            exchange_rates_provider=exchange_rates_provider,
            metal_price_provider=metal_price_provider,
        )

        register = _gold_register()
        request = UpdateCommodityPosition(registers=[register])

        await use_case.execute(request)

        position_port.delete_position_for_date.assert_called_once()
        assert call_order == ["delete", "save"]


# ---------------------------------------------------------------------------
# TestFetchRecordSaved
# ---------------------------------------------------------------------------


class TestFetchRecordSaved:
    @pytest.mark.asyncio
    async def test_saves_fetch_record_after_save(self):
        last_fetches_port = AsyncMock()
        position_port = AsyncMock()

        metal_price_provider = AsyncMock()
        metal_price_provider.get_price = AsyncMock(return_value=_gold_price())

        exchange_rates_provider = AsyncMock()
        exchange_rates_provider.get_matrix = AsyncMock(return_value={})

        use_case = _build_use_case(
            position_port=position_port,
            exchange_rates_provider=exchange_rates_provider,
            metal_price_provider=metal_price_provider,
            last_fetches_port=last_fetches_port,
        )

        register = _gold_register()
        request = UpdateCommodityPosition(registers=[register])

        await use_case.execute(request)

        last_fetches_port.save.assert_called_once()
        fetch_records = last_fetches_port.save.call_args[0][0]
        assert len(fetch_records) == 1
        assert fetch_records[0].entity_id == COMMODITIES.id


# ---------------------------------------------------------------------------
# TestCurrencyConversion
# ---------------------------------------------------------------------------


class TestCurrencyConversion:
    @pytest.mark.asyncio
    async def test_converts_metal_price_currency_via_fiat_matrix(self):
        # Metal price is in USD, register currency is EUR
        metal_price_provider = AsyncMock()
        metal_price_provider.get_price = AsyncMock(
            return_value=_gold_price(
                price=Dezimal("100"), unit=WeightUnit.GRAM, currency="USD"
            )
        )

        # The code does: fiat_matrix[exchange_rate.currency][currency]
        # i.e. fiat_matrix["USD"]["EUR"]
        fiat_matrix = {
            "USD": {"EUR": Dezimal("0.9")},
        }
        exchange_rates_provider = AsyncMock()
        exchange_rates_provider.get_matrix = AsyncMock(return_value=fiat_matrix)

        position_port = AsyncMock()

        use_case = _build_use_case(
            position_port=position_port,
            exchange_rates_provider=exchange_rates_provider,
            metal_price_provider=metal_price_provider,
        )

        register = _gold_register(
            amount=Dezimal("10"), unit=WeightUnit.GRAM, currency="EUR"
        )
        request = UpdateCommodityPosition(registers=[register])

        await use_case.execute(request)

        # rate = 100 * 0.9 = 90 EUR/gram
        # market_value = round(10 * 90, 2) = 900
        saved_position = position_port.save.call_args[0][0]
        commodity = saved_position.products[ProductType.COMMODITY].entries[0]
        assert commodity.market_value == Dezimal("900")
