import time
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from application.ports.networth_timeline_port import NetworthTimelinePort
from application.use_cases.get_networth_timeline import GetNetworthTimelineImpl
from domain.commodity import CommodityType, WeightUnit
from domain.dezimal import Dezimal
from domain.exchange_rate import HistoricMetalRates
from domain.global_position import ProductType
from domain.networth_timeline import (
    COMMODITY_HISTORIC_CUTOFF,
    HoldingValuation,
    MortgageValuation,
    NetworthTimelinePoint,
    NetworthTimelineQuery,
    NetworthTimelineState,
    PositionSnapshot,
)
from domain.real_estate import RealEstateFlowSubtype

_ONE_TROY_OUNCE_GRAMS = "31.1034768"


def _holding(product_type, amount, currency="EUR", loan_ref=None):
    return HoldingValuation(
        product_type=ProductType(product_type),
        currency=currency,
        amount=Dezimal(amount),
        loan_ref=loan_ref,
    )


def _commodity(
    amount,
    weight,
    unit=WeightUnit.GRAM,
    commodity_type=CommodityType.GOLD,
    currency="EUR",
):
    return HoldingValuation(
        product_type=ProductType.COMMODITY,
        currency=currency,
        amount=Dezimal(amount),
        commodity_type=commodity_type,
        weight=Dezimal(weight),
        weight_unit=unit,
    )


def _historic(days, prices):
    return HistoricMetalRates(
        unit=WeightUnit.TROY_OUNCE,
        days=tuple(days),
        prices={
            currency: tuple(Dezimal(v) for v in values)
            for currency, values in prices.items()
        },
    )


def _snapshot(holder, day, holdings, hour=12, deleted_at=None, redeclaring=False):
    return PositionSnapshot(
        holder=holder,
        moment=datetime(day.year, day.month, day.day, hour, 0, 0),
        holdings=holdings,
        holder_deleted_at=deleted_at,
        redeclaring=redeclaring,
    )


def _mortgage(loan_ref, day, outstanding, currency="EUR", origination=None):
    return MortgageValuation(
        loan_ref=loan_ref,
        moment=datetime(day.year, day.month, day.day, 12, 0, 0),
        outstanding=Dezimal(outstanding),
        currency=currency,
        origination=origination,
    )


def _re_loan_flow(linked_hash, outstanding=None):
    payload = SimpleNamespace(
        principal_outstanding=Dezimal(outstanding) if outstanding is not None else None
    )
    return SimpleNamespace(
        flow_subtype=RealEstateFlowSubtype.LOAN,
        linked_loan_hash=linked_hash,
        payload=payload,
    )


def _real_estate(
    purchase_date,
    purchase_price,
    estimated_market_value,
    valuations=None,
    flows=None,
    currency="EUR",
    is_residence=False,
    id=None,
):
    return SimpleNamespace(
        id=id,
        basic_info=SimpleNamespace(
            name="Test Property",
            is_residence=is_residence,
            is_rented=False,
        ),
        purchase_info=SimpleNamespace(
            date=purchase_date, price=Dezimal(purchase_price)
        ),
        valuation_info=SimpleNamespace(
            estimated_market_value=Dezimal(estimated_market_value),
            valuations=valuations or [],
        ),
        currency=currency,
        flows=flows or [],
    )


def _build(
    *,
    rates=None,
    disabled=None,
    real_estate=None,
    state=None,
    snapshots=None,
    mortgages=None,
    points=None,
    metal_rates=None,
):
    port = AsyncMock(spec=NetworthTimelinePort)
    port.get_state.return_value = state or NetworthTimelineState()
    port.get_position_snapshots.return_value = snapshots or []
    port.get_mortgage_valuations.return_value = mortgages or []
    port.get_points.return_value = points or []

    exchange = AsyncMock()
    exchange.get.return_value = rates if rates is not None else {}

    entity = AsyncMock()
    entity.get_disabled_entities.return_value = disabled or []

    real_estate_port = AsyncMock()
    real_estate_port.get_all.return_value = real_estate or []

    metal = AsyncMock()
    if metal_rates is None:
        metal.get_partial_historic_rates.return_value = None
    else:
        metal.get_partial_historic_rates.side_effect = lambda commodity, **kwargs: (
            metal_rates.get(commodity)
        )

    use_case = GetNetworthTimelineImpl(port, exchange, entity, real_estate_port, metal)
    return use_case, port


