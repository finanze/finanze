import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from domain.auto_contributions import (
    AutoContributions,
    ContributionFrequency,
    ContributionTargetSubtype,
    ContributionTargetType,
    PeriodicContribution,
)
from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType
from domain.fetch_record import DataSource

CONTRIBUTIONS_URL = "/api/v1/data/manual/contributions"
GET_CONTRIBUTIONS_URL = "/api/v1/contributions"
EVENTS_URL = "/api/v1/events"
SIGNUP_URL = "/api/v1/signup"
ENTITY_ID = "e0000000-0000-0000-0000-000000000001"
ENTITY_ID_2 = "e0000000-0000-0000-0000-000000000002"
REAL_ENTITY_ID = "e0000000-0000-0000-0000-000000000099"

USERNAME = "testuser"
PASSWORD = "securePass123"


async def _signup(client):
    response = await client.post(
        SIGNUP_URL, json={"username": USERNAME, "password": PASSWORD}
    )
    assert response.status_code == 204


def _make_entity(entity_id=ENTITY_ID, name="Test Entity", origin=EntityOrigin.MANUAL):
    return Entity(
        id=uuid.UUID(entity_id),
        name=name,
        natural_id=None,
        type=EntityType.FINANCIAL_INSTITUTION,
        origin=origin,
        icon_url=None,
    )


def _contribution_entry(**overrides):
    base = {
        "entity_id": ENTITY_ID,
        "name": "Monthly ACME",
        "target": "ACME",
        "target_name": "ACME Corp",
        "target_type": "STOCK_ETF",
        "amount": "200.00",
        "currency": "EUR",
        "since": "2025-01-01",
        "until": None,
        "frequency": "MONTHLY",
    }
    base.update(overrides)
    return base


def _make_real_contribution(entity):
    return PeriodicContribution(
        id=uuid.uuid4(),
        alias="Real DCA",
        target="MSFT",
        target_name="Microsoft",
        target_type=ContributionTargetType.STOCK_ETF,
        amount=Dezimal("500"),
        currency="EUR",
        since=date(2024, 1, 1),
        until=None,
        frequency=ContributionFrequency.MONTHLY,
        active=True,
        source=DataSource.REAL,
    )


class TestUpdateContributionsValidation:
    @pytest.mark.asyncio
    async def test_missing_entries(self, client):
        response = await client.post(CONTRIBUTIONS_URL, json={})
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_invalid_entity_id(self, client):
        entry = _contribution_entry(entity_id="not-a-uuid")
        response = await client.post(CONTRIBUTIONS_URL, json={"entries": [entry]})
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_invalid_target_type(self, client):
        entry = _contribution_entry(target_type="INVALID")
        response = await client.post(CONTRIBUTIONS_URL, json={"entries": [entry]})
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_invalid_frequency(self, client):
        entry = _contribution_entry(frequency="DAILY")
        response = await client.post(CONTRIBUTIONS_URL, json={"entries": [entry]})
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_missing_required_field(self, client):
        entry = {"entity_id": ENTITY_ID, "name": "Test"}
        response = await client.post(CONTRIBUTIONS_URL, json={"entries": [entry]})
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_invalid_since_date(self, client):
        entry = _contribution_entry(since="not-a-date")
        response = await client.post(CONTRIBUTIONS_URL, json={"entries": [entry]})
        assert response.status_code == 400


class TestUpdateContributionsEntityNotFound:
    @pytest.mark.asyncio
    async def test_entity_not_found(self, client, entity_port, auto_contr_port):
        entity_port.get_by_id = AsyncMock(return_value=None)

        entry = _contribution_entry()
        response = await client.post(CONTRIBUTIONS_URL, json={"entries": [entry]})
        assert response.status_code == 404
        body = await response.get_json()
        assert body["code"] == "ENTITY_NOT_FOUND"


