from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from application.ports.gains_timeline_port import GainsTimelinePort
from application.use_cases.get_gains_timeline import GetGainsTimelineImpl
from domain.dezimal import Dezimal
from domain.gains_timeline import (
    AssetSnapshot,
    AssetValuation,
    GainsAssetFilter,
    GainsFlow,
    GainsQuality,
    GainsTimelineQuery,
    GainsWarning,
)
from domain.global_position import ProductType
from domain.transactions import TxType

_START = date(2025, 1, 1)
_HOLDER = "broker"
_ASSET = "ACME"
_MARKET_TYPES = [ProductType.STOCK_ETF, ProductType.FUND, ProductType.CRYPTO]


def _day(offset):
    return _START + timedelta(days=offset)


def _position(
    quantity, value, cost, *, asset_key=_ASSET, product_type=ProductType.STOCK_ETF
):
    return AssetValuation(
        product_type=product_type,
        asset_key=asset_key,
        currency="EUR",
        quantity=Dezimal(quantity),
        market_value=Dezimal(value),
        cost_basis=Dezimal(cost) if cost is not None else None,
    )


def _snapshot(offset, *positions, holder=_HOLDER):
    day = _day(offset)
    return AssetSnapshot(
        holder=holder,
        moment=datetime(day.year, day.month, day.day, 12),
        valuations=list(positions),
    )


def _held(
    offset,
    quantity,
    value,
    cost,
    product_type=ProductType.STOCK_ETF,
    *,
    holder=_HOLDER,
    asset_key=_ASSET,
):
    return _snapshot(
        offset,
        _position(
            quantity, value, cost, asset_key=asset_key, product_type=product_type
        ),
        holder=holder,
    )


def _trade(
    offset,
    transaction_type,
    amount,
    quantity,
    product_type=ProductType.STOCK_ETF,
    *,
    asset_key=_ASSET,
    holder=_HOLDER,
    fees="0",
    ratio=None,
):
    day = _day(offset)
    return GainsFlow(
        holder=holder,
        product_type=product_type,
        asset_key=asset_key,
        moment=datetime(day.year, day.month, day.day, 12),
        amount=Dezimal(amount),
        currency="EUR",
        quantity=Dezimal(quantity) if quantity is not None else None,
        split_ratio=Dezimal(ratio) if ratio is not None else None,
        fees=Dezimal(fees),
        transaction_type=transaction_type,
    )


def _round_trip(
    product_type=ProductType.STOCK_ETF,
    *,
    buy_day=4,
    sell_day=5,
    bought="5",
    sold="5",
    buy_amount="500",
    sell_amount="550",
    fees="0",
    holder=_HOLDER,
):
    return [
        _trade(
            buy_day,
            TxType.BUY,
            buy_amount,
            bought,
            product_type,
            fees=fees,
            holder=holder,
        ),
        _trade(
            sell_day,
            TxType.SELL,
            sell_amount,
            sold,
            product_type,
            fees=fees,
            holder=holder,
        ),
    ]


def _use_case(snapshots, flows):
    port = AsyncMock(spec=GainsTimelinePort)
    port.get_data_version.return_value = "1"
    port.get_asset_snapshots.return_value = snapshots
    port.get_flows.return_value = flows
    port.get_settlements.return_value = []
    port.get_split_ratios.return_value = []
    exchange = AsyncMock()
    exchange.get.return_value = {}
    entity = AsyncMock()
    entity.get_disabled_entities.return_value = []
    entity.get_all.return_value = []
    metal = AsyncMock()
    metal.get_partial_historic_rates.return_value = None
    return GetGainsTimelineImpl(port, exchange, entity, metal)


async def _timeline(
    snapshots, flows, last, *, first=None, product_type=ProductType.STOCK_ETF
):
    query = GainsTimelineQuery(
        assets=[GainsAssetFilter(product_type=product_type)],
        entities=[uuid4()],
        from_date=_day(first) if first is not None else None,
        to_date=_day(last),
    )
    return await _use_case(snapshots, flows).execute(query)


def _metrics(result):
    return {point.date: point.metrics for point in result.points}


def _days(result):
    return [point.date for point in result.points]