def _persisted(port):
    port.persist.assert_awaited_once()
    args = port.persist.await_args.args
    return {
        "points": args[0],
        "currency": args[1],
        "state": args[2],
        "wipe": args[3],
    }


class TestCompute:
    @pytest.mark.asyncio
    async def test_carry_forward_across_holders(self):
        snapshots = [
            _snapshot("e1||REAL", date(2025, 1, 1), [_holding("ACCOUNT", "100")]),
            _snapshot("e2||REAL", date(2025, 1, 2), [_holding("FUND", "200")]),
            _snapshot("e1||REAL", date(2025, 1, 3), [_holding("ACCOUNT", "150")]),
        ]
        use_case, port = _build(snapshots=snapshots)

        await use_case.execute(NetworthTimelineQuery())

        result = _persisted(port)
        assert result["wipe"] is True
        by_day = {p.date: p for p in result["points"]}
        assert by_day[date(2025, 1, 1)].breakdown["ACCOUNT"] == Dezimal(100)
        assert by_day[date(2025, 1, 1)].total == Dezimal(100)
        assert by_day[date(2025, 1, 2)].breakdown["ACCOUNT"] == Dezimal(100)
        assert by_day[date(2025, 1, 2)].breakdown["FUND"] == Dezimal(200)
        assert by_day[date(2025, 1, 2)].total == Dezimal(300)
        assert by_day[date(2025, 1, 3)].breakdown["ACCOUNT"] == Dezimal(150)
        assert by_day[date(2025, 1, 3)].total == Dezimal(350)

    @pytest.mark.asyncio
    async def test_currency_conversion(self):
        snapshots = [
            _snapshot(
                "e1||REAL",
                date(2025, 1, 1),
                [_holding("ACCOUNT", "110", currency="USD")],
            )
        ]
        rates = {"EUR": {"USD": Dezimal("1.1")}}
        use_case, port = _build(snapshots=snapshots, rates=rates)

        await use_case.execute(NetworthTimelineQuery())

        result = _persisted(port)
        assert result["points"][0].breakdown["ACCOUNT"] == Dezimal(100)

    @pytest.mark.asyncio
    async def test_missing_rate_skips_value(self):
        snapshots = [
            _snapshot(
                "e1||REAL",
                date(2025, 1, 1),
                [
                    _holding("ACCOUNT", "100", currency="EUR"),
                    _holding("FUND", "50", currency="JPY"),
                ],
            )
        ]
        use_case, port = _build(snapshots=snapshots, rates={})

        await use_case.execute(NetworthTimelineQuery())

        point = _persisted(port)["points"][0]
        assert point.breakdown["ACCOUNT"] == Dezimal(100)
        assert "FUND" not in point.breakdown

    @pytest.mark.asyncio
    async def test_debts_negative_and_linked_mortgage_excluded(self):
        snapshots = [
            _snapshot(
                "e1||REAL",
                date(2025, 1, 1),
                [
                    _holding("ACCOUNT", "1000"),
                    _holding("LOAN", "500", loan_ref="hashLINKED"),
                    _holding("LOAN", "300", loan_ref="hashFREE"),
                    _holding("CARD", "20"),
                    _holding("CREDIT", "10"),
                ],
            )
        ]
        real_estate = [
            _real_estate(
                date(2024, 1, 1),
                "100000",
                "100000",
                flows=[_re_loan_flow("hashLINKED", outstanding="500")],
            )
        ]
        use_case, port = _build(snapshots=snapshots, real_estate=real_estate)

        await use_case.execute(NetworthTimelineQuery())

        point = _persisted(port)["points"][0]
        assert point.breakdown["ACCOUNT"] == Dezimal(1000)
        assert point.breakdown["LOAN"] == Dezimal(-300)
        assert point.breakdown["CARD"] == Dezimal(-20)
        assert point.breakdown["CREDIT"] == Dezimal(-10)

    @pytest.mark.asyncio
    async def test_estimated_market_value_is_fixed_from_purchase(self):
        real_estate = _real_estate(
            date(2025, 8, 7),
            "165000",
            "190000",
            valuations=[
                SimpleNamespace(date=date(2025, 6, 30), amount=Dezimal("191879.41"))
            ],
        )
        use_case, _ = _build()

        breakpoints = use_case._build_value_breakpoints(real_estate, "EUR", {})

        # Single fixed breakpoint at the purchase date using the estimated value.
        assert breakpoints == [(date(2025, 8, 7), Dezimal(190000))]
        # No value before the property is owned.
        assert use_case._value_at(breakpoints, date(2025, 6, 30)) == Dezimal(0)
        # Fixed estimated market value from the purchase date on.
        assert use_case._value_at(breakpoints, date(2025, 8, 10)) == Dezimal(190000)

    @pytest.mark.asyncio
    async def test_deleted_holder_stops_contributing_after_deletion(self):
        snapshots = [
            _snapshot(
                "e1|acc-old|REAL",
                date(2025, 4, 1),
                [_holding("ACCOUNT", "1000000")],
                deleted_at=date(2025, 4, 10),
            ),
            _snapshot(
                "e1|acc-new|REAL",
                date(2025, 4, 15),
                [_holding("ACCOUNT", "1000000")],
            ),
        ]
        use_case, port = _build(snapshots=snapshots)

        await use_case.execute(NetworthTimelineQuery())

        by_day = {p.date: p for p in _persisted(port)["points"]}
        assert by_day[date(2025, 4, 1)].total == Dezimal(1000000)
        # Deleted on 2025-04-10 → no contribution from that day on.
        assert by_day[date(2025, 4, 10)].total == Dezimal(0)
        # Re-added account counted once, not stacked on the deleted holder.
        assert by_day[date(2025, 4, 15)].total == Dezimal(1000000)

    @pytest.mark.asyncio
    async def test_sheets_import_replaces_previous(self):
        # A re-declaring source (Sheets) produces one snapshot per import held by
        # the source itself, carrying the whole portfolio that import declared.
        # A later import fully replaces the previous one, so a holding dropped
        # from it stops contributing; a non-redeclaring (REAL) holder is
        # untouched and keeps carrying forward.
        snapshots = [
            _snapshot(
                "e0||REAL",
                date(2025, 9, 1),
                [_holding("ACCOUNT", "5000")],
            ),
            _snapshot(
                "SHEETS",
                date(2025, 9, 11),
                [_holding("LOAN", "148500"), _holding("LOAN", "12718")],
                redeclaring=True,
            ),
            _snapshot(
                "SHEETS",
                date(2025, 11, 19),
                [_holding("LOAN", "12718")],
                redeclaring=True,
            ),
        ]
        use_case, port = _build(snapshots=snapshots)

        await use_case.execute(NetworthTimelineQuery())

        by_day = {p.date: p for p in _persisted(port)["points"]}
        # First import: both Sheets loans plus the REAL account.
        assert by_day[date(2025, 9, 11)].breakdown["LOAN"] == Dezimal(-161218)
        assert by_day[date(2025, 9, 11)].breakdown["ACCOUNT"] == Dezimal(5000)
        # Second import drops the 148500 loan → only the 12718 loan remains.
        assert by_day[date(2025, 11, 19)].breakdown["LOAN"] == Dezimal(-12718)
        # The non-redeclaring REAL holder is untouched by the Sheets replacement.
        assert by_day[date(2025, 11, 19)].breakdown["ACCOUNT"] == Dezimal(5000)

    @pytest.mark.asyncio
    async def test_manual_redeclaring_replaces_stale_holders(self):
        # The same logical position re-entered manually (e.g. once with an
        # account, later without) must not be double-counted: the latest import
        # carries the whole manual portfolio and replaces the previous one.
        snapshots = [
            _snapshot(
                "MANUAL",
                date(2026, 1, 30),
                [_holding("FACTORING", "1111"), _holding("DEPOSIT", "2000")],
                redeclaring=True,
            ),
            _snapshot(
                "MANUAL",
                date(2026, 4, 12),
                [_holding("FACTORING", "1100"), _holding("DEPOSIT", "2000")],
                redeclaring=True,
            ),
        ]
        use_case, port = _build(snapshots=snapshots)

        await use_case.execute(NetworthTimelineQuery())

        by_day = {p.date: p for p in _persisted(port)["points"]}
        assert by_day[date(2026, 1, 30)].breakdown["FACTORING"] == Dezimal(1111)
        # Latest manual import replaces the stale 1111 factoring with 1100; the
        # deposit it still declares is kept (not dropped, not duplicated).
        assert by_day[date(2026, 4, 12)].breakdown["FACTORING"] == Dezimal(1100)
        assert by_day[date(2026, 4, 12)].breakdown["DEPOSIT"] == Dezimal(2000)
        assert by_day[date(2026, 4, 12)].total == Dezimal(3100)


