from datetime import date, timedelta

import pytest

SIGNUP_URL = "/api/v1/signup"
PERIODIC_FLOWS_URL = "/api/v1/flows/periodic"
PENDING_FLOWS_URL = "/api/v1/flows/pending"
EVENTS_URL = "/api/v1/events"

USERNAME = "testuser"
PASSWORD = "securePass123"


async def _signup(client):
    response = await client.post(
        SIGNUP_URL, json={"username": USERNAME, "password": PASSWORD}
    )
    assert response.status_code == 204


def _periodic_flow_payload(**overrides):
    payload = {
        "name": "Monthly Salary",
        "amount": "3000",
        "currency": "EUR",
        "flow_type": "EARNING",
        "frequency": "MONTHLY",
        "category": "salary",
        "enabled": True,
        "since": "2025-01-01",
        "until": None,
        "icon": "briefcase",
    }
    payload.update(overrides)
    return payload


def _pending_flow_payload(**overrides):
    payload = {
        "name": "Tax Refund",
        "amount": "500",
        "currency": "EUR",
        "flow_type": "EARNING",
        "category": "taxes",
        "enabled": True,
        "date": "2026-06-01",
        "icon": "receipt",
    }
    payload.update(overrides)
    return payload


class TestSavePeriodicFlow:
    @pytest.mark.asyncio
    async def test_save_returns_201(self, client):
        await _signup(client)
        response = await client.post(PERIODIC_FLOWS_URL, json=_periodic_flow_payload())
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_save_appears_in_get(self, client):
        await _signup(client)
        await client.post(PERIODIC_FLOWS_URL, json=_periodic_flow_payload())

        response = await client.get(PERIODIC_FLOWS_URL)
        assert response.status_code == 200
        flows = await response.get_json()
        assert len(flows) == 1
        assert flows[0]["name"] == "Monthly Salary"
        assert float(flows[0]["amount"]) == 3000
        assert flows[0]["currency"] == "EUR"
        assert flows[0]["flow_type"] == "EARNING"
        assert flows[0]["frequency"] == "MONTHLY"
        assert flows[0]["category"] == "salary"
        assert flows[0]["enabled"] is True
        assert flows[0]["since"] == "2025-01-01"
        assert flows[0]["until"] is None
        assert flows[0]["icon"] == "briefcase"
        assert flows[0]["linked"] is False
        assert flows[0]["real_estate_flow"] is None

    @pytest.mark.asyncio
    async def test_save_multiple_flows(self, client):
        await _signup(client)
        await client.post(PERIODIC_FLOWS_URL, json=_periodic_flow_payload())
        await client.post(
            PERIODIC_FLOWS_URL,
            json=_periodic_flow_payload(
                name="Rent",
                amount="1200",
                flow_type="EXPENSE",
                frequency="MONTHLY",
                category="housing",
            ),
        )

        response = await client.get(PERIODIC_FLOWS_URL)
        flows = await response.get_json()
        assert len(flows) == 2
        names = {f["name"] for f in flows}
        assert names == {"Monthly Salary", "Rent"}

    @pytest.mark.asyncio
    async def test_save_with_until_date(self, client):
        await _signup(client)
        await client.post(
            PERIODIC_FLOWS_URL,
            json=_periodic_flow_payload(until="2027-12-31"),
        )

        response = await client.get(PERIODIC_FLOWS_URL)
        flows = await response.get_json()
        assert flows[0]["until"] == "2027-12-31"

    @pytest.mark.asyncio
    async def test_save_with_max_amount(self, client):
        await _signup(client)
        await client.post(
            PERIODIC_FLOWS_URL,
            json=_periodic_flow_payload(max_amount="5000"),
        )

        response = await client.get(PERIODIC_FLOWS_URL)
        flows = await response.get_json()
        assert float(flows[0]["max_amount"]) == 5000

    @pytest.mark.asyncio
    async def test_save_returns_400_on_missing_name(self, client):
        await _signup(client)
        payload = _periodic_flow_payload()
        del payload["name"]
        response = await client.post(PERIODIC_FLOWS_URL, json=payload)
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_save_returns_400_on_invalid_flow_type(self, client):
        await _signup(client)
        response = await client.post(
            PERIODIC_FLOWS_URL,
            json=_periodic_flow_payload(flow_type="INVALID"),
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_save_returns_400_on_invalid_frequency(self, client):
        await _signup(client)
        response = await client.post(
            PERIODIC_FLOWS_URL,
            json=_periodic_flow_payload(frequency="INVALID"),
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_save_disabled_flow(self, client):
        await _signup(client)
        await client.post(
            PERIODIC_FLOWS_URL,
            json=_periodic_flow_payload(enabled=False),
        )

        response = await client.get(PERIODIC_FLOWS_URL)
        flows = await response.get_json()
        assert flows[0]["enabled"] is False
        assert flows[0]["next_date"] is None

    @pytest.mark.asyncio
    async def test_save_all_frequencies(self, client):
        await _signup(client)
        frequencies = [
            "DAILY",
            "WEEKLY",
            "BIWEEKLY",
            "SEMIMONTHLY",
            "MONTHLY",
            "EVERY_TWO_MONTHS",
            "QUARTERLY",
            "EVERY_FOUR_MONTHS",
            "SEMIANNUALLY",
            "YEARLY",
        ]
        for freq in frequencies:
            response = await client.post(
                PERIODIC_FLOWS_URL,
                json=_periodic_flow_payload(name=f"Flow {freq}", frequency=freq),
            )
            assert response.status_code == 201

        response = await client.get(PERIODIC_FLOWS_URL)
        flows = await response.get_json()
        assert len(flows) == len(frequencies)


class TestGetPeriodicFlows:
    @pytest.mark.asyncio
    async def test_get_empty_list(self, client):
        await _signup(client)
        response = await client.get(PERIODIC_FLOWS_URL)
        assert response.status_code == 200
        flows = await response.get_json()
        assert flows == []

    @pytest.mark.asyncio
    async def test_get_returns_next_date_for_enabled_flow(self, client):
        await _signup(client)
        await client.post(
            PERIODIC_FLOWS_URL,
            json=_periodic_flow_payload(since="2025-01-01", frequency="MONTHLY"),
        )

        response = await client.get(PERIODIC_FLOWS_URL)
        flows = await response.get_json()
        assert flows[0]["next_date"] is not None

    @pytest.mark.asyncio
    async def test_get_returns_id(self, client):
        await _signup(client)
        await client.post(PERIODIC_FLOWS_URL, json=_periodic_flow_payload())

        response = await client.get(PERIODIC_FLOWS_URL)
        flows = await response.get_json()
        assert flows[0]["id"] is not None
        assert len(flows[0]["id"]) == 36


class TestUpdatePeriodicFlow:
    @pytest.mark.asyncio
    async def test_update_returns_204(self, client):
        await _signup(client)
        await client.post(PERIODIC_FLOWS_URL, json=_periodic_flow_payload())
        flows = await (await client.get(PERIODIC_FLOWS_URL)).get_json()
        flow_id = flows[0]["id"]

        response = await client.put(
            PERIODIC_FLOWS_URL,
            json=_periodic_flow_payload(id=flow_id, name="Updated Salary"),
        )
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_update_reflects_in_get(self, client):
        await _signup(client)
        await client.post(PERIODIC_FLOWS_URL, json=_periodic_flow_payload())
        flows = await (await client.get(PERIODIC_FLOWS_URL)).get_json()
        flow_id = flows[0]["id"]

        await client.put(
            PERIODIC_FLOWS_URL,
            json=_periodic_flow_payload(
                id=flow_id,
                name="Updated Salary",
                amount="3500",
                category="income",
                icon="money",
            ),
        )

        flows = await (await client.get(PERIODIC_FLOWS_URL)).get_json()
        assert len(flows) == 1
        assert flows[0]["name"] == "Updated Salary"
        assert float(flows[0]["amount"]) == 3500
        assert flows[0]["category"] == "income"
        assert flows[0]["icon"] == "money"

    @pytest.mark.asyncio
    async def test_update_flow_type(self, client):
        await _signup(client)
        await client.post(PERIODIC_FLOWS_URL, json=_periodic_flow_payload())
        flows = await (await client.get(PERIODIC_FLOWS_URL)).get_json()
        flow_id = flows[0]["id"]

        await client.put(
            PERIODIC_FLOWS_URL,
            json=_periodic_flow_payload(id=flow_id, flow_type="EXPENSE"),
        )

        flows = await (await client.get(PERIODIC_FLOWS_URL)).get_json()
        assert flows[0]["flow_type"] == "EXPENSE"

    @pytest.mark.asyncio
    async def test_update_frequency(self, client):
        await _signup(client)
        await client.post(PERIODIC_FLOWS_URL, json=_periodic_flow_payload())
        flows = await (await client.get(PERIODIC_FLOWS_URL)).get_json()
        flow_id = flows[0]["id"]

        await client.put(
            PERIODIC_FLOWS_URL,
            json=_periodic_flow_payload(id=flow_id, frequency="QUARTERLY"),
        )

        flows = await (await client.get(PERIODIC_FLOWS_URL)).get_json()
        assert flows[0]["frequency"] == "QUARTERLY"

    @pytest.mark.asyncio
    async def test_update_enable_disable(self, client):
        await _signup(client)
        await client.post(PERIODIC_FLOWS_URL, json=_periodic_flow_payload())
        flows = await (await client.get(PERIODIC_FLOWS_URL)).get_json()
        flow_id = flows[0]["id"]

        await client.put(
            PERIODIC_FLOWS_URL,
            json=_periodic_flow_payload(id=flow_id, enabled=False),
        )

        flows = await (await client.get(PERIODIC_FLOWS_URL)).get_json()
        assert flows[0]["enabled"] is False
        assert flows[0]["next_date"] is None

        await client.put(
            PERIODIC_FLOWS_URL,
            json=_periodic_flow_payload(id=flow_id, enabled=True),
        )

        flows = await (await client.get(PERIODIC_FLOWS_URL)).get_json()
        assert flows[0]["enabled"] is True
        assert flows[0]["next_date"] is not None

    @pytest.mark.asyncio
    async def test_update_until_date(self, client):
        await _signup(client)
        await client.post(PERIODIC_FLOWS_URL, json=_periodic_flow_payload())
        flows = await (await client.get(PERIODIC_FLOWS_URL)).get_json()
        flow_id = flows[0]["id"]

        await client.put(
            PERIODIC_FLOWS_URL,
            json=_periodic_flow_payload(id=flow_id, until="2027-06-30"),
        )

        flows = await (await client.get(PERIODIC_FLOWS_URL)).get_json()
        assert flows[0]["until"] == "2027-06-30"

    @pytest.mark.asyncio
    async def test_update_max_amount(self, client):
        await _signup(client)
        await client.post(PERIODIC_FLOWS_URL, json=_periodic_flow_payload())
        flows = await (await client.get(PERIODIC_FLOWS_URL)).get_json()
        flow_id = flows[0]["id"]

        await client.put(
            PERIODIC_FLOWS_URL,
            json=_periodic_flow_payload(id=flow_id, max_amount="6000"),
        )

        flows = await (await client.get(PERIODIC_FLOWS_URL)).get_json()
        assert flows[0]["max_amount"] is not None
        assert float(flows[0]["max_amount"]) == 6000

    @pytest.mark.asyncio
    async def test_update_returns_400_on_invalid_body(self, client):
        await _signup(client)
        response = await client.put(PERIODIC_FLOWS_URL, json={"name": "no id"})
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_update_does_not_affect_other_flows(self, client):
        await _signup(client)
        await client.post(PERIODIC_FLOWS_URL, json=_periodic_flow_payload())
        await client.post(
            PERIODIC_FLOWS_URL,
            json=_periodic_flow_payload(
                name="Rent", amount="1200", flow_type="EXPENSE"
            ),
        )

        flows = await (await client.get(PERIODIC_FLOWS_URL)).get_json()
        salary_flow = next(f for f in flows if f["name"] == "Monthly Salary")

        await client.put(
            PERIODIC_FLOWS_URL,
            json=_periodic_flow_payload(
                id=salary_flow["id"], name="Big Salary", amount="5000"
            ),
        )

        flows = await (await client.get(PERIODIC_FLOWS_URL)).get_json()
        updated = next(f for f in flows if f["id"] == salary_flow["id"])
        rent = next(f for f in flows if f["name"] == "Rent")
        assert updated["name"] == "Big Salary"
        assert float(updated["amount"]) == 5000
        assert float(rent["amount"]) == 1200


class TestDeletePeriodicFlow:
    @pytest.mark.asyncio
    async def test_delete_returns_204(self, client):
        await _signup(client)
        await client.post(PERIODIC_FLOWS_URL, json=_periodic_flow_payload())
        flows = await (await client.get(PERIODIC_FLOWS_URL)).get_json()
        flow_id = flows[0]["id"]

        response = await client.delete(f"{PERIODIC_FLOWS_URL}/{flow_id}")
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_removes_from_get(self, client):
        await _signup(client)
        await client.post(PERIODIC_FLOWS_URL, json=_periodic_flow_payload())
        flows = await (await client.get(PERIODIC_FLOWS_URL)).get_json()
        flow_id = flows[0]["id"]

        await client.delete(f"{PERIODIC_FLOWS_URL}/{flow_id}")

        flows = await (await client.get(PERIODIC_FLOWS_URL)).get_json()
        assert len(flows) == 0

    @pytest.mark.asyncio
    async def test_delete_only_target_flow(self, client):
        await _signup(client)
        await client.post(PERIODIC_FLOWS_URL, json=_periodic_flow_payload())
        await client.post(
            PERIODIC_FLOWS_URL,
            json=_periodic_flow_payload(name="Rent", flow_type="EXPENSE"),
        )

        flows = await (await client.get(PERIODIC_FLOWS_URL)).get_json()
        salary = next(f for f in flows if f["name"] == "Monthly Salary")

        await client.delete(f"{PERIODIC_FLOWS_URL}/{salary['id']}")

        flows = await (await client.get(PERIODIC_FLOWS_URL)).get_json()
        assert len(flows) == 1
        assert flows[0]["name"] == "Rent"

    @pytest.mark.asyncio
    async def test_delete_invalid_uuid_returns_400(self, client):
        await _signup(client)
        response = await client.delete(f"{PERIODIC_FLOWS_URL}/not-a-uuid")
        assert response.status_code == 400


class TestSavePendingFlows:
    @pytest.mark.asyncio
    async def test_save_returns_204(self, client):
        await _signup(client)
        response = await client.post(
            PENDING_FLOWS_URL,
            json={"flows": [_pending_flow_payload()]},
        )
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_save_appears_in_get(self, client):
        await _signup(client)
        await client.post(
            PENDING_FLOWS_URL,
            json={"flows": [_pending_flow_payload()]},
        )

        response = await client.get(PENDING_FLOWS_URL)
        assert response.status_code == 200
        flows = await response.get_json()
        assert len(flows) == 1
        assert flows[0]["name"] == "Tax Refund"
        assert float(flows[0]["amount"]) == 500
        assert flows[0]["currency"] == "EUR"
        assert flows[0]["flow_type"] == "EARNING"
        assert flows[0]["category"] == "taxes"
        assert flows[0]["enabled"] is True
        assert flows[0]["date"] == "2026-06-01"
        assert flows[0]["icon"] == "receipt"

    @pytest.mark.asyncio
    async def test_save_multiple_pending_flows(self, client):
        await _signup(client)
        await client.post(
            PENDING_FLOWS_URL,
            json={
                "flows": [
                    _pending_flow_payload(),
                    _pending_flow_payload(
                        name="Insurance Bill",
                        amount="200",
                        flow_type="EXPENSE",
                        category="insurance",
                    ),
                ]
            },
        )

        response = await client.get(PENDING_FLOWS_URL)
        flows = await response.get_json()
        assert len(flows) == 2
        names = {f["name"] for f in flows}
        assert names == {"Tax Refund", "Insurance Bill"}

    @pytest.mark.asyncio
    async def test_save_replaces_all_existing(self, client):
        await _signup(client)
        await client.post(
            PENDING_FLOWS_URL,
            json={"flows": [_pending_flow_payload()]},
        )
        flows = await (await client.get(PENDING_FLOWS_URL)).get_json()
        assert len(flows) == 1

        await client.post(
            PENDING_FLOWS_URL,
            json={
                "flows": [
                    _pending_flow_payload(name="New Flow A"),
                    _pending_flow_payload(name="New Flow B"),
                ]
            },
        )

        flows = await (await client.get(PENDING_FLOWS_URL)).get_json()
        assert len(flows) == 2
        names = {f["name"] for f in flows}
        assert names == {"New Flow A", "New Flow B"}

    @pytest.mark.asyncio
    async def test_save_empty_clears_all(self, client):
        await _signup(client)
        await client.post(
            PENDING_FLOWS_URL,
            json={"flows": [_pending_flow_payload()]},
        )
        flows = await (await client.get(PENDING_FLOWS_URL)).get_json()
        assert len(flows) == 1

        await client.post(PENDING_FLOWS_URL, json={"flows": []})

        flows = await (await client.get(PENDING_FLOWS_URL)).get_json()
        assert len(flows) == 0

    @pytest.mark.asyncio
    async def test_save_without_date(self, client):
        await _signup(client)
        await client.post(
            PENDING_FLOWS_URL,
            json={"flows": [_pending_flow_payload(date=None)]},
        )

        flows = await (await client.get(PENDING_FLOWS_URL)).get_json()
        assert flows[0]["date"] is None

    @pytest.mark.asyncio
    async def test_save_disabled_pending_flow(self, client):
        await _signup(client)
        await client.post(
            PENDING_FLOWS_URL,
            json={"flows": [_pending_flow_payload(enabled=False)]},
        )

        flows = await (await client.get(PENDING_FLOWS_URL)).get_json()
        assert flows[0]["enabled"] is False

    @pytest.mark.asyncio
    async def test_save_returns_400_on_missing_name(self, client):
        await _signup(client)
        flow = _pending_flow_payload()
        del flow["name"]
        response = await client.post(PENDING_FLOWS_URL, json={"flows": [flow]})
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_save_returns_400_on_invalid_flow_type(self, client):
        await _signup(client)
        response = await client.post(
            PENDING_FLOWS_URL,
            json={"flows": [_pending_flow_payload(flow_type="INVALID")]},
        )
        assert response.status_code == 400


class TestGetPendingFlows:
    @pytest.mark.asyncio
    async def test_get_empty_list(self, client):
        await _signup(client)
        response = await client.get(PENDING_FLOWS_URL)
        assert response.status_code == 200
        flows = await response.get_json()
        assert flows == []

    @pytest.mark.asyncio
    async def test_get_returns_id(self, client):
        await _signup(client)
        await client.post(
            PENDING_FLOWS_URL,
            json={"flows": [_pending_flow_payload()]},
        )

        flows = await (await client.get(PENDING_FLOWS_URL)).get_json()
        assert flows[0]["id"] is not None
        assert len(flows[0]["id"]) == 36


class TestGetMoneyEvents:
    @pytest.mark.asyncio
    async def test_returns_400_without_dates(self, client):
        await _signup(client)
        response = await client.get(EVENTS_URL)
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_400_with_invalid_date(self, client):
        await _signup(client)
        response = await client.get(f"{EVENTS_URL}?from_date=bad&to_date=also-bad")
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_400_when_from_after_to(self, client):
        await _signup(client)
        response = await client.get(
            f"{EVENTS_URL}?from_date=2026-12-01&to_date=2026-01-01"
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_empty_events(self, client):
        await _signup(client)
        response = await client.get(
            f"{EVENTS_URL}?from_date=2026-01-01&to_date=2026-12-31"
        )
        assert response.status_code == 200
        body = await response.get_json()
        assert body["events"] == []

    @pytest.mark.asyncio
    async def test_periodic_flow_appears_as_event(self, client):
        await _signup(client)
        await client.post(
            PERIODIC_FLOWS_URL,
            json=_periodic_flow_payload(
                since="2026-01-01",
                frequency="MONTHLY",
            ),
        )

        today = date.today()
        from_date = today.isoformat()
        to_date = (today + timedelta(days=365)).isoformat()

        response = await client.get(
            f"{EVENTS_URL}?from_date={from_date}&to_date={to_date}"
        )
        assert response.status_code == 200
        body = await response.get_json()
        periodic_events = [e for e in body["events"] if e["type"] == "PERIODIC_FLOW"]
        assert len(periodic_events) > 0
        assert periodic_events[0]["name"] == "Monthly Salary"
        assert periodic_events[0]["frequency"] == "MONTHLY"

    @pytest.mark.asyncio
    async def test_periodic_expense_has_negative_amount(self, client):
        await _signup(client)
        await client.post(
            PERIODIC_FLOWS_URL,
            json=_periodic_flow_payload(
                name="Rent",
                amount="1200",
                flow_type="EXPENSE",
                since="2026-01-01",
                frequency="MONTHLY",
            ),
        )

        today = date.today()
        from_date = today.isoformat()
        to_date = (today + timedelta(days=365)).isoformat()

        response = await client.get(
            f"{EVENTS_URL}?from_date={from_date}&to_date={to_date}"
        )
        body = await response.get_json()
        expense_events = [e for e in body["events"] if e["type"] == "PERIODIC_FLOW"]
        assert len(expense_events) > 0
        for event in expense_events:
            assert float(event["amount"]) < 0

    @pytest.mark.asyncio
    async def test_pending_flow_appears_as_event(self, client):
        await _signup(client)
        await client.post(
            PENDING_FLOWS_URL,
            json={"flows": [_pending_flow_payload(date="2026-06-15")]},
        )

        response = await client.get(
            f"{EVENTS_URL}?from_date=2026-01-01&to_date=2026-12-31"
        )
        body = await response.get_json()
        pending_events = [e for e in body["events"] if e["type"] == "PENDING_FLOW"]
        assert len(pending_events) == 1
        assert pending_events[0]["name"] == "Tax Refund"
        assert pending_events[0]["date"] == "2026-06-15"

    @pytest.mark.asyncio
    async def test_pending_flow_outside_range_not_included(self, client):
        await _signup(client)
        await client.post(
            PENDING_FLOWS_URL,
            json={"flows": [_pending_flow_payload(date="2027-06-15")]},
        )

        response = await client.get(
            f"{EVENTS_URL}?from_date=2026-01-01&to_date=2026-12-31"
        )
        body = await response.get_json()
        pending_events = [e for e in body["events"] if e["type"] == "PENDING_FLOW"]
        assert len(pending_events) == 0

    @pytest.mark.asyncio
    async def test_disabled_pending_flow_not_included(self, client):
        await _signup(client)
        await client.post(
            PENDING_FLOWS_URL,
            json={"flows": [_pending_flow_payload(date="2026-06-15", enabled=False)]},
        )

        response = await client.get(
            f"{EVENTS_URL}?from_date=2026-01-01&to_date=2026-12-31"
        )
        body = await response.get_json()
        pending_events = [e for e in body["events"] if e["type"] == "PENDING_FLOW"]
        assert len(pending_events) == 0

    @pytest.mark.asyncio
    async def test_pending_expense_has_negative_amount(self, client):
        await _signup(client)
        await client.post(
            PENDING_FLOWS_URL,
            json={
                "flows": [
                    _pending_flow_payload(
                        name="Car Repair",
                        amount="800",
                        flow_type="EXPENSE",
                        date="2026-06-15",
                    )
                ]
            },
        )

        response = await client.get(
            f"{EVENTS_URL}?from_date=2026-01-01&to_date=2026-12-31"
        )
        body = await response.get_json()
        pending_events = [e for e in body["events"] if e["type"] == "PENDING_FLOW"]
        assert len(pending_events) == 1
        assert float(pending_events[0]["amount"]) < 0

    @pytest.mark.asyncio
    async def test_events_reflect_updated_periodic_flow(self, client):
        await _signup(client)
        await client.post(
            PERIODIC_FLOWS_URL,
            json=_periodic_flow_payload(since="2026-01-01", frequency="MONTHLY"),
        )
        flows = await (await client.get(PERIODIC_FLOWS_URL)).get_json()
        flow_id = flows[0]["id"]

        await client.put(
            PERIODIC_FLOWS_URL,
            json=_periodic_flow_payload(
                id=flow_id,
                name="Updated Salary",
                amount="4000",
                since="2026-01-01",
                frequency="MONTHLY",
            ),
        )

        today = date.today()
        from_date = today.isoformat()
        to_date = (today + timedelta(days=365)).isoformat()

        response = await client.get(
            f"{EVENTS_URL}?from_date={from_date}&to_date={to_date}"
        )
        body = await response.get_json()
        periodic_events = [e for e in body["events"] if e["type"] == "PERIODIC_FLOW"]
        assert len(periodic_events) > 0
        assert periodic_events[0]["name"] == "Updated Salary"

    @pytest.mark.asyncio
    async def test_events_reflect_deleted_periodic_flow(self, client):
        await _signup(client)
        await client.post(
            PERIODIC_FLOWS_URL,
            json=_periodic_flow_payload(since="2026-01-01", frequency="MONTHLY"),
        )
        flows = await (await client.get(PERIODIC_FLOWS_URL)).get_json()
        flow_id = flows[0]["id"]

        await client.delete(f"{PERIODIC_FLOWS_URL}/{flow_id}")

        today = date.today()
        from_date = today.isoformat()
        to_date = (today + timedelta(days=365)).isoformat()

        response = await client.get(
            f"{EVENTS_URL}?from_date={from_date}&to_date={to_date}"
        )
        body = await response.get_json()
        periodic_events = [e for e in body["events"] if e["type"] == "PERIODIC_FLOW"]
        assert len(periodic_events) == 0

    @pytest.mark.asyncio
    async def test_events_reflect_replaced_pending_flows(self, client):
        await _signup(client)
        await client.post(
            PENDING_FLOWS_URL,
            json={"flows": [_pending_flow_payload(date="2026-06-15")]},
        )

        response = await client.get(
            f"{EVENTS_URL}?from_date=2026-01-01&to_date=2026-12-31"
        )
        body = await response.get_json()
        assert len([e for e in body["events"] if e["type"] == "PENDING_FLOW"]) == 1

        await client.post(
            PENDING_FLOWS_URL,
            json={
                "flows": [
                    _pending_flow_payload(name="New Pending A", date="2026-07-01"),
                    _pending_flow_payload(name="New Pending B", date="2026-08-01"),
                ]
            },
        )

        response = await client.get(
            f"{EVENTS_URL}?from_date=2026-01-01&to_date=2026-12-31"
        )
        body = await response.get_json()
        pending_events = [e for e in body["events"] if e["type"] == "PENDING_FLOW"]
        assert len(pending_events) == 2
        names = {e["name"] for e in pending_events}
        assert names == {"New Pending A", "New Pending B"}

    @pytest.mark.asyncio
    async def test_events_contain_icon(self, client):
        await _signup(client)
        await client.post(
            PERIODIC_FLOWS_URL,
            json=_periodic_flow_payload(
                since="2026-01-01", frequency="MONTHLY", icon="wallet"
            ),
        )

        today = date.today()
        from_date = today.isoformat()
        to_date = (today + timedelta(days=365)).isoformat()

        response = await client.get(
            f"{EVENTS_URL}?from_date={from_date}&to_date={to_date}"
        )
        body = await response.get_json()
        periodic_events = [e for e in body["events"] if e["type"] == "PERIODIC_FLOW"]
        assert periodic_events[0]["icon"] == "wallet"

    @pytest.mark.asyncio
    async def test_events_mixed_periodic_and_pending(self, client):
        await _signup(client)
        await client.post(
            PERIODIC_FLOWS_URL,
            json=_periodic_flow_payload(since="2026-01-01", frequency="MONTHLY"),
        )
        await client.post(
            PENDING_FLOWS_URL,
            json={"flows": [_pending_flow_payload(date="2026-06-15")]},
        )

        today = date.today()
        from_date = today.isoformat()
        to_date = (today + timedelta(days=365)).isoformat()

        response = await client.get(
            f"{EVENTS_URL}?from_date={from_date}&to_date={to_date}"
        )
        body = await response.get_json()
        types = {e["type"] for e in body["events"]}
        assert "PERIODIC_FLOW" in types
        assert "PENDING_FLOW" in types

    @pytest.mark.asyncio
    async def test_disabled_periodic_flow_no_events(self, client):
        await _signup(client)
        await client.post(
            PERIODIC_FLOWS_URL,
            json=_periodic_flow_payload(
                since="2026-01-01", frequency="MONTHLY", enabled=False
            ),
        )

        today = date.today()
        from_date = today.isoformat()
        to_date = (today + timedelta(days=365)).isoformat()

        response = await client.get(
            f"{EVENTS_URL}?from_date={from_date}&to_date={to_date}"
        )
        body = await response.get_json()
        periodic_events = [e for e in body["events"] if e["type"] == "PERIODIC_FLOW"]
        assert len(periodic_events) == 0


class TestPeriodicFlowLifecycle:
    @pytest.mark.asyncio
    async def test_full_crud_lifecycle(self, client):
        await _signup(client)

        create_resp = await client.post(
            PERIODIC_FLOWS_URL, json=_periodic_flow_payload()
        )
        assert create_resp.status_code == 201

        flows = await (await client.get(PERIODIC_FLOWS_URL)).get_json()
        assert len(flows) == 1
        flow_id = flows[0]["id"]

        update_resp = await client.put(
            PERIODIC_FLOWS_URL,
            json=_periodic_flow_payload(
                id=flow_id,
                name="Updated",
                amount="4000",
                frequency="QUARTERLY",
                enabled=False,
            ),
        )
        assert update_resp.status_code == 204

        flows = await (await client.get(PERIODIC_FLOWS_URL)).get_json()
        assert len(flows) == 1
        assert flows[0]["name"] == "Updated"
        assert float(flows[0]["amount"]) == 4000
        assert flows[0]["frequency"] == "QUARTERLY"
        assert flows[0]["enabled"] is False

        delete_resp = await client.delete(f"{PERIODIC_FLOWS_URL}/{flow_id}")
        assert delete_resp.status_code == 204

        flows = await (await client.get(PERIODIC_FLOWS_URL)).get_json()
        assert len(flows) == 0

    @pytest.mark.asyncio
    async def test_events_track_lifecycle(self, client):
        await _signup(client)

        today = date.today()
        from_date = today.isoformat()
        to_date = (today + timedelta(days=365)).isoformat()

        response = await client.get(
            f"{EVENTS_URL}?from_date={from_date}&to_date={to_date}"
        )
        body = await response.get_json()
        assert body["events"] == []

        await client.post(
            PERIODIC_FLOWS_URL,
            json=_periodic_flow_payload(since="2026-01-01", frequency="MONTHLY"),
        )

        response = await client.get(
            f"{EVENTS_URL}?from_date={from_date}&to_date={to_date}"
        )
        body = await response.get_json()
        periodic_count = len(
            [e for e in body["events"] if e["type"] == "PERIODIC_FLOW"]
        )
        assert periodic_count > 0

        flows = await (await client.get(PERIODIC_FLOWS_URL)).get_json()
        flow_id = flows[0]["id"]
        await client.put(
            PERIODIC_FLOWS_URL,
            json=_periodic_flow_payload(
                id=flow_id, name="Changed", since="2026-01-01", frequency="MONTHLY"
            ),
        )

        response = await client.get(
            f"{EVENTS_URL}?from_date={from_date}&to_date={to_date}"
        )
        body = await response.get_json()
        periodic_events = [e for e in body["events"] if e["type"] == "PERIODIC_FLOW"]
        assert all(e["name"] == "Changed" for e in periodic_events)

        await client.delete(f"{PERIODIC_FLOWS_URL}/{flow_id}")

        response = await client.get(
            f"{EVENTS_URL}?from_date={from_date}&to_date={to_date}"
        )
        body = await response.get_json()
        periodic_events = [e for e in body["events"] if e["type"] == "PERIODIC_FLOW"]
        assert len(periodic_events) == 0


class TestPendingFlowLifecycle:
    @pytest.mark.asyncio
    async def test_save_replace_cycle(self, client):
        await _signup(client)

        await client.post(
            PENDING_FLOWS_URL,
            json={"flows": [_pending_flow_payload(name="First")]},
        )
        flows = await (await client.get(PENDING_FLOWS_URL)).get_json()
        assert len(flows) == 1
        assert flows[0]["name"] == "First"

        await client.post(
            PENDING_FLOWS_URL,
            json={
                "flows": [
                    _pending_flow_payload(name="Second"),
                    _pending_flow_payload(name="Third"),
                ]
            },
        )
        flows = await (await client.get(PENDING_FLOWS_URL)).get_json()
        assert len(flows) == 2
        names = {f["name"] for f in flows}
        assert "First" not in names
        assert names == {"Second", "Third"}

        await client.post(PENDING_FLOWS_URL, json={"flows": []})
        flows = await (await client.get(PENDING_FLOWS_URL)).get_json()
        assert len(flows) == 0

    @pytest.mark.asyncio
    async def test_events_track_pending_lifecycle(self, client):
        await _signup(client)

        await client.post(
            PENDING_FLOWS_URL,
            json={"flows": [_pending_flow_payload(date="2026-06-15")]},
        )

        response = await client.get(
            f"{EVENTS_URL}?from_date=2026-01-01&to_date=2026-12-31"
        )
        body = await response.get_json()
        assert len([e for e in body["events"] if e["type"] == "PENDING_FLOW"]) == 1

        await client.post(PENDING_FLOWS_URL, json={"flows": []})

        response = await client.get(
            f"{EVENTS_URL}?from_date=2026-01-01&to_date=2026-12-31"
        )
        body = await response.get_json()
        assert len([e for e in body["events"] if e["type"] == "PENDING_FLOW"]) == 0
