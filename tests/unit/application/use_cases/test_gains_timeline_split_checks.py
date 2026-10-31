from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

import application.use_cases.get_gains_timeline as gains_module
from application.ports.gains_timeline_port import GainsTimelinePort
from application.use_cases.get_gains_timeline import GetGainsTimelineImpl
from domain.dezimal import Dezimal
from domain.gains_timeline import (
    AssetSnapshot,
    AssetValuation,
    GainsAssetFilter,
    GainsFlow,
    GainsTimelineQuery,
)
from domain.global_position import ProductType
from domain.instrument import InstrumentDataRequest, InstrumentType
from domain.instrument_history import InstrumentPricePoint, InstrumentSplit
from domain.transactions import TxType

_CHECK_DAY = date(2026, 1, 15)
_START = date(2025, 1, 1)
_SPLIT = InstrumentSplit(date=date(2025, 6, 2), ratio=Dezimal(2))


def _day(offset):
    return _START + timedelta(days=offset)


class _FrozenDatetime(datetime):
    frozen = _CHECK_DAY

    @classmethod
    def now(cls, tz=None):
        moment = datetime(cls.frozen.year, cls.frozen.month, cls.frozen.day, 12)
        return moment.replace(tzinfo=tz)


@pytest.fixture
def freeze_today(monkeypatch):
    def freeze(day):
        monkeypatch.setattr(
            gains_module,
            "datetime",
            type("FrozenDatetime", (_FrozenDatetime,), {"frozen": day}),
        )

    freeze(_CHECK_DAY)
    return freeze


class _CoverageStore:
    def __init__(self):
        self.today = _CHECK_DAY
        self.splits = []
        self.checked = None

    async def get_splits(self, instrument_key):
        return list(self.splits)

    async def save_splits(self, instrument_key, splits):
        self.splits = list(splits)

    async def is_splits_checked(self, instrument_key, from_date=None, to_date=None):
        if self.checked is None:
            return False
        checked_on, start, end = self.checked
        return (
            (self.today - checked_on).days < 7
            and (from_date is None or start <= from_date)
            and (to_date is None or end >= to_date)
        )

    async def mark_splits_checked(self, instrument_key, from_date=None, to_date=None):
        self.checked = (self.today, from_date, to_date)

    async def get_resolved_symbol(self, instrument_key):
        return None


def _request(instrument_type=InstrumentType.STOCK):
    return InstrumentDataRequest(type=instrument_type, ticker="ACME")


def _provider(splits=None):
    provider = AsyncMock()
    provider.get_splits.return_value = [] if splits is None else splits
    provider.get_history.return_value = ([], None, None)
    return provider


def _storage(checked=True, splits=None, history=None):
    storage = AsyncMock()
    storage.is_splits_checked.return_value = checked
    storage.get_splits.return_value = [] if splits is None else splits
    storage.get_resolved_symbol.return_value = None
    storage.is_no_result.return_value = False
    storage.get_empty_gap_days.return_value = set()
    points = history or []
    storage.get_history.side_effect = lambda key, start, end: [
        point for point in points if start <= point.date <= end
    ]
    storage.get_covered_range.return_value = (
        (points[0].date, points[-1].date) if points else None
    )
    return storage


def _use_case(provider=None, storage=None, snapshots=(), flows=()):
    port = AsyncMock(spec=GainsTimelinePort)
    port.get_data_version.return_value = "1"
    port.get_asset_snapshots.return_value = list(snapshots)
    port.get_flows.return_value = list(flows)
    port.get_settlements.return_value = []
    port.get_split_ratios.return_value = []
    exchange = AsyncMock()
    exchange.get.return_value = {}
    entity = AsyncMock()
    entity.get_disabled_entities.return_value = []
    entity.get_all.return_value = []
    metal = AsyncMock()
    metal.get_partial_historic_rates.return_value = None
    return GetGainsTimelineImpl(port, exchange, entity, metal, provider, storage)


def _held(offset, quantity, holder="broker"):
    day = _day(offset)
    return AssetSnapshot(
        holder=holder,
        moment=datetime(day.year, day.month, day.day, 12),
        valuations=[
            AssetValuation(
                product_type=ProductType.STOCK_ETF,
                asset_key="ACME",
                currency="EUR",
                quantity=Dezimal(quantity),
                market_value=Dezimal(quantity) * Dezimal(100),
                cost_basis=Dezimal(quantity) * Dezimal(100),
            )
        ],
    )


def _buy(offset, quantity, holder="broker"):
    day = _day(offset)
    return GainsFlow(
        holder=holder,
        product_type=ProductType.STOCK_ETF,
        asset_key="ACME",
        moment=datetime(day.year, day.month, day.day, 12),
        amount=Dezimal(quantity) * Dezimal(100),
        currency="EUR",
        quantity=Dezimal(quantity),
        transaction_type=TxType.BUY,
    )


def _query(last, first=None):
    return GainsTimelineQuery(
        assets=[GainsAssetFilter(product_type=ProductType.STOCK_ETF)],
        entities=[uuid4()],
        from_date=_day(first) if first is not None else None,
        to_date=_day(last),
    )


