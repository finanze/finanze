from uuid import uuid4

import pytest
from unittest.mock import AsyncMock, MagicMock

from application.use_cases.update_tracked_quotes import UpdateTrackedQuotesImpl
from domain.dezimal import Dezimal
from domain.global_position import (
    EquityType,
    FundDetail,
    FundType,
    ManualEntryData,
    ManualPositionData,
    ProductType,
    StockDetail,
)
from domain.instrument import InstrumentDataRequest, InstrumentInfo, InstrumentType


def _build_use_case(
    position_port=None,
    manual_position_data_port=None,
    instrument_info_provider=None,
    exchange_rate_provider=None,
):
    if position_port is None:
        position_port = MagicMock()
    if manual_position_data_port is None:
        manual_position_data_port = MagicMock()
        manual_position_data_port.get_trackable = AsyncMock(return_value=[])
    if instrument_info_provider is None:
        instrument_info_provider = MagicMock()
    if exchange_rate_provider is None:
        exchange_rate_provider = MagicMock()
        exchange_rate_provider.get_matrix = AsyncMock(return_value={})

    return UpdateTrackedQuotesImpl(
        position_port=position_port,
        manual_position_data_port=manual_position_data_port,
        instrument_info_provider=instrument_info_provider,
        exchange_rate_provider=exchange_rate_provider,
    )


def _make_trackable_entry(
    product_type: ProductType = ProductType.STOCK_ETF,
    tracker_key: str = "AAPL",
) -> ManualPositionData:
    return ManualPositionData(
        entry_id=uuid4(),
        global_position_id=uuid4(),
        product_type=product_type,
        data=ManualEntryData(tracker_key=tracker_key),
    )


def _make_stock_detail(
    entry_id=None,
    shares=Dezimal(10),
    currency="EUR",
    equity_type=EquityType.STOCK,
) -> StockDetail:
    return StockDetail(
        id=entry_id or uuid4(),
        name="Test Stock",
        ticker="TST",
        isin="US0000000000",
        shares=shares,
        market_value=Dezimal(0),
        currency=currency,
        type=equity_type,
        initial_investment=Dezimal(100),
    )


def _make_fund_detail(
    entry_id=None,
    shares=Dezimal(10),
    currency="EUR",
    fund_type=FundType.MUTUAL_FUND,
) -> FundDetail:
    return FundDetail(
        id=entry_id or uuid4(),
        name="Test Fund",
        isin="LU0000000000",
        market=None,
        shares=shares,
        market_value=Dezimal(0),
        currency=currency,
        type=fund_type,
        initial_investment=Dezimal(100),
    )


def _make_instrument_info(
    price=Dezimal(50),
    currency="EUR",
    instrument_type=InstrumentType.STOCK,
) -> InstrumentInfo:
    return InstrumentInfo(
        name="Test Instrument",
        currency=currency,
        type=instrument_type,
        price=price,
    )


def _make_fiat_matrix(rates=None):
    """Build a fiat exchange rate matrix.

    The matrix is indexed as fiat_matrix[target_currency][source_currency] = rate.
    To convert a price from source to target: price / rate.
    """
    if rates is None:
        return {}
    return rates


class TestNoTrackableEntries:
    @pytest.mark.asyncio
    async def test_does_nothing_when_no_trackable_entries(self):
        position_port = MagicMock()
        position_port.get_stock_detail = AsyncMock()
        position_port.get_fund_detail = AsyncMock()
        position_port.update_market_value = AsyncMock()

        exchange_rate_provider = MagicMock()
        exchange_rate_provider.get_matrix = AsyncMock(return_value={})

        manual_position_data_port = MagicMock()
        manual_position_data_port.get_trackable = AsyncMock(return_value=[])

        use_case = _build_use_case(
            position_port=position_port,
            manual_position_data_port=manual_position_data_port,
            exchange_rate_provider=exchange_rate_provider,
        )

        await use_case.execute()

        exchange_rate_provider.get_matrix.assert_not_called()
        position_port.get_stock_detail.assert_not_called()
        position_port.get_fund_detail.assert_not_called()
        position_port.update_market_value.assert_not_called()