class TestControlFlow:
    @pytest.mark.asyncio
    async def test_no_calculation_skips_compute(self):
        use_case, port = _build(points=[])
        await use_case.execute(NetworthTimelineQuery(no_calculation=True))
        port.persist.assert_not_awaited()
        port.get_position_snapshots.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_fast_exit_when_nothing_new(self):
        snapshots = [
            _snapshot("e1||REAL", date(2025, 1, 1), [_holding("ACCOUNT", "100")])
        ]
        signature = GetNetworthTimelineImpl._signature("EUR", [], set(), [])
        state = NetworthTimelineState(
            inputs_signature=signature, last_computed_date=date(2025, 1, 1)
        )
        use_case, port = _build(snapshots=snapshots, state=state)

        await use_case.execute(NetworthTimelineQuery())

        port.persist.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_signature_change_wipes(self):
        snapshots = [
            _snapshot("e1||REAL", date(2025, 1, 1), [_holding("ACCOUNT", "100")])
        ]
        state = NetworthTimelineState(
            inputs_signature="stale", last_computed_date=date(2025, 1, 1)
        )
        use_case, port = _build(snapshots=snapshots, state=state)

        await use_case.execute(NetworthTimelineQuery())

        assert _persisted(port)["wipe"] is True

    @pytest.mark.asyncio
    async def test_incremental_persists_only_new_days(self):
        snapshots = [
            _snapshot("e1||REAL", date(2025, 1, 1), [_holding("ACCOUNT", "100")]),
            _snapshot("e1||REAL", date(2025, 1, 3), [_holding("ACCOUNT", "150")]),
        ]
        signature = GetNetworthTimelineImpl._signature("EUR", [], set(), [])
        state = NetworthTimelineState(
            inputs_signature=signature, last_computed_date=date(2025, 1, 1)
        )
        use_case, port = _build(snapshots=snapshots, state=state)

        await use_case.execute(NetworthTimelineQuery())

        result = _persisted(port)
        assert result["wipe"] is False
        days = [p.date for p in result["points"]]
        assert days == [date(2025, 1, 3)]


