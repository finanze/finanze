import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
import pytest_asyncio

from domain.dezimal import Dezimal
from domain.fetch_result import FetchResult, FetchResultCode
from domain.entity_login import LoginConfirmationType
from domain.global_position import ProductType


class ToolCaller:
    def __init__(self, env, token: str):
        self._env = env
        self._token = token

    async def _call(self, tool: str, arguments: dict):
        async with self._env.connect(self._token) as mcp_client:
            return await mcp_client.call_tool(tool, arguments)

    async def ok(self, tool: str, **arguments):
        result = await self._call(tool, arguments)
        assert not result.is_error, result.content[0].text
        return json.loads(result.content[0].text)

    async def error(self, tool: str, **arguments) -> str:
        result = await self._call(tool, arguments)
        assert result.is_error
        return result.content[0].text


@pytest_asyncio.fixture
async def tools(mcp_env):
    token = (await mcp_env.configure(enabled=True, read_only=False))["token"]
    return ToolCaller(mcp_env, token)


class TestMcpTools:
    @pytest.mark.asyncio
    async def test_context(self, tools):
        context = await tools.ok("get_context")

        assert context["default_currency"] == "EUR"
        assert context["read_only"] is False
        assert context["version"] == "0.0.0-test"

    @pytest.mark.asyncio
    async def test_label_and_periodic_flow_lifecycle(self, tools):
        label = await tools.ok("save_label", name="Salary", category="INCOME")

        created = await tools.ok(
            "save_periodic_flow",
            name="Salary",
            amount="3000.50",
            currency="eur",
            flow_type="EARNING",
            frequency="MONTHLY",
            since="2025-01-01",
            label_id=label["id"],
        )
        flow_id = created["created"]

        await tools.ok("save_periodic_flow", flow_id=flow_id, amount=3200)
        flows = await tools.ok("list_periodic_flows")

        assert len(flows) == 1
        assert flows[0]["id"] == flow_id
        assert flows[0]["name"] == "Salary"
        assert flows[0]["amount"] == 3200
        assert flows[0]["currency"] == "EUR"
        assert flows[0]["label_id"] == label["id"]

        await tools.ok("delete_periodic_flow", flow_id=flow_id)
        assert await tools.ok("list_periodic_flows") == []

    @pytest.mark.asyncio
    async def test_label_update_keeps_other_fields(self, tools):
        label = await tools.ok("save_label", name="Groceries", color="#22c55e")

        updated = await tools.ok("save_label", label_id=label["id"], name="Food")

        assert updated["name"] == "Food"
        assert updated["color"] == "#22c55e"
        assert updated["category"] == "EXPENSE"

    @pytest.mark.asyncio
    async def test_errors_are_reported_to_the_model(self, tools):
        missing = await tools.error("save_periodic_flow", name="Rent")
        assert "Missing required fields" in missing

        not_found = await tools.error(
            "save_periodic_flow", flow_id=str(uuid4()), amount=10
        )
        assert "Flow not found" in not_found

        invalid = await tools.error(
            "save_periodic_flow",
            name="Rent",
            amount=-5,
            currency="EUR",
            flow_type="EXPENSE",
            frequency="MONTHLY",
            since="2025-01-01",
        )
        assert "amount" in invalid

    @pytest.mark.asyncio
    async def test_real_estate_partial_update(self, tools):
        created = await tools.ok(
            "save_real_estate",
            basic_info={"name": "Flat", "is_residence": True},
            purchase_info={"date": "2020-05-01", "price": "200000"},
            valuation_info={
                "valuations": [
                    {"date": "2024-01-01", "amount": "250000", "market_value": True}
                ]
            },
            currency="EUR",
        )

        await tools.ok(
            "save_real_estate",
            real_estate_id=created["created"],
            basic_info={"name": "Beach flat", "is_residence": False},
        )
        [real_estate] = await tools.ok("list_real_estate")

        assert real_estate["id"] == created["created"]
        assert real_estate["basic_info"]["name"] == "Beach flat"
        assert real_estate["purchase_info"]["price"] == 200000
        assert real_estate["valuation_info"]["estimated_market_value"] == 250000

    @pytest.mark.asyncio
    async def test_real_estate_requires_market_valuation(self, tools):
        error = await tools.error(
            "save_real_estate",
            basic_info={"name": "Flat"},
            purchase_info={"date": "2020-05-01", "price": "200000"},
            valuation_info={"valuations": [{"date": "2024-01-01", "amount": "250000"}]},
            currency="EUR",
        )

        assert "Invalid input" in error

    @pytest.mark.asyncio
    async def test_loan_calculation(self, tools):
        result = await tools.ok(
            "calculate_loan",
            interest_rate="0.03",
            interest_type="FIXED",
            start="2024-01-01",
            end="2049-01-01",
            loan_amount="200000",
        )

        assert 900 < result["current_installment_payment"] < 1000

    @pytest.mark.asyncio
    async def test_fetch_requests_two_factor_without_leaking_details(
        self, tools, mcp_env
    ):
        mcp_env.ucs.fetch_financial_data.execute.return_value = FetchResult(
            FetchResultCode.CODE_REQUESTED,
            details={"message": "SMS sent", "processId": "p-1", "secret": "x"},
            confirmation_type=LoginConfirmationType.CHALLENGE,
        )

        result = await tools.ok("fetch_entity_data", account_id=str(uuid4()))

        assert result["code"] == "CODE_REQUESTED"
        assert result["process_id"] == "p-1"
        assert "secret" not in json.dumps(result)
        assert "code they received" in result["next_step"]

    @pytest.mark.asyncio
    async def test_net_worth_aggregates_positions_and_real_estate(self, tools, mcp_env):
        for name, is_residence, value in (
            ("Home", True, "300000"),
            ("Flat", False, "150000"),
        ):
            await tools.ok(
                "save_real_estate",
                basic_info={"name": name, "is_residence": is_residence},
                purchase_info={"date": "2020-01-15", "price": "100000"},
                valuation_info={
                    "valuations": [
                        {"date": "2024-01-15", "amount": value, "market_value": True}
                    ]
                },
                currency="EUR",
            )
        account = SimpleNamespace(total=Dezimal("2500.5"), currency="EUR")
        mcp_env.position_port.get_last_by_entity_broken_down.return_value = {
            uuid4(): [
                SimpleNamespace(
                    products={ProductType.ACCOUNT: SimpleNamespace(entries=[account])}
                )
            ]
        }

        result = await tools.ok("get_net_worth")

        assert result["currency"] == "EUR"
        assert result["total"] == 452500.5
        assert result["breakdown"] == {
            "ACCOUNT": 2500.5,
            "REAL_ESTATE": 150000,
            "REAL_ESTATE_RESIDENCE": 300000,
        }