class TestMarketFlowSettlementBaseline:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("product_type", _MARKET_TYPES)
    async def test_buy_is_booked_by_same_day_snapshot(self, product_type):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000", product_type),
                _held(3, "12", "1240", "1200", product_type),
            ],
            [_trade(3, TxType.BUY, "200", "2", product_type)],
            3,
            product_type=product_type,
        )

        metrics = _metrics(result)[_day(3)]
        assert metrics.value == Dezimal(1240)
        assert metrics.net_contributions == Dezimal(1200)
        assert metrics.gain == Dezimal(40)
        assert result.quality == GainsQuality.COMPLETE
        assert result.warnings == []
        assert result.xirr is not None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("product_type", _MARKET_TYPES)
    async def test_buy_is_booked_by_next_snapshot(self, product_type):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000", product_type),
                _held(3, "12", "1230", "1200", product_type),
            ],
            [_trade(2, TxType.BUY, "200", "2", product_type)],
            3,
            product_type=product_type,
        )

        by_day = _metrics(result)
        assert by_day[_day(2)].value == Dezimal(1000)
        assert by_day[_day(2)].net_contributions == Dezimal(1000)
        assert by_day[_day(3)].value == Dezimal(1230)
        assert by_day[_day(3)].net_contributions == Dezimal(1200)
        assert by_day[_day(3)].gain == Dezimal(30)
        assert result.quality == GainsQuality.COMPLETE

    @pytest.mark.asyncio
    @pytest.mark.parametrize("product_type", _MARKET_TYPES)
    async def test_in_flight_buy_holds_back_unchanged_snapshot_day(self, product_type):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000", product_type),
                _held(2, "10", "990", "1000", product_type),
                _held(4, "12", "1220", "1200", product_type),
            ],
            [_trade(1, TxType.BUY, "200", "2", product_type)],
            4,
            product_type=product_type,
        )

        assert _days(result) == [_day(0), _day(1), _day(3), _day(4)]
        by_day = _metrics(result)
        assert by_day[_day(3)].value == Dezimal(990)
        assert by_day[_day(3)].net_contributions == Dezimal(1000)
        assert by_day[_day(4)].value == Dezimal(1220)
        assert by_day[_day(4)].net_contributions == Dezimal(1200)
        assert by_day[_day(4)].gain == Dezimal(20)
        assert result.quality == GainsQuality.COMPLETE

    @pytest.mark.asyncio
    @pytest.mark.parametrize("product_type", _MARKET_TYPES)
    async def test_in_flight_sell_holds_back_unchanged_snapshot_day(self, product_type):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000", product_type),
                _held(2, "10", "1010", "1000", product_type),
                _held(4, "8", "840", "800", product_type),
            ],
            [_trade(1, TxType.SELL, "220", "2", product_type)],
            4,
            product_type=product_type,
        )

        assert _days(result) == [_day(0), _day(1), _day(3), _day(4)]
        metrics = _metrics(result)[_day(4)]
        assert metrics.value == Dezimal(840)
        assert metrics.net_contributions == Dezimal(780)
        assert metrics.gain == Dezimal(60)
        assert result.quality == GainsQuality.COMPLETE

    @pytest.mark.asyncio
    @pytest.mark.parametrize("product_type", _MARKET_TYPES)
    async def test_slow_settlement_books_buy_when_units_arrive(self, product_type):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000", product_type),
                _held(5, "10", "1000", "1000", product_type),
                _held(9, "10", "1000", "1000", product_type),
                _held(10, "12", "1200", "1200", product_type),
            ],
            [_trade(1, TxType.BUY, "200", "2", product_type)],
            10,
            product_type=product_type,
        )

        assert _day(5) not in _days(result)
        metrics = _metrics(result)[_day(10)]
        assert metrics.value == Dezimal(1200)
        assert metrics.net_contributions == Dezimal(1200)
        assert metrics.gain == Dezimal(0)
        assert result.quality == GainsQuality.COMPLETE
        assert result.xirr is not None

    @pytest.mark.asyncio
    async def test_partial_settlement_books_each_fill_at_its_cost(self):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000"),
                _held(2, "11", "1100", "1100"),
                _held(3, "12", "1200", "1200"),
            ],
            [_trade(1, TxType.BUY, "200", "2")],
            3,
        )

        by_day = _metrics(result)
        assert by_day[_day(2)].net_contributions == Dezimal(1100)
        assert by_day[_day(3)].net_contributions == Dezimal(1200)
        assert by_day[_day(3)].gain == Dezimal(0)
        assert result.quality == GainsQuality.ESTIMATED

    @pytest.mark.asyncio
    @pytest.mark.parametrize("product_type", _MARKET_TYPES)
    async def test_buys_settling_together_are_booked_together(self, product_type):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000", product_type),
                _held(3, "13", "1300", "1300", product_type),
            ],
            [
                _trade(1, TxType.BUY, "100", "1", product_type),
                _trade(2, TxType.BUY, "200", "2", product_type),
            ],
            3,
            product_type=product_type,
        )

        metrics = _metrics(result)[_day(3)]
        assert metrics.net_contributions == Dezimal(1300)
        assert metrics.gain == Dezimal(0)
        assert result.quality == GainsQuality.COMPLETE

    @pytest.mark.asyncio
    async def test_trades_settling_one_by_one_are_booked_one_by_one(self):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000"),
                _held(2, "11", "1100", "1100"),
                _held(4, "13", "1300", "1300"),
            ],
            [
                _trade(1, TxType.BUY, "100", "1"),
                _trade(3, TxType.BUY, "200", "2"),
            ],
            4,
        )

        by_day = _metrics(result)
        assert by_day[_day(2)].net_contributions == Dezimal(1100)
        assert by_day[_day(4)].net_contributions == Dezimal(1300)
        assert by_day[_day(4)].gain == Dezimal(0)
        assert result.quality == GainsQuality.COMPLETE

    @pytest.mark.asyncio
    @pytest.mark.parametrize("product_type", _MARKET_TYPES)
    async def test_old_unobserved_buy_degrades_quality(self, product_type):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000", product_type),
                _held(10, "10", "1000", "1000", product_type),
            ],
            [_trade(1, TxType.BUY, "200", "2", product_type)],
            10,
            product_type=product_type,
        )

        assert result.quality == GainsQuality.DEGRADED
        assert result.warnings == [GainsWarning.UNRECONCILED_FLOWS]
        assert result.xirr is None
        assert all(
            point.metrics.net_contributions == Dezimal(1000) for point in result.points
        )

    @pytest.mark.asyncio
    async def test_recent_unobserved_buy_keeps_quality_and_holds_back_snapshot(self):
        result = await _timeline(
            [_held(0, "10", "1000", "1000"), _held(10, "10", "1000", "1000")],
            [_trade(8, TxType.BUY, "200", "2")],
            10,
        )

        assert _day(10) not in _days(result)
        assert result.points[-1].metrics.net_contributions == Dezimal(1000)
        assert result.quality == GainsQuality.COMPLETE

    @pytest.mark.asyncio
    @pytest.mark.parametrize("product_type", _MARKET_TYPES)
    async def test_round_trip_settling_leg_by_leg_is_not_double_counted(
        self, product_type
    ):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000", product_type),
                _held(3, "15", "1500", "1500", product_type),
                _held(4, "10", "1000", "1000", product_type),
                _held(20, "10", "1100", "1000", product_type),
            ],
            _round_trip(product_type, buy_day=1, sell_day=2),
            20,
            product_type=product_type,
        )

        by_day = _metrics(result)
        assert by_day[_day(3)].net_contributions == Dezimal(1500)
        assert by_day[_day(4)].net_contributions == Dezimal(950)
        assert by_day[_day(20)].net_contributions == Dezimal(950)
        assert by_day[_day(20)].gain == Dezimal(150)
        assert result.quality == GainsQuality.COMPLETE

    @pytest.mark.asyncio
    async def test_late_round_trip_leg_is_still_matched_by_size(self):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000"),
                _held(10, "15", "1500", "1500"),
                _held(20, "10", "1100", "1000"),
            ],
            _round_trip(buy_day=1, sell_day=2),
            20,
        )

        by_day = _metrics(result)
        assert by_day[_day(10)].net_contributions == Dezimal(1500)
        assert by_day[_day(20)].net_contributions == Dezimal(950)
        assert by_day[_day(20)].gain == Dezimal(150)
        assert result.quality == GainsQuality.COMPLETE

    @pytest.mark.asyncio
    @pytest.mark.parametrize("product_type", _MARKET_TYPES)
    async def test_round_trip_is_booked_with_later_matching_buy(self, product_type):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000", product_type),
                _held(10, "10", "1000", "1000", product_type),
                _held(30, "20", "2000", "2000", product_type),
                _held(60, "20", "2200", "2000", product_type),
            ],
            _round_trip(product_type)
            + [_trade(29, TxType.BUY, "1000", "10", product_type)],
            60,
            product_type=product_type,
        )

        by_day = _metrics(result)
        assert by_day[_day(30)].net_contributions == Dezimal(1950)
        assert by_day[_day(60)].gain == Dezimal(250)
        assert result.quality == GainsQuality.COMPLETE
        assert result.xirr is not None

    @pytest.mark.asyncio
    async def test_full_exit_is_booked_when_position_disappears(self):
        result = await _timeline(
            [_held(0, "10", "1000", "1000"), _snapshot(2)],
            [_trade(1, TxType.SELL, "1100", "10")],
            2,
        )

        metrics = _metrics(result)[_day(2)]
        assert metrics.value == Dezimal(0)
        assert metrics.net_contributions == Dezimal(-100)
        assert metrics.gain == Dezimal(100)
        assert result.quality == GainsQuality.COMPLETE

    @pytest.mark.asyncio
    async def test_trade_in_flight_elsewhere_does_not_hold_back_observed_holder(self):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000", holder="pending"),
                _held(0, "5", "500", "500", holder="observed", asset_key="OTHER"),
                _held(2, "10", "990", "1000", holder="pending"),
                _held(2, "5", "550", "500", holder="observed", asset_key="OTHER"),
            ],
            [_trade(1, TxType.BUY, "200", "2", holder="pending")],
            2,
        )

        metrics = _metrics(result)[_day(2)]
        assert metrics.value == Dezimal(1540)
        assert metrics.net_contributions == Dezimal(1500)

    @pytest.mark.asyncio
    async def test_change_matching_one_round_trip_leg_books_that_leg(self):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000"),
                _held(10, "10", "1000", "1000"),
                _held(30, "15", "1500", "1500"),
                _held(60, "15", "1650", "1500"),
            ],
            _round_trip(),
            60,
        )

        assert _metrics(result)[_day(30)].net_contributions == Dezimal(1500)
        assert result.quality == GainsQuality.DEGRADED

    @pytest.mark.asyncio
    async def test_round_trip_inside_settle_window_stays_pending(self):
        result = await _timeline(
            [_held(0, "10", "1000", "1000"), _held(10, "10", "1000", "1000")],
            _round_trip(),
            10,
        )

        assert _day(10) not in _days(result)
        assert result.points[-1].metrics.net_contributions == Dezimal(1000)
        assert result.quality == GainsQuality.COMPLETE

    @pytest.mark.asyncio
    async def test_round_trip_of_holder_without_later_snapshots_stays_flagged(self):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000", holder="idle"),
                _held(0, "5", "500", "500", holder="active", asset_key="OTHER"),
                _held(10, "10", "1000", "1000", holder="idle"),
                _held(30, "5", "550", "500", holder="active", asset_key="OTHER"),
                _held(60, "5", "600", "500", holder="active", asset_key="OTHER"),
            ],
            _round_trip(holder="idle"),
            60,
        )

        metrics = _metrics(result)[_day(60)]
        assert metrics.value == Dezimal(1600)
        assert metrics.net_contributions == Dezimal(1500)
        assert result.quality == GainsQuality.DEGRADED

    @pytest.mark.asyncio
    async def test_bounded_range_after_settled_round_trip_ignores_it(self):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000"),
                _held(10, "10", "1000", "1000"),
                _held(60, "10", "1100", "1000"),
                _held(75, "10", "1150", "1000"),
                _held(80, "10", "1200", "1000"),
            ],
            _round_trip(),
            80,
            first=70,
        )

        assert result.opening_value == Dezimal(1100)
        by_day = _metrics(result)
        assert by_day[_day(75)].gain == Dezimal(50)
        assert by_day[_day(80)].gain == Dezimal(100)
        assert by_day[_day(80)].net_contributions == Dezimal(0)
        assert result.quality == GainsQuality.COMPLETE

    @pytest.mark.asyncio
    async def test_bounded_range_books_leg_left_unsettled_at_its_start(self):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000"),
                _held(22, "15", "1500", "1500"),
                _held(30, "10", "1050", "1000"),
            ],
            _round_trip(buy_day=20, sell_day=21),
            30,
            first=25,
        )

        assert result.opening_value == Dezimal(1500)
        metrics = _metrics(result)[_day(30)]
        assert metrics.net_contributions == Dezimal(-550)
        assert metrics.gain == Dezimal(100)


