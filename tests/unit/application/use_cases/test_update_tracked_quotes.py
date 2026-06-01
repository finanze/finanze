from uuid import uuid4

import pytest
from unittest.mock import AsyncMock, MagicMock

from application.use_cases.update_tracked_quotes import UpdateTrackedQuotesImpl
from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType
from domain.global_position import (
    EquityType,
    FundDetail,
    FundInvestments,
    FundType,
    GlobalPosition,
    ManualEntryData,
    ManualPositionData,
    ProductType,
    StockDetail,
    StockInvestments,
)
from domain.instrument import InstrumentDataRequest, InstrumentInfo, InstrumentType


class _NoopTransaction:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *args):
        return False


def _make_transaction_handler():
    handler = MagicMock()
    handler.start = MagicMock(return_value=_NoopTransaction())
    return handler


def _make_entity() -> Entity:
    return Entity(
        id=uuid4(),
        name="Manual",
        natural_id=None,
        type=EntityType.FINANCIAL_INSTITUTION,
        origin=EntityOrigin.MANUAL,
        icon_url=None,
    )


def _build_use_case(
    position_port=None,
    manual_position_data_port=None,
    instrument_info_provider=None,
    exchange_rate_provider=None,
    snapshot_writer=None,
    transaction_handler_port=None,
):
    if position_port is None:
        position_port = MagicMock()
        position_port.get_by_id = AsyncMock(return_value=None)
    if manual_position_data_port is None:
        manual_position_data_port = MagicMock()
        manual_position_data_port.get_trackable = AsyncMock(return_value=[])
    if instrument_info_provider is None:
        instrument_info_provider = MagicMock()
        instrument_info_provider.get_info = AsyncMock(return_value=None)
    if exchange_rate_provider is None:
        exchange_rate_provider = MagicMock()
        exchange_rate_provider.get_matrix = AsyncMock(return_value={})
    if snapshot_writer is None:
        snapshot_writer = MagicMock()
        snapshot_writer.write = AsyncMock()
    if transaction_handler_port is None:
        transaction_handler_port = _make_transaction_handler()

    return UpdateTrackedQuotesImpl(
        position_port=position_port,
        manual_position_data_port=manual_position_data_port,
        instrument_info_provider=instrument_info_provider,
        exchange_rate_provider=exchange_rate_provider,
        snapshot_writer=snapshot_writer,
        transaction_handler_port=transaction_handler_port,
    )


def _make_trackable_entry(
    entry_id=None,
    global_position_id=None,
    product_type: ProductType = ProductType.STOCK_ETF,
    tracker_key: str = "AAPL",
) -> ManualPositionData:
    return ManualPositionData(
        entry_id=entry_id or uuid4(),
        global_position_id=global_position_id or uuid4(),
        product_type=product_type,
        data=ManualEntryData(tracker_key=tracker_key),
    )


def _make_stock_detail(
    entry_id=None,
    shares=Dezimal(10),
    currency="EUR",
    equity_type=EquityType.STOCK,
    market_value=Dezimal(0),
) -> StockDetail:
    return StockDetail(
        id=entry_id or uuid4(),
        name="Test Stock",
        ticker="TST",
        isin="US0000000000",
        shares=shares,
        market_value=market_value,
        currency=currency,
        type=equity_type,
        initial_investment=Dezimal(100),
    )


def _make_fund_detail(
    entry_id=None,
    shares=Dezimal(10),
    currency="EUR",
    fund_type=FundType.MUTUAL_FUND,
    market_value=Dezimal(0),
) -> FundDetail:
    return FundDetail(
        id=entry_id or uuid4(),
        name="Test Fund",
        isin="LU0000000000",
        market=None,
        shares=shares,
        market_value=market_value,
        currency=currency,
        type=fund_type,
        initial_investment=Dezimal(100),
    )