class TestMergeAndRealEstate:
    @pytest.mark.asyncio
    async def test_range_filters_returned_points(self):
        points = [
            NetworthTimelinePoint(date(2025, 1, d), Dezimal(d), {"ACCOUNT": Dezimal(d)})
            for d in range(1, 6)
        ]
        use_case, _ = _build(points=points)

        result = await use_case.execute(
            NetworthTimelineQuery(from_date=date(2025, 1, 3), no_calculation=True)
        )

        days = [p.date for p in result.points]
        assert days == [date(2025, 1, 3), date(2025, 1, 4), date(2025, 1, 5)]

    @pytest.mark.asyncio
    async def test_real_estate_equity_merged(self):
        points = [
            NetworthTimelinePoint(
                date(2025, 6, 1), Dezimal(1000), {"ACCOUNT": Dezimal(1000)}
            )
        ]
        real_estate = [_real_estate(date(2025, 3, 1), "200000", "200000")]
        use_case, _ = _build(points=points, real_estate=real_estate)

        result = await use_case.execute(NetworthTimelineQuery(no_calculation=True))

        by_day = {p.date: p for p in result.points}
        assert by_day[date(2025, 3, 1)].breakdown["REAL_ESTATE"] == Dezimal(200000)
        assert by_day[date(2025, 3, 1)].total == Dezimal(200000)
        assert by_day[date(2025, 6, 1)].breakdown["ACCOUNT"] == Dezimal(1000)
        assert by_day[date(2025, 6, 1)].breakdown["REAL_ESTATE"] == Dezimal(200000)
        assert by_day[date(2025, 6, 1)].total == Dezimal(201000)

    @pytest.mark.asyncio
    async def test_real_estate_residence_split_into_separate_bucket(self):
        real_estate = [
            _real_estate(date(2025, 3, 1), "200000", "200000", is_residence=False),
            _real_estate(date(2025, 3, 1), "300000", "300000", is_residence=True),
        ]
        use_case, _ = _build(real_estate=real_estate)

        result = await use_case.execute(NetworthTimelineQuery(no_calculation=True))

        by_day = {p.date: p for p in result.points}
        point = by_day[date(2025, 3, 1)]
        assert point.breakdown["REAL_ESTATE"] == Dezimal(200000)
        assert point.breakdown["REAL_ESTATE_RESIDENCE"] == Dezimal(300000)
        assert point.total == Dezimal(500000)

    @pytest.mark.asyncio
    async def test_linked_mortgage_gap_backfill(self):
        flows = [_re_loan_flow("hashM", outstanding="80000")]
        real_estate = [_real_estate(date(2025, 1, 1), "200000", "200000", flows=flows)]
        mortgages = [
            _mortgage("hashM", date(2025, 4, 1), "80000", origination=date(2025, 1, 1)),
            _mortgage("hashM", date(2025, 5, 1), "78000", origination=date(2025, 1, 1)),
        ]
        use_case, _ = _build(points=[], real_estate=real_estate, mortgages=mortgages)

        result = await use_case.execute(
            NetworthTimelineQuery(to_date=date(2025, 5, 31), no_calculation=True)
        )

        by_day = {p.date: p for p in result.points}
        # Purchase/anchor day: outstanding backfilled flat from earliest snapshot (80000)
        assert by_day[date(2025, 1, 1)].breakdown["REAL_ESTATE"] == Dezimal(120000)
        assert by_day[date(2025, 4, 1)].breakdown["REAL_ESTATE"] == Dezimal(120000)
        assert by_day[date(2025, 5, 1)].breakdown["REAL_ESTATE"] == Dezimal(122000)

    @pytest.mark.asyncio
    async def test_unlinked_mortgage_subtracted_from_equity(self):
        # A manually entered mortgage (no linked loan hash) must still reduce the
        # real estate equity using its declared outstanding principal.
        flows = [_re_loan_flow(None, outstanding="12718")]
        real_estate = [_real_estate(date(2025, 1, 1), "30000", "30000", flows=flows)]
        use_case, _ = _build(points=[], real_estate=real_estate)

        result = await use_case.execute(NetworthTimelineQuery(no_calculation=True))

        by_day = {p.date: p for p in result.points}
        assert by_day[date(2025, 1, 1)].breakdown["REAL_ESTATE"] == Dezimal(
            30000 - 12718
        )

    @pytest.mark.asyncio
    async def test_unlinked_mortgage_currency_converted(self):
        # The unlinked mortgage outstanding is expressed in the property currency
        # and must be converted into the target currency before netting.
        flows = [_re_loan_flow(None, outstanding="11000")]
        real_estate = [
            _real_estate(
                date(2025, 1, 1), "30000", "30000", flows=flows, currency="USD"
            )
        ]
        rates = {"EUR": {"USD": Dezimal("1.1")}}
        use_case, _ = _build(points=[], real_estate=real_estate, rates=rates)

        result = await use_case.execute(NetworthTimelineQuery(no_calculation=True))

        by_day = {p.date: p for p in result.points}
        # value 30000/1.1 = 27272.72..., outstanding 11000/1.1 = 10000
        assert by_day[date(2025, 1, 1)].breakdown["REAL_ESTATE"] == Dezimal(
            "30000"
        ) / Dezimal("1.1") - Dezimal(10000)