class TestSettledRoundTrips:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("product_type", _MARKET_TYPES)
    async def test_round_trip_is_booked_once_unchanged_position_confirms_it(
        self, product_type
    ):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000", product_type),
                _held(10, "10", "1000", "1000", product_type),
                _held(60, "10", "1100", "1000", product_type),
            ],
            _round_trip(product_type),
            60,
            product_type=product_type,
        )

        by_day = _metrics(result)
        assert _day(10) not in by_day
        assert by_day[_day(59)].net_contributions == Dezimal(1000)
        metrics = by_day[_day(60)]
        assert metrics.value == Dezimal(1100)
        assert metrics.net_contributions == Dezimal(950)
        assert metrics.gain == Dezimal(150)
        assert metrics.period_return == Dezimal("0.15")
        assert metrics.index == Dezimal(115)
        assert result.quality == GainsQuality.COMPLETE
        assert result.warnings == []
        assert result.not_applicable_reasons == []
        assert result.xirr is not None
        assert result.xirr > 0

    @pytest.mark.asyncio
    @pytest.mark.parametrize("product_type", _MARKET_TYPES)
    async def test_round_trip_is_not_split_by_later_unrelated_change(
        self, product_type
    ):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000", product_type),
                _held(10, "10", "1000", "1000", product_type),
                _held(30, "20", "2000", "2000", product_type),
                _held(60, "20", "2200", "2000", product_type),
            ],
            _round_trip(product_type),
            60,
            product_type=product_type,
        )

        by_day = _metrics(result)
        assert by_day[_day(30)].value == Dezimal(2000)
        assert by_day[_day(30)].net_contributions == Dezimal(1950)
        assert by_day[_day(30)].gain == Dezimal(50)
        assert by_day[_day(60)].net_contributions == Dezimal(1950)
        assert by_day[_day(60)].gain == Dezimal(250)
        assert result.quality == GainsQuality.ESTIMATED
        assert result.warnings == [GainsWarning.INFERRED_FLOWS]
        assert result.xirr is not None

    @pytest.mark.asyncio
    async def test_round_trip_with_opposite_unrelated_change(self):
        result = await _timeline(
            [
                _held(0, "20", "2000", "2000"),
                _held(10, "20", "2000", "2000"),
                _held(30, "10", "1000", "1000"),
                _held(60, "10", "1100", "1000"),
            ],
            _round_trip(),
            60,
        )

        by_day = _metrics(result)
        assert by_day[_day(30)].net_contributions == Dezimal(950)
        assert by_day[_day(60)].net_contributions == Dezimal(950)
        assert by_day[_day(60)].gain == Dezimal(150)
        assert result.quality == GainsQuality.ESTIMATED

    @pytest.mark.asyncio
    async def test_same_day_round_trip_is_booked(self):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000"),
                _held(10, "10", "1000", "1000"),
                _held(60, "10", "1100", "1000"),
            ],
            _round_trip(buy_day=4, sell_day=4),
            60,
        )

        metrics = _metrics(result)[_day(60)]
        assert metrics.net_contributions == Dezimal(950)
        assert metrics.gain == Dezimal(150)
        assert result.quality == GainsQuality.COMPLETE

    @pytest.mark.asyncio
    async def test_round_trip_of_several_legs_is_booked_together(self):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000"),
                _held(10, "10", "1000", "1000"),
                _held(60, "10", "1100", "1000"),
            ],
            [
                _trade(2, TxType.BUY, "300", "3"),
                _trade(3, TxType.BUY, "200", "2"),
                _trade(4, TxType.SELL, "550", "5"),
            ],
            60,
        )

        metrics = _metrics(result)[_day(60)]
        assert metrics.net_contributions == Dezimal(950)
        assert metrics.gain == Dezimal(150)
        assert result.quality == GainsQuality.COMPLETE

    @pytest.mark.asyncio
    async def test_round_trip_with_rounded_quantities_is_booked(self):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000"),
                _held(10, "10", "1000", "1000"),
                _held(60, "10", "1100", "1000"),
            ],
            _round_trip(bought="5.001"),
            60,
        )

        metrics = _metrics(result)[_day(60)]
        assert metrics.net_contributions == Dezimal("949.89")
        assert metrics.gain == Dezimal("150.11")
        assert result.quality == GainsQuality.ESTIMATED
        assert result.xirr is not None

    @pytest.mark.asyncio
    async def test_round_trip_tolerance_includes_its_boundary(self):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000"),
                _held(10, "10", "1000", "1000"),
                _held(60, "10", "1100", "1000"),
            ],
            _round_trip(sold="5.1"),
            60,
        )

        metrics = _metrics(result)[_day(60)]
        assert metrics.net_contributions == Dezimal(961)
        assert metrics.gain == Dezimal(139)
        assert result.quality == GainsQuality.ESTIMATED

    @pytest.mark.asyncio
    async def test_round_trip_fees_are_part_of_the_realized_result(self):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000"),
                _held(10, "10", "1000", "1000"),
                _held(60, "10", "1100", "1000"),
            ],
            _round_trip(fees="2"),
            60,
        )

        metrics = _metrics(result)[_day(60)]
        assert metrics.net_contributions == Dezimal(954)
        assert metrics.gain == Dezimal(146)
        assert result.quality == GainsQuality.COMPLETE

    @pytest.mark.asyncio
    async def test_round_trip_in_holder_with_other_assets(self):
        result = await _timeline(
            [
                _snapshot(
                    0,
                    _position("10", "1000", "1000"),
                    _position("5", "500", "500", asset_key="OTHER"),
                ),
                _snapshot(
                    10,
                    _position("10", "1000", "1000"),
                    _position("5", "510", "500", asset_key="OTHER"),
                ),
                _snapshot(
                    60,
                    _position("10", "1100", "1000"),
                    _position("5", "520", "500", asset_key="OTHER"),
                ),
            ],
            _round_trip(),
            60,
        )

        by_day = _metrics(result)
        assert by_day[_day(10)].value == Dezimal(1510)
        assert by_day[_day(60)].value == Dezimal(1620)
        assert by_day[_day(60)].net_contributions == Dezimal(1450)
        assert by_day[_day(60)].gain == Dezimal(170)
        assert result.quality == GainsQuality.COMPLETE

    @pytest.mark.asyncio
    async def test_round_trip_waits_for_its_newest_leg_to_settle(self):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000"),
                _held(60, "10", "1000", "1000"),
                _held(70, "10", "1100", "1000"),
            ],
            _round_trip(buy_day=50, sell_day=56),
            70,
        )

        by_day = _metrics(result)
        assert _day(60) not in by_day
        assert by_day[_day(69)].net_contributions == Dezimal(1000)
        assert by_day[_day(70)].net_contributions == Dezimal(950)
        assert by_day[_day(70)].gain == Dezimal(150)
        assert result.quality == GainsQuality.COMPLETE

    @pytest.mark.asyncio
    async def test_round_trip_is_booked_before_a_later_in_flight_buy(self):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000"),
                _held(10, "10", "1000", "1000"),
                _held(60, "10", "1100", "1000"),
                _held(62, "13", "1430", "1300"),
            ],
            _round_trip() + [_trade(55, TxType.BUY, "300", "3")],
            62,
        )

        by_day = _metrics(result)
        assert _day(60) not in by_day
        assert by_day[_day(61)].value == Dezimal(1100)
        assert by_day[_day(61)].net_contributions == Dezimal(950)
        assert by_day[_day(62)].net_contributions == Dezimal(1250)
        assert by_day[_day(62)].gain == Dezimal(180)
        assert result.quality == GainsQuality.COMPLETE

    @pytest.mark.asyncio
    async def test_round_trip_across_split_with_unrelated_change(self):
        result = await _timeline(
            [_held(0, "10", "1000", "1000"), _held(20, "24", "1200", "1000")],
            [
                _trade(4, TxType.BUY, "500", "5"),
                _trade(6, TxType.SPLIT, "0", None, ratio="2"),
                _trade(8, TxType.SELL, "550", "10"),
            ],
            20,
        )

        metrics = _metrics(result)[_day(20)]
        assert metrics.value == Dezimal(1200)
        assert metrics.net_contributions == Dezimal(1150)
        assert metrics.gain == Dezimal(50)
        assert result.quality == GainsQuality.ESTIMATED

    @pytest.mark.asyncio
    async def test_consecutive_round_trips_are_booked_separately(self):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000"),
                _held(20, "10", "1000", "1000"),
                _held(50, "10", "1100", "1000"),
            ],
            _round_trip()
            + _round_trip(buy_day=30, sell_day=31, buy_amount="600", sell_amount="650"),
            50,
        )

        by_day = _metrics(result)
        assert by_day[_day(20)].net_contributions == Dezimal(950)
        assert by_day[_day(49)].net_contributions == Dezimal(950)
        assert by_day[_day(50)].net_contributions == Dezimal(900)
        assert by_day[_day(50)].gain == Dezimal(200)
        assert result.quality == GainsQuality.COMPLETE

    @pytest.mark.asyncio
    async def test_fractional_crypto_round_trip_is_booked(self):
        product_type = ProductType.CRYPTO
        result = await _timeline(
            [
                _held(0, "0.5", "10000", "10000", product_type),
                _held(10, "0.5", "10000", "10000", product_type),
                _held(60, "0.5", "11000", "10000", product_type),
            ],
            _round_trip(
                product_type,
                bought="0.1",
                sold="0.1",
                buy_amount="2000",
                sell_amount="2200",
            ),
            60,
            product_type=product_type,
        )

        metrics = _metrics(result)[_day(60)]
        assert metrics.net_contributions == Dezimal(9800)
        assert metrics.gain == Dezimal(1200)
        assert result.quality == GainsQuality.COMPLETE


