from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest
from unittest.mock import AsyncMock, MagicMock, PropertyMock

from application.use_cases.register_user import RegisterUserImpl
from domain.user import User
from domain.user_login import LoginRequest


def _make_user(username: str = "testuser") -> User:
    return User(
        id=uuid4(),
        username=username,
        path=Path(f"/data/{username}"),
        last_login=None,
    )


def _create_mocks(unlocked=False, users=None):
    source_initiator = MagicMock()
    type(source_initiator).unlocked = PropertyMock(return_value=unlocked)
    source_initiator.initialize = AsyncMock()

    data_manager = MagicMock()
    data_manager.get_users = AsyncMock(return_value=users if users is not None else [])
    data_manager.create_user = AsyncMock(
        side_effect=lambda user_reg: User(
            id=user_reg.id,
            username=user_reg.username,
            path=Path(f"/data/{user_reg.username}"),
            last_login=datetime.now(),
        )
    )
    data_manager.set_last_user = AsyncMock()

    config_port = MagicMock()
    config_port.connect = AsyncMock()

    sheets_initiator = MagicMock()
    sheets_initiator.connect = MagicMock()

    cloud_register = MagicMock()
    cloud_register.connect = AsyncMock()

    return source_initiator, data_manager, config_port, sheets_initiator, cloud_register


class TestRegisterUserRejection:
    @pytest.mark.asyncio
    async def test_raises_when_source_initiator_is_unlocked(self):
        (
            source_initiator,
            data_manager,
            config_port,
            sheets_initiator,
            cloud_register,
        ) = _create_mocks(unlocked=True)

        use_case = RegisterUserImpl(
            source_initiator=source_initiator,
            data_manager=data_manager,
            config_port=config_port,
            sheets_initiator=sheets_initiator,
            cloud_register=cloud_register,
        )

        with pytest.raises(ValueError, match="Cannot register users while logged in"):
            await use_case.execute(LoginRequest(username="alice", password="pass"))

    @pytest.mark.asyncio
    async def test_raises_when_user_exists_and_multi_user_not_set(self, monkeypatch):
        monkeypatch.delenv("MULTI_USER", raising=False)
        existing_user = _make_user("existing")
        (
            source_initiator,
            data_manager,
            config_port,
            sheets_initiator,
            cloud_register,
        ) = _create_mocks(unlocked=False, users=[existing_user])

        use_case = RegisterUserImpl(
            source_initiator=source_initiator,
            data_manager=data_manager,
            config_port=config_port,
            sheets_initiator=sheets_initiator,
            cloud_register=cloud_register,
        )

        with pytest.raises(ValueError, match="only one user is supported"):
            await use_case.execute(LoginRequest(username="alice", password="pass"))

    @pytest.mark.asyncio
    async def test_raises_when_user_exists_and_multi_user_is_zero(self, monkeypatch):
        monkeypatch.setenv("MULTI_USER", "0")
        existing_user = _make_user("existing")
        (
            source_initiator,
            data_manager,
            config_port,
            sheets_initiator,
            cloud_register,
        ) = _create_mocks(unlocked=False, users=[existing_user])

        use_case = RegisterUserImpl(
            source_initiator=source_initiator,
            data_manager=data_manager,
            config_port=config_port,
            sheets_initiator=sheets_initiator,
            cloud_register=cloud_register,
        )

        with pytest.raises(ValueError, match="only one user is supported"):
            await use_case.execute(LoginRequest(username="alice", password="pass"))


class TestRegisterUserSuccess:
    @pytest.mark.asyncio
    async def test_registers_user_with_no_existing_users(self, monkeypatch):
        monkeypatch.delenv("MULTI_USER", raising=False)
        (
            source_initiator,
            data_manager,
            config_port,
            sheets_initiator,
            cloud_register,
        ) = _create_mocks(unlocked=False, users=[])

        use_case = RegisterUserImpl(
            source_initiator=source_initiator,
            data_manager=data_manager,
            config_port=config_port,
            sheets_initiator=sheets_initiator,
            cloud_register=cloud_register,
        )

        await use_case.execute(LoginRequest(username="alice", password="secret"))

        data_manager.create_user.assert_called_once()
        assert data_manager.create_user.call_args[0][0].username == "alice"

        data_manager.set_last_user.assert_called_once()
        assert data_manager.set_last_user.call_args[0][0].username == "alice"

        config_port.connect.assert_called_once()
        assert config_port.connect.call_args[0][0].username == "alice"

        sheets_initiator.connect.assert_called_once()
        assert sheets_initiator.connect.call_args[0][0].username == "alice"

        cloud_register.connect.assert_called_once()
        assert cloud_register.connect.call_args[0][0].username == "alice"

        source_initiator.initialize.assert_called_once()
        params = source_initiator.initialize.call_args[0][0]
        assert params.user.username == "alice"
        assert params.password == "secret"
        assert params.context.config is config_port

    @pytest.mark.asyncio
    async def test_allows_registration_when_multi_user_enabled(self, monkeypatch):
        monkeypatch.setenv("MULTI_USER", "1")
        existing_user = _make_user("existing")
        (
            source_initiator,
            data_manager,
            config_port,
            sheets_initiator,
            cloud_register,
        ) = _create_mocks(unlocked=False, users=[existing_user])

        use_case = RegisterUserImpl(
            source_initiator=source_initiator,
            data_manager=data_manager,
            config_port=config_port,
            sheets_initiator=sheets_initiator,
            cloud_register=cloud_register,
        )

        await use_case.execute(LoginRequest(username="bob", password="pass"))


class TestRegisterUserCallOrder:
    @pytest.mark.asyncio
    async def test_calls_ports_in_correct_order(self, monkeypatch):
        monkeypatch.delenv("MULTI_USER", raising=False)
        (
            source_initiator,
            data_manager,
            config_port,
            sheets_initiator,
            cloud_register,
        ) = _create_mocks(unlocked=False, users=[])

        manager = MagicMock()
        manager.attach_mock(data_manager.create_user, "data_manager_create_user")
        manager.attach_mock(data_manager.set_last_user, "data_manager_set_last_user")
        manager.attach_mock(config_port.connect, "config_port_connect")
        manager.attach_mock(sheets_initiator.connect, "sheets_initiator_connect")
        manager.attach_mock(cloud_register.connect, "cloud_register_connect")
        manager.attach_mock(source_initiator.initialize, "source_initiator_initialize")

        use_case = RegisterUserImpl(
            source_initiator=source_initiator,
            data_manager=data_manager,
            config_port=config_port,
            sheets_initiator=sheets_initiator,
            cloud_register=cloud_register,
        )

        await use_case.execute(LoginRequest(username="alice", password="secret"))

        call_names = [c[0] for c in manager.mock_calls]
        assert call_names == [
            "data_manager_create_user",
            "data_manager_set_last_user",
            "config_port_connect",
            "sheets_initiator_connect",
            "cloud_register_connect",
            "source_initiator_initialize",
        ]
