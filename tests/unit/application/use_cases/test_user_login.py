from pathlib import Path
from uuid import uuid4

import pytest
from unittest.mock import AsyncMock, MagicMock, PropertyMock

from application.use_cases.user_login import UserLoginImpl
from domain.exception.exceptions import (
    InvalidUserCredentials,
    UserAlreadyLoggedIn,
    UserNotFound,
)
from domain.user import User
from domain.user_login import LoginRequest


def _make_user(username: str = "testuser") -> User:
    return User(
        id=uuid4(),
        username=username,
        path=Path(f"/data/{username}"),
        last_login=None,
    )


def _create_mocks(unlocked=False, user=None):
    source_initiator = MagicMock()
    type(source_initiator).unlocked = PropertyMock(return_value=unlocked)
    source_initiator.initialize = AsyncMock()

    data_manager = MagicMock()
    data_manager.get_user = AsyncMock(return_value=user)
    data_manager.set_last_user = AsyncMock()

    config_port = MagicMock()
    config_port.connect = AsyncMock()
    config_port.disconnect = AsyncMock()

    sheets_initiator = MagicMock()
    sheets_initiator.connect = MagicMock()
    sheets_initiator.disconnect = MagicMock()

    cloud_register = MagicMock()
    cloud_register.connect = AsyncMock()
    cloud_register.disconnect = AsyncMock()

    return source_initiator, data_manager, config_port, sheets_initiator, cloud_register


class TestUserLoginRejection:
    @pytest.mark.asyncio
    async def test_raises_when_already_logged_in(self):
        (
            source_initiator,
            data_manager,
            config_port,
            sheets_initiator,
            cloud_register,
        ) = _create_mocks(unlocked=True)

        use_case = UserLoginImpl(
            source_initiator=source_initiator,
            data_manager=data_manager,
            config_port=config_port,
            sheets_initiator=sheets_initiator,
            cloud_register=cloud_register,
        )

        with pytest.raises(UserAlreadyLoggedIn):
            await use_case.execute(LoginRequest(username="alice", password="pass"))

    @pytest.mark.asyncio
    async def test_raises_when_user_not_found(self):
        (
            source_initiator,
            data_manager,
            config_port,
            sheets_initiator,
            cloud_register,
        ) = _create_mocks(unlocked=False, user=None)

        use_case = UserLoginImpl(
            source_initiator=source_initiator,
            data_manager=data_manager,
            config_port=config_port,
            sheets_initiator=sheets_initiator,
            cloud_register=cloud_register,
        )

        with pytest.raises(UserNotFound):
            await use_case.execute(LoginRequest(username="unknown", password="pass"))