class TestRoundTripLateSettlement:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("product_type", _MARKET_TYPES)
    async def test_late_legs_are_still_matched_by_size(self, product_type):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000", product_type),
                _held(12, "10", "1000", "1000", product_type),
                _held(13, "15", "1500", "1500", product_type),
                _held(14, "10", "1000", "1000", product_type),
                _held(40, "10", "1100", "1000", product_type),
            ],
            _round_trip(product_type),
            40,
            product_type=product_type,
        )

        by_day = _metrics(result)
        assert by_day[_day(12)].net_contributions == Dezimal(1000)
        assert by_day[_day(13)].net_contributions == Dezimal(1500)
        assert by_day[_day(14)].net_contributions == Dezimal(950)
        assert by_day[_day(40)].gain == Dezimal(150)
        assert result.quality == GainsQuality.COMPLETE
        assert result.warnings == []

    @pytest.mark.asyncio
    async def test_late_leg_settling_with_a_new_trade_is_matched(self):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000"),
                _held(12, "10", "1000", "1000"),
                _held(13, "15", "1500", "1500"),
                _held(18, "30", "3000", "3000"),
                _held(40, "30", "3300", "3000"),
            ],
            _round_trip() + [_trade(16, TxType.BUY, "2000", "20")],
            40,
        )

        by_day = _metrics(result)
        assert by_day[_day(13)].net_contributions == Dezimal(1500)
        assert by_day[_day(18)].net_contributions == Dezimal(2950)
        assert by_day[_day(40)].gain == Dezimal(350)
        assert result.quality == GainsQuality.COMPLETE

    @pytest.mark.asyncio
    async def test_round_trip_is_confirmed_when_no_late_leg_can_follow(self):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000"),
                _held(12, "10", "1000", "1000"),
                _held(20, "13", "1300", "1300"),
                _held(40, "13", "1430", "1300"),
            ],
            _round_trip(),
            40,
        )

        by_day = _metrics(result)
        assert by_day[_day(12)].net_contributions == Dezimal(950)
        assert by_day[_day(20)].net_contributions == Dezimal(1250)
        assert by_day[_day(40)].gain == Dezimal(180)
        assert result.quality == GainsQuality.ESTIMATED

    @pytest.mark.asyncio
    async def test_round_trip_waits_for_a_change_that_may_be_a_late_leg(self):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000"),
                _held(12, "10", "1000", "1000"),
                _held(15, "13", "1300", "1300"),
                _held(40, "13", "1430", "1300"),
            ],
            _round_trip(),
            40,
        )

        by_day = _metrics(result)
        assert by_day[_day(12)].net_contributions == Dezimal(1000)
        assert by_day[_day(15)].net_contributions == Dezimal(1250)
        assert by_day[_day(40)].gain == Dezimal(180)
        assert result.quality == GainsQuality.ESTIMATED

    @pytest.mark.asyncio
    async def test_change_beyond_the_range_does_not_hold_the_round_trip(self):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000"),
                _held(12, "10", "1100", "1000"),
                _held(15, "13", "1300", "1300"),
            ],
            _round_trip(),
            12,
        )

        metrics = _metrics(result)[_day(12)]
        assert metrics.net_contributions == Dezimal(950)
        assert metrics.gain == Dezimal(150)
        assert result.quality == GainsQuality.COMPLETE

    @pytest.mark.asyncio
    async def test_other_holder_changes_do_not_hold_the_round_trip(self):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000"),
                _held(0, "5", "500", "500", holder="other", asset_key="OTHER"),
                _held(12, "10", "1100", "1000"),
                _held(13, "8", "800", "800", holder="other", asset_key="OTHER"),
                _held(40, "10", "1100", "1000"),
            ],
            _round_trip(),
            40,
        )

        assert _metrics(result)[_day(12)].net_contributions == Dezimal(1450)

    @pytest.mark.asyncio
    async def test_change_in_another_asset_of_the_holder_does_not_hold_it(self):
        result = await _timeline(
            [
                _snapshot(
                    0,
                    _position("10", "1000", "1000"),
                    _position("5", "500", "500", asset_key="OTHER"),
                ),
                _snapshot(
                    12,
                    _position("10", "1100", "1000"),
                    _position("5", "500", "500", asset_key="OTHER"),
                ),
                _snapshot(
                    13,
                    _position("10", "1100", "1000"),
                    _position("8", "800", "800", asset_key="OTHER"),
                ),
            ],
            _round_trip(),
            13,
        )

        assert _metrics(result)[_day(12)].net_contributions == Dezimal(1450)

    @pytest.mark.asyncio
    async def test_position_closing_soon_after_holds_the_round_trip(self):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000"),
                _held(12, "10", "1100", "1000"),
                _snapshot(14),
            ],
            _round_trip() + [_trade(13, TxType.SELL, "1100", "10")],
            14,
        )

        by_day = _metrics(result)
        assert by_day[_day(12)].net_contributions == Dezimal(1000)
        assert by_day[_day(14)].value == Dezimal(0)
        assert by_day[_day(14)].net_contributions == Dezimal(-150)
        assert by_day[_day(14)].gain == Dezimal(150)
        assert result.quality == GainsQuality.COMPLETE


