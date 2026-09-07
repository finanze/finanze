from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from domain.dezimal import Dezimal
from domain.gains_timeline import (
    FixedIncomeAccrual,
    GainsCalculationMode,
    GainsMetrics,
    GainsTimeline,
    GainsTimelinePoint,
)
from domain.global_position import ProductType
from infrastructure.controller.config import quart
from infrastructure.controller.routes.gains_timeline import gains_timeline


def _empty_payload() -> dict:
    return {
        "currency": "EUR",
        "method": "HYBRID_VALUE",
        "basis": "NET_CONTRIBUTIONS",
        "quality": "COMPLETE",
        "basis_status": "NOT_APPLICABLE",
        "xirr": None,
        "annualized_xirr": None,
        "opening_value": None,
        "warnings": [],
        "not_applicable_reasons": [],
        "points": [],
    }


@pytest.mark.asyncio
async def test_parses_asset_filter_and_serializes_gains_timeline():
    entity_id = uuid4()
    wallet_id = uuid4()
    use_case = AsyncMock()
    use_case.execute.return_value = GainsTimeline(
        currency="EUR",
        points=[
            GainsTimelinePoint(
                date=date(2025, 1, 2),
                metrics=GainsMetrics(
                    value=Dezimal(120),
                    cost_basis=Dezimal(100),
                    net_contributions=Dezimal(100),
                    gain=Dezimal(20),
                    period_return=Dezimal("0.2"),
                    index=Dezimal(120),
                ),
            )
        ],
    )
    app = quart(Path("."))

    async with app.test_request_context(
        f"/?base_currency=EUR&product_type=CRYPTO&asset=CRYPTO:BTC&wallet_id={wallet_id}&entity={entity_id}&from_date=2025-01-01&to_date=2025-01-02"
    ):
        response, status = await gains_timeline(use_case)

    assert status == 200
    assert await response.get_json() == {
        "currency": "EUR",
        "method": "HYBRID_VALUE",
        "basis": "NET_CONTRIBUTIONS",
        "quality": "COMPLETE",
        "basis_status": "NOT_APPLICABLE",
        "xirr": None,
        "annualized_xirr": None,
        "opening_value": None,
        "warnings": [],
        "not_applicable_reasons": [],
        "points": [
            {
                "date": "2025-01-02",
                "value": 120.0,
                "cost_basis": 100.0,
                "net_contributions": 100.0,
                "gain": 20.0,
                "period_return": 0.2,
                "index": 120.0,
                "breakdown": {},
                "estimated": False,
            }
        ],
    }
    query = use_case.execute.await_args.args[0]
    assert query.entities == [entity_id]
    assert query.from_date == date(2025, 1, 1)
    assert query.to_date == date(2025, 1, 2)
    assert query.assets[0].product_type == ProductType.CRYPTO
    assert query.assets[0].asset_keys == ["BTC"]
    assert query.assets[0].wallet_ids == [wallet_id]
    assert query.accrue_fixed_income == FixedIncomeAccrual.NONE
    assert query.calculation_mode == GainsCalculationMode.HYBRID


@pytest.mark.asyncio
async def test_parses_fund_portfolio_and_stock_equity_type_filters():
    use_case = AsyncMock()
    use_case.execute.return_value = GainsTimeline(currency="EUR")
    app = quart(Path("."))

    async with app.test_request_context(
        "/?base_currency=EUR&product_type=FUND&portfolio=Long-term&portfolio=Retirement"
        "&product_type=STOCK_ETF&equity_type=STOCK&equity_type=ETF"
    ):
        response, status = await gains_timeline(use_case)

    assert status == 200
    assert await response.get_json() == _empty_payload()
    filters = {
        asset.product_type: asset
        for asset in use_case.execute.await_args.args[0].assets
    }
    assert filters[ProductType.FUND].portfolio_names == ["Long-term", "Retirement"]
    assert filters[ProductType.STOCK_ETF].equity_types == ["STOCK", "ETF"]


@pytest.mark.asyncio
async def test_parses_fixed_income_accrual_mode():
    use_case = AsyncMock()
    use_case.execute.return_value = GainsTimeline(currency="EUR")
    app = quart(Path("."))

    async with app.test_request_context(
        "/?base_currency=EUR&product_type=DEPOSIT&accrue_fixed_income=net"
    ):
        response, status = await gains_timeline(use_case)

    assert status == 200
    assert await response.get_json() == _empty_payload()
    query = use_case.execute.await_args.args[0]
    assert query.accrue_fixed_income == FixedIncomeAccrual.NET


@pytest.mark.asyncio
async def test_parses_snapshots_calculation_mode():
    use_case = AsyncMock()
    use_case.execute.return_value = GainsTimeline(currency="EUR")
    app = quart(Path("."))

    async with app.test_request_context(
        "/?base_currency=EUR&product_type=CRYPTO&calculation_mode=snapshots"
    ):
        response, status = await gains_timeline(use_case)

    assert status == 200
    query = use_case.execute.await_args.args[0]
    assert query.calculation_mode == GainsCalculationMode.SNAPSHOTS


@pytest.mark.asyncio
async def test_rejects_invalid_calculation_mode():
    use_case = AsyncMock()
    app = quart(Path("."))

    async with app.test_request_context(
        "/?base_currency=EUR&product_type=CRYPTO&calculation_mode=DAILY"
    ):
        response, status = await gains_timeline(use_case)

    assert status == 400
    assert (await response.get_json())["message"] == (
        "Invalid calculation_mode. Use HYBRID or SNAPSHOTS."
    )
    use_case.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_rejects_invalid_fixed_income_accrual_mode():
    use_case = AsyncMock()
    app = quart(Path("."))

    async with app.test_request_context(
        "/?base_currency=EUR&product_type=DEPOSIT&accrue_fixed_income=DAILY"
    ):
        response, status = await gains_timeline(use_case)

    assert status == 400
    assert (await response.get_json())["code"] == "INVALID_REQUEST"
    use_case.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_rejects_wallet_filters_without_crypto():
    use_case = AsyncMock()
    app = quart(Path("."))

    async with app.test_request_context(
        f"/?base_currency=EUR&product_type=FUND&wallet_id={uuid4()}"
    ):
        response, status = await gains_timeline(use_case)

    assert status == 400
    assert (await response.get_json())["message"] == (
        "wallet_id requires CRYPTO as a product_type or asset."
    )
    use_case.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_rejects_excluded_crowdlending_product_type():
    use_case = AsyncMock()
    app = quart(Path("."))

    async with app.test_request_context(
        "/?base_currency=EUR&product_type=CROWDLENDING"
    ):
        response, status = await gains_timeline(use_case)

    assert status == 400
    assert (await response.get_json())["code"] == "INVALID_REQUEST"
    use_case.execute.assert_not_awaited()
