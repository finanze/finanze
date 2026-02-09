import asyncio
import logging
from typing import TYPE_CHECKING

from infrastructure.controller.router import Router
from infrastructure.repository.db.capacitor_client import CapacitorDBClient
from infrastructure.repository.db.capacitor_db_manager import CapacitorDBManager
from infrastructure.user_files.capacitor_data_manager import (
    CapacitorSingleUserDataManager,
)
from infrastructure.config.capacitor_server_details_adapter import (
    CapacitorServerDetailsAdapter,
)
from infrastructure.client.features.feature_flag_client import FeatureFlagClient

from domain.platform import OS

from application.use_cases.get_status import GetStatusImpl

if TYPE_CHECKING:
    from finanze.app_deferred import DeferredComponents


class MobileAppCore:
    def __init__(self):
        self.log = logging.getLogger(__name__)
        self._router = Router()
        self.operative_system: OS | None = None
        self._deferred: "DeferredComponents | None" = None
        self._deferred_ready = asyncio.Event()
        self._deferred_loading = False

        self.db_client: CapacitorDBClient | None = None
        self.db_manager: CapacitorDBManager | None = None
        self.data_manager: CapacitorSingleUserDataManager | None = None

        self.status: GetStatusImpl | None = None
        self.ff_client: FeatureFlagClient | None = None

    @property
    def router(self):
        return self._router

    @property
    def deferred(self) -> "DeferredComponents | None":
        return self._deferred

    def is_deferred_ready(self) -> bool:
        return self._deferred_ready.is_set()

    async def wait_deferred(self) -> "DeferredComponents":
        await self._deferred_ready.wait()
        return self._deferred

    async def initialize(self, operative_system: str | None = None):
        self.operative_system = (
            OS(operative_system.upper()) if operative_system else None
        )

        self.db_client = CapacitorDBClient()
        self.db_manager = CapacitorDBManager(self.db_client)
        self.data_manager = CapacitorSingleUserDataManager()

        users = await self.data_manager.get_users()

        server_details = CapacitorServerDetailsAdapter(self.operative_system)
        self.ff_client = FeatureFlagClient(
            users=users, operative_system=server_details.get_os()
        )
        self.status = GetStatusImpl(
            self.db_manager,
            self.data_manager,
            server_details,
            self.ff_client,
        )

        self._setup_core_routes()

        print("MobileApp Core Initialized")

    def _setup_core_routes(self):
        from finanze.mobile_routes import setup_core_routes

        setup_core_routes(self.router, self)

    async def initialize_deferred(self):
        if self._deferred_loading:
            await self._deferred_ready.wait()
            return

        self._deferred_loading = True

        from infrastructure.client.entity.financial.tr.tr_websocket_patch import (
            apply_traderepublic_websocket_patch,
        )

        apply_traderepublic_websocket_patch()

        from finanze.app_deferred import DeferredComponents

        self._deferred = DeferredComponents(self)
        await self._deferred.initialize()
        self._setup_deferred_routes()

        await self.ff_client.load()

        self._deferred_ready.set()
        print("MobileApp Deferred Components Initialized")

    def _setup_deferred_routes(self):
        from finanze.mobile_routes import setup_deferred_routes

        setup_deferred_routes(self.router, self._deferred)
