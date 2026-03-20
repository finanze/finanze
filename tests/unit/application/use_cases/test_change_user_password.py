from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, PropertyMock
from uuid import uuid4

import pytest

from application.use_cases.change_user_password import ChangeUserPasswordImpl
from domain.exception.exceptions import UserAlreadyLoggedIn, UserNotFound
from domain.user import User
from domain.user_login import ChangePasswordRequest


def _make_user(username: str = "testuser") -> User:
    return User(
        id=uuid4(),
        username=username,
        path=Path("/data/testuser"),
        last_login=datetime(2025, 1, 1),
    )


def _build_use_case(unlocked: bool = False, user: User = None):
    source_initiator = MagicMock()
    type(source_initiator).unlocked = PropertyMock(return_value=unlocked)
    source_initiator.change_password = AsyncMock()
    data_manager = AsyncMock()
    data_manager.get_user.return_value = user
    use_case = ChangeUserPasswordImpl(
        source_initiator=source_initiator,
        data_manager=data_manager,
    )
    return use_case, source_initiator, data_manager


class TestChangePasswordRaisesWhenLoggedIn:
    @pytest.mark.asyncio
    async def test_raises_user_already_logged_in_when_unlocked(self):
        use_case, _, _ = _build_use_case(unlocked=True)
        request = ChangePasswordRequest(
            username="testuser",
            old_password="old",
            new_password="new",
        )

        with pytest.raises(UserAlreadyLoggedIn):
            await use_case.execute(request)


class TestChangePasswordRaisesOnSamePassword:
    @pytest.mark.asyncio
    async def test_raises_value_error_when_passwords_match(self):
        use_case, _, _ = _build_use_case(unlocked=False)
        request = ChangePasswordRequest(
            username="testuser",
            old_password="samepass",
            new_password="samepass",
        )

        with pytest.raises(ValueError, match="different"):
            await use_case.execute(request)


class TestChangePasswordRaisesWhenUserNotFound:
    @pytest.mark.asyncio
    async def test_raises_user_not_found_when_user_does_not_exist(self):
        use_case, _, _ = _build_use_case(unlocked=False, user=None)
        request = ChangePasswordRequest(
            username="nonexistent",
            old_password="old",
            new_password="new",
        )

        with pytest.raises(UserNotFound):
            await use_case.execute(request)


class TestChangePasswordSuccess:
    @pytest.mark.asyncio
    async def test_calls_change_password_with_correct_params(self):
        user = _make_user("testuser")
        use_case, source_initiator, _ = _build_use_case(unlocked=False, user=user)
        request = ChangePasswordRequest(
            username="testuser",
            old_password="oldpass",
            new_password="newpass",
        )

        await use_case.execute(request)

        source_initiator.change_password.assert_called_once()
        call_args = source_initiator.change_password.call_args
        params = call_args[0][0]
        new_password = call_args[1]["new_password"]
        assert params.user is user
        assert params.password == "oldpass"
        assert new_password == "newpass"