class TestAddSingleContributionAndRead:
    @pytest.mark.asyncio
    async def test_single_contribution_then_read_it(
        self,
        client,
        entity_port,
        auto_contr_port,
        virtual_import_registry,
    ):
        entity = _make_entity()
        entity_port.get_by_id = AsyncMock(return_value=entity)
        virtual_import_registry.get_last_import_records = AsyncMock(return_value=[])

        entry = _contribution_entry()
        response = await client.post(CONTRIBUTIONS_URL, json={"entries": [entry]})
        assert response.status_code == 204

        auto_contr_port.delete_by_source.assert_awaited_once_with(DataSource.MANUAL)
        auto_contr_port.save.assert_awaited_once()

        save_args = auto_contr_port.save.await_args
        assert save_args[0][0] == uuid.UUID(ENTITY_ID)
        saved_contribs = save_args[0][1]
        assert len(saved_contribs.periodic) == 1
        assert saved_contribs.periodic[0].alias == "Monthly ACME"
        assert saved_contribs.periodic[0].target == "ACME"
        assert saved_contribs.periodic[0].source == DataSource.MANUAL

        # Read back via GET /contributions
        auto_contr_port.get_all_grouped_by_entity = AsyncMock(
            return_value={entity: saved_contribs}
        )
        get_resp = await client.get(GET_CONTRIBUTIONS_URL)
        assert get_resp.status_code == 200
        body = await get_resp.get_json()

        assert ENTITY_ID in body
        periodic = body[ENTITY_ID]["periodic"]
        assert len(periodic) == 1
        assert periodic[0]["alias"] == "Monthly ACME"
        assert periodic[0]["target"] == "ACME"
        assert periodic[0]["target_name"] == "ACME Corp"
        assert periodic[0]["source"] == "MANUAL"
        assert periodic[0]["amount"] == 200.0
        assert periodic[0]["currency"] == "EUR"
        assert periodic[0]["frequency"] == "MONTHLY"
        assert periodic[0]["active"] is True


class TestAddMultipleContributionsAndRead:
    @pytest.mark.asyncio
    async def test_multiple_contributions_same_entity_then_read(
        self,
        client,
        entity_port,
        auto_contr_port,
        virtual_import_registry,
    ):
        entity = _make_entity()
        entity_port.get_by_id = AsyncMock(return_value=entity)
        virtual_import_registry.get_last_import_records = AsyncMock(return_value=[])

        entries = [
            _contribution_entry(name="Monthly ACME", target="ACME"),
            _contribution_entry(
                name="Monthly BETA",
                target="BETA",
                target_name="Beta Corp",
                amount="300.00",
            ),
        ]
        response = await client.post(CONTRIBUTIONS_URL, json={"entries": entries})
        assert response.status_code == 204

        auto_contr_port.save.assert_awaited_once()
        saved_contribs = auto_contr_port.save.await_args[0][1]
        assert len(saved_contribs.periodic) == 2

        # Read back
        auto_contr_port.get_all_grouped_by_entity = AsyncMock(
            return_value={entity: saved_contribs}
        )
        get_resp = await client.get(GET_CONTRIBUTIONS_URL)
        assert get_resp.status_code == 200
        body = await get_resp.get_json()

        periodic = body[ENTITY_ID]["periodic"]
        assert len(periodic) == 2
        aliases = {p["alias"] for p in periodic}
        assert aliases == {"Monthly ACME", "Monthly BETA"}

    @pytest.mark.asyncio
    async def test_contributions_multiple_entities_then_read(
        self,
        client,
        entity_port,
        auto_contr_port,
        virtual_import_registry,
    ):
        entity1 = _make_entity(ENTITY_ID, "Entity 1")
        entity2 = _make_entity(ENTITY_ID_2, "Entity 2")

        async def get_entity(eid):
            if str(eid) == ENTITY_ID:
                return entity1
            if str(eid) == ENTITY_ID_2:
                return entity2
            return None

        entity_port.get_by_id = AsyncMock(side_effect=get_entity)
        virtual_import_registry.get_last_import_records = AsyncMock(return_value=[])

        entries = [
            _contribution_entry(entity_id=ENTITY_ID, target="ACME"),
            _contribution_entry(entity_id=ENTITY_ID_2, target="BETA"),
        ]
        response = await client.post(CONTRIBUTIONS_URL, json={"entries": entries})
        assert response.status_code == 204

        assert auto_contr_port.save.await_count == 2

        # Capture saved contributions per entity
        saved_entity1 = auto_contr_port.save.await_args_list[0][0][1]
        saved_entity2 = auto_contr_port.save.await_args_list[1][0][1]

        # Read back — both entities visible
        auto_contr_port.get_all_grouped_by_entity = AsyncMock(
            return_value={entity1: saved_entity1, entity2: saved_entity2}
        )
        get_resp = await client.get(GET_CONTRIBUTIONS_URL)
        assert get_resp.status_code == 200
        body = await get_resp.get_json()

        assert ENTITY_ID in body
        assert ENTITY_ID_2 in body
        assert len(body[ENTITY_ID]["periodic"]) == 1
        assert body[ENTITY_ID]["periodic"][0]["target"] == "ACME"
        assert len(body[ENTITY_ID_2]["periodic"]) == 1
        assert body[ENTITY_ID_2]["periodic"][0]["target"] == "BETA"