class TestStockQuoteUpdate:
    @pytest.mark.asyncio
    async def test_updates_stock_market_value(self):
        entry = _make_trackable_entry(
            product_type=ProductType.STOCK_ETF,
            tracker_key="TST",
        )
        stock_detail = _make_stock_detail(
            entry_id=entry.entry_id,
            shares=Dezimal(10),
            currency="EUR",
            equity_type=EquityType.STOCK,
        )
        instrument_info = _make_instrument_info(
            price=Dezimal(50),
            currency="EUR",
            instrument_type=InstrumentType.STOCK,
        )

        position_port = MagicMock()
        position_port.get_stock_detail = AsyncMock(return_value=stock_detail)
        position_port.update_market_value = AsyncMock()

        manual_position_data_port = MagicMock()
        manual_position_data_port.get_trackable = AsyncMock(return_value=[entry])

        instrument_info_provider = MagicMock()
        instrument_info_provider.get_info = AsyncMock(return_value=instrument_info)

        exchange_rate_provider = MagicMock()
        exchange_rate_provider.get_matrix = AsyncMock(return_value={})

        use_case = _build_use_case(
            position_port=position_port,
            manual_position_data_port=manual_position_data_port,
            instrument_info_provider=instrument_info_provider,
            exchange_rate_provider=exchange_rate_provider,
        )

        await use_case.execute()

        position_port.update_market_value.assert_called_once_with(
            entry.entry_id, ProductType.STOCK_ETF, Dezimal(500)
        )

    @pytest.mark.asyncio
    async def test_updates_etf_market_value(self):
        entry = _make_trackable_entry(
            product_type=ProductType.STOCK_ETF,
            tracker_key="VWCE",
        )
        stock_detail = _make_stock_detail(
            entry_id=entry.entry_id,
            shares=Dezimal(5),
            currency="EUR",
            equity_type=EquityType.ETF,
        )
        instrument_info = _make_instrument_info(
            price=Dezimal(100),
            currency="EUR",
            instrument_type=InstrumentType.ETF,
        )

        position_port = MagicMock()
        position_port.get_stock_detail = AsyncMock(return_value=stock_detail)
        position_port.update_market_value = AsyncMock()

        manual_position_data_port = MagicMock()
        manual_position_data_port.get_trackable = AsyncMock(return_value=[entry])

        instrument_info_provider = MagicMock()
        instrument_info_provider.get_info = AsyncMock(return_value=instrument_info)

        exchange_rate_provider = MagicMock()
        exchange_rate_provider.get_matrix = AsyncMock(return_value={})

        use_case = _build_use_case(
            position_port=position_port,
            manual_position_data_port=manual_position_data_port,
            instrument_info_provider=instrument_info_provider,
            exchange_rate_provider=exchange_rate_provider,
        )

        await use_case.execute()

        instrument_info_provider.get_info.assert_called_once_with(
            InstrumentDataRequest(type=InstrumentType.ETF, ticker="VWCE")
        )
        position_port.update_market_value.assert_called_once_with(
            entry.entry_id, ProductType.STOCK_ETF, Dezimal(500)
        )

    @pytest.mark.asyncio
    async def test_converts_currency_when_price_currency_differs(self):
        entry = _make_trackable_entry(
            product_type=ProductType.STOCK_ETF,
            tracker_key="AAPL",
        )
        stock_detail = _make_stock_detail(
            entry_id=entry.entry_id,
            shares=Dezimal(10),
            currency="EUR",
            equity_type=EquityType.STOCK,
        )
        # Instrument price is in USD
        instrument_info = _make_instrument_info(
            price=Dezimal(100),
            currency="USD",
            instrument_type=InstrumentType.STOCK,
        )

        # fiat_matrix[target_currency][source_currency] = rate
        # conversion: price / rate => 100 / 1.25 = 80 EUR
        # market_value = 10 * 80 = 800
        fiat_matrix = {
            "EUR": {"USD": Dezimal("1.25")},
        }

        position_port = MagicMock()
        position_port.get_stock_detail = AsyncMock(return_value=stock_detail)
        position_port.update_market_value = AsyncMock()

        manual_position_data_port = MagicMock()
        manual_position_data_port.get_trackable = AsyncMock(return_value=[entry])

        instrument_info_provider = MagicMock()
        instrument_info_provider.get_info = AsyncMock(return_value=instrument_info)

        exchange_rate_provider = MagicMock()
        exchange_rate_provider.get_matrix = AsyncMock(return_value=fiat_matrix)

        use_case = _build_use_case(
            position_port=position_port,
            manual_position_data_port=manual_position_data_port,
            instrument_info_provider=instrument_info_provider,
            exchange_rate_provider=exchange_rate_provider,
        )

        await use_case.execute()

        # price_in_eur = 100 / 1.25 = 80
        # market_value = round(10 * 80, 4) = 800
        call_args = position_port.update_market_value.call_args
        assert call_args[0][0] == entry.entry_id
        assert call_args[0][1] == ProductType.STOCK_ETF
        expected_price = Dezimal(100) / Dezimal("1.25")
        expected_market_value = round(Dezimal(10) * expected_price, 4)
        assert call_args[0][2] == expected_market_value