class TestSplitCheckCoverage:
    @pytest.mark.asyncio
    async def test_requires_coverage_until_window_end(self, freeze_today):
        storage = _storage()
        use_case = _use_case(_provider(), storage)

        await use_case._load_splits({"ACME": _request()}, {"ACME": (_day(0), _day(59))})

        storage.is_splits_checked.assert_awaited_once_with("ACME", _day(0), _day(59))

    @pytest.mark.asyncio
    async def test_caps_required_coverage_at_yesterday(self, freeze_today):
        storage = _storage()
        use_case = _use_case(_provider(), storage)

        await use_case._load_splits(
            {"ACME": _request()},
            {"ACME": (_day(0), _CHECK_DAY + timedelta(days=10))},
        )

        storage.is_splits_checked.assert_awaited_once_with(
            "ACME", _day(0), _CHECK_DAY - timedelta(days=1)
        )

    @pytest.mark.asyncio
    async def test_records_coverage_from_window_start_until_yesterday(
        self, freeze_today
    ):
        storage = _storage(checked=False)
        provider = _provider([_SPLIT])
        use_case = _use_case(provider, storage)
        request = _request()

        splits = await use_case._load_splits(
            {"ACME": request}, {"ACME": (_day(0), _day(59))}
        )

        assert splits == {"ACME": {_SPLIT.date: _SPLIT.ratio}}
        provider.get_splits.assert_awaited_once_with(
            request, _day(0), _CHECK_DAY, None, None
        )
        storage.save_splits.assert_awaited_once_with("ACME", [_SPLIT])
        storage.mark_splits_checked.assert_awaited_once_with(
            "ACME", _day(0), _CHECK_DAY - timedelta(days=1)
        )

    @pytest.mark.asyncio
    async def test_empty_answer_is_recorded_without_saving_splits(self, freeze_today):
        storage = _storage(checked=False)
        use_case = _use_case(_provider([]), storage)

        splits = await use_case._load_splits(
            {"ACME": _request()}, {"ACME": (_day(0), _day(59))}
        )

        assert splits == {}
        storage.save_splits.assert_not_awaited()
        storage.mark_splits_checked.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_covered_check_uses_cached_splits_without_provider(
        self, freeze_today
    ):
        provider = _provider()
        use_case = _use_case(provider, _storage(splits=[_SPLIT]))

        splits = await use_case._load_splits(
            {"ACME": _request()}, {"ACME": (_day(0), _day(59))}
        )

        assert splits == {"ACME": {_SPLIT.date: _SPLIT.ratio}}
        provider.get_splits.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_provider_failure_keeps_cached_splits_unrecorded(self, freeze_today):
        storage = _storage(checked=False, splits=[_SPLIT])
        provider = _provider()
        provider.get_splits.return_value = None
        use_case = _use_case(provider, storage)

        splits = await use_case._load_splits(
            {"ACME": _request()}, {"ACME": (_day(0), _day(59))}
        )

        assert splits == {"ACME": {_SPLIT.date: _SPLIT.ratio}}
        storage.mark_splits_checked.assert_not_awaited()
        storage.save_splits.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_provider_without_split_support_uses_cached_splits(
        self, freeze_today
    ):
        storage = _storage(splits=[_SPLIT])
        provider = AsyncMock(spec=["get_history"])
        use_case = _use_case(provider, storage)

        splits = await use_case._load_splits(
            {"ACME": _request()}, {"ACME": (_day(0), _day(59))}
        )

        assert splits == {"ACME": {_SPLIT.date: _SPLIT.ratio}}
        storage.is_splits_checked.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_mutual_funds_are_never_looked_up(self, freeze_today):
        storage = _storage(checked=False)
        provider = _provider([_SPLIT])
        use_case = _use_case(provider, storage)

        splits = await use_case._load_splits(
            {"ACME": _request(InstrumentType.MUTUAL_FUND)},
            {"ACME": (_day(0), _day(59))},
        )

        assert splits == {}
        provider.get_splits.assert_not_awaited()
        storage.is_splits_checked.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_resolved_price_symbol_is_preferred(self, freeze_today):
        storage = _storage(checked=False)
        storage.get_resolved_symbol.return_value = ("ACME.MC", "yfinance")
        provider = _provider()
        use_case = _use_case(provider, storage)
        request = _request()

        await use_case._load_splits({"ACME": request}, {"ACME": (_day(0), _day(59))})

        storage.get_resolved_symbol.assert_awaited_once_with("STOCK_ETF:ACME")
        provider.get_splits.assert_awaited_once_with(
            request, _day(0), _CHECK_DAY, "ACME.MC", "yfinance"
        )