class TestRoundTripSafety:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "flows",
        [
            pytest.param(_round_trip(sold="3", sell_amount="330"), id="partial-sell"),
            pytest.param(_round_trip(sold="5.2", sell_amount="572"), id="over-sold"),
            pytest.param(
                _round_trip() + [_trade(6, TxType.BUY, "300", "3")],
                id="extra-buy",
            ),
            pytest.param(
                [_trade(4, TxType.BUY, "500", "5"), _trade(5, TxType.BUY, "500", "5")],
                id="buys-only",
            ),
            pytest.param(
                [
                    _trade(4, TxType.SELL, "550", "5"),
                    _trade(5, TxType.SELL, "550", "5"),
                ],
                id="sells-only",
            ),
        ],
    )
    async def test_old_legs_that_do_not_net_out_are_not_booked(self, flows):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000"),
                _held(10, "10", "1000", "1000"),
                _held(60, "10", "1100", "1000"),
            ],
            flows,
            60,
        )

        assert result.points[-1].metrics.net_contributions == Dezimal(1000)
        assert result.quality == GainsQuality.DEGRADED
        assert result.xirr is None

    @pytest.mark.asyncio
    async def test_unbalanced_old_legs_do_not_absorb_a_later_change(self):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000"),
                _held(10, "10", "1000", "1000"),
                _held(30, "20", "2000", "2000"),
            ],
            _round_trip(sold="3", sell_amount="330"),
            30,
        )

        metrics = _metrics(result)[_day(30)]
        assert metrics.value == Dezimal(2000)
        assert result.quality == GainsQuality.DEGRADED

    @pytest.mark.asyncio
    async def test_round_trip_is_not_booked_by_another_holder_snapshot(self):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000"),
                _held(10, "10", "1000", "1000"),
                _snapshot(30, holder="bank"),
                _snapshot(60, holder="bank"),
            ],
            _round_trip(),
            60,
        )

        assert result.points[-1].metrics.net_contributions == Dezimal(1000)
        assert result.quality == GainsQuality.DEGRADED


