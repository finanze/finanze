from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from domain.data_init import MigrationAheadOfTime
from infrastructure.controller.config import quart
from infrastructure.controller.routes.change_user_password import change_user_password
from infrastructure.controller.routes.register_user import register_user
from infrastructure.controller.routes.user_login import user_login


_MESSAGE = "Database has migrations not present in this version: add_foo"


def _use_case() -> AsyncMock:
    use_case = AsyncMock()
    use_case.execute.side_effect = MigrationAheadOfTime(_MESSAGE)
    return use_case


@pytest.mark.asyncio
async def test_login_returns_service_unavailable():
    app = quart(Path("."))

    async with app.test_request_context(
        "/", method="POST", json={"username": "user", "password": "pass"}
    ):
        response, status = await user_login(_use_case())

    assert status == 503
    assert (await response.get_json())["message"] == _MESSAGE


@pytest.mark.asyncio
async def test_signup_returns_service_unavailable():
    app = quart(Path("."))

    async with app.test_request_context(
        "/", method="POST", json={"username": "user", "password": "pass"}
    ):
        response, status = await register_user(_use_case())

    assert status == 503
    assert (await response.get_json())["message"] == _MESSAGE


@pytest.mark.asyncio
async def test_change_password_returns_service_unavailable():
    app = quart(Path("."))

    async with app.test_request_context(
        "/",
        method="POST",
        json={"username": "user", "oldPassword": "old", "newPassword": "new"},
    ):
        response, status = await change_user_password(_use_case())

    assert status == 503
    assert (await response.get_json())["message"] == _MESSAGE