class TestCommodityRevaluation:
    @pytest.mark.asyncio
    async def test_daily_revaluation_densifies_and_overrides_stored_value(self):
        snapshots = [
            _snapshot(
                "h1", date(2025, 6, 15), [_commodity("1000", _ONE_TROY_OUNCE_GRAMS)]
            )
        ]
        historic = _historic(
            [date(2025, 6, 15), date(2025, 6, 20), date(2025, 6, 25)],
            {"EUR": ["2000", "2100", "2200"]},
        )
        use_case, port = _build(
            snapshots=snapshots, metal_rates={CommodityType.GOLD: historic}
        )

        await use_case.execute(NetworthTimelineQuery())

        persisted = _persisted(port)
        points = {p.date: p for p in persisted["points"]}
        assert len(points) == 3
        # The historic price overrides the stale stored market value (1000).
        assert points[date(2025, 6, 15)].breakdown["COMMODITY"] == Dezimal(2000)
        # Days without snapshots still get a revalued point.
        assert points[date(2025, 6, 20)].breakdown["COMMODITY"] == Dezimal(2100)
        assert points[date(2025, 6, 25)].breakdown["COMMODITY"] == Dezimal(2200)
        # The memo cursor extends to the last densified day.
        assert persisted["state"].last_computed_date == date(2025, 6, 25)

    @pytest.mark.asyncio
    async def test_troy_ounce_weight_used_directly(self):
        snapshots = [
            _snapshot(
                "h1",
                date(2025, 6, 15),
                [_commodity("1000", "2", unit=WeightUnit.TROY_OUNCE)],
            )
        ]
        historic = _historic([date(2025, 6, 15)], {"EUR": ["2000"]})
        use_case, port = _build(
            snapshots=snapshots, metal_rates={CommodityType.GOLD: historic}
        )

        await use_case.execute(NetworthTimelineQuery())

        points = _persisted(port)["points"]
        assert points[0].breakdown["COMMODITY"] == Dezimal(4000)

    @pytest.mark.asyncio
    async def test_fallback_to_stored_value_without_historic_rates(self):
        snapshots = [
            _snapshot(
                "h1", date(2025, 6, 15), [_commodity("1000", _ONE_TROY_OUNCE_GRAMS)]
            )
        ]
        use_case, port = _build(snapshots=snapshots)

        await use_case.execute(NetworthTimelineQuery())

        points = _persisted(port)["points"]
        assert len(points) == 1
        assert points[0].breakdown["COMMODITY"] == Dezimal(1000)

    def test_post_cutoff_days_use_stored_value(self):
        holding = _commodity("1000", _ONE_TROY_OUNCE_GRAMS)
        historic = _historic([date(2025, 6, 15)], {"EUR": ["2000"]})
        use_case, _ = _build()

        value = use_case._commodity_value_at(
            holding,
            COMMODITY_HISTORIC_CUTOFF,
            {CommodityType.GOLD: historic},
            "EUR",
            {},
        )

        assert value == Dezimal(1000)

    @pytest.mark.asyncio
    async def test_native_currency_series_converted_to_target(self):
        snapshots = [
            _snapshot(
                "h1",
                date(2025, 6, 15),
                [_commodity("1000", _ONE_TROY_OUNCE_GRAMS, currency="USD")],
            )
        ]
        historic = _historic([date(2025, 6, 15)], {"USD": ["2500"]})
        rates = {"EUR": {"USD": Dezimal("1.25")}}
        use_case, port = _build(
            snapshots=snapshots,
            rates=rates,
            metal_rates={CommodityType.GOLD: historic},
        )

        await use_case.execute(NetworthTimelineQuery())

        points = _persisted(port)["points"]
        assert points[0].breakdown["COMMODITY"] == Dezimal(2000)

    @pytest.mark.asyncio
    async def test_target_currency_series_when_native_missing(self):
        snapshots = [
            _snapshot(
                "h1",
                date(2025, 6, 15),
                [_commodity("1000", _ONE_TROY_OUNCE_GRAMS, currency="USD")],
            )
        ]
        historic = _historic([date(2025, 6, 15)], {"EUR": ["2000"]})
        use_case, port = _build(
            snapshots=snapshots, metal_rates={CommodityType.GOLD: historic}
        )

        await use_case.execute(NetworthTimelineQuery())

        points = _persisted(port)["points"]
        assert points[0].breakdown["COMMODITY"] == Dezimal(2000)

    @pytest.mark.asyncio
    async def test_stored_value_converted_when_no_usable_series(self):
        snapshots = [
            _snapshot(
                "h1",
                date(2025, 6, 15),
                [_commodity("1000", _ONE_TROY_OUNCE_GRAMS, currency="USD")],
            )
        ]
        historic = _historic([date(2025, 6, 15)], {"GBP": ["1800"]})
        rates = {"EUR": {"USD": Dezimal("1.25")}}
        use_case, port = _build(
            snapshots=snapshots,
            rates=rates,
            metal_rates={CommodityType.GOLD: historic},
        )

        await use_case.execute(NetworthTimelineQuery())

        points = _persisted(port)["points"]
        assert points[0].breakdown["COMMODITY"] == Dezimal(800)

    @pytest.mark.asyncio
    async def test_provider_not_called_without_commodities(self):
        snapshots = [_snapshot("h1", date(2025, 1, 1), [_holding("ACCOUNT", "100")])]
        use_case, _ = _build(snapshots=snapshots)

        await use_case.execute(NetworthTimelineQuery())

        use_case._metal_price_provider.get_partial_historic_rates.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rates_appearing_wipes_memo(self):
        snapshots = [
            _snapshot(
                "h1", date(2025, 6, 15), [_commodity("1000", _ONE_TROY_OUNCE_GRAMS)]
            )
        ]
        use_case, port = _build(snapshots=snapshots)
        await use_case.execute(NetworthTimelineQuery())
        signature = _persisted(port)["state"].inputs_signature

        historic = _historic([date(2025, 6, 15)], {"EUR": ["2000"]})
        state = NetworthTimelineState(
            inputs_signature=signature, last_computed_date=date(2025, 6, 15)
        )
        use_case2, port2 = _build(
            snapshots=snapshots,
            state=state,
            metal_rates={CommodityType.GOLD: historic},
        )
        await use_case2.execute(NetworthTimelineQuery())

        persisted = _persisted(port2)
        assert persisted["wipe"] is True
        assert persisted["points"][0].breakdown["COMMODITY"] == Dezimal(2000)

    @pytest.mark.asyncio
    async def test_provider_not_called_when_memo_current(self):
        snapshots = [
            _snapshot(
                "h1", date(2025, 6, 15), [_commodity("1000", _ONE_TROY_OUNCE_GRAMS)]
            )
        ]
        historic = _historic(
            [date(2025, 6, 15), COMMODITY_HISTORIC_CUTOFF - timedelta(days=1)],
            {"EUR": ["2000", "2100"]},
        )
        metal_rates = {CommodityType.GOLD: historic}
        use_case, port = _build(snapshots=snapshots, metal_rates=metal_rates)
        await use_case.execute(NetworthTimelineQuery())
        state = _persisted(port)["state"]

        use_case2, port2 = _build(
            snapshots=snapshots, state=state, metal_rates=metal_rates
        )
        await use_case2.execute(NetworthTimelineQuery())

        use_case2._metal_price_provider.get_partial_historic_rates.assert_not_awaited()
        port2.persist.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_provider_not_called_for_post_cutoff_snapshots(self):
        snapshots = [
            _snapshot(
                "h1",
                COMMODITY_HISTORIC_CUTOFF,
                [_commodity("1000", _ONE_TROY_OUNCE_GRAMS)],
            )
        ]
        use_case, _ = _build(metal_rates={})

        historic, part = await use_case._resolve_historic_rates(
            snapshots, NetworthTimelineState(), "base", COMMODITY_HISTORIC_CUTOFF
        )

        assert historic == {}
        assert part == ""
        use_case._metal_price_provider.get_partial_historic_rates.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_dataset_extension_appends_without_wipe(self):
        snapshots = [
            _snapshot(
                "h1", date(2025, 6, 15), [_commodity("1000", _ONE_TROY_OUNCE_GRAMS)]
            )
        ]
        historic = _historic([date(2025, 6, 15)], {"EUR": ["2000"]})
        use_case, port = _build(
            snapshots=snapshots, metal_rates={CommodityType.GOLD: historic}
        )
        await use_case.execute(NetworthTimelineQuery())
        state = _persisted(port)["state"]

        extended = _historic(
            [date(2025, 6, 15), date(2025, 6, 20)], {"EUR": ["2000", "2100"]}
        )
        use_case2, port2 = _build(
            snapshots=snapshots,
            state=state,
            metal_rates={CommodityType.GOLD: extended},
        )
        await use_case2.execute(NetworthTimelineQuery())

        persisted = _persisted(port2)
        assert persisted["wipe"] is False
        assert len(persisted["points"]) == 1
        assert persisted["points"][0].date == date(2025, 6, 20)
        assert persisted["points"][0].breakdown["COMMODITY"] == Dezimal(2100)

    @pytest.mark.asyncio
    async def test_deleted_holder_commodity_stops_on_deletion_day(self):
        snapshots = [
            _snapshot(
                "h1",
                date(2025, 6, 15),
                [_commodity("1000", _ONE_TROY_OUNCE_GRAMS)],
                deleted_at=date(2025, 6, 22),
            )
        ]
        historic = _historic(
            [date(2025, 6, 15), date(2025, 6, 20), date(2025, 6, 25)],
            {"EUR": ["2000", "2100", "2200"]},
        )
        use_case, port = _build(
            snapshots=snapshots, metal_rates={CommodityType.GOLD: historic}
        )

        await use_case.execute(NetworthTimelineQuery())

        points = {p.date: p for p in _persisted(port)["points"]}
        assert points[date(2025, 6, 20)].breakdown["COMMODITY"] == Dezimal(2100)
        assert points[date(2025, 6, 22)].breakdown == {}
        assert points[date(2025, 6, 25)].breakdown == {}


