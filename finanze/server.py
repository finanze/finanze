import argparse
import logging

import domain.native_entities
from application.use_cases.add_entity_credentials import AddEntityCredentialsImpl
from application.use_cases.disconnect_entity import DisconnectEntityImpl
from application.use_cases.get_available_entities import GetAvailableEntitiesImpl
from application.use_cases.get_contributions import GetContributionsImpl
from application.use_cases.get_exchange_rates import GetExchangeRatesImpl
from application.use_cases.get_login_status import GetLoginStatusImpl
from application.use_cases.get_position import GetPositionImpl
from application.use_cases.get_settings import GetSettingsImpl
from application.use_cases.get_transactions import GetTransactionsImpl
from application.use_cases.register_user import RegisterUserImpl
from application.use_cases.fetch_financial_data import FetchFinancialDataImpl
from application.use_cases.update_settings import UpdateSettingsImpl
from application.use_cases.update_sheets import UpdateSheetsImpl
from application.use_cases.user_login import UserLoginImpl
from application.use_cases.user_logout import UserLogoutImpl
from application.use_cases.virtual_fetch import VirtualFetchImpl
from domain.data_init import DatasourceInitParams
from infrastructure.client.currency.exchange_rate_client import ExchangeRateClient
from infrastructure.client.entity.f24.f24_fetcher import F24Fetcher
from infrastructure.client.entity.indexa_capital.indexa_capital_fetcher import (
    IndexaCapitalFetcher,
)
from infrastructure.client.entity.mintos.mintos_fetcher import MintosFetcher
from infrastructure.client.entity.myinvestor import MyInvestorScraper
from infrastructure.client.entity.sego.sego_fetcher import SegoFetcher
from infrastructure.client.entity.tr.trade_republic_fetcher import TradeRepublicFetcher
from infrastructure.client.entity.unicaja.unicaja_fetcher import UnicajaFetcher
from infrastructure.client.entity.urbanitae.urbanitae_fetcher import UrbanitaeFetcher
from infrastructure.client.entity.wecity.wecity_fetcher import WecityFetcher
from infrastructure.config.config_loader import ConfigLoader
from infrastructure.controller.config import flask
from infrastructure.controller.controllers import register_routes
from infrastructure.credentials.credentials_reader import CredentialsReader
from infrastructure.repository import (
    AutoContributionsRepository,
    EntityRepository,
    HistoricRepository,
    PositionRepository,
    TransactionRepository,
)
from infrastructure.repository.credentials.credentials_repository import (
    CredentialsRepository,
)
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.manager import DBManager
from infrastructure.repository.db.transaction_handler import TransactionHandler
from infrastructure.repository.sessions.sessions_repository import SessionsRepository
from infrastructure.repository.virtual.virtual_import_repository import (
    VirtualImportRepository,
)
from infrastructure.sheets.exporter.sheets_exporter import SheetsExporter
from infrastructure.sheets.importer.sheets_importer import SheetsImporter
from infrastructure.sheets.sheets_service_loader import SheetsServiceLoader
from infrastructure.user_files.user_data_manager import UserDataManager
from waitress import serve