class TestFundQuoteUpdate:
    @pytest.mark.asyncio
    async def test_updates_mutual_fund_market_value(self):
        entry = _make_trackable_entry(
            product_type=ProductType.FUND,
            tracker_key="LU0001",
        )
        fund_detail = _make_fund_detail(
            entry_id=entry.entry_id,
            shares=Dezimal(20),
            currency="EUR",
            fund_type=FundType.MUTUAL_FUND,
        )
        instrument_info = _make_instrument_info(
            price=Dezimal(25),
            currency="EUR",
            instrument_type=InstrumentType.MUTUAL_FUND,
        )

        position_port = MagicMock()
        position_port.get_fund_detail = AsyncMock(return_value=fund_detail)
        position_port.update_market_value = AsyncMock()

        manual_position_data_port = MagicMock()
        manual_position_data_port.get_trackable = AsyncMock(return_value=[entry])

        instrument_info_provider = MagicMock()
        instrument_info_provider.get_info = AsyncMock(return_value=instrument_info)

        exchange_rate_provider = MagicMock()
        exchange_rate_provider.get_matrix = AsyncMock(return_value={})

        use_case = _build_use_case(
            position_port=position_port,
            manual_position_data_port=manual_position_data_port,
            instrument_info_provider=instrument_info_provider,
            exchange_rate_provider=exchange_rate_provider,
        )

        await use_case.execute()

        instrument_info_provider.get_info.assert_called_once_with(
            InstrumentDataRequest(type=InstrumentType.MUTUAL_FUND, ticker="LU0001")
        )
        position_port.update_market_value.assert_called_once_with(
            entry.entry_id, ProductType.FUND, Dezimal(500)
        )

    @pytest.mark.asyncio
    async def test_skips_non_mutual_fund(self):
        entry = _make_trackable_entry(
            product_type=ProductType.FUND,
            tracker_key="PEN001",
        )
        fund_detail = _make_fund_detail(
            entry_id=entry.entry_id,
            shares=Dezimal(10),
            currency="EUR",
            fund_type=FundType.PENSION_FUND,
        )

        position_port = MagicMock()
        position_port.get_fund_detail = AsyncMock(return_value=fund_detail)
        position_port.update_market_value = AsyncMock()

        manual_position_data_port = MagicMock()
        manual_position_data_port.get_trackable = AsyncMock(return_value=[entry])

        instrument_info_provider = MagicMock()
        instrument_info_provider.get_info = AsyncMock()

        exchange_rate_provider = MagicMock()
        exchange_rate_provider.get_matrix = AsyncMock(return_value={})

        use_case = _build_use_case(
            position_port=position_port,
            manual_position_data_port=manual_position_data_port,
            instrument_info_provider=instrument_info_provider,
            exchange_rate_provider=exchange_rate_provider,
        )

        await use_case.execute()

        instrument_info_provider.get_info.assert_not_called()
        position_port.update_market_value.assert_not_called()