class TestUserLoginSuccess:
    @pytest.mark.asyncio
    async def test_successful_login(self):
        user = _make_user("alice")
        (
            source_initiator,
            data_manager,
            config_port,
            sheets_initiator,
            cloud_register,
        ) = _create_mocks(unlocked=False, user=user)

        use_case = UserLoginImpl(
            source_initiator=source_initiator,
            data_manager=data_manager,
            config_port=config_port,
            sheets_initiator=sheets_initiator,
            cloud_register=cloud_register,
        )

        await use_case.execute(LoginRequest(username="alice", password="secret"))

        config_port.connect.assert_called_once()
        sheets_initiator.connect.assert_called_once()
        cloud_register.connect.assert_called_once()
        data_manager.set_last_user.assert_called_once()
        source_initiator.initialize.assert_called_once()

        params = source_initiator.initialize.call_args[0][0]
        assert params.user is user
        assert params.password == "secret"
        assert params.context.config is config_port

    @pytest.mark.asyncio
    async def test_login_call_order(self):
        user = _make_user("alice")
        (
            source_initiator,
            data_manager,
            config_port,
            sheets_initiator,
            cloud_register,
        ) = _create_mocks(unlocked=False, user=user)

        manager = MagicMock()
        manager.attach_mock(config_port.connect, "config_port_connect")
        manager.attach_mock(sheets_initiator.connect, "sheets_initiator_connect")
        manager.attach_mock(cloud_register.connect, "cloud_register_connect")
        manager.attach_mock(data_manager.set_last_user, "data_manager_set_last_user")
        manager.attach_mock(source_initiator.initialize, "source_initiator_initialize")

        use_case = UserLoginImpl(
            source_initiator=source_initiator,
            data_manager=data_manager,
            config_port=config_port,
            sheets_initiator=sheets_initiator,
            cloud_register=cloud_register,
        )

        await use_case.execute(LoginRequest(username="alice", password="secret"))

        call_names = [c[0] for c in manager.mock_calls]
        assert call_names == [
            "config_port_connect",
            "sheets_initiator_connect",
            "cloud_register_connect",
            "data_manager_set_last_user",
            "source_initiator_initialize",
        ]

    @pytest.mark.asyncio
    async def test_reports_hashed_user_id_to_telemetry(self):
        user = _make_user("alice")
        (
            source_initiator,
            data_manager,
            config_port,
            sheets_initiator,
            cloud_register,
        ) = _create_mocks(unlocked=False, user=user)
        error_reporter = MagicMock()

        use_case = UserLoginImpl(
            source_initiator=source_initiator,
            data_manager=data_manager,
            config_port=config_port,
            sheets_initiator=sheets_initiator,
            cloud_register=cloud_register,
            error_reporter=error_reporter,
        )

        await use_case.execute(LoginRequest(username="alice", password="secret"))

        error_reporter.set_user.assert_called_once_with(user.hashed_id())


class TestUserLoginRollback:
    @pytest.mark.asyncio
    async def test_rolls_back_on_sheets_connect_failure(self):
        user = _make_user("alice")
        (
            source_initiator,
            data_manager,
            config_port,
            sheets_initiator,
            cloud_register,
        ) = _create_mocks(unlocked=False, user=user)
        sheets_initiator.connect.side_effect = RuntimeError("sheets failed")

        use_case = UserLoginImpl(
            source_initiator=source_initiator,
            data_manager=data_manager,
            config_port=config_port,
            sheets_initiator=sheets_initiator,
            cloud_register=cloud_register,
        )

        with pytest.raises(RuntimeError, match="sheets failed"):
            await use_case.execute(LoginRequest(username="alice", password="pass"))

        config_port.connect.assert_called_once()
        config_port.disconnect.assert_called_once()
        sheets_initiator.disconnect.assert_called_once()
        data_manager.set_last_user.assert_not_called()
        source_initiator.initialize.assert_not_called()
        cloud_register.connect.assert_not_called()

    @pytest.mark.asyncio
    async def test_rolls_back_on_initialize_failure(self):
        user = _make_user("alice")
        (
            source_initiator,
            data_manager,
            config_port,
            sheets_initiator,
            cloud_register,
        ) = _create_mocks(unlocked=False, user=user)
        source_initiator.initialize.side_effect = RuntimeError("init failed")

        manager = MagicMock()
        manager.attach_mock(source_initiator.initialize, "source_initiator_initialize")
        manager.attach_mock(config_port.disconnect, "config_port_disconnect")

        use_case = UserLoginImpl(
            source_initiator=source_initiator,
            data_manager=data_manager,
            config_port=config_port,
            sheets_initiator=sheets_initiator,
            cloud_register=cloud_register,
        )

        with pytest.raises(RuntimeError, match="init failed"):
            await use_case.execute(LoginRequest(username="alice", password="pass"))

        config_port.connect.assert_called_once()
        sheets_initiator.connect.assert_called_once()
        cloud_register.connect.assert_called_once()
        data_manager.set_last_user.assert_called_once()
        source_initiator.initialize.assert_called_once()
        config_port.disconnect.assert_called_once()
        sheets_initiator.disconnect.assert_called_once()
        cloud_register.disconnect.assert_called_once()

        call_names = [c[0] for c in manager.mock_calls]
        disconnect_idx = call_names.index("config_port_disconnect")
        init_idx = call_names.index("source_initiator_initialize")
        assert disconnect_idx > init_idx