class TestRealEstateCache:
    @pytest.mark.asyncio
    async def test_series_cached_within_ttl(self):
        real_estate = [_real_estate(date(2025, 1, 1), "200000", "200000")]
        use_case, port = _build(points=[], real_estate=real_estate)

        await use_case.execute(NetworthTimelineQuery(no_calculation=True))
        await use_case.execute(NetworthTimelineQuery(no_calculation=True))

        assert port.get_mortgage_valuations.await_count == 1

    @pytest.mark.asyncio
    async def test_signature_change_recomputes(self):
        real_estate = [_real_estate(date(2025, 1, 1), "200000", "200000")]
        use_case, port = _build(points=[], real_estate=real_estate)

        await use_case.execute(NetworthTimelineQuery(no_calculation=True))

        use_case._real_estate_port.get_all.return_value = [
            _real_estate(date(2025, 1, 1), "200000", "250000")
        ]
        result = await use_case.execute(NetworthTimelineQuery(no_calculation=True))

        assert port.get_mortgage_valuations.await_count == 2
        by_day = {p.date: p for p in result.points}
        assert by_day[date(2025, 1, 1)].breakdown["REAL_ESTATE"] == Dezimal(250000)

    @pytest.mark.asyncio
    async def test_expired_ttl_recomputes(self):
        real_estate = [_real_estate(date(2025, 1, 1), "200000", "200000")]
        use_case, port = _build(points=[], real_estate=real_estate)

        await use_case.execute(NetworthTimelineQuery(no_calculation=True))

        signature, _, series = use_case._re_series_cache
        use_case._re_series_cache = (signature, time.monotonic() - 1, series)
        await use_case.execute(NetworthTimelineQuery(no_calculation=True))

        assert port.get_mortgage_valuations.await_count == 2

    @pytest.mark.asyncio
    async def test_no_real_estate_does_not_cache(self):
        use_case, port = _build(points=[], real_estate=[])

        await use_case.execute(NetworthTimelineQuery(no_calculation=True))

        assert use_case._re_series_cache is None
        port.get_mortgage_valuations.assert_not_awaited()
