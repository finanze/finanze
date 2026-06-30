from typing import Optional
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from application.use_cases.complete_external_entity_connection import (
    CompleteExternalEntityConnectionImpl,
)
from application.use_cases.connect_external_entity import ConnectExternalEntityImpl
from domain.entity import Entity
from domain.external_entity import (
    CompleteExternalEntityLinkRequest,
    ConnectExternalEntityRequest,
    ExternalEntity,
    ExternalEntitySetupResponseCode,
    ExternalEntityStatus,
)
from domain.external_integration import ExternalIntegrationId, ExternalIntegrationType
from infrastructure.client.entity.financial.psd2.enablebanking_fetcher import (
    EnableBankingFetcher,
)
from infrastructure.client.financial.enablebanking.enablebanking_client import (
    EnableBankingClient,
)

ASPSP = {
    "name": "Test Bank",
    "country": "ES",
    "bic": "TESTESMMXXX",
    "logo": "https://example.com/logo.png",
    "maximum_consent_validity": 7776000,
}


class InMemoryEntityPort:
    def __init__(self):
        self._by_id: dict[UUID, Entity] = {}

    async def insert(self, entity: Entity):
        self._by_id[entity.id] = entity

    async def update(self, entity: Entity):
        self._by_id[entity.id] = entity

    async def get_by_id(self, entity_id: UUID) -> Optional[Entity]:
        return self._by_id.get(entity_id)

    async def get_all(self) -> list[Entity]:
        return list(self._by_id.values())

    async def get_by_natural_id(self, natural_id: str) -> Optional[Entity]:
        return next(
            (e for e in self._by_id.values() if e.natural_id == natural_id), None
        )

    async def get_by_name(self, name: str) -> Optional[Entity]:
        return next((e for e in self._by_id.values() if e.name == name), None)

    async def delete_by_id(self, entity_id: UUID):
        self._by_id.pop(entity_id, None)

    async def get_disabled_entities(self) -> list[Entity]:
        return []


class InMemoryExternalEntityPort:
    def __init__(self):
        self._by_id: dict[UUID, ExternalEntity] = {}

    async def upsert(self, ee: ExternalEntity):
        self._by_id[ee.id] = ee

    async def update_status(self, ee_id: UUID, status: ExternalEntityStatus):
        self._by_id[ee_id].status = status

    async def get_by_id(self, ee_id) -> Optional[ExternalEntity]:
        if isinstance(ee_id, str):
            ee_id = UUID(ee_id)
        return self._by_id.get(ee_id)

    async def get_by_entity_id(self, entity_id: UUID) -> Optional[ExternalEntity]:
        return next((e for e in self._by_id.values() if e.entity_id == entity_id), None)

    async def delete_by_id(self, ee_id: UUID):
        self._by_id.pop(ee_id, None)

    async def get_all(self) -> list[ExternalEntity]:
        return list(self._by_id.values())


class InMemoryExternalIntegrationPort:
    def __init__(self, payloads: dict):
        self._payloads = payloads

    async def deactivate(self, integration):
        self._payloads.pop(integration, None)

    async def activate(self, integration, payload):
        self._payloads[integration] = payload

    async def get_payload(self, integration):
        return self._payloads.get(integration)

    async def get_payloads_by_type(self, integration_type: ExternalIntegrationType):
        if integration_type == ExternalIntegrationType.ENTITY_PROVIDER:
            return dict(self._payloads)
        return {}

    async def get_all(self):
        return []