class TestInFlightSuppression:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("product_type", _MARKET_TYPES)
    async def test_snapshot_days_resume_once_pending_trade_is_past_settle_window(
        self, product_type
    ):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000", product_type),
                _held(5, "10", "990", "1000", product_type),
                _held(10, "10", "980", "1000", product_type),
                _held(20, "10", "1020", "1000", product_type),
            ],
            [_trade(1, TxType.BUY, "200", "2", product_type)],
            20,
            product_type=product_type,
        )

        by_day = _metrics(result)
        assert _day(5) not in by_day
        assert by_day[_day(10)].value == Dezimal(980)
        assert by_day[_day(20)].value == Dezimal(1020)
        assert by_day[_day(20)].net_contributions == Dezimal(1000)
        assert by_day[_day(20)].gain == Dezimal(20)
        assert result.points[-1].date == _day(20)
        assert result.quality == GainsQuality.DEGRADED

    @pytest.mark.asyncio
    async def test_other_holder_snapshot_resumes_once_trade_is_past_settle_window(
        self,
    ):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000"),
                _snapshot(10, holder="bank"),
                _snapshot(12, holder="bank"),
            ],
            [_trade(1, TxType.BUY, "200", "2")],
            12,
        )

        days = _days(result)
        assert _day(10) in days
        assert days[-1] == _day(12)

    @pytest.mark.asyncio
    async def test_other_holder_snapshot_is_held_back_while_trade_is_in_flight(self):
        result = await _timeline(
            [_held(0, "10", "1000", "1000"), _snapshot(10, holder="bank")],
            [_trade(8, TxType.BUY, "200", "2")],
            10,
        )

        assert _day(10) not in _days(result)

    @pytest.mark.asyncio
    async def test_unbalanced_old_legs_do_not_hide_the_latest_snapshot(self):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000"),
                _held(10, "10", "1000", "1000"),
                _held(60, "10", "1100", "1000"),
            ],
            _round_trip(sold="3", sell_amount="330"),
            60,
        )

        assert result.points[-1].date == _day(60)
        assert result.points[-1].metrics.value == Dezimal(1100)

    @pytest.mark.asyncio
    async def test_in_flight_trade_keeps_holding_back_while_older_one_is_stuck(self):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000"),
                _held(20, "10", "1000", "1000"),
                _held(22, "12", "1200", "1200"),
            ],
            [
                _trade(1, TxType.BUY, "500", "5"),
                _trade(18, TxType.BUY, "200", "2"),
            ],
            22,
        )

        by_day = _metrics(result)
        assert _day(20) not in by_day
        assert by_day[_day(22)].net_contributions == Dezimal(1200)
        assert result.quality == GainsQuality.DEGRADED


