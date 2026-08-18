import logging

from application.ports.exchange_rate_provider import ExchangeRateProvider
from domain.exchange_rate import ExchangeRates
from domain.platform import OS
from domain.user import User


class StorageBackedExchangeRateProvider(ExchangeRateProvider):
    """Serves fiat exchange rates from the shared Preferences storage that the
    main worker keeps fresh (GetExchangeRatesImpl). The background worker never
    performs the FX HTTP fetch itself."""

    def __init__(self, storage):
        self._storage = storage

    async def get_available_currencies(self, **kwargs) -> dict[str, str]:
        return {}

    async def get_matrix(self, **kwargs) -> ExchangeRates:
        return await self._storage.get()


class MobileBackgroundApp:
    """Composition root for the second Pyodide worker. Wires only the
    dependencies needed by the tracked quote/loan update use cases and binds
    them to the shared SQLite connection opened by the main worker."""

    DB_NAME = "data.db"

    def __init__(self):
        self.log = logging.getLogger(__name__)
        self.operative_system: OS | None = None

        self.db_client = None
        self.data_manager = None
        self.ex_storage = None

        self.up_tracked = None
        self.up_tracked_loans = None
        self.get_networth_timeline_uc = None
        self.get_gains_timeline_uc = None

        self._connected = False
        self._user: User | None = None
        self._db_name: str | None = None

    async def initialize(self, operative_system: str | None = None):
        from finanze.logs import configure_logging

        configure_logging()

        self.operative_system = (
            OS(operative_system.upper()) if operative_system else None
        )

        from domain import position_aggregation

        position_aggregation.add_extensions()

        from infrastructure.client.http.httpx_patch import apply_httpx_patch
        from infrastructure.repository.db.capacitor_client import CapacitorDBClient
        from infrastructure.user_files.capacitor_data_manager import (
            CapacitorSingleUserDataManager,
        )
        from infrastructure.file_storage.preference_exchange_storage import (
            PreferenceExchangeRateStorage,
        )
        from infrastructure.client.instrument.instrument_provider_adapter import (
            InstrumentProviderAdapter,
        )
        from infrastructure.repository.position.position_repository import (
            PositionSQLRepository as PositionRepository,
        )
        from infrastructure.repository.position.manual_position_data_repository import (
            ManualPositionDataSQLRepository,
        )
        from infrastructure.repository.virtual.virtual_import_repository import (
            VirtualImportRepository,
        )
        from infrastructure.repository.real_estate.real_estate_repository import (
            RealEstateRepository,
        )
        from infrastructure.repository.tracked_updates.tracked_updates_repository import (
            TrackedUpdatesRepository,
        )
        from infrastructure.repository.entity.entity_repository import (
            EntitySQLRepository as EntityRepository,
        )
        from infrastructure.repository.networth_timeline.networth_timeline_repository import (
            NetworthTimelineSQLRepository,
        )
        from infrastructure.repository.gains_timeline.gains_timeline_repository import (
            GainsTimelineSQLRepository,
        )
        from infrastructure.repository.instrument_history.instrument_price_history_repository import (
            InstrumentPriceHistorySQLRepository,
        )
        from infrastructure.client.rates.metal.historic_metal_price_client import (
            HistoricMetalPriceClient,
        )
        from infrastructure.repository.db.transaction_handler import TransactionHandler
        from infrastructure.calculations.loan_calculator import LoanCalculator
        from finanze.build_config import INCLUDE_CONNECTIONS
        from application.use_cases.manual_position_snapshot import (
            ManualPositionSnapshotWriter,
        )
        from application.use_cases.update_tracked_quotes import UpdateTrackedQuotesImpl
        from application.use_cases.update_tracked_loans import UpdateTrackedLoansImpl
        from application.use_cases.get_networth_timeline import (
            GetNetworthTimelineImpl,
        )
        from application.use_cases.get_gains_timeline import GetGainsTimelineImpl

        apply_httpx_patch()

        self.db_client = CapacitorDBClient()
        self.data_manager = CapacitorSingleUserDataManager()
        self.ex_storage = PreferenceExchangeRateStorage()

        position_repo = PositionRepository(client=self.db_client)
        manual_repo = ManualPositionDataSQLRepository(client=self.db_client)
        virtual_repo = VirtualImportRepository(client=self.db_client)
        re_repo = RealEstateRepository(client=self.db_client)
        throttle_repo = TrackedUpdatesRepository(client=self.db_client)
        entity_repo = EntityRepository(client=self.db_client)
        networth_repo = NetworthTimelineSQLRepository(client=self.db_client)
        gains_timeline_repo = GainsTimelineSQLRepository(client=self.db_client)
        instrument_history_repo = InstrumentPriceHistorySQLRepository(
            client=self.db_client
        )
        tx_handler = TransactionHandler(client=self.db_client)
        loan_calculator = LoanCalculator()
        inst_provider = InstrumentProviderAdapter(
            enabled_clients=(
                (["ft"] if INCLUDE_CONNECTIONS else [])
                + ["yf", "finect", "jeh", "tv", "ee", "le"]
            )
        )
        historic_metal_client = HistoricMetalPriceClient()

        ex_provider = StorageBackedExchangeRateProvider(self.ex_storage)

        snapshot_writer = ManualPositionSnapshotWriter(
            position_repo,
            manual_repo,
            virtual_repo,
            re_repo,
            loan_calculator,
        )

        self.up_tracked = UpdateTrackedQuotesImpl(
            position_repo,
            manual_repo,
            inst_provider,
            ex_provider,
            self.ex_storage,
            virtual_repo,
            snapshot_writer,
            throttle_repo,
            tx_handler,
        )
        self.up_tracked_loans = UpdateTrackedLoansImpl(
            position_repo,
            manual_repo,
            loan_calculator,
            snapshot_writer,
            throttle_repo,
            tx_handler,
        )
        self.get_networth_timeline_uc = GetNetworthTimelineImpl(
            networth_repo,
            self.ex_storage,
            entity_repo,
            re_repo,
            historic_metal_client,
        )
        self.get_gains_timeline_uc = GetGainsTimelineImpl(
            gains_timeline_repo,
            self.ex_storage,
            entity_repo,
            historic_metal_client,
            inst_provider,
            instrument_history_repo,
        )

        await self.ex_storage.initialize()

    async def connect(self, username: str | None = None):
        """Attach to the already-open shared SQLite connection. The main worker
        owns the connection lifecycle (open/migrations/rekey); the background
        worker only binds its client to it."""
        import js

        if self._connected:
            return

        user = await self.data_manager.get_last_user()
        if user is None:
            raise RuntimeError("No active user; cannot connect background worker")

        if username and user.username != username:
            self.log.warning(
                "Background worker user mismatch (expected %s, found %s)",
                username,
                user.username,
            )

        db_name = f"{user.hashed_id()}_{self.DB_NAME}"

        connection = await js.jsBridge.sqlite.openDatabase(db_name)

        self.db_client.set_connection(connection)
        self._user = user
        self._db_name = db_name
        self._connected = True
        self.log.info("Background worker connected to shared DB %s", db_name)

    async def disconnect(self):
        """Drop the local connection reference. NEVER closes the native
        connection (owned by the main worker)."""
        if not self._connected:
            return
        self.db_client.set_connection(None)
        self._connected = False
        self._user = None
        self._db_name = None
        self.log.info("Background worker disconnected from shared DB")

    @property
    def connected(self) -> bool:
        return self._connected

    async def update_quotes(self) -> dict:
        if not self._connected:
            raise RuntimeError("Background worker not connected")
        await self.ex_storage.initialize()
        result = await self.up_tracked.execute()
        return self._serialize_result(result)

    async def update_loans(self) -> dict:
        if not self._connected:
            raise RuntimeError("Background worker not connected")
        result = await self.up_tracked_loans.execute()
        return self._serialize_result(result)

    async def get_networth_timeline(
        self,
        base_currency: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        no_calculation: bool = False,
    ) -> dict:
        from datetime import date
        from domain.networth_timeline import NetworthTimelineQuery

        if not self._connected:
            raise RuntimeError("Background worker not connected")
        await self.ex_storage.initialize()

        query = NetworthTimelineQuery(
            base_currency=base_currency or "EUR",
            from_date=date.fromisoformat(from_date) if from_date else None,
            to_date=date.fromisoformat(to_date) if to_date else None,
            no_calculation=no_calculation,
        )
        result = await self.get_networth_timeline_uc.execute(query)
        return self._serialize_timeline(result)

    async def get_gains_timeline(self, query: dict | None = None) -> dict:
        from datetime import date
        from uuid import UUID

        from domain.gains_timeline import (
            FixedIncomeAccrual,
            GainsAssetFilter,
            GainsCalculationMode,
            GainsTimelineQuery,
        )
        from domain.global_position import EquityType, ProductType

        if not self._connected:
            raise RuntimeError("Background worker not connected")
        await self.ex_storage.initialize()

        payload = query or {}
        assets = [
            GainsAssetFilter(
                product_type=ProductType(asset["product_type"]),
                asset_keys=asset.get("asset_keys", []),
                portfolio_names=asset.get("portfolio_names", []),
                equity_types=[
                    EquityType(equity_type)
                    for equity_type in asset.get("equity_types", [])
                ],
                wallet_ids=[
                    UUID(wallet_id) for wallet_id in asset.get("wallet_ids", [])
                ],
            )
            for asset in payload.get("assets", [])
        ]
        result = await self.get_gains_timeline_uc.execute(
            GainsTimelineQuery(
                assets=assets,
                base_currency=payload.get("base_currency") or "EUR",
                entities=[UUID(entity_id) for entity_id in payload.get("entities", [])]
                or None,
                from_date=(
                    date.fromisoformat(payload["from_date"])
                    if payload.get("from_date")
                    else None
                ),
                to_date=(
                    date.fromisoformat(payload["to_date"])
                    if payload.get("to_date")
                    else None
                ),
                accrue_fixed_income=FixedIncomeAccrual(
                    payload.get("accrue_fixed_income", FixedIncomeAccrual.NONE.value)
                ),
                calculation_mode=GainsCalculationMode(
                    payload.get("calculation_mode", GainsCalculationMode.HYBRID.value)
                ),
            )
        )
        return self._serialize_gains_timeline(result)

    @staticmethod
    def _serialize_timeline(result) -> dict:
        return {
            "currency": result.currency,
            "points": [
                {
                    "date": point.date.isoformat(),
                    "total": float(point.total),
                    "breakdown": {
                        key: float(value) for key, value in point.breakdown.items()
                    },
                }
                for point in result.points
            ],
        }

    @staticmethod
    def _serialize_gains_timeline(result) -> dict:
        def serialize_metrics(metrics) -> dict:
            def number(value):
                return float(value) if value is not None else None

            return {
                "value": float(metrics.value),
                "cost_basis": float(metrics.cost_basis),
                "net_contributions": float(metrics.net_contributions),
                "gain": number(metrics.gain),
                "period_return": number(metrics.period_return),
                "index": number(metrics.index),
            }

        return {
            "currency": result.currency,
            "method": result.method.value,
            "basis": result.basis.value,
            "quality": result.quality.value,
            "basis_status": result.basis_status.value,
            "xirr": float(result.xirr) if result.xirr is not None else None,
            "annualized_xirr": (
                float(result.annualized_xirr)
                if result.annualized_xirr is not None
                else None
            ),
            "opening_value": (
                float(result.opening_value)
                if result.opening_value is not None
                else None
            ),
            "warnings": result.warnings,
            "not_applicable_reasons": result.not_applicable_reasons,
            "points": [
                {
                    "date": point.date.isoformat(),
                    **serialize_metrics(point.metrics),
                    "breakdown": {
                        product_type: serialize_metrics(metrics)
                        for product_type, metrics in point.breakdown.items()
                    },
                }
                for point in result.points
            ],
        }

    @staticmethod
    def _serialize_result(result) -> dict:
        return {
            "hadTracked": result.had_tracked,
            "changed": result.changed,
            "changedEntities": [str(eid) for eid in result.changed_entities],
            "throttled": result.throttled,
        }
