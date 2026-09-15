from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from application.use_cases.add_entity_credentials import AddEntityCredentialsImpl
from domain.entity_login import EntityLoginRequest, EntityLoginResult, EntitySession
from domain.native_entities import POLYMARKET, URBANITAE
from domain.public_keychain import PublicKeychain


class TestAddEntityCredentials:
    def _build_use_case(self, entity=POLYMARKET):
        fetcher = AsyncMock()
        fetcher.login.return_value = EntityLoginResult(
            code="CREATED",
            session=EntitySession(
                creation=datetime.now(timezone.utc),
                expiration=None,
                payload={"mock": True},
            ),
        )

        credentials_port = AsyncMock()
        sessions_port = AsyncMock()
        transaction_handler_port = MagicMock()
        transaction_handler_port.start.return_value = AsyncMock()
        keychain_loader = AsyncMock()
        keychain_loader.load.return_value = PublicKeychain({})
        entity_account_port = AsyncMock()
        feature_flag_port = MagicMock()
        feature_flag_port.get_all.return_value = {}

        use_case = AddEntityCredentialsImpl(
            entity_fetchers={entity: fetcher},
            credentials_port=credentials_port,
            sessions_port=sessions_port,
            transaction_handler_port=transaction_handler_port,
            keychain_loader=keychain_loader,
            entity_account_port=entity_account_port,
            feature_flag_port=feature_flag_port,
        )
        entity_account_port.get_by_entity_id.return_value = []

        return (
            use_case,
            fetcher,
            credentials_port,
            sessions_port,
            entity_account_port,
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("entity", "credentials", "expected_name"),
        [
            (POLYMARKET, {"identifier": "market-user"}, "market-user"),
            (
                URBANITAE,
                {"user": "investor@example.com", "password": "secret"},
                "investor@example.com",
            ),
        ],
    )
    async def test_missing_account_alias_uses_user_or_email_credential(
        self, entity, credentials, expected_name
    ):
        use_case, _, _, _, entity_account_port = self._build_use_case(entity)

        await use_case.execute(
            EntityLoginRequest(entity_id=entity.id, credentials=credentials)
        )

        account = entity_account_port.create.await_args.args[0]
        assert account.name == expected_name

    @pytest.mark.asyncio
    async def test_market_forecast_login_creates_account(self):
        use_case, _, credentials_port, _, entity_account_port = self._build_use_case()

        result = await use_case.execute(
            EntityLoginRequest(
                entity_id=POLYMARKET.id,
                credentials={"identifier": "market-user"},
                account_name="Main",
            )
        )

        assert result.entity_account_id is not None
        entity_account_port.create.assert_awaited_once()
        account = entity_account_port.create.await_args.args[0]
        assert account.id == result.entity_account_id
        assert account.entity_id == POLYMARKET.id
        assert account.name == "Main"
        credentials_port.save.assert_awaited_once_with(
            result.entity_account_id,
            POLYMARKET.id,
            {"identifier": "market-user"},
        )

    @pytest.mark.asyncio
    async def test_market_forecast_logins_without_account_id_create_distinct_accounts(
        self,
    ):
        use_case, _, _, _, entity_account_port = self._build_use_case()

        first_result = await use_case.execute(
            EntityLoginRequest(
                entity_id=POLYMARKET.id,
                credentials={"identifier": "first-user"},
            )
        )
        second_result = await use_case.execute(
            EntityLoginRequest(
                entity_id=POLYMARKET.id,
                credentials={"identifier": "second-user"},
            )
        )

        assert first_result.entity_account_id != second_result.entity_account_id
        assert entity_account_port.create.await_count == 2

    @pytest.mark.asyncio
    async def test_market_forecast_relogin_replaces_selected_account(self):
        use_case, _, credentials_port, sessions_port, entity_account_port = (
            self._build_use_case()
        )
        entity_account_id = uuid4()

        result = await use_case.execute(
            EntityLoginRequest(
                entity_id=POLYMARKET.id,
                credentials={"identifier": "updated-user"},
                entity_account_id=entity_account_id,
            )
        )

        assert result.entity_account_id == entity_account_id
        credentials_port.delete.assert_awaited_once_with(entity_account_id)
        sessions_port.delete.assert_awaited_once_with(entity_account_id)
        entity_account_port.create.assert_not_awaited()
        credentials_port.save.assert_awaited_once_with(
            entity_account_id,
            POLYMARKET.id,
            {"identifier": "updated-user"},
        )