class TestSkipScenarios:
    @pytest.mark.asyncio
    async def test_skips_entry_without_tracker_key(self):
        entry = ManualPositionData(
            entry_id=uuid4(),
            global_position_id=uuid4(),
            product_type=ProductType.STOCK_ETF,
            data=ManualEntryData(tracker_key=None),
        )

        position_port = MagicMock()
        position_port.get_stock_detail = AsyncMock()
        position_port.get_fund_detail = AsyncMock()
        position_port.update_market_value = AsyncMock()

        manual_position_data_port = MagicMock()
        manual_position_data_port.get_trackable = AsyncMock(return_value=[entry])

        instrument_info_provider = MagicMock()
        instrument_info_provider.get_info = AsyncMock()

        exchange_rate_provider = MagicMock()
        exchange_rate_provider.get_matrix = AsyncMock(return_value={})

        use_case = _build_use_case(
            position_port=position_port,
            manual_position_data_port=manual_position_data_port,
            instrument_info_provider=instrument_info_provider,
            exchange_rate_provider=exchange_rate_provider,
        )

        await use_case.execute()

        position_port.get_stock_detail.assert_not_called()
        position_port.get_fund_detail.assert_not_called()
        instrument_info_provider.get_info.assert_not_called()
        position_port.update_market_value.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_stock_detail_not_found(self):
        entry = _make_trackable_entry(
            product_type=ProductType.STOCK_ETF,
            tracker_key="MISSING",
        )

        position_port = MagicMock()
        position_port.get_stock_detail = AsyncMock(return_value=None)
        position_port.update_market_value = AsyncMock()

        manual_position_data_port = MagicMock()
        manual_position_data_port.get_trackable = AsyncMock(return_value=[entry])

        instrument_info_provider = MagicMock()
        instrument_info_provider.get_info = AsyncMock()

        exchange_rate_provider = MagicMock()
        exchange_rate_provider.get_matrix = AsyncMock(return_value={})

        use_case = _build_use_case(
            position_port=position_port,
            manual_position_data_port=manual_position_data_port,
            instrument_info_provider=instrument_info_provider,
            exchange_rate_provider=exchange_rate_provider,
        )

        await use_case.execute()

        instrument_info_provider.get_info.assert_not_called()
        position_port.update_market_value.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_instrument_info_not_found(self):
        entry = _make_trackable_entry(
            product_type=ProductType.STOCK_ETF,
            tracker_key="TST",
        )
        stock_detail = _make_stock_detail(
            entry_id=entry.entry_id,
            shares=Dezimal(10),
            currency="EUR",
            equity_type=EquityType.STOCK,
        )

        position_port = MagicMock()
        position_port.get_stock_detail = AsyncMock(return_value=stock_detail)
        position_port.update_market_value = AsyncMock()

        manual_position_data_port = MagicMock()
        manual_position_data_port.get_trackable = AsyncMock(return_value=[entry])

        instrument_info_provider = MagicMock()
        instrument_info_provider.get_info = AsyncMock(return_value=None)

        exchange_rate_provider = MagicMock()
        exchange_rate_provider.get_matrix = AsyncMock(return_value={})

        use_case = _build_use_case(
            position_port=position_port,
            manual_position_data_port=manual_position_data_port,
            instrument_info_provider=instrument_info_provider,
            exchange_rate_provider=exchange_rate_provider,
        )

        await use_case.execute()

        position_port.update_market_value.assert_not_called()


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_continues_on_individual_entry_failure(self):
        entry_fail = _make_trackable_entry(
            product_type=ProductType.STOCK_ETF,
            tracker_key="FAIL",
        )
        entry_ok = _make_trackable_entry(
            product_type=ProductType.STOCK_ETF,
            tracker_key="OK",
        )

        stock_detail_ok = _make_stock_detail(
            entry_id=entry_ok.entry_id,
            shares=Dezimal(5),
            currency="EUR",
            equity_type=EquityType.STOCK,
        )
        instrument_info_ok = _make_instrument_info(
            price=Dezimal(20),
            currency="EUR",
            instrument_type=InstrumentType.STOCK,
        )

        async def get_stock_detail_side_effect(entry_id):
            if entry_id == entry_fail.entry_id:
                raise RuntimeError("Simulated failure")
            return stock_detail_ok

        position_port = MagicMock()
        position_port.get_stock_detail = AsyncMock(
            side_effect=get_stock_detail_side_effect
        )
        position_port.update_market_value = AsyncMock()

        manual_position_data_port = MagicMock()
        manual_position_data_port.get_trackable = AsyncMock(
            return_value=[entry_fail, entry_ok]
        )

        instrument_info_provider = MagicMock()
        instrument_info_provider.get_info = AsyncMock(return_value=instrument_info_ok)

        exchange_rate_provider = MagicMock()
        exchange_rate_provider.get_matrix = AsyncMock(return_value={})

        use_case = _build_use_case(
            position_port=position_port,
            manual_position_data_port=manual_position_data_port,
            instrument_info_provider=instrument_info_provider,
            exchange_rate_provider=exchange_rate_provider,
        )

        await use_case.execute()

        # The second entry should still be processed despite the first one failing
        position_port.update_market_value.assert_called_once_with(
            entry_ok.entry_id, ProductType.STOCK_ETF, Dezimal(100)
        )
