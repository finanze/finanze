from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, PropertyMock
from uuid import uuid4

import pytest

from application.use_cases.get_status import GetStatusImpl
from domain.status import LoginStatusCode
from domain.user import User
from infrastructure.api_session.in_memory_api_session_store import (
    InMemoryApiSessionStore,
)


def _make_user(guest: bool = False) -> User:
    return User(
        id=uuid4(),
        username="alice",
        path=Path("/data/alice"),
        last_login=None,
        guest=guest,
    )


def _build(unlocked: bool, user: User, api_session_port=None):
    source_initiator = MagicMock()
    type(source_initiator).unlocked = PropertyMock(return_value=unlocked)
    source_initiator.get_user.return_value = user

    data_manager = MagicMock()
    data_manager.get_last_user = AsyncMock(return_value=user)

    server_details_port = MagicMock()
    server_details_port.get_backend_details = AsyncMock(return_value=MagicMock())

    feature_flag_port = MagicMock()
    feature_flag_port.get_all.return_value = {}

    return GetStatusImpl(
        source_initiator,
        data_manager,
        server_details_port,
        feature_flag_port,
        api_session_port=api_session_port,
    )


class TestGetStatusApiSession:
    @pytest.mark.asyncio
    async def test_unlocked_without_session_port(self):
        user = _make_user()
        use_case = _build(unlocked=True, user=user)

        result = await use_case.execute()

        assert result.status == LoginStatusCode.UNLOCKED
        assert result.user is user
        assert result.api_session is False

    @pytest.mark.asyncio
    async def test_unlocked_with_valid_token(self):
        user = _make_user()
        store = InMemoryApiSessionStore()
        token = store.create()
        use_case = _build(unlocked=True, user=user, api_session_port=store)

        result = await use_case.execute(token)

        assert result.status == LoginStatusCode.UNLOCKED
        assert result.user is user
        assert result.api_session is True

    @pytest.mark.asyncio
    @pytest.mark.parametrize("token", [None, "", "forged"])
    async def test_unlocked_without_valid_token_is_masked_as_locked(self, token):
        user = _make_user()
        store = InMemoryApiSessionStore()
        store.create()
        use_case = _build(unlocked=True, user=user, api_session_port=store)

        result = await use_case.execute(token)

        assert result.status == LoginStatusCode.LOCKED
        assert result.user is None
        assert result.last_logged == "alice"

    @pytest.mark.asyncio
    async def test_locked_keeps_pending_guest_user(self):
        user = _make_user(guest=True)
        use_case = _build(
            unlocked=False, user=user, api_session_port=InMemoryApiSessionStore()
        )

        result = await use_case.execute()

        assert result.status == LoginStatusCode.LOCKED
        assert result.user is user
        assert result.pending_register is True