class TestCoexistenceWithRealContributions:
    @pytest.mark.asyncio
    async def test_manual_and_real_contributions_both_returned(
        self,
        client,
        entity_port,
        auto_contr_port,
        virtual_import_registry,
    ):
        manual_entity = _make_entity()
        real_entity = _make_entity(REAL_ENTITY_ID, "Real Bank", EntityOrigin.NATIVE)

        entity_port.get_by_id = AsyncMock(return_value=manual_entity)
        virtual_import_registry.get_last_import_records = AsyncMock(return_value=[])

        entry = _contribution_entry()
        response = await client.post(CONTRIBUTIONS_URL, json={"entries": [entry]})
        assert response.status_code == 204

        saved_manual = auto_contr_port.save.await_args[0][1]
        real_contrib = _make_real_contribution(real_entity)

        # GET returns both manual and real entities' contributions
        auto_contr_port.get_all_grouped_by_entity = AsyncMock(
            return_value={
                manual_entity: saved_manual,
                real_entity: AutoContributions(periodic=[real_contrib]),
            }
        )
        get_resp = await client.get(GET_CONTRIBUTIONS_URL)
        assert get_resp.status_code == 200
        body = await get_resp.get_json()

        assert ENTITY_ID in body
        assert REAL_ENTITY_ID in body

        manual_periodic = body[ENTITY_ID]["periodic"]
        assert len(manual_periodic) == 1
        assert manual_periodic[0]["source"] == "MANUAL"
        assert manual_periodic[0]["alias"] == "Monthly ACME"

        real_periodic = body[REAL_ENTITY_ID]["periodic"]
        assert len(real_periodic) == 1
        assert real_periodic[0]["source"] == "REAL"
        assert real_periodic[0]["alias"] == "Real DCA"
        assert real_periodic[0]["target"] == "MSFT"
        assert real_periodic[0]["amount"] == 500.0

    @pytest.mark.asyncio
    async def test_real_and_manual_contributions_same_entity(
        self,
        client,
        entity_port,
        auto_contr_port,
        virtual_import_registry,
    ):
        entity = _make_entity()
        entity_port.get_by_id = AsyncMock(return_value=entity)
        virtual_import_registry.get_last_import_records = AsyncMock(return_value=[])

        entry = _contribution_entry()
        response = await client.post(CONTRIBUTIONS_URL, json={"entries": [entry]})
        assert response.status_code == 204

        saved_manual = auto_contr_port.save.await_args[0][1]
        real_contrib = _make_real_contribution(entity)

        # Same entity has both real and manual contributions
        combined = AutoContributions(periodic=saved_manual.periodic + [real_contrib])
        auto_contr_port.get_all_grouped_by_entity = AsyncMock(
            return_value={entity: combined}
        )
        get_resp = await client.get(GET_CONTRIBUTIONS_URL)
        assert get_resp.status_code == 200
        body = await get_resp.get_json()

        periodic = body[ENTITY_ID]["periodic"]
        assert len(periodic) == 2
        sources = {p["source"] for p in periodic}
        assert sources == {"MANUAL", "REAL"}


