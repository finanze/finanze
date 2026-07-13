from uuid import uuid4

import pytest

from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType
from domain.fetch_record import DataSource
from domain.global_position import (
    Account,
    Accounts,
    AccountType,
    GlobalPosition,
    ProductType,
)

SIGNUP_URL = "/api/v1/signup"
PENDING_FLOWS_URL = "/api/v1/flows/pending"
SETTLE_URL = "/api/v1/flows/pending/settle"

USERNAME = "testuser"
PASSWORD = "securePass123"


async def _signup(client):
    response = await client.post(
        SIGNUP_URL, json={"username": USERNAME, "password": PASSWORD}
    )
    assert response.status_code == 204


def _pending_flow_payload(**overrides):
    payload = {
        "name": "Tax Refund",
        "amount": "100",
        "currency": "EUR",
        "flow_type": "EARNING",
        "category": "taxes",
        "status": "ACTIVE",
        "date": None,
        "icon": "receipt",
    }
    payload.update(overrides)
    return payload


def _make_entity():
    return Entity(
        id=uuid4(),
        name="Manual",
        natural_id=None,
        type=EntityType.FINANCIAL_INSTITUTION,
        origin=EntityOrigin.MANUAL,
        icon_url=None,
    )


def _make_position(entity, account):
    return GlobalPosition(
        id=uuid4(),
        entity=entity,
        products={ProductType.ACCOUNT: Accounts(entries=[account])},
    )


def _make_account(total=Dezimal(1000)):
    return Account(
        id=uuid4(),
        total=total,
        currency="EUR",
        type=AccountType.CHECKING,
        name="Main",
        iban="ES0000000000000000001234",
        source=DataSource.MANUAL,
    )


async def _create_flow(client, **overrides):
    await client.post(PENDING_FLOWS_URL, json=_pending_flow_payload(**overrides))
    flows = (await (await client.get(PENDING_FLOWS_URL)).get_json())["entries"]
    return flows[0]


class TestSettlePendingFlow:
    @pytest.mark.asyncio
    async def test_earning_settles_and_completes(
        self, client, position_port, virtual_import_registry
    ):
        await _signup(client)
        flow = await _create_flow(client, amount="100", flow_type="EARNING")

        entity = _make_entity()
        account = _make_account(total=Dezimal(1000))
        position = _make_position(entity, account)
        position_port.get_last_grouped_by_entity.return_value = {entity: position}
        virtual_import_registry.get_last_import_records.return_value = []

        response = await client.post(
            SETTLE_URL,
            json={"flow_id": flow["id"], "account_id": str(account.id)},
        )
        assert response.status_code == 204

        assert account.total == Dezimal(1100)
        position_port.save.assert_awaited()

        flows = (await (await client.get(PENDING_FLOWS_URL)).get_json())["entries"]
        settled = next(f for f in flows if f["id"] == flow["id"])
        assert settled["status"] == "COMPLETED"

    @pytest.mark.asyncio
    async def test_expense_subtracts(
        self, client, position_port, virtual_import_registry
    ):
        await _signup(client)
        flow = await _create_flow(client, amount="250", flow_type="EXPENSE")

        entity = _make_entity()
        account = _make_account(total=Dezimal(1000))
        position = _make_position(entity, account)
        position_port.get_last_grouped_by_entity.return_value = {entity: position}
        virtual_import_registry.get_last_import_records.return_value = []

        response = await client.post(
            SETTLE_URL,
            json={"flow_id": flow["id"], "account_id": str(account.id)},
        )
        assert response.status_code == 204
        assert account.total == Dezimal(750)

    @pytest.mark.asyncio
    async def test_flow_not_found_returns_404(self, client, position_port):
        await _signup(client)
        entity = _make_entity()
        account = _make_account()
        position_port.get_last_grouped_by_entity.return_value = {
            entity: _make_position(entity, account)
        }

        response = await client.post(
            SETTLE_URL,
            json={
                "flow_id": "00000000-0000-0000-0000-000000000000",
                "account_id": str(account.id),
            },
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_account_not_found_returns_404(self, client, position_port):
        await _signup(client)
        flow = await _create_flow(client)
        position_port.get_last_grouped_by_entity.return_value = {}

        response = await client.post(
            SETTLE_URL,
            json={"flow_id": flow["id"], "account_id": str(uuid4())},
        )
        assert response.status_code == 404