def _build_with_session(source_initiator, data_manager, config_port, sheets, cloud):
    api_session_port = MagicMock()
    api_session_port.create.return_value = "issued-token"
    use_case = UserLoginImpl(
        source_initiator=source_initiator,
        data_manager=data_manager,
        config_port=config_port,
        sheets_initiator=sheets,
        cloud_register=cloud,
        api_session_port=api_session_port,
    )
    return use_case, api_session_port


class TestUserLoginApiSession:
    @pytest.mark.asyncio
    async def test_returns_no_token_without_session_port(self):
        user = _make_user("alice")
        mocks = _create_mocks(unlocked=False, user=user)
        use_case = UserLoginImpl(*mocks)

        result = await use_case.execute(
            LoginRequest(username="alice", password="secret")
        )

        assert result.session_token is None

    @pytest.mark.asyncio
    async def test_unlock_issues_session_token(self):
        user = _make_user("alice")
        mocks = _create_mocks(unlocked=False, user=user)
        use_case, api_session_port = _build_with_session(*mocks)

        result = await use_case.execute(
            LoginRequest(username="alice", password="secret")
        )

        assert result.session_token == "issued-token"
        api_session_port.create.assert_called_once_with(remember=False)

    @pytest.mark.asyncio
    async def test_unlock_forwards_remember_flag(self):
        user = _make_user("alice")
        mocks = _create_mocks(unlocked=False, user=user)
        use_case, api_session_port = _build_with_session(*mocks)

        await use_case.execute(
            LoginRequest(username="alice", password="secret", remember=True)
        )

        api_session_port.create.assert_called_once_with(remember=True)

    @pytest.mark.asyncio
    async def test_failed_unlock_issues_no_token(self):
        user = _make_user("alice")
        mocks = _create_mocks(unlocked=False, user=user)
        mocks[0].initialize.side_effect = RuntimeError("bad key")
        use_case, api_session_port = _build_with_session(*mocks)

        with pytest.raises(RuntimeError):
            await use_case.execute(LoginRequest(username="alice", password="bad"))

        api_session_port.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_already_unlocked_issues_token_after_verifying_password(self):
        user = _make_user("alice")
        mocks = _create_mocks(unlocked=True, user=user)
        source_initiator = mocks[0]
        source_initiator.get_user.return_value = user
        source_initiator.verify_password = AsyncMock(return_value=True)
        use_case, api_session_port = _build_with_session(*mocks)

        result = await use_case.execute(
            LoginRequest(username="alice", password="secret", remember=True)
        )

        assert result.session_token == "issued-token"
        api_session_port.create.assert_called_once_with(remember=True)
        source_initiator.verify_password.assert_awaited_once_with("secret")
        source_initiator.initialize.assert_not_called()
        mocks[2].connect.assert_not_called()

    @pytest.mark.asyncio
    async def test_already_unlocked_rejects_wrong_password(self):
        user = _make_user("alice")
        mocks = _create_mocks(unlocked=True, user=user)
        source_initiator = mocks[0]
        source_initiator.get_user.return_value = user
        source_initiator.verify_password = AsyncMock(return_value=False)
        use_case, api_session_port = _build_with_session(*mocks)

        with pytest.raises(InvalidUserCredentials):
            await use_case.execute(LoginRequest(username="alice", password="wrong"))

        api_session_port.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_already_unlocked_rejects_other_username(self):
        user = _make_user("alice")
        mocks = _create_mocks(unlocked=True, user=user)
        source_initiator = mocks[0]
        source_initiator.get_user.return_value = user
        source_initiator.verify_password = AsyncMock(return_value=True)
        use_case, api_session_port = _build_with_session(*mocks)

        with pytest.raises(InvalidUserCredentials):
            await use_case.execute(LoginRequest(username="bob", password="secret"))

        source_initiator.verify_password.assert_not_called()
        api_session_port.create.assert_not_called()