class TestEmptyContributionsAndRead:
    @pytest.mark.asyncio
    async def test_empty_contributions_clears_manual_real_still_visible(
        self,
        client,
        auto_contr_port,
        virtual_import_registry,
    ):
        virtual_import_registry.get_last_import_records = AsyncMock(return_value=[])

        response = await client.post(CONTRIBUTIONS_URL, json={"entries": []})
        assert response.status_code == 204

        auto_contr_port.delete_by_source.assert_awaited_once_with(DataSource.MANUAL)
        auto_contr_port.save.assert_not_awaited()

        # After clearing manual, GET returns only real contributions
        real_entity = _make_entity(REAL_ENTITY_ID, "Real Bank", EntityOrigin.NATIVE)
        real_contrib = _make_real_contribution(real_entity)

        auto_contr_port.get_all_grouped_by_entity = AsyncMock(
            return_value={real_entity: AutoContributions(periodic=[real_contrib])}
        )
        get_resp = await client.get(GET_CONTRIBUTIONS_URL)
        assert get_resp.status_code == 200
        body = await get_resp.get_json()

        assert ENTITY_ID not in body
        assert REAL_ENTITY_ID in body
        real_periodic = body[REAL_ENTITY_ID]["periodic"]
        assert len(real_periodic) == 1
        assert real_periodic[0]["source"] == "REAL"


class TestContributionFields:
    @pytest.mark.asyncio
    async def test_contribution_with_until_date(
        self,
        client,
        entity_port,
        auto_contr_port,
        virtual_import_registry,
    ):
        entity = _make_entity()
        entity_port.get_by_id = AsyncMock(return_value=entity)
        virtual_import_registry.get_last_import_records = AsyncMock(return_value=[])

        entry = _contribution_entry(until="2026-12-31")
        response = await client.post(CONTRIBUTIONS_URL, json={"entries": [entry]})
        assert response.status_code == 204

        saved_contribs = auto_contr_port.save.await_args[0][1]
        assert saved_contribs.periodic[0].until == date(2026, 12, 31)

        # Read back to verify until field in response
        auto_contr_port.get_all_grouped_by_entity = AsyncMock(
            return_value={entity: saved_contribs}
        )
        get_resp = await client.get(GET_CONTRIBUTIONS_URL)
        assert get_resp.status_code == 200
        body = await get_resp.get_json()

        periodic = body[ENTITY_ID]["periodic"]
        assert periodic[0]["until"] == "2026-12-31"

    @pytest.mark.asyncio
    async def test_contribution_with_target_subtype(
        self,
        client,
        entity_port,
        auto_contr_port,
        virtual_import_registry,
    ):
        entity = _make_entity()
        entity_port.get_by_id = AsyncMock(return_value=entity)
        virtual_import_registry.get_last_import_records = AsyncMock(return_value=[])

        entry = _contribution_entry(target_subtype="ETF")
        response = await client.post(CONTRIBUTIONS_URL, json={"entries": [entry]})
        assert response.status_code == 204

        saved_contribs = auto_contr_port.save.await_args[0][1]
        assert (
            saved_contribs.periodic[0].target_subtype == ContributionTargetSubtype.ETF
        )

        # Read back to verify subtype
        auto_contr_port.get_all_grouped_by_entity = AsyncMock(
            return_value={entity: saved_contribs}
        )
        get_resp = await client.get(GET_CONTRIBUTIONS_URL)
        assert get_resp.status_code == 200
        body = await get_resp.get_json()

        periodic = body[ENTITY_ID]["periodic"]
        assert periodic[0]["target_subtype"] == "ETF"

    @pytest.mark.asyncio
    async def test_crypto_target_type(
        self,
        client,
        entity_port,
        auto_contr_port,
        virtual_import_registry,
    ):
        entity = _make_entity()
        entity_port.get_by_id = AsyncMock(return_value=entity)
        virtual_import_registry.get_last_import_records = AsyncMock(return_value=[])

        entry = _contribution_entry(
            target_type="CRYPTO", target="BTC", target_name="Bitcoin"
        )
        response = await client.post(CONTRIBUTIONS_URL, json={"entries": [entry]})
        assert response.status_code == 204

        saved_contribs = auto_contr_port.save.await_args[0][1]
        assert saved_contribs.periodic[0].target_type == ContributionTargetType.CRYPTO

        # Read back to verify target_type
        auto_contr_port.get_all_grouped_by_entity = AsyncMock(
            return_value={entity: saved_contribs}
        )
        get_resp = await client.get(GET_CONTRIBUTIONS_URL)
        assert get_resp.status_code == 200
        body = await get_resp.get_json()

        periodic = body[ENTITY_ID]["periodic"]
        assert periodic[0]["target_type"] == "CRYPTO"
        assert periodic[0]["target"] == "BTC"
        assert periodic[0]["target_name"] == "Bitcoin"

    @pytest.mark.asyncio
    async def test_all_frequency_types(
        self,
        client,
        entity_port,
        auto_contr_port,
        virtual_import_registry,
    ):
        entity_port.get_by_id = AsyncMock(return_value=_make_entity())
        virtual_import_registry.get_last_import_records = AsyncMock(return_value=[])

        for freq in ["WEEKLY", "MONTHLY", "YEARLY", "QUARTERLY"]:
            auto_contr_port.reset_mock()
            entry = _contribution_entry(frequency=freq)
            response = await client.post(CONTRIBUTIONS_URL, json={"entries": [entry]})
            assert response.status_code == 204, f"Failed for frequency {freq}"