@pytest.fixture
def setup():
    entity_port = InMemoryEntityPort()
    external_entity_port = InMemoryExternalEntityPort()
    external_integration_port = InMemoryExternalIntegrationPort(
        {
            ExternalIntegrationId.ENABLE_BANKING: {
                "application_id": "app-id",
                "private_key": "pem",
            }
        }
    )

    client = AsyncMock(spec=EnableBankingClient)
    client.get_aspsps.return_value = [ASPSP]
    client.start_auth.return_value = {
        "url": "https://api.enablebanking.com/auth/redirect",
        "authorization_id": "authz-1",
    }
    client.create_session.return_value = {
        "session_id": "session-1",
        "accounts": [
            {
                "uid": "acc-uid-1",
                "currency": "EUR",
                "name": "Main Account",
                "account_id": {"iban": "ES1234567890"},
                "cash_account_type": "CACC",
            }
        ],
        "aspsp": {"name": ASPSP["name"], "country": ASPSP["country"]},
        "access": {"valid_until": "2030-01-01T00:00:00+00:00"},
    }

    fetcher = EnableBankingFetcher(client)
    fetchers = {ExternalIntegrationId.ENABLE_BANKING: fetcher}

    connect_uc = ConnectExternalEntityImpl(
        entity_port,
        external_entity_port,
        fetchers,
        external_integration_port,
    )
    complete_uc = CompleteExternalEntityConnectionImpl(
        external_entity_port,
        fetchers,
        external_integration_port,
    )

    return (
        connect_uc,
        complete_uc,
        entity_port,
        external_entity_port,
        client,
    )


class TestEnableBankingConnectFlow:
    @pytest.mark.asyncio
    async def test_connect_then_complete_links_entity(self, setup):
        connect_uc, complete_uc, entity_port, external_entity_port, client = setup

        result = await connect_uc.execute(
            ConnectExternalEntityRequest(
                institution_id="ES:Test Bank",
                external_entity_id=None,
                provider=ExternalIntegrationId.ENABLE_BANKING,
            )
        )

        assert result.code == ExternalEntitySetupResponseCode.CONTINUE_WITH_LINK
        assert result.link == "https://api.enablebanking.com/auth/redirect"
        assert result.id is not None

        entities = await entity_port.get_all()
        assert len(entities) == 1
        assert entities[0].name == "Test Bank"
        assert entities[0].natural_id == "TESTESMMXXX"

        external_entities = await external_entity_port.get_all()
        assert len(external_entities) == 1
        external_entity = external_entities[0]
        assert external_entity.status == ExternalEntityStatus.UNLINKED
        assert external_entity.provider == ExternalIntegrationId.ENABLE_BANKING

        client.start_auth.assert_awaited_once()

        await complete_uc.execute(
            CompleteExternalEntityLinkRequest(
                payload={
                    "code": "auth-code-123",
                    "state": str(external_entity.id),
                },
                external_entity_id=str(external_entity.id),
            )
        )

        linked = await external_entity_port.get_by_id(external_entity.id)
        assert linked.status == ExternalEntityStatus.LINKED
        assert linked.provider_instance_id == "session-1"
        assert linked.payload["accounts"][0]["uid"] == "acc-uid-1"
        assert linked.payload["accounts"][0]["iban"] == "ES1234567890"

        client.create_session.assert_awaited_once_with("auth-code-123")

    @pytest.mark.asyncio
    async def test_complete_missing_code_raises(self, setup):
        connect_uc, complete_uc, _, external_entity_port, _ = setup

        await connect_uc.execute(
            ConnectExternalEntityRequest(
                institution_id="ES:Test Bank",
                external_entity_id=None,
                provider=ExternalIntegrationId.ENABLE_BANKING,
            )
        )
        external_entity = (await external_entity_port.get_all())[0]

        from domain.exception.exceptions import ExternalEntityLinkError

        with pytest.raises(ExternalEntityLinkError):
            await complete_uc.execute(
                CompleteExternalEntityLinkRequest(
                    payload={"state": str(external_entity.id)},
                    external_entity_id=str(external_entity.id),
                )
            )

    @pytest.mark.asyncio
    async def test_completion_url_is_encoded_in_auth_state(self, setup):
        connect_uc, _, _, external_entity_port, client = setup

        completion_url = "https://my-host.example/#/entities"
        await connect_uc.execute(
            ConnectExternalEntityRequest(
                institution_id="ES:Test Bank",
                external_entity_id=None,
                provider=ExternalIntegrationId.ENABLE_BANKING,
                completion_url=completion_url,
            )
        )

        external_entity = (await external_entity_port.get_all())[0]
        state = client.start_auth.await_args.kwargs["state"]
        entity_part, _, encoded = state.partition("~")
        assert entity_part == str(external_entity.id)

        import base64

        padding = "=" * (-len(encoded) % 4)
        decoded = base64.urlsafe_b64decode(encoded + padding).decode("utf-8")
        assert decoded == completion_url
