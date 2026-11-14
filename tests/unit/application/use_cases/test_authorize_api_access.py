from unittest.mock import MagicMock, PropertyMock

import pytest

from application.use_cases.authorize_api_access import AuthorizeApiAccessImpl
from infrastructure.api_session.in_memory_api_session_store import (
    InMemoryApiSessionStore,
)


def _build(unlocked: bool):
    store = InMemoryApiSessionStore()
    source_initiator = MagicMock()
    type(source_initiator).unlocked = PropertyMock(return_value=unlocked)
    return AuthorizeApiAccessImpl(store, source_initiator), store


class TestAuthorizeApiAccess:
    @pytest.mark.asyncio
    async def test_locked_allows_requests_without_token(self):
        use_case, _ = _build(unlocked=False)

        assert await use_case.execute(None) is True

    @pytest.mark.asyncio
    async def test_unlocked_requires_valid_token(self):
        use_case, store = _build(unlocked=True)
        token = store.create()

        assert await use_case.execute(token) is True
        assert await use_case.execute(None) is False
        assert await use_case.execute("forged") is False

    @pytest.mark.asyncio
    async def test_revoked_token_is_rejected(self):
        use_case, store = _build(unlocked=True)
        token = store.create()
        store.revoke_all()

        assert await use_case.execute(token) is False