class TestSameDayUpdate:
    @pytest.mark.asyncio
    async def test_same_day_update_reuses_import_id(
        self,
        client,
        entity_port,
        auto_contr_port,
        virtual_import_registry,
    ):
        entity_port.get_by_id = AsyncMock(return_value=_make_entity())

        existing_import = MagicMock()
        existing_import.import_id = uuid.uuid4()
        from datetime import datetime
        from dateutil.tz import tzlocal

        existing_import.date = datetime.now(tzlocal())
        existing_import.feature = MagicMock()

        virtual_import_registry.get_last_import_records = AsyncMock(
            return_value=[existing_import]
        )

        entry = _contribution_entry()
        response = await client.post(CONTRIBUTIONS_URL, json={"entries": [entry]})
        assert response.status_code == 204

        virtual_import_registry.delete_by_import_and_feature.assert_awaited_once()


class TestContributionEventsIntegration:
    @pytest.mark.asyncio
    async def test_contribution_appears_as_event(
        self,
        client,
        entity_port,
        auto_contr_port,
        virtual_import_registry,
    ):
        await _signup(client)
        entity = _make_entity()
        entity_port.get_by_id = AsyncMock(return_value=entity)
        virtual_import_registry.get_last_import_records = AsyncMock(return_value=[])

        entry = _contribution_entry(since="2026-01-01", frequency="MONTHLY")
        response = await client.post(CONTRIBUTIONS_URL, json={"entries": [entry]})
        assert response.status_code == 204

        saved_contribs = auto_contr_port.save.await_args[0][1]
        auto_contr_port.get_all_grouped_by_entity = AsyncMock(
            return_value={entity: saved_contribs}
        )

        response = await client.get(
            f"{EVENTS_URL}?from_date=2026-04-01&to_date=2027-04-01"
        )
        assert response.status_code == 200
        body = await response.get_json()
        contrib_events = [e for e in body["events"] if e["type"] == "CONTRIBUTION"]
        assert len(contrib_events) > 0
        assert contrib_events[0]["name"] == "Monthly ACME"
        assert contrib_events[0]["frequency"] == "MONTHLY"
        assert float(contrib_events[0]["amount"]) == 200.0
        assert contrib_events[0]["currency"] == "EUR"

    @pytest.mark.asyncio
    async def test_contribution_event_contains_details(
        self,
        client,
        entity_port,
        auto_contr_port,
        virtual_import_registry,
    ):
        await _signup(client)
        entity = _make_entity()
        entity_port.get_by_id = AsyncMock(return_value=entity)
        virtual_import_registry.get_last_import_records = AsyncMock(return_value=[])

        entry = _contribution_entry(
            since="2026-01-01",
            frequency="MONTHLY",
            target_type="STOCK_ETF",
            target_subtype="ETF",
            target="ACME",
            target_name="ACME Corp",
        )
        response = await client.post(CONTRIBUTIONS_URL, json={"entries": [entry]})
        assert response.status_code == 204

        saved_contribs = auto_contr_port.save.await_args[0][1]
        auto_contr_port.get_all_grouped_by_entity = AsyncMock(
            return_value={entity: saved_contribs}
        )

        response = await client.get(
            f"{EVENTS_URL}?from_date=2026-04-01&to_date=2027-04-01"
        )
        body = await response.get_json()
        contrib_events = [e for e in body["events"] if e["type"] == "CONTRIBUTION"]
        assert len(contrib_events) > 0
        details = contrib_events[0]["details"]
        assert details is not None
        assert details["target_type"] == "STOCK_ETF"
        assert details["target_subtype"] == "ETF"
        assert details["target"] == "ACME"
        assert details["target_name"] == "ACME Corp"

    @pytest.mark.asyncio
    async def test_contribution_generates_multiple_monthly_events(
        self,
        client,
        entity_port,
        auto_contr_port,
        virtual_import_registry,
    ):
        await _signup(client)
        entity = _make_entity()
        entity_port.get_by_id = AsyncMock(return_value=entity)
        virtual_import_registry.get_last_import_records = AsyncMock(return_value=[])

        entry = _contribution_entry(since="2026-01-01", frequency="MONTHLY")
        response = await client.post(CONTRIBUTIONS_URL, json={"entries": [entry]})
        assert response.status_code == 204

        saved_contribs = auto_contr_port.save.await_args[0][1]
        auto_contr_port.get_all_grouped_by_entity = AsyncMock(
            return_value={entity: saved_contribs}
        )

        response = await client.get(
            f"{EVENTS_URL}?from_date=2026-05-01&to_date=2026-12-31"
        )
        body = await response.get_json()
        contrib_events = [e for e in body["events"] if e["type"] == "CONTRIBUTION"]
        assert len(contrib_events) >= 7
        dates = [e["date"] for e in contrib_events]
        assert len(set(dates)) == len(dates)

    @pytest.mark.asyncio
    async def test_contribution_with_until_limits_events(
        self,
        client,
        entity_port,
        auto_contr_port,
        virtual_import_registry,
    ):
        await _signup(client)
        entity = _make_entity()
        entity_port.get_by_id = AsyncMock(return_value=entity)
        virtual_import_registry.get_last_import_records = AsyncMock(return_value=[])

        entry = _contribution_entry(
            since="2026-01-01", until="2026-06-30", frequency="MONTHLY"
        )
        response = await client.post(CONTRIBUTIONS_URL, json={"entries": [entry]})
        assert response.status_code == 204

        saved_contribs = auto_contr_port.save.await_args[0][1]
        auto_contr_port.get_all_grouped_by_entity = AsyncMock(
            return_value={entity: saved_contribs}
        )

        response = await client.get(
            f"{EVENTS_URL}?from_date=2026-01-01&to_date=2026-12-31"
        )
        body = await response.get_json()
        contrib_events = [e for e in body["events"] if e["type"] == "CONTRIBUTION"]
        for event in contrib_events:
            assert event["date"] <= "2026-06-30"

    @pytest.mark.asyncio
    async def test_cleared_contributions_no_events(
        self,
        client,
        auto_contr_port,
        virtual_import_registry,
    ):
        await _signup(client)
        virtual_import_registry.get_last_import_records = AsyncMock(return_value=[])

        response = await client.post(CONTRIBUTIONS_URL, json={"entries": []})
        assert response.status_code == 204

        auto_contr_port.get_all_grouped_by_entity = AsyncMock(return_value={})

        response = await client.get(
            f"{EVENTS_URL}?from_date=2026-01-01&to_date=2026-12-31"
        )
        assert response.status_code == 200
        body = await response.get_json()
        contrib_events = [e for e in body["events"] if e["type"] == "CONTRIBUTION"]
        assert len(contrib_events) == 0

    @pytest.mark.asyncio
    async def test_updated_contributions_reflected_in_events(
        self,
        client,
        entity_port,
        auto_contr_port,
        virtual_import_registry,
    ):
        await _signup(client)
        entity = _make_entity()
        entity_port.get_by_id = AsyncMock(return_value=entity)
        virtual_import_registry.get_last_import_records = AsyncMock(return_value=[])

        entry = _contribution_entry(
            name="Monthly ACME", since="2026-01-01", frequency="MONTHLY"
        )
        response = await client.post(CONTRIBUTIONS_URL, json={"entries": [entry]})
        assert response.status_code == 204

        saved_contribs = auto_contr_port.save.await_args[0][1]
        auto_contr_port.get_all_grouped_by_entity = AsyncMock(
            return_value={entity: saved_contribs}
        )

        response = await client.get(
            f"{EVENTS_URL}?from_date=2026-04-01&to_date=2027-04-01"
        )
        body = await response.get_json()
        contrib_events = [e for e in body["events"] if e["type"] == "CONTRIBUTION"]
        assert all(e["name"] == "Monthly ACME" for e in contrib_events)

        auto_contr_port.reset_mock()
        entry_updated = _contribution_entry(
            name="Updated DCA",
            amount="500.00",
            target="BETA",
            target_name="Beta Corp",
            since="2026-01-01",
            frequency="QUARTERLY",
        )
        response = await client.post(
            CONTRIBUTIONS_URL, json={"entries": [entry_updated]}
        )
        assert response.status_code == 204

        saved_updated = auto_contr_port.save.await_args[0][1]
        auto_contr_port.get_all_grouped_by_entity = AsyncMock(
            return_value={entity: saved_updated}
        )

        response = await client.get(
            f"{EVENTS_URL}?from_date=2026-04-01&to_date=2027-04-01"
        )
        body = await response.get_json()
        contrib_events = [e for e in body["events"] if e["type"] == "CONTRIBUTION"]
        assert len(contrib_events) > 0
        assert all(e["name"] == "Updated DCA" for e in contrib_events)
        assert all(float(e["amount"]) == 500.0 for e in contrib_events)
        assert all(e["frequency"] == "QUARTERLY" for e in contrib_events)

    @pytest.mark.asyncio
    async def test_multiple_contributions_generate_separate_events(
        self,
        client,
        entity_port,
        auto_contr_port,
        virtual_import_registry,
    ):
        await _signup(client)
        entity = _make_entity()
        entity_port.get_by_id = AsyncMock(return_value=entity)
        virtual_import_registry.get_last_import_records = AsyncMock(return_value=[])

        entries = [
            _contribution_entry(
                name="DCA ACME", target="ACME", since="2026-01-01", frequency="MONTHLY"
            ),
            _contribution_entry(
                name="DCA BETA",
                target="BETA",
                target_name="Beta Corp",
                amount="300.00",
                since="2026-01-01",
                frequency="MONTHLY",
            ),
        ]
        response = await client.post(CONTRIBUTIONS_URL, json={"entries": entries})
        assert response.status_code == 204

        saved_contribs = auto_contr_port.save.await_args[0][1]
        auto_contr_port.get_all_grouped_by_entity = AsyncMock(
            return_value={entity: saved_contribs}
        )

        response = await client.get(
            f"{EVENTS_URL}?from_date=2026-05-01&to_date=2026-07-31"
        )
        body = await response.get_json()
        contrib_events = [e for e in body["events"] if e["type"] == "CONTRIBUTION"]
        names = {e["name"] for e in contrib_events}
        assert "DCA ACME" in names
        assert "DCA BETA" in names
        acme_events = [e for e in contrib_events if e["name"] == "DCA ACME"]
        beta_events = [e for e in contrib_events if e["name"] == "DCA BETA"]
        assert len(acme_events) >= 2
        assert len(beta_events) >= 2