class TestSplitCheckFrequency:
    @pytest.mark.asyncio
    async def test_lookup_repeats_weekly_not_daily(self, freeze_today):
        store = _CoverageStore()
        provider = _provider([_SPLIT])
        use_case = _use_case(provider, store)
        windows = {"ACME": (_day(0), date(2025, 12, 31))}

        calls = []
        for offset in range(9):
            day = _CHECK_DAY + timedelta(days=offset)
            freeze_today(day)
            store.today = day
            splits = await use_case._load_splits({"ACME": _request()}, windows)
            assert splits == {"ACME": {_SPLIT.date: _SPLIT.ratio}}
            calls.append(provider.get_splits.await_count)

        assert calls == [1, 1, 1, 1, 1, 1, 1, 2, 2]

    @pytest.mark.asyncio
    async def test_change_after_last_check_is_looked_up_once(self, freeze_today):
        store = _CoverageStore()
        provider = _provider()
        use_case = _use_case(provider, store)

        await use_case._load_splits(
            {"ACME": _request()}, {"ACME": (_day(0), date(2025, 12, 31))}
        )
        recent_change = _CHECK_DAY + timedelta(days=2)
        for offset in (3, 4, 5):
            day = _CHECK_DAY + timedelta(days=offset)
            freeze_today(day)
            store.today = day
            await use_case._load_splits(
                {"ACME": _request()}, {"ACME": (_day(0), recent_change)}
            )

        assert provider.get_splits.await_count == 2

    @pytest.mark.asyncio
    async def test_earlier_window_start_is_looked_up_again(self, freeze_today):
        store = _CoverageStore()
        provider = _provider()
        use_case = _use_case(provider, store)

        await use_case._load_splits(
            {"ACME": _request()}, {"ACME": (_day(150), date(2025, 12, 31))}
        )
        await use_case._load_splits(
            {"ACME": _request()}, {"ACME": (_day(150), date(2025, 12, 31))}
        )
        await use_case._load_splits(
            {"ACME": _request()}, {"ACME": (_day(0), date(2025, 12, 31))}
        )

        assert provider.get_splits.await_count == 2

    @pytest.mark.asyncio
    async def test_failed_lookup_is_retried_next_time(self, freeze_today):
        store = _CoverageStore()
        provider = _provider()
        provider.get_splits.side_effect = [None, [_SPLIT]]
        use_case = _use_case(provider, store)
        windows = {"ACME": (_day(0), date(2025, 12, 31))}

        first = await use_case._load_splits({"ACME": _request()}, windows)
        second = await use_case._load_splits({"ACME": _request()}, windows)
        third = await use_case._load_splits({"ACME": _request()}, windows)

        assert first == {}
        assert second == {"ACME": {_SPLIT.date: _SPLIT.ratio}}
        assert third == second
        assert provider.get_splits.await_count == 2


class TestSplitCheckRanges:
    @pytest.mark.asyncio
    async def test_unexplained_change_bounds_the_checked_range(self):
        storage = _storage()
        use_case = _use_case(
            _provider(),
            storage,
            [_held(0, "10"), _held(10, "12"), _held(21, "13"), _held(30, "13")],
            [_buy(20, "1")],
        )

        await use_case.execute(_query(30))

        storage.is_splits_checked.assert_awaited_once_with("ACME", _day(0), _day(10))

    @pytest.mark.asyncio
    async def test_latest_unexplained_change_bounds_the_checked_range(self):
        storage = _storage()
        use_case = _use_case(
            _provider(),
            storage,
            [_held(0, "10"), _held(10, "12"), _held(20, "14"), _held(30, "14")],
        )

        await use_case.execute(_query(30))

        storage.is_splits_checked.assert_awaited_once_with("ACME", _day(0), _day(20))

    @pytest.mark.asyncio
    async def test_explained_snapshots_need_no_split_check(self):
        storage = _storage()
        provider = _provider()
        use_case = _use_case(
            provider,
            storage,
            [_held(0, "10"), _held(21, "11"), _held(30, "11")],
            [_buy(20, "1")],
        )

        await use_case.execute(_query(30))

        storage.is_splits_checked.assert_not_awaited()
        provider.get_splits.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_trade_only_position_is_checked_until_its_last_trade(self):
        storage = _storage()
        use_case = _use_case(_provider(), storage, [], [_buy(0, "10"), _buy(10, "1")])

        await use_case.execute(_query(30))

        storage.is_splits_checked.assert_awaited_once_with("ACME", _day(0), _day(10))

    @pytest.mark.asyncio
    async def test_checked_range_keeps_the_latest_end_across_holders(self):
        storage = _storage()
        use_case = _use_case(
            _provider(),
            storage,
            [_held(0, "10", holder="observed"), _held(10, "12", holder="observed")],
            [_buy(0, "10", holder="traded"), _buy(40, "1", holder="traded")],
        )

        await use_case.execute(_query(50))

        storage.is_splits_checked.assert_awaited_once_with("ACME", _day(0), _day(40))

    @pytest.mark.asyncio
    async def test_in_range_replay_is_checked_until_its_last_trade(self):
        storage = _storage(
            history=[
                InstrumentPricePoint(
                    date=_day(offset), price=Dezimal(100), currency="EUR"
                )
                for offset in range(25, 30)
            ]
        )
        use_case = _use_case(
            _provider(),
            storage,
            [_held(0, "10"), _held(30, "11")],
            [_buy(25, "1")],
        )

        await use_case.execute(_query(30, first=20))

        storage.is_splits_checked.assert_awaited_once_with("ACME", _day(25), _day(25))
