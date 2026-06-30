import base64
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from domain.entity import Entity, EntityOrigin, EntityType
from domain.exception.exceptions import (
    ExternalEntityLinkError,
    ExternalIntegrationRequired,
)
from domain.external_entity import (
    ExternalEntity,
    ExternalEntityFetchRequest,
    ExternalEntityLoginRequest,
    ExternalEntityStatus,
    ExternalEntitySetupResponseCode,
)
from domain.external_integration import ExternalIntegrationId
from domain.global_position import AccountType, ProductType
from infrastructure.client.entity.financial.psd2.enablebanking_fetcher import (
    EnableBankingFetcher,
)


def _make_fetcher():
    client = MagicMock()
    fetcher = EnableBankingFetcher(client)
    return fetcher, client


def _external_entity(**kwargs):
    defaults = dict(
        id=uuid4(),
        entity_id=uuid4(),
        status=ExternalEntityStatus.UNLINKED,
        provider=ExternalIntegrationId.ENABLE_BANKING,
    )
    defaults.update(kwargs)
    return ExternalEntity(**defaults)


class TestSetup:
    @pytest.mark.asyncio
    async def test_setup_requires_integration(self):
        fetcher, _ = _make_fetcher()
        with pytest.raises(ExternalIntegrationRequired):
            await fetcher.setup({})

    @pytest.mark.asyncio
    async def test_setup_calls_client(self):
        fetcher, client = _make_fetcher()
        client.setup = AsyncMock()
        credentials = {"application_id": "a", "private_key": "k"}
        await fetcher.setup({ExternalIntegrationId.ENABLE_BANKING: credentials})
        client.setup.assert_awaited_once_with(credentials)


class TestGetEntities:
    @pytest.mark.asyncio
    async def test_maps_aspsps(self):
        fetcher, client = _make_fetcher()
        client.get_aspsps = AsyncMock(
            return_value=[
                {
                    "name": "Bank",
                    "country": "ES",
                    "bic": "BANKESMM",
                    "logo": "https://logo",
                }
            ]
        )

        entities = await fetcher.get_entities(country="ES")

        assert len(entities) == 1
        assert entities[0].id == "ES:Bank"
        assert entities[0].name == "Bank"
        assert entities[0].bic == "BANKESMM"
        assert entities[0].type == EntityType.FINANCIAL_INSTITUTION
        assert entities[0].icon == "https://logo"

    @pytest.mark.asyncio
    async def test_get_entity_parses_id(self):
        fetcher, client = _make_fetcher()
        client.get_aspsps = AsyncMock(
            return_value=[{"name": "Bank", "country": "ES", "logo": "l"}]
        )

        entity = await fetcher.get_entity("ES:Bank")

        assert entity is not None
        assert entity.name == "Bank"


class TestCreateOrLink:
    @pytest.mark.asyncio
    async def test_returns_continue_with_link(self):
        fetcher, client = _make_fetcher()
        client.get_aspsps = AsyncMock(
            return_value=[
                {"name": "Bank", "country": "ES", "maximum_consent_validity": 7776000}
            ]
        )
        client.start_auth = AsyncMock(
            return_value={"url": "https://auth", "authorization_id": "auth-1"}
        )

        request = ExternalEntityLoginRequest(
            external_entity=_external_entity(),
            institution_id="ES:Bank",
        )

        result = await fetcher.create_or_link(request)

        assert result.code == ExternalEntitySetupResponseCode.CONTINUE_WITH_LINK
        assert result.link == "https://auth"
        assert result.provider_instance_id == "auth-1"
        assert result.payload["aspsp"] == {"name": "Bank", "country": "ES"}
        client.start_auth.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_state_is_plain_entity_id_without_completion_url(self):
        fetcher, client = _make_fetcher()
        client.get_aspsps = AsyncMock(
            return_value=[
                {"name": "Bank", "country": "ES", "maximum_consent_validity": 7776000}
            ]
        )
        client.start_auth = AsyncMock(
            return_value={"url": "https://auth", "authorization_id": "auth-1"}
        )

        external_entity = _external_entity()
        request = ExternalEntityLoginRequest(
            external_entity=external_entity,
            institution_id="ES:Bank",
        )

        await fetcher.create_or_link(request)

        assert client.start_auth.await_args.kwargs["state"] == str(external_entity.id)

    @pytest.mark.asyncio
    async def test_state_encodes_completion_url_when_present(self):
        fetcher, client = _make_fetcher()
        client.get_aspsps = AsyncMock(
            return_value=[
                {"name": "Bank", "country": "ES", "maximum_consent_validity": 7776000}
            ]
        )
        client.start_auth = AsyncMock(
            return_value={"url": "https://auth", "authorization_id": "auth-1"}
        )

        external_entity = _external_entity()
        completion_url = "https://my-host.example/#/entities"
        request = ExternalEntityLoginRequest(
            external_entity=external_entity,
            institution_id="ES:Bank",
            completion_url=completion_url,
        )

        await fetcher.create_or_link(request)

        state = client.start_auth.await_args.kwargs["state"]
        entity_part, _, encoded = state.partition("~")
        assert entity_part == str(external_entity.id)
        assert encoded != ""

        padding = "=" * (-len(encoded) % 4)
        decoded = base64.urlsafe_b64decode(encoded + padding).decode("utf-8")
        assert decoded == completion_url


