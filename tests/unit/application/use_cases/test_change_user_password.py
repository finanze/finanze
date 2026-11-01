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
    config_port = AsyncMock()
    use_case = ChangeUserPasswordImpl(
        source_initiator=source_initiator,
        data_manager=data_manager,
        config_port=config_port,
    )
    return use_case, source_initiator, data_manager, config_port


class TestChangePasswordRaisesWhenLoggedIn:
    @pytest.mark.asyncio
    async def test_raises_user_already_logged_in_when_unlocked(self):
        use_case, *_ = _build_use_case(unlocked=True)
        request = ChangePasswordRequest(
            username="testuser",
            old_password="oldpass!1",
            new_password="newpass!1",
        )

        with pytest.raises(UserAlreadyLoggedIn):
            await use_case.execute(request)


class TestChangePasswordRaisesOnSamePassword:
    @pytest.mark.asyncio
    async def test_raises_value_error_when_passwords_match(self):
        use_case, *_ = _build_use_case(unlocked=False)
        request = ChangePasswordRequest(
            username="testuser",
            old_password="samepass1",
            new_password="samepass1",
        )

        with pytest.raises(ValueError, match="different"):
            await use_case.execute(request)


class TestChangePasswordRaisesWhenUserNotFound:
    @pytest.mark.asyncio
    async def test_raises_user_not_found_when_user_does_not_exist(self):
        use_case, _, _, config_port = _build_use_case(unlocked=False, user=None)
        request = ChangePasswordRequest(
            username="nonexistent",
            old_password="oldpass!1",
            new_password="newpass!1",
        )

        with pytest.raises(UserNotFound):
            await use_case.execute(request)
        config_port.connect.assert_not_called()


class TestChangePasswordSuccess:
    @pytest.mark.asyncio
    async def test_calls_change_password_with_correct_params(self):
        user = _make_user("testuser")
        use_case, source_initiator, _, config_port = _build_use_case(
            unlocked=False, user=user
        )
        request = ChangePasswordRequest(
            username="testuser",
            old_password="oldpass!1",
            new_password="newpass!1",
        )

        await use_case.execute(request)

        source_initiator.change_password.assert_called_once()
        call_args = source_initiator.change_password.call_args
        params = call_args[0][0]
        new_password = call_args[1]["new_password"]
        assert params.user is user
        assert params.password == "oldpass!1"
        assert new_password == "newpass!1"
        assert params.context.config is config_port
        config_port.connect.assert_awaited_once_with(user)
        config_port.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disconnects_config_when_change_password_fails(self):
        user = _make_user("testuser")
        use_case, source_initiator, _, config_port = _build_use_case(
            unlocked=False, user=user
        )
        source_initiator.change_password.side_effect = RuntimeError("boom")
        request = ChangePasswordRequest(
            username="testuser",
            old_password="oldpass!1",
            new_password="newpass!1",
        )

        with pytest.raises(RuntimeError):
            await use_case.execute(request)

        config_port.connect.assert_awaited_once_with(user)
        config_port.disconnect.assert_awaited_once()
