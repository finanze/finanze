from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from application.use_cases.disconnect_entity import DisconnectEntityImpl
from domain.entity_account import EntityAccount
from domain.entity_login import EntityDisconnectRequest
from domain.exception.exceptions import EntityNotFound
from domain.native_entities import BINANCE, MY_INVESTOR


class TestDisconnectEntityExecute:
    def _build_use_case(self):
        credentials_port = AsyncMock()
        sessions_port = AsyncMock()
        transaction_handler_port = MagicMock()
        transaction_handler_port.start.return_value = AsyncMock()
        entity_account_port = AsyncMock()
        transaction_port = AsyncMock()
        auto_contributions_port = AsyncMock()
        historic_port = AsyncMock()

        use_case = DisconnectEntityImpl(
            credentials_port=credentials_port,
            sessions_port=sessions_port,
            transaction_handler_port=transaction_handler_port,
            entity_account_port=entity_account_port,
            transaction_port=transaction_port,
            auto_contributions_port=auto_contributions_port,
            historic_port=historic_port,
        )

        return (
            use_case,
            credentials_port,
            sessions_port,
            entity_account_port,
            transaction_port,
            auto_contributions_port,
            historic_port,
        )

    def _make_entity_account(self, entity_id, entity_account_id=None):
        return EntityAccount(
            id=entity_account_id or uuid4(),
            entity_id=entity_id,
            created_at=MagicMock(),
        )

    @pytest.mark.asyncio
    async def test_crypto_exchange_deletes_by_entity_account_id(self):
        use_case, credentials_port, sessions_port, entity_account_port, _, _, _ = (
            self._build_use_case()
        )
        entity_account_id = uuid4()
        entity_account = self._make_entity_account(BINANCE.id, entity_account_id)
        entity_account_port.get_by_id.return_value = entity_account

        await use_case.execute(
            EntityDisconnectRequest(entity_account_id=entity_account_id)
        )

        credentials_port.delete.assert_called_once_with(entity_account_id)
        sessions_port.delete.assert_called_once_with(entity_account_id)
        entity_account_port.soft_delete.assert_called_once_with(entity_account_id)

    @pytest.mark.asyncio
    async def test_financial_institution_deletes_by_entity_id(self):
        use_case, credentials_port, sessions_port, entity_account_port, _, _, _ = (
            self._build_use_case()
        )
        entity_account_id = uuid4()
        entity_account = self._make_entity_account(MY_INVESTOR.id, entity_account_id)
        entity_account_port.get_by_id.return_value = entity_account

        await use_case.execute(
            EntityDisconnectRequest(entity_account_id=entity_account_id)
        )

        credentials_port.delete_by_entity_id.assert_called_once_with(MY_INVESTOR.id)
        sessions_port.delete_by_entity_id.assert_called_once_with(MY_INVESTOR.id)
        entity_account_port.soft_delete_by_entity_id.assert_called_once_with(
            MY_INVESTOR.id
        )

    @pytest.mark.asyncio
    async def test_crypto_exchange_deletes_shared_data(self):
        (
            use_case,
            _,
            _,
            entity_account_port,
            transaction_port,
            auto_contributions_port,
            historic_port,
        ) = self._build_use_case()
        entity_account_id = uuid4()
        entity_account = self._make_entity_account(BINANCE.id, entity_account_id)
        entity_account_port.get_by_id.return_value = entity_account

        await use_case.execute(
            EntityDisconnectRequest(entity_account_id=entity_account_id)
        )

        transaction_port.delete_by_entity_account_id.assert_called_once_with(
            entity_account_id
        )
        auto_contributions_port.delete_by_entity_account_id.assert_called_once_with(
            entity_account_id
        )
        historic_port.delete_by_entity_account_id.assert_called_once_with(
            entity_account_id
        )

    @pytest.mark.asyncio
    async def test_financial_institution_deletes_shared_data(self):
        (
            use_case,
            _,
            _,
            entity_account_port,
            transaction_port,
            auto_contributions_port,
            historic_port,
        ) = self._build_use_case()
        entity_account_id = uuid4()
        entity_account = self._make_entity_account(MY_INVESTOR.id, entity_account_id)
        entity_account_port.get_by_id.return_value = entity_account

        await use_case.execute(
            EntityDisconnectRequest(entity_account_id=entity_account_id)
        )

        transaction_port.delete_by_entity_account_id.assert_called_once_with(
            entity_account_id
        )
        auto_contributions_port.delete_by_entity_account_id.assert_called_once_with(
            entity_account_id
        )
        historic_port.delete_by_entity_account_id.assert_called_once_with(
            entity_account_id
        )

    @pytest.mark.asyncio
    async def test_entity_account_not_found_raises(self):
        use_case, _, _, entity_account_port, _, _, _ = self._build_use_case()
        entity_account_id = uuid4()
        entity_account_port.get_by_id.return_value = None

        with pytest.raises(EntityNotFound):
            await use_case.execute(
                EntityDisconnectRequest(entity_account_id=entity_account_id)
            )

    @pytest.mark.asyncio
    async def test_native_entity_not_found_raises(self):
        use_case, _, _, entity_account_port, _, _, _ = self._build_use_case()
        entity_account_id = uuid4()
        unknown_entity_id = uuid4()
        entity_account = self._make_entity_account(unknown_entity_id, entity_account_id)
        entity_account_port.get_by_id.return_value = entity_account

        with pytest.raises(EntityNotFound):
            await use_case.execute(
                EntityDisconnectRequest(entity_account_id=entity_account_id)
            )
