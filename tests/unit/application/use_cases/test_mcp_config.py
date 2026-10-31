from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from application.ports.datasource_initiator import DatasourceInitiator
from application.ports.mcp_config_port import McpConfigPort
from application.use_cases.authorize_mcp_access import AuthorizeMcpAccessImpl
from application.use_cases.regenerate_mcp_token import RegenerateMcpTokenImpl
from application.use_cases.update_mcp_config import UpdateMcpConfigImpl
from domain.mcp import (
    McpAccess,
    McpCategoryAccess,
    McpConfig,
    McpToolCategory,
    UpdateMcpConfigRequest,
)


def _port(config: McpConfig):
    port = AsyncMock(spec=McpConfigPort)
    port.get.return_value = config
    return port


def _initiator(unlocked: bool = True):
    initiator = MagicMock(spec=DatasourceInitiator)
    initiator.unlocked = unlocked
    return initiator


class TestUpdateMcpConfig:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("changes", [None, {}])
    async def test_omitted_categories_preserve_preferences(self, changes):
        preferences = {McpToolCategory.CRYPTO: McpCategoryAccess(False, False)}
        port = _port(McpConfig(category_access=preferences))

        config = await UpdateMcpConfigImpl(port).execute(
            UpdateMcpConfigRequest(True, True, changes)
        )

        assert config.category_access == preferences

    @pytest.mark.asyncio
    async def test_partial_categories_merge_without_mutating_current(self):
        current = McpConfig(
            category_access={McpToolCategory.CRYPTO: McpCategoryAccess(False, False)}
        )
        port = _port(current)

        config = await UpdateMcpConfigImpl(port).execute(
            UpdateMcpConfigRequest(
                True, False, {McpToolCategory.BUDGET: McpCategoryAccess(True, False)}
            )
        )

        assert config.category_access == {
            McpToolCategory.CRYPTO: McpCategoryAccess(False, False),
            McpToolCategory.BUDGET: McpCategoryAccess(True, False),
        }
        assert McpToolCategory.BUDGET not in current.category_access

    @pytest.mark.asyncio
    async def test_enabling_generates_token(self):
        port = _port(McpConfig())

        config = await UpdateMcpConfigImpl(port).execute(
            UpdateMcpConfigRequest(enabled=True, read_only=True)
        )

        assert config.enabled is True
        assert config.read_only is True
        assert config.token and len(config.token) >= 32
        port.save.assert_awaited_once_with(config)

    @pytest.mark.asyncio
    async def test_keeps_existing_token(self):
        port = _port(McpConfig(enabled=False, token="existing"))

        config = await UpdateMcpConfigImpl(port).execute(
            UpdateMcpConfigRequest(enabled=True, read_only=False)
        )

        assert config == McpConfig(enabled=True, read_only=False, token="existing")

    @pytest.mark.asyncio
    async def test_disabling_without_token_does_not_generate_one(self):
        port = _port(McpConfig())

        config = await UpdateMcpConfigImpl(port).execute(
            UpdateMcpConfigRequest(enabled=False, read_only=True)
        )

        assert config.token is None


class TestRegenerateMcpToken:
    @pytest.mark.asyncio
    async def test_preserves_category_preferences(self):
        preferences = {McpToolCategory.POSITIONS: McpCategoryAccess(True, False)}
        port = _port(McpConfig(category_access=preferences))

        config = await RegenerateMcpTokenImpl(port).execute()

        assert config.category_access == preferences

    @pytest.mark.asyncio
    async def test_replaces_token_keeping_flags(self):
        port = _port(McpConfig(enabled=True, read_only=False, token="old"))

        config = await RegenerateMcpTokenImpl(port).execute()

        assert config.enabled is True
        assert config.read_only is False
        assert config.token and config.token != "old"
        port.save.assert_awaited_once_with(config)


class TestMcpCategoryAccess:
    def test_defaults_allow_reads_and_writes(self):
        assert McpCategoryAccess() == McpCategoryAccess(True, True)
        assert McpConfig().category_access == {}

    def test_config_defaults_are_independent(self):
        config = McpConfig()
        config.category_access[McpToolCategory.BUDGET] = McpCategoryAccess(False, False)
        assert McpConfig().category_access == {}

    @pytest.mark.parametrize(
        "preferences",
        [
            {"crypto": {"read_enabled": False, "write_enabled": True}},
            {"crypto": {"read_enabled": "false", "write_enabled": False}},
            {"crypto": {"read_enabled": True, "write_enabled": 1}},
            {"essential": {"read_enabled": False, "write_enabled": False}},
            {"unknown": {}},
        ],
    )
    def test_rejects_invalid_preferences(self, preferences):
        with pytest.raises(ValidationError):
            UpdateMcpConfigRequest(True, True, preferences)


class TestAuthorizeMcpAccess:
    @pytest.mark.asyncio
    async def test_locked(self):
        port = _port(McpConfig(enabled=True, token="t"))

        access = await AuthorizeMcpAccessImpl(port, _initiator(False)).execute("t")

        assert access.access == McpAccess.LOCKED
        port.get.assert_not_awaited()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "config",
        [McpConfig(enabled=False, token="t"), McpConfig(enabled=True, token=None)],
    )
    async def test_disabled(self, config):
        access = await AuthorizeMcpAccessImpl(_port(config), _initiator()).execute("t")

        assert access.access == McpAccess.DISABLED

    @pytest.mark.asyncio
    @pytest.mark.parametrize("token", [None, "", "wrong"])
    async def test_unauthorized(self, token):
        port = _port(McpConfig(enabled=True, token="t"))

        access = await AuthorizeMcpAccessImpl(port, _initiator()).execute(token)

        assert access.access == McpAccess.UNAUTHORIZED

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "read_only,expected",
        [(True, McpAccess.READ_ONLY), (False, McpAccess.READ_WRITE)],
    )
    async def test_authorized(self, read_only, expected):
        preferences = {McpToolCategory.CRYPTO: McpCategoryAccess(False, False)}
        port = _port(
            McpConfig(
                enabled=True,
                read_only=read_only,
                token="t",
                category_access=preferences,
            )
        )

        access = await AuthorizeMcpAccessImpl(port, _initiator()).execute("t")

        assert access.access == expected
        assert access.category_access == preferences
        assert not hasattr(access, "token")
        port.get.assert_awaited_once_with()
