import json
import sys
from datetime import date
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import urlencode
from uuid import uuid4

import pytest

from domain.budget import BudgetComparison, BudgetLabelComparison
from domain.cashflow import CashflowGranularity
from domain.dezimal import Dezimal
from domain.earnings_expenses import FlowType
from domain.use_cases.get_cashflow_summary import GetCashflowSummary

ROOT = Path(__file__).resolve().parents[3]
MOBILE_ROOT = ROOT / "frontend/app/src/python/finanze"


def _load_module(name, path):
    spec = spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def mobile_transport(monkeypatch):
    quart = _load_module("mobile_quart", MOBILE_ROOT / "quart.py")
    wrapper = _load_module(
        "mobile_request_wrapper",
        MOBILE_ROOT / "infrastructure/controller/request_wrapper.py",
    )
    monkeypatch.setitem(sys.modules, "quart", quart)
    monkeypatch.setitem(
        sys.modules, "infrastructure.controller.request_wrapper", wrapper
    )
    handler = _load_module(
        "mobile_handler", MOBILE_ROOT / "infrastructure/controller/handler.py"
    )
    monkeypatch.setitem(sys.modules, "infrastructure.controller.handler", handler)
    router = _load_module(
        "mobile_router", MOBILE_ROOT / "infrastructure/controller/router.py"
    )
    cashflow = _load_module(
        "mobile_cashflow_summary",
        ROOT / "finanze/infrastructure/controller/routes/cashflow_summary.py",
    )
    return SimpleNamespace(
        RequestWrapper=wrapper.RequestWrapper,
        router=router.Router(),
        cashflow_summary=cashflow.cashflow_summary,
    )


@pytest.mark.parametrize(
    "values,expected", [(["first", "second"], "first"), ([""], "")]
)
def test_query_indexing_returns_first_value(mobile_transport, values, expected):
    request = mobile_transport.RequestWrapper(
        "GET", "/api/v1/cashflow", None, {}, {"from_date": values}
    )

    assert request.args["from_date"] == expected
    assert request.args.get("from_date") == expected
    assert request.args.getlist("from_date") == values


@pytest.mark.parametrize("args", [{}, {"from_date": []}])
def test_query_indexing_raises_key_error_for_missing_values(mobile_transport, args):
    request = mobile_transport.RequestWrapper("GET", "/api/v1/cashflow", None, {}, args)

    with pytest.raises(KeyError) as error:
        request.args["from_date"]

    assert error.value.args == ("from_date",)
    assert request.args.get("from_date", "default") == "default"
    assert request.args.getlist("from_date") == []


@pytest.mark.parametrize("with_entities", [False, True])
@pytest.mark.asyncio
async def test_cashflow_request_through_mobile_router(mobile_transport, with_entities):
    use_case = AsyncMock(spec=GetCashflowSummary)
    use_case.execute.return_value = {"currency": "EUR"}

    async def route(_request):
        return await mobile_transport.cashflow_summary(use_case)

    mobile_transport.router.add("GET", "/api/v1/cashflow", route)
    entity_ids = [uuid4(), uuid4()] if with_entities else []
    args = {
        "currency": "EUR",
        "from_date": "2026-08-01",
        "to_date": "2026-10-05",
        "granularity": "MONTH",
        "entity": [str(entity_id) for entity_id in entity_ids],
    }

    response = await mobile_transport.router.handle(
        "GET", f"/api/v1/cashflow?{urlencode(args, doseq=True)}", None, {}
    )

    assert response["status"] == 200
    assert json.loads(response["json"]) == {"currency": "EUR"}
    assert response["headers"]["Content-Type"] == "application/json"
    use_case.execute.assert_awaited_once()
    query = use_case.execute.await_args.args[0]
    assert query.currency == "EUR"
    assert query.from_date == date(2026, 8, 1)
    assert query.to_date == date(2026, 10, 5)
    assert query.granularity == CashflowGranularity.MONTH
    assert query.entities == (entity_ids or None)


@pytest.mark.parametrize(
    "dates",
    [
        {"to_date": "2026-10-05"},
        {"from_date": "2026-08-01"},
        {"from_date": "invalid", "to_date": "2026-10-05"},
        {"from_date": "2026-08-01", "to_date": "invalid"},
        {"from_date": "2026-10-05", "to_date": "2026-08-01"},
    ],
)
@pytest.mark.asyncio
async def test_invalid_cashflow_dates_return_400_on_mobile(mobile_transport, dates):
    use_case = AsyncMock(spec=GetCashflowSummary)

    async def route(_request):
        return await mobile_transport.cashflow_summary(use_case)

    mobile_transport.router.add("GET", "/api/v1/cashflow", route)
    args = {"currency": "EUR", **dates}

    response = await mobile_transport.router.handle(
        "GET", f"/api/v1/cashflow?{urlencode(args)}", None, {}
    )

    assert response["status"] == 400
    assert json.loads(response["json"])["code"] == "INVALID_REQUEST"
    use_case.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_json_responses_keep_nulls_and_drop_non_finite_numbers(
    mobile_transport,
):
    comparison = BudgetComparison(
        expected=Dezimal("300"), actual=None, ratio=None, difference=None
    )
    row = BudgetLabelComparison(
        label_id=None, flow_type=FlowType.EXPENSE, comparison=comparison
    )

    async def route(_request):
        return {"rows": [row], "nan": float("nan"), "inf": Dezimal("Infinity")}

    mobile_transport.router.add("GET", "/api/v1/budget", route)

    response = await mobile_transport.router.handle("GET", "/api/v1/budget", None, {})

    assert "data" not in response
    assert json.loads(response["json"]) == {
        "rows": [
            {
                "label_id": None,
                "flow_type": "EXPENSE",
                "comparison": {
                    "expected": 300.0,
                    "actual": None,
                    "ratio": None,
                    "difference": None,
                },
            }
        ],
        "nan": None,
        "inf": None,
    }


@pytest.mark.asyncio
async def test_binary_and_unserializable_responses_keep_raw_data(mobile_transport):
    quart = sys.modules["quart"]
    payload = b"\x89PNG"

    async def image(_request):
        return quart.Response(data=payload, mimetype="image/png")

    async def nested_bytes(_request):
        return {"content": payload}

    mobile_transport.router.add("GET", "/api/v1/image", image)
    mobile_transport.router.add("GET", "/api/v1/nested", nested_bytes)

    image_response = await mobile_transport.router.handle(
        "GET", "/api/v1/image", None, {}
    )
    nested_response = await mobile_transport.router.handle(
        "GET", "/api/v1/nested", None, {}
    )

    assert image_response["data"] == payload
    assert "json" not in image_response
    assert nested_response["data"] == {"content": payload}
    assert "json" not in nested_response