def _make_position(
    global_position_id,
    stocks=None,
    funds=None,
) -> GlobalPosition:
    products = {}
    if stocks is not None:
        products[ProductType.STOCK_ETF] = StockInvestments(entries=stocks)
    if funds is not None:
        products[ProductType.FUND] = FundInvestments(entries=funds)
    return GlobalPosition(
        id=global_position_id,
        entity=_make_entity(),
        products=products,
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


class TestNoTrackableEntries:
    @pytest.mark.asyncio
    async def test_does_nothing_when_no_trackable_entries(self):
        position_port = MagicMock()
        position_port.get_by_id = AsyncMock()

        exchange_rate_provider = MagicMock()
        exchange_rate_provider.get_matrix = AsyncMock(return_value={})

        manual_position_data_port = MagicMock()
        manual_position_data_port.get_trackable = AsyncMock(return_value=[])

        snapshot_writer = MagicMock()
        snapshot_writer.write = AsyncMock()

        use_case = _build_use_case(
            position_port=position_port,
            manual_position_data_port=manual_position_data_port,
            exchange_rate_provider=exchange_rate_provider,
            snapshot_writer=snapshot_writer,
        )

        await use_case.execute()

        exchange_rate_provider.get_matrix.assert_not_called()
        position_port.get_by_id.assert_not_called()
        snapshot_writer.write.assert_not_called()


class TestStockQuoteUpdate:
    @pytest.mark.asyncio
    async def test_updates_stock_market_value(self):
        global_position_id = uuid4()
        entry = _make_trackable_entry(
            global_position_id=global_position_id,
            product_type=ProductType.STOCK_ETF,
            tracker_key="TST",
        )
        stock_detail = _make_stock_detail(
            entry_id=entry.entry_id,
            shares=Dezimal(10),
            currency="EUR",
            equity_type=EquityType.STOCK,
        )
        position = _make_position(global_position_id, stocks=[stock_detail])
        instrument_info = _make_instrument_info(
            price=Dezimal(50),
            currency="EUR",
            instrument_type=InstrumentType.STOCK,
        )

        position_port = MagicMock()
        position_port.get_by_id = AsyncMock(return_value=position)

        manual_position_data_port = MagicMock()
        manual_position_data_port.get_trackable = AsyncMock(return_value=[entry])

        instrument_info_provider = MagicMock()
        instrument_info_provider.get_info = AsyncMock(return_value=instrument_info)

        snapshot_writer = MagicMock()
        snapshot_writer.write = AsyncMock()

        use_case = _build_use_case(
            position_port=position_port,
            manual_position_data_port=manual_position_data_port,
            instrument_info_provider=instrument_info_provider,
            snapshot_writer=snapshot_writer,
        )

        await use_case.execute()

        assert stock_detail.market_value == Dezimal(500)
        snapshot_writer.write.assert_awaited_once()
        written_entity, written_position = snapshot_writer.write.await_args.args
        assert written_entity is position.entity
        assert written_position is position

    @pytest.mark.asyncio
    async def test_updates_etf_market_value(self):
        global_position_id = uuid4()
        entry = _make_trackable_entry(
            global_position_id=global_position_id,
            product_type=ProductType.STOCK_ETF,
            tracker_key="VWCE",
        )
        stock_detail = _make_stock_detail(
            entry_id=entry.entry_id,
            shares=Dezimal(5),
            currency="EUR",
            equity_type=EquityType.ETF,
        )
        position = _make_position(global_position_id, stocks=[stock_detail])
        instrument_info = _make_instrument_info(
            price=Dezimal(100),
            currency="EUR",
            instrument_type=InstrumentType.ETF,
        )

        position_port = MagicMock()
        position_port.get_by_id = AsyncMock(return_value=position)

        manual_position_data_port = MagicMock()
        manual_position_data_port.get_trackable = AsyncMock(return_value=[entry])

        instrument_info_provider = MagicMock()
        instrument_info_provider.get_info = AsyncMock(return_value=instrument_info)

        snapshot_writer = MagicMock()
        snapshot_writer.write = AsyncMock()

        use_case = _build_use_case(
            position_port=position_port,
            manual_position_data_port=manual_position_data_port,
            instrument_info_provider=instrument_info_provider,
            snapshot_writer=snapshot_writer,
        )

        await use_case.execute()

        instrument_info_provider.get_info.assert_called_once_with(
            InstrumentDataRequest(type=InstrumentType.ETF, ticker="VWCE")
        )
        assert stock_detail.market_value == Dezimal(500)
        snapshot_writer.write.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_converts_currency_when_price_currency_differs(self):
        global_position_id = uuid4()
        entry = _make_trackable_entry(
            global_position_id=global_position_id,
            product_type=ProductType.STOCK_ETF,
            tracker_key="AAPL",
        )
        stock_detail = _make_stock_detail(
            entry_id=entry.entry_id,
            shares=Dezimal(10),
            currency="EUR",
            equity_type=EquityType.STOCK,
        )
        position = _make_position(global_position_id, stocks=[stock_detail])
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
        position_port.get_by_id = AsyncMock(return_value=position)

        manual_position_data_port = MagicMock()
        manual_position_data_port.get_trackable = AsyncMock(return_value=[entry])

        instrument_info_provider = MagicMock()
        instrument_info_provider.get_info = AsyncMock(return_value=instrument_info)

        exchange_rate_provider = MagicMock()
        exchange_rate_provider.get_matrix = AsyncMock(return_value=fiat_matrix)

        snapshot_writer = MagicMock()
        snapshot_writer.write = AsyncMock()

        use_case = _build_use_case(
            position_port=position_port,
            manual_position_data_port=manual_position_data_port,
            instrument_info_provider=instrument_info_provider,
            exchange_rate_provider=exchange_rate_provider,
            snapshot_writer=snapshot_writer,
        )

        await use_case.execute()

        expected_price = Dezimal(100) / Dezimal("1.25")
        expected_market_value = round(Dezimal(10) * expected_price, 4)
        assert stock_detail.market_value == expected_market_value
        snapshot_writer.write.assert_awaited_once()


class TestFundQuoteUpdate:
    @pytest.mark.asyncio
    async def test_updates_mutual_fund_market_value(self):
        global_position_id = uuid4()
        entry = _make_trackable_entry(
            global_position_id=global_position_id,
            product_type=ProductType.FUND,
            tracker_key="LU0001",
        )
        fund_detail = _make_fund_detail(
            entry_id=entry.entry_id,
            shares=Dezimal(20),
            currency="EUR",
            fund_type=FundType.MUTUAL_FUND,
        )
        position = _make_position(global_position_id, funds=[fund_detail])
        instrument_info = _make_instrument_info(
            price=Dezimal(25),
            currency="EUR",
            instrument_type=InstrumentType.MUTUAL_FUND,
        )

        position_port = MagicMock()
        position_port.get_by_id = AsyncMock(return_value=position)

        manual_position_data_port = MagicMock()
        manual_position_data_port.get_trackable = AsyncMock(return_value=[entry])

        instrument_info_provider = MagicMock()
        instrument_info_provider.get_info = AsyncMock(return_value=instrument_info)

        snapshot_writer = MagicMock()
        snapshot_writer.write = AsyncMock()

        use_case = _build_use_case(
            position_port=position_port,
            manual_position_data_port=manual_position_data_port,
            instrument_info_provider=instrument_info_provider,
            snapshot_writer=snapshot_writer,
        )

        await use_case.execute()

        instrument_info_provider.get_info.assert_called_once_with(
            InstrumentDataRequest(type=InstrumentType.MUTUAL_FUND, ticker="LU0001")
        )
        assert fund_detail.market_value == Dezimal(500)
        snapshot_writer.write.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skips_non_mutual_fund(self):
        global_position_id = uuid4()
        entry = _make_trackable_entry(
            global_position_id=global_position_id,
            product_type=ProductType.FUND,
            tracker_key="PEN001",
        )
        fund_detail = _make_fund_detail(
            entry_id=entry.entry_id,
            shares=Dezimal(10),
            currency="EUR",
            fund_type=FundType.PENSION_FUND,
        )
        position = _make_position(global_position_id, funds=[fund_detail])

        position_port = MagicMock()
        position_port.get_by_id = AsyncMock(return_value=position)

        manual_position_data_port = MagicMock()
        manual_position_data_port.get_trackable = AsyncMock(return_value=[entry])

        instrument_info_provider = MagicMock()
        instrument_info_provider.get_info = AsyncMock()

        snapshot_writer = MagicMock()
        snapshot_writer.write = AsyncMock()

        use_case = _build_use_case(
            position_port=position_port,
            manual_position_data_port=manual_position_data_port,
            instrument_info_provider=instrument_info_provider,
            snapshot_writer=snapshot_writer,
        )

        await use_case.execute()

        instrument_info_provider.get_info.assert_not_called()
        snapshot_writer.write.assert_not_called()


class TestSkipScenarios:
    @pytest.mark.asyncio
    async def test_skips_entry_without_tracker_key(self):
        global_position_id = uuid4()
        entry = ManualPositionData(
            entry_id=uuid4(),
            global_position_id=global_position_id,
            product_type=ProductType.STOCK_ETF,
            data=ManualEntryData(tracker_key=None),
        )
        stock_detail = _make_stock_detail(entry_id=entry.entry_id)
        position = _make_position(global_position_id, stocks=[stock_detail])

        position_port = MagicMock()
        position_port.get_by_id = AsyncMock(return_value=position)

        manual_position_data_port = MagicMock()
        manual_position_data_port.get_trackable = AsyncMock(return_value=[entry])

        instrument_info_provider = MagicMock()
        instrument_info_provider.get_info = AsyncMock()

        snapshot_writer = MagicMock()
        snapshot_writer.write = AsyncMock()

        use_case = _build_use_case(
            position_port=position_port,
            manual_position_data_port=manual_position_data_port,
            instrument_info_provider=instrument_info_provider,
            snapshot_writer=snapshot_writer,
        )

        await use_case.execute()

        instrument_info_provider.get_info.assert_not_called()
        snapshot_writer.write.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_position_not_found(self):
        entry = _make_trackable_entry(
            product_type=ProductType.STOCK_ETF,
            tracker_key="MISSING",
        )

        position_port = MagicMock()
        position_port.get_by_id = AsyncMock(return_value=None)

        manual_position_data_port = MagicMock()
        manual_position_data_port.get_trackable = AsyncMock(return_value=[entry])

        instrument_info_provider = MagicMock()
        instrument_info_provider.get_info = AsyncMock()

        snapshot_writer = MagicMock()
        snapshot_writer.write = AsyncMock()

        use_case = _build_use_case(
            position_port=position_port,
            manual_position_data_port=manual_position_data_port,
            instrument_info_provider=instrument_info_provider,
            snapshot_writer=snapshot_writer,
        )

        await use_case.execute()

        instrument_info_provider.get_info.assert_not_called()
        snapshot_writer.write.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_instrument_info_not_found(self):
        global_position_id = uuid4()
        entry = _make_trackable_entry(
            global_position_id=global_position_id,
            product_type=ProductType.STOCK_ETF,
            tracker_key="TST",
        )
        stock_detail = _make_stock_detail(
            entry_id=entry.entry_id,
            shares=Dezimal(10),
            currency="EUR",
            equity_type=EquityType.STOCK,
        )
        position = _make_position(global_position_id, stocks=[stock_detail])

        position_port = MagicMock()
        position_port.get_by_id = AsyncMock(return_value=position)

        manual_position_data_port = MagicMock()
        manual_position_data_port.get_trackable = AsyncMock(return_value=[entry])

        instrument_info_provider = MagicMock()
        instrument_info_provider.get_info = AsyncMock(return_value=None)

        snapshot_writer = MagicMock()
        snapshot_writer.write = AsyncMock()

        use_case = _build_use_case(
            position_port=position_port,
            manual_position_data_port=manual_position_data_port,
            instrument_info_provider=instrument_info_provider,
            snapshot_writer=snapshot_writer,
        )

        await use_case.execute()

        snapshot_writer.write.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_write_when_value_unchanged(self):
        global_position_id = uuid4()
        entry = _make_trackable_entry(
            global_position_id=global_position_id,
            product_type=ProductType.STOCK_ETF,
            tracker_key="TST",
        )
        stock_detail = _make_stock_detail(
            entry_id=entry.entry_id,
            shares=Dezimal(10),
            currency="EUR",
            equity_type=EquityType.STOCK,
            market_value=Dezimal(500),
        )
        position = _make_position(global_position_id, stocks=[stock_detail])
        instrument_info = _make_instrument_info(
            price=Dezimal(50),
            currency="EUR",
            instrument_type=InstrumentType.STOCK,
        )

        position_port = MagicMock()
        position_port.get_by_id = AsyncMock(return_value=position)

        manual_position_data_port = MagicMock()
        manual_position_data_port.get_trackable = AsyncMock(return_value=[entry])

        instrument_info_provider = MagicMock()
        instrument_info_provider.get_info = AsyncMock(return_value=instrument_info)

        snapshot_writer = MagicMock()
        snapshot_writer.write = AsyncMock()

        use_case = _build_use_case(
            position_port=position_port,
            manual_position_data_port=manual_position_data_port,
            instrument_info_provider=instrument_info_provider,
            snapshot_writer=snapshot_writer,
        )

        await use_case.execute()

        snapshot_writer.write.assert_not_called()


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_continues_on_individual_position_failure(self):
        gp_fail = uuid4()
        gp_ok = uuid4()
        entry_fail = _make_trackable_entry(
            global_position_id=gp_fail,
            product_type=ProductType.STOCK_ETF,
            tracker_key="FAIL",
        )
        entry_ok = _make_trackable_entry(
            global_position_id=gp_ok,
            product_type=ProductType.STOCK_ETF,
            tracker_key="OK",
        )

        stock_ok = _make_stock_detail(
            entry_id=entry_ok.entry_id,
            shares=Dezimal(5),
            currency="EUR",
            equity_type=EquityType.STOCK,
        )
        position_ok = _make_position(gp_ok, stocks=[stock_ok])
        instrument_info_ok = _make_instrument_info(
            price=Dezimal(20),
            currency="EUR",
            instrument_type=InstrumentType.STOCK,
        )

        async def get_by_id_side_effect(position_id):
            if position_id == gp_fail:
                raise RuntimeError("Simulated failure")
            return position_ok

        position_port = MagicMock()
        position_port.get_by_id = AsyncMock(side_effect=get_by_id_side_effect)

        manual_position_data_port = MagicMock()
        manual_position_data_port.get_trackable = AsyncMock(
            return_value=[entry_fail, entry_ok]
        )

        instrument_info_provider = MagicMock()
        instrument_info_provider.get_info = AsyncMock(return_value=instrument_info_ok)

        snapshot_writer = MagicMock()
        snapshot_writer.write = AsyncMock()

        use_case = _build_use_case(
            position_port=position_port,
            manual_position_data_port=manual_position_data_port,
            instrument_info_provider=instrument_info_provider,
            snapshot_writer=snapshot_writer,
        )

        await use_case.execute()

        assert stock_ok.market_value == Dezimal(100)
        snapshot_writer.write.assert_awaited_once()
        _, written_position = snapshot_writer.write.await_args.args
        assert written_position is position_ok
