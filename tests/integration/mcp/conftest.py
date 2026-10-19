import asyncio
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, fields
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import httpx2
import pytest_asyncio
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from quart import jsonify

from application.ports.cloud_register import CloudRegister
from application.ports.entity_port import EntityPort
from application.ports.exchange_rate_storage import ExchangeRateStorage
from application.ports.file_storage_port import FileStoragePort
from application.ports.position_port import PositionPort
from application.ports.sheets_initiator import SheetsInitiator
from application.use_cases.authorize_mcp_access import AuthorizeMcpAccessImpl
from application.use_cases.calculate_loan import CalculateLoanImpl
from application.use_cases.create_label import CreateLabelImpl
from application.use_cases.create_real_estate import CreateRealEstateImpl
from application.use_cases.delete_label import DeleteLabelImpl
from application.use_cases.delete_periodic_flow import DeletePeriodicFlowImpl
from application.use_cases.delete_real_estate import DeleteRealEstateImpl
from application.use_cases.get_labels import GetLabelsImpl
from application.use_cases.get_mcp_config import GetMcpConfigImpl
from application.use_cases.get_networth_summary import GetNetworthSummaryImpl
from application.use_cases.get_periodic_flows import GetPeriodicFlowsImpl
from application.use_cases.get_settings import GetSettingsImpl
from application.use_cases.list_real_estate import ListRealEstateImpl
from application.use_cases.regenerate_mcp_token import RegenerateMcpTokenImpl
from application.use_cases.register_user import RegisterUserImpl
from application.use_cases.save_periodic_flow import SavePeriodicFlowImpl
from application.use_cases.update_label import UpdateLabelImpl
from application.use_cases.update_mcp_config import UpdateMcpConfigImpl
from application.use_cases.update_periodic_flow import UpdatePeriodicFlowImpl
from application.use_cases.update_real_estate import UpdateRealEstateImpl
from domain.user_login import LoginRequest
from infrastructure.calculations.loan_calculator import LoanCalculator
from infrastructure.config.file_legacy_config_source import FileLegacyConfigSource
from infrastructure.controller.config import quart
from infrastructure.controller.routes.get_mcp_config import get_mcp_config
from infrastructure.controller.routes.regenerate_mcp_token import (
    regenerate_mcp_token,
)
from infrastructure.controller.routes.update_mcp_config import update_mcp_config
from infrastructure.mcp.gateway import McpGateway
from infrastructure.mcp.server_factory import (
    MCP_PATH,
    build_http_app,
    build_mcp_server,
)
from infrastructure.mcp.use_cases import McpUseCases
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.manager import DBManager
from infrastructure.repository.db.transaction_handler import TransactionHandler
from infrastructure.repository.earnings_expenses.periodic_flow_repository import (
    PeriodicFlowRepository,
)
from infrastructure.repository.labeling.label_repository import LabelRepository
from infrastructure.repository.labeling.labeling_rule_repository import (
    LabelingRuleRepository,
)
from infrastructure.repository.mcp.mcp_config_repository import McpConfigRepository
from infrastructure.repository.real_estate.real_estate_repository import (
    RealEstateRepository,
)
from infrastructure.repository.settings.settings_repository import SettingsRepository
from infrastructure.user_files.user_data_manager import UserDataManager

BASE_URL = "http://finanze.test"
USERNAME = "mcpuser"
PASSWORD = "securePass123"


@dataclass
class McpEnv:
    gateway: McpGateway
    db_manager: DBManager
    ucs: McpUseCases
    position_port: PositionPort

    def http(self, token: Optional[str] = None) -> httpx2.AsyncClient:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=self.gateway),
            base_url=BASE_URL,
            headers=headers,
        )

    @asynccontextmanager
    async def connect(self, token: str):
        async with self.http(token) as http_client:
            transport = streamable_http_client(
                f"{BASE_URL}{MCP_PATH}", http_client=http_client
            )
            async with Client(transport) as client:
                yield client

    async def configure(self, enabled: bool, read_only: bool) -> dict:
        async with self.http() as http_client:
            response = await http_client.put(
                "/api/v1/mcp/config",
                json={"enabled": enabled, "read_only": read_only},
            )
            assert response.status_code == 200
            return response.json()