class FinanzeServer:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self._log = logging.getLogger(__name__)

        self._log.info("Initializing components...")

        self.db_client = DBClient()
        self.db_manager = DBManager(self.db_client)
        self.data_manager = UserDataManager(self.args.data_dir)

        self.config_loader = ConfigLoader()
        self.sheets_initiator = SheetsServiceLoader()

        self.entity_fetchers = {
            domain.native_entities.MY_INVESTOR: MyInvestorScraper(),
            domain.native_entities.TRADE_REPUBLIC: TradeRepublicFetcher(),
            domain.native_entities.UNICAJA: UnicajaFetcher(),
            domain.native_entities.URBANITAE: UrbanitaeFetcher(),
            domain.native_entities.WECITY: WecityFetcher(),
            domain.native_entities.SEGO: SegoFetcher(),
            domain.native_entities.MINTOS: MintosFetcher(),
            domain.native_entities.F24: F24Fetcher(),
            domain.native_entities.INDEXA_CAPITAL: IndexaCapitalFetcher(),
        }

        self.virtual_fetcher = SheetsImporter(self.sheets_initiator)
        self.exporter = SheetsExporter(self.sheets_initiator)

        position_repository = PositionRepository(client=self.db_client)
        auto_contrib_repository = AutoContributionsRepository(client=self.db_client)
        transaction_repository = TransactionRepository(client=self.db_client)
        historic_repository = HistoricRepository(client=self.db_client)
        entity_repository = EntityRepository(client=self.db_client)
        sessions_port = SessionsRepository(client=self.db_client)
        virtual_import_repository = VirtualImportRepository(client=self.db_client)
        exchange_rate_client = ExchangeRateClient()

        credentials_storage_mode = self.args.credentials_storage_mode
        if credentials_storage_mode == "DB":
            credentials_port = CredentialsRepository(client=self.db_client)
        elif credentials_storage_mode == "ENV":
            credentials_port = CredentialsReader()
        else:
            raise ValueError(
                f"Invalid credentials storage mode: {credentials_storage_mode}"
            )

        transaction_handler = TransactionHandler(client=self.db_client)

        user_login = UserLoginImpl(
            self.db_manager,
            self.data_manager,
            self.config_loader,
            self.sheets_initiator,
        )
        register_user = RegisterUserImpl(
            self.db_manager,
            self.data_manager,
            self.config_loader,
            self.sheets_initiator,
        )
        get_login_status = GetLoginStatusImpl(self.db_manager, self.data_manager)
        user_logout = UserLogoutImpl(
            self.db_manager, self.config_loader, self.sheets_initiator
        )

        get_available_entities = GetAvailableEntitiesImpl(
            self.config_loader, credentials_port
        )
        fetch_financial_data = FetchFinancialDataImpl(
            position_repository,
            auto_contrib_repository,
            transaction_repository,
            historic_repository,
            self.entity_fetchers,
            self.config_loader,
            credentials_port,
            sessions_port,
            transaction_handler,
        )
        update_sheets = UpdateSheetsImpl(
            position_repository,
            auto_contrib_repository,
            transaction_repository,
            historic_repository,
            self.exporter,
            self.config_loader,
        )
        virtual_fetch = VirtualFetchImpl(
            position_repository,
            transaction_repository,
            self.virtual_fetcher,
            entity_repository,
            self.config_loader,
            virtual_import_repository,
            transaction_handler,
        )
        add_entity_credentials = AddEntityCredentialsImpl(
            self.entity_fetchers, credentials_port, sessions_port, transaction_handler
        )
        disconnect_entity = DisconnectEntityImpl(
            credentials_port, sessions_port, transaction_handler
        )
        get_settings = GetSettingsImpl(self.config_loader)
        update_settings = UpdateSettingsImpl(self.config_loader)
        get_entities_position = GetPositionImpl(position_repository)
        get_contributions = GetContributionsImpl(auto_contrib_repository)
        get_transactions = GetTransactionsImpl(transaction_repository)
        get_exchange_rates = GetExchangeRatesImpl(exchange_rate_client)

        self._log.info("Initial component setup completed.")

        if args.logged_username and args.logged_password:
            self._log.info("User provided, initializing data...")
            user = self.data_manager.get_user(args.logged_username)
            if user:
                self.sheets_initiator.connect(user)
                self.config_loader.connect(user)
                self.db_manager.initialize(
                    DatasourceInitParams(user, args.logged_password)
                )
            else:
                self._log.warning(
                    f"User {args.logged_username} not found in the data directory."
                )

        self._log.info("Setting up REST API...")

        self.flask_app = flask()
        register_routes(
            self.flask_app,
            user_login,
            register_user,
            get_available_entities,
            fetch_financial_data,
            update_sheets,
            virtual_fetch,
            add_entity_credentials,
            get_login_status,
            user_logout,
            get_settings,
            update_settings,
            disconnect_entity,
            get_entities_position,
            get_contributions,
            get_transactions,
            get_exchange_rates,
        )
        self._log.info("Completed.")

    def run(self):
        self._log.info(f"Starting Finanze server on port {self.args.port}...")
        try:
            serve(self.flask_app, host="0.0.0.0", port=self.args.port)
        except OSError as e:
            self._log.error(f"Could not start server on port {self.args.port}: {e}")
            # Handle specific errors like EADDRINUSE if needed
            raise
        except Exception:
            self._log.exception(
                "An unexpected error occurred while running the server."
            )
            raise
        finally:
            self._log.info("Finanze server shutting down.")
            if self.db_client:
                if self.db_client.silent_close():
                    self._log.info("Database connection closed.")