class TestReleasableMarketFlows:
    @staticmethod
    def _release(flows, anchor, quantity, offset, allow_stale=True):
        return _use_case([], [])._releasable_market_flows(
            flows,
            Dezimal(anchor) if anchor is not None else None,
            _position(quantity, "0", None),
            _day(offset),
            allow_stale,
        )

    def test_total_match_releases_every_leg(self):
        flows = _round_trip() + [_trade(20, TxType.BUY, "1000", "10")]

        assert self._release(flows, "10", "20", 21) == flows

    def test_largest_fitting_leg_is_released_first(self):
        flows = [_trade(1, TxType.BUY, "500", "5"), _trade(18, TxType.BUY, "200", "2")]

        assert self._release(flows, "10", "12", 20) == [flows[1]]

    def test_settled_round_trip_is_released_with_an_unrelated_change(self):
        flows = _round_trip()

        assert self._release(flows, "10", "20", 30) == flows

    def test_settled_round_trip_is_released_with_a_matching_in_flight_leg(self):
        flows = _round_trip() + [_trade(28, TxType.BUY, "300", "3")]

        assert self._release(flows, "10", "23", 30) == flows

    def test_settled_round_trip_keeps_a_leg_that_explains_the_change(self):
        flows = _round_trip(buy_day=1, sell_day=2)

        assert self._release(flows, "10", "15", 10) == [flows[0]]

    def test_in_flight_round_trip_is_matched_leg_by_leg(self):
        flows = _round_trip()

        assert self._release(flows, "10", "20", 8) == [flows[0]]

    def test_round_trip_is_not_forced_without_stale_release(self):
        flows = _round_trip()

        assert self._release(flows, "10", "20", 30, allow_stale=False) == [flows[0]]

    def test_stale_transfer_leg_is_still_force_released(self):
        flows = [_trade(1, TxType.TRANSFER_IN, "500", "5")]

        assert self._release(flows, "10", "12", 20) == flows

    def test_unquantified_leg_is_released(self):
        flows = [_trade(1, TxType.BUY, "500", None)]

        assert self._release(flows, "10", "12", 2) == flows

    def test_unknown_anchor_releases_everything(self):
        flows = _round_trip()

        assert self._release(flows, None, "20", 6) == flows

    def test_equal_buys_with_different_cash_are_held_back(self):
        flows = [_trade(1, TxType.BUY, "500", "5"), _trade(2, TxType.BUY, "520", "5")]

        assert self._release(flows, "10", "15", 3) == []