@pytest_asyncio.fixture
async def mcp_env(tmp_path):
    db_client = DBClient()
    db_manager = DBManager(db_client)
    data_manager = UserDataManager(str(tmp_path))
    config_loader = SettingsRepository(db_client, FileLegacyConfigSource())
    cloud_register = MagicMock(spec=CloudRegister)
    cloud_register.connect = AsyncMock()
    cloud_register.disconnect = AsyncMock()

    await RegisterUserImpl(
        db_manager,
        data_manager,
        config_loader,
        MagicMock(spec=SheetsInitiator),
        cloud_register,
    ).execute(LoginRequest(USERNAME, PASSWORD))

    mcp_config_repo = McpConfigRepository(db_client)
    label_repo = LabelRepository(client=db_client)
    labeling_rule_repo = LabelingRuleRepository(client=db_client)
    periodic_flow_repo = PeriodicFlowRepository(client=db_client)
    real_estate_repo = RealEstateRepository(client=db_client)
    transaction_handler = TransactionHandler(client=db_client)
    position_port = AsyncMock(spec=PositionPort)
    file_storage = AsyncMock(spec=FileStoragePort)
    entity_port = AsyncMock(spec=EntityPort)
    entity_port.get_disabled_entities.return_value = []
    exchange_rate_storage = AsyncMock(spec=ExchangeRateStorage)
    exchange_rate_storage.get.return_value = {}

    real = {
        "get_settings": GetSettingsImpl(config_loader),
        "get_labels": GetLabelsImpl(label_repo),
        "create_label": CreateLabelImpl(label_repo),
        "update_label": UpdateLabelImpl(label_repo),
        "delete_label": DeleteLabelImpl(
            label_repo, labeling_rule_repo, transaction_handler
        ),
        "get_periodic_flows": GetPeriodicFlowsImpl(periodic_flow_repo),
        "save_periodic_flow": SavePeriodicFlowImpl(periodic_flow_repo, label_repo),
        "update_periodic_flow": UpdatePeriodicFlowImpl(periodic_flow_repo, label_repo),
        "delete_periodic_flow": DeletePeriodicFlowImpl(periodic_flow_repo),
        "list_real_estate": ListRealEstateImpl(real_estate_repo, position_port),
        "create_real_estate": CreateRealEstateImpl(
            real_estate_repo, periodic_flow_repo, transaction_handler, file_storage
        ),
        "update_real_estate": UpdateRealEstateImpl(
            real_estate_repo, periodic_flow_repo, transaction_handler, file_storage
        ),
        "delete_real_estate": DeleteRealEstateImpl(
            real_estate_repo, periodic_flow_repo, transaction_handler, file_storage
        ),
        "calculate_loan": CalculateLoanImpl(LoanCalculator()),
        "get_networth_summary": GetNetworthSummaryImpl(
            position_port, entity_port, real_estate_repo, exchange_rate_storage
        ),
    }
    ucs = McpUseCases(
        **{f.name: real.get(f.name) or AsyncMock() for f in fields(McpUseCases)}
    )

    static_dir = tmp_path / "static"
    static_dir.mkdir()
    default_app = quart(static_dir)
    get_mcp_config_uc = GetMcpConfigImpl(mcp_config_repo)
    update_mcp_config_uc = UpdateMcpConfigImpl(mcp_config_repo)
    regenerate_mcp_token_uc = RegenerateMcpTokenImpl(mcp_config_repo)

    @default_app.route("/api/v1/mcp/config", methods=["GET"])
    async def get_mcp_config_route():
        return await get_mcp_config(get_mcp_config_uc)

    @default_app.route("/api/v1/mcp/config", methods=["PUT"])
    async def update_mcp_config_route():
        return await update_mcp_config(update_mcp_config_uc)

    @default_app.route("/api/v1/mcp/config/token", methods=["POST"])
    async def regenerate_mcp_token_route():
        return await regenerate_mcp_token(regenerate_mcp_token_uc)

    @default_app.route("/api/v1/ping", methods=["GET"])
    async def ping_route():
        return jsonify({"pong": True}), 200

    servers = [
        build_mcp_server(ucs, "0.0.0-test", writes_enabled)
        for writes_enabled in (False, True)
    ]
    read_app, full_app = [build_http_app(server) for server in servers]
    gateway = McpGateway(
        default_app,
        read_app,
        full_app,
        AuthorizeMcpAccessImpl(mcp_config_repo, db_manager),
        MCP_PATH,
    )

    ready = asyncio.Event()
    stop = asyncio.Event()

    async def run_session_managers():
        async with AsyncExitStack() as stack:
            for server in servers:
                await stack.enter_async_context(server.session_manager.run())
            ready.set()
            await stop.wait()

    runner = asyncio.create_task(run_session_managers())
    await ready.wait()

    yield McpEnv(
        gateway=gateway, db_manager=db_manager, ucs=ucs, position_port=position_port
    )

    stop.set()
    await runner
    if db_manager.unlocked:
        await db_manager.lock()
