from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from application.use_cases.get_available_entities import GetAvailableEntitiesImpl
from domain.available_sources import FinancialEntityStatus
from domain.entity import Entity, EntityOrigin, EntityType
from domain.entity_account import EntityAccount
from domain.external_entity import ExternalEntity, ExternalEntityStatus
from domain.external_integration import ExternalIntegrationId
from domain.native_entities import POLYMARKET
from domain.native_entity import FinancialEntityCredentialsEntry


def _build_use_case(
    *,
    entity,
    external_entity,
    enabled_provider_payloads,
    external_entity_fetchers,
    logged_entities=None,
    accounts=None,
    entity_fetchers=None,
):
    entity_port = AsyncMock()
    entity_port.get_all = AsyncMock(return_value=[entity])

    external_entity_port = AsyncMock()
    external_entity_port.get_by_entity_id = AsyncMock(return_value=external_entity)

    external_integration_port = AsyncMock()
    external_integration_port.get_payloads_by_type = AsyncMock(
        return_value=enabled_provider_payloads
    )

    credentials_port = AsyncMock()
    credentials_port.get_available_entities = AsyncMock(
        return_value=logged_entities or []
    )

    crypto_wallet_port = AsyncMock()
    last_fetches_port = AsyncMock()
    last_fetches_port.get_by_entity_id = AsyncMock(return_value=[])

    virtual_import_registry = AsyncMock()
    virtual_import_registry.get_last_import_records = AsyncMock(return_value=[])

    entity_account_port = AsyncMock()
    entity_account_port.get_by_ids = AsyncMock(return_value=accounts or [])

    return GetAvailableEntitiesImpl(
        entity_port,
        external_entity_port,
        external_integration_port,
        credentials_port,
        crypto_wallet_port,
        last_fetches_port,
        virtual_import_registry,
        entity_fetchers or {},
        external_entity_fetchers,
        entity_account_port,
        {},
    )


def _external_entity(entity_id, provider):
    return ExternalEntity(
        id=uuid4(),
        entity_id=entity_id,
        status=ExternalEntityStatus.LINKED,
        provider=provider,
    )


def _external_provided_entity():
    return Entity(
        id=uuid4(),
        name="Some Bank",
        natural_id="some-bank",
        type=EntityType.FINANCIAL_INSTITUTION,
        origin=EntityOrigin.EXTERNALLY_PROVIDED,
        icon_url=None,
    )


@pytest.mark.asyncio
async def test_external_entity_fetchable_when_provider_enabled_and_bundled():
    entity = _external_provided_entity()
    external_entity = _external_entity(entity.id, ExternalIntegrationId.ENABLE_BANKING)
    use_case = _build_use_case(
        entity=entity,
        external_entity=external_entity,
        enabled_provider_payloads={ExternalIntegrationId.ENABLE_BANKING: {}},
        external_entity_fetchers={ExternalIntegrationId.ENABLE_BANKING: MagicMock()},
    )

    result = await use_case.execute()

    source = result.entities[0]
    assert source.fetchable is True
    assert source.status == FinancialEntityStatus.CONNECTED


@pytest.mark.asyncio
async def test_external_entity_not_fetchable_when_provider_disabled():
    entity = _external_provided_entity()
    external_entity = _external_entity(entity.id, ExternalIntegrationId.ENABLE_BANKING)
    use_case = _build_use_case(
        entity=entity,
        external_entity=external_entity,
        enabled_provider_payloads={},
        external_entity_fetchers={ExternalIntegrationId.ENABLE_BANKING: MagicMock()},
    )

    result = await use_case.execute()

    assert result.entities[0].fetchable is False


@pytest.mark.asyncio
async def test_external_entity_not_fetchable_when_provider_not_bundled():
    entity = _external_provided_entity()
    external_entity = _external_entity(entity.id, ExternalIntegrationId.GOCARDLESS)
    use_case = _build_use_case(
        entity=entity,
        external_entity=external_entity,
        enabled_provider_payloads={ExternalIntegrationId.GOCARDLESS: {}},
        external_entity_fetchers={ExternalIntegrationId.ENABLE_BANKING: MagicMock()},
    )

    result = await use_case.execute()

    assert result.entities[0].fetchable is False


@pytest.mark.asyncio
async def test_market_forecast_account_is_serialized_with_status_and_name():
    account_id = uuid4()
    account = EntityAccount(
        id=account_id,
        entity_id=POLYMARKET.id,
        created_at=datetime.now(timezone.utc),
        name="Main",
    )
    credential_entry = FinancialEntityCredentialsEntry(
        entity_id=POLYMARKET.id,
        entity_account_id=account_id,
    )
    use_case = _build_use_case(
        entity=POLYMARKET,
        external_entity=None,
        enabled_provider_payloads={},
        external_entity_fetchers={},
        logged_entities=[credential_entry],
        accounts=[account],
        entity_fetchers={POLYMARKET: MagicMock()},
    )

    result = await use_case.execute()

    source = result.entities[0]
    assert source.status == FinancialEntityStatus.CONNECTED
    assert source.accounts is not None
    assert source.accounts[0].id == account_id
    assert source.accounts[0].name == "Main"
    assert source.accounts[0].status == FinancialEntityStatus.CONNECTED