class TestSettledRoundTripLegs:
    @staticmethod
    def _legs(flows, offset, splits=None):
        use_case = _use_case([], [])
        if splits:
            use_case._splits_by_key[(ProductType.STOCK_ETF, _ASSET)] = splits
        return use_case._settled_round_trip(flows, _day(offset))

    def test_balanced_legs_past_settle_window_are_returned(self):
        flows = _round_trip()

        assert self._legs(flows, 12) == flows

    def test_leg_inside_settle_window_keeps_round_trip_open(self):
        flows = _round_trip()

        assert self._legs(flows, 11) == []

    @pytest.mark.parametrize(
        "flows",
        [
            pytest.param(_round_trip(sold="4.8", sell_amount="528"), id="unbalanced"),
            pytest.param(
                [_trade(4, TxType.BUY, "500", "5"), _trade(5, TxType.BUY, "500", "5")],
                id="buys-only",
            ),
            pytest.param(
                [
                    _trade(4, TxType.SELL, "550", "5"),
                    _trade(5, TxType.SELL, "550", "5"),
                ],
                id="sells-only",
            ),
            pytest.param([], id="empty"),
        ],
    )
    def test_legs_that_do_not_net_out_are_not_returned(self, flows):
        assert self._legs(flows, 30) == []

    def test_quantities_are_compared_across_splits(self):
        flows = [
            _trade(4, TxType.BUY, "500", "5"),
            _trade(8, TxType.SELL, "550", "10"),
        ]

        assert self._legs(flows, 30, {_day(6): Dezimal(2)}) == flows

    def test_non_trade_legs_are_left_out(self):
        transfer = _trade(3, TxType.TRANSFER_IN, "300", "3")
        flows = _round_trip() + [transfer]

        assert self._legs(flows, 30) == flows[:2]

    def test_newer_legs_are_left_out(self):
        flows = _round_trip() + [_trade(28, TxType.BUY, "300", "3")]

        assert self._legs(flows, 30) == flows[:2]


class TestRoundTripBoundedRanges:
    @staticmethod
    def _snapshots():
        return [
            _held(0, "10", "1000", "1000"),
            _held(22, "10", "1000", "1000"),
            _held(30, "10", "1050", "1000"),
            _held(40, "10", "1100", "1000"),
        ]

    @pytest.mark.asyncio
    async def test_round_trip_just_before_range_is_booked_inside_it(self):
        result = await _timeline(
            self._snapshots(),
            _round_trip(buy_day=20, sell_day=21),
            40,
            first=25,
        )

        assert result.opening_value == Dezimal(1000)
        by_day = _metrics(result)
        assert by_day[_day(30)].net_contributions == Dezimal(-50)
        assert by_day[_day(30)].gain == Dezimal(100)
        assert by_day[_day(40)].gain == Dezimal(150)
        assert result.quality == GainsQuality.COMPLETE
        assert result.xirr is not None

    @pytest.mark.asyncio
    async def test_bounded_gain_matches_unbounded_change(self):
        unbounded = await _timeline(
            self._snapshots(), _round_trip(buy_day=20, sell_day=21), 40
        )
        bounded = await _timeline(
            self._snapshots(),
            _round_trip(buy_day=20, sell_day=21),
            40,
            first=25,
        )

        full = _metrics(unbounded)
        assert full[_day(24)].gain == Dezimal(0)
        assert full[_day(40)].gain == Dezimal(150)
        assert (
            _metrics(bounded)[_day(40)].gain
            == full[_day(40)].gain - full[_day(24)].gain
        )

    @pytest.mark.asyncio
    async def test_round_trip_before_first_range_snapshot_is_replayed(self):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000"),
                _held(10, "10", "1000", "1000"),
                _held(60, "10", "1100", "1000"),
            ],
            _round_trip(),
            60,
            first=1,
        )

        assert result.opening_value == Dezimal(1000)
        metrics = _metrics(result)[_day(60)]
        assert metrics.net_contributions == Dezimal(-50)
        assert metrics.gain == Dezimal(150)
        assert result.quality == GainsQuality.ESTIMATED
        assert result.warnings == [GainsWarning.REPLAYED_POSITIONS]

    @pytest.mark.asyncio
    async def test_round_trip_after_first_range_snapshot_is_booked(self):
        result = await _timeline(
            [
                _held(0, "10", "1000", "1000"),
                _held(2, "10", "1000", "1000"),
                _held(10, "10", "1000", "1000"),
                _held(60, "10", "1100", "1000"),
            ],
            _round_trip(),
            60,
            first=1,
        )

        assert result.opening_value == Dezimal(1000)
        by_day = _metrics(result)
        assert _day(10) not in by_day
        assert by_day[_day(60)].net_contributions == Dezimal(-50)
        assert by_day[_day(60)].gain == Dezimal(150)
        assert result.quality == GainsQuality.COMPLETE
        assert result.warnings == []