class TestCompleteLink:
    @pytest.mark.asyncio
    async def test_creates_session_and_returns_accounts(self):
        fetcher, client = _make_fetcher()
        client.create_session = AsyncMock(
            return_value={
                "session_id": "sess-1",
                "accounts": [
                    {
                        "uid": "acc-uid",
                        "currency": "EUR",
                        "name": "Main",
                        "account_id": {"iban": "ES123"},
                        "cash_account_type": "CACC",
                    }
                ],
                "aspsp": {"name": "Bank", "country": "ES"},
                "access": {"valid_until": "2024-01-01T00:00:00+00:00"},
            }
        )

        completion = await fetcher.complete_link(
            _external_entity(payload={"aspsp": {"name": "Bank", "country": "ES"}}),
            {"code": "code-1"},
        )

        assert completion.linked is True
        assert completion.provider_instance_id == "sess-1"
        accounts = completion.payload["accounts"]
        assert accounts[0]["uid"] == "acc-uid"
        assert accounts[0]["iban"] == "ES123"
        assert completion.payload["valid_until"] == "2024-01-01T00:00:00+00:00"

    @pytest.mark.asyncio
    async def test_missing_code_raises(self):
        fetcher, _ = _make_fetcher()
        with pytest.raises(ExternalEntityLinkError):
            await fetcher.complete_link(_external_entity(), {})


class TestGlobalPosition:
    @pytest.mark.asyncio
    async def test_builds_accounts_from_balances(self):
        fetcher, client = _make_fetcher()
        client.get_account_balances = AsyncMock(
            return_value={
                "balances": [
                    {
                        "balance_type": "CLAV",
                        "balance_amount": {"amount": "100.50", "currency": "EUR"},
                    }
                ]
            }
        )

        external_entity = _external_entity(
            status=ExternalEntityStatus.LINKED,
            provider_instance_id="sess-1",
            payload={
                "accounts": [
                    {
                        "uid": "acc-uid",
                        "currency": "EUR",
                        "name": "Main",
                        "iban": "ES123",
                        "cash_account_type": "SVGS",
                    }
                ]
            },
        )
        entity = Entity(
            id=uuid4(),
            name="Bank",
            natural_id="BANKESMM",
            type=EntityType.FINANCIAL_INSTITUTION,
            origin=EntityOrigin.EXTERNALLY_PROVIDED,
            icon_url=None,
        )

        position = await fetcher.global_position(
            ExternalEntityFetchRequest(external_entity=external_entity, entity=entity)
        )

        accounts = position.products[ProductType.ACCOUNT].entries
        assert len(accounts) == 1
        assert str(accounts[0].total) == "100.50"
        assert accounts[0].currency == "EUR"
        assert accounts[0].type == AccountType.SAVINGS
        assert accounts[0].iban == "ES123"
