from datetime import date
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from domain.dezimal import Dezimal
from domain.gains_timeline import GainsMetrics, GainsTimeline, GainsTimelinePoint
from domain.global_position import EquityType, ProductType


_MODULE_PATH = (
    Path(__file__).resolve().parents[3]
    / "frontend/app/src/python/finanze/app_background.py"
)
_MODULE_SPEC = spec_from_file_location("mobile_app_background", _MODULE_PATH)
assert _MODULE_SPEC is not None and _MODULE_SPEC.loader is not None
_MODULE = module_from_spec(_MODULE_SPEC)
_MODULE_SPEC.loader.exec_module(_MODULE)
MobileBackgroundApp = _MODULE.MobileBackgroundApp


@pytest.mark.asyncio
async def test_get_gains_timeline_maps_query_and_serializes_response():
    entity_id = uuid4()
    wallet_id = uuid4()
    app = MobileBackgroundApp()
    app._connected = True
    app.ex_storage = AsyncMock()
    app.get_gains_timeline_uc = AsyncMock()
    app.get_gains_timeline_uc.execute.return_value = GainsTimeline(
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
                breakdown={
                    "FUND": GainsMetrics(
                        value=Dezimal(120),
                        cost_basis=Dezimal(100),
                        net_contributions=Dezimal(100),
                        gain=Dezimal(20),
                        period_return=Dezimal("0.2"),
                        index=Dezimal(120),
                    )
                },
            )
        ],
    )

    result = await app.get_gains_timeline(
        {
            "assets": [
                {
                    "product_type": "FUND",
                    "asset_keys": ["IE00TEST0001"],
                    "portfolio_names": ["Long-term"],
                },
                {
                    "product_type": "STOCK_ETF",
                    "equity_types": ["ETF"],
                },
                {
                    "product_type": "CRYPTO",
                    "wallet_ids": [str(wallet_id)],
                },
            ],
            "base_currency": "EUR",
            "entities": [str(entity_id)],
            "from_date": "2025-01-01",
            "to_date": "2025-01-02",
            "accrue_fixed_income": "NET",
            "calculation_mode": "SNAPSHOTS",
        }
    )

    app.ex_storage.initialize.assert_awaited_once()
    query = app.get_gains_timeline_uc.execute.await_args.args[0]
    assert query.base_currency == "EUR"
    assert query.entities == [entity_id]
    assert query.from_date == date(2025, 1, 1)
    assert query.to_date == date(2025, 1, 2)
    assert query.accrue_fixed_income.value == "NET"
    assert query.calculation_mode.value == "SNAPSHOTS"
    assert query.assets[0].product_type == ProductType.FUND
    assert query.assets[0].asset_keys == ["IE00TEST0001"]
    assert query.assets[0].portfolio_names == ["Long-term"]
    assert query.assets[1].product_type == ProductType.STOCK_ETF
    assert query.assets[1].equity_types == [EquityType.ETF]
    assert query.assets[2].product_type == ProductType.CRYPTO
    assert query.assets[2].wallet_ids == [wallet_id]
    assert result == {
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
                "breakdown": {
                    "FUND": {
                        "value": 120.0,
                        "cost_basis": 100.0,
                        "net_contributions": 100.0,
                        "gain": 20.0,
                        "period_return": 0.2,
                        "index": 120.0,
                    }
                },
                "estimated": False,
            }
        ],
    }
