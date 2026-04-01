import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

from infrastructure.controller.config import quart
from infrastructure.controller.routes.register_user import register_user
from infrastructure.controller.routes.user_login import user_login
from infrastructure.controller.routes.logout import logout
from infrastructure.controller.routes.change_user_password import change_user_password
from infrastructure.controller.routes.get_status import status
from infrastructure.controller.routes.get_settings import get_settings
from infrastructure.controller.routes.update_settings import update_settings
from infrastructure.controller.routes.add_entity_login import add_entity_login
from infrastructure.controller.routes.fetch_financial_data import fetch_financial_data
from infrastructure.controller.routes.get_backups import get_backups
from infrastructure.controller.routes.upload_backup import upload_backup
from infrastructure.controller.routes.import_backup import import_backup
from infrastructure.controller.routes.connect_crypto_wallet import connect_crypto_wallet
from infrastructure.controller.routes.update_crypto_wallet import update_crypto_wallet
from infrastructure.controller.routes.delete_crypto_wallet import delete_crypto_wallet
from infrastructure.controller.routes.fetch_crypto_data import (
    fetch_crypto_data as fetch_crypto_data_route,
)
from infrastructure.controller.routes.update_position import update_position
from infrastructure.controller.routes.add_manual_transaction import (
    add_manual_transaction,
)
from infrastructure.controller.routes.update_manual_transaction import (
    update_manual_transaction,
)
from infrastructure.controller.routes.delete_manual_transaction import (
    delete_manual_transaction,
)
from infrastructure.controller.routes.update_contributions import update_contributions
from infrastructure.controller.routes.positions import positions as positions_route
from infrastructure.controller.routes.transactions import (
    transactions as transactions_route,
)
from infrastructure.controller.routes.contributions import (
    contributions as contributions_route,
)
from infrastructure.controller.routes.get_available_sources import get_available_sources
from infrastructure.controller.routes.create_real_estate import (
    create_real_estate as create_real_estate_route,
)
from infrastructure.controller.routes.update_real_estate import (
    update_real_estate as update_real_estate_route,
)
from infrastructure.controller.routes.list_real_estate import (
    list_real_estate as list_real_estate_route,
)
from infrastructure.controller.routes.delete_real_estate import (
    delete_real_estate as delete_real_estate_route,
)
from infrastructure.controller.exception_handler import register_exception_handlers

from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.manager import DBManager
from infrastructure.user_files.user_data_manager import UserDataManager
from infrastructure.config.config_loader import ConfigLoader

from application.ports.sheets_initiator import SheetsInitiator
from application.ports.cloud_register import CloudRegister
from application.ports.server_details_port import ServerDetailsPort
from application.ports.feature_flag_port import FeatureFlagPort
from application.ports.credentials_port import CredentialsPort
from application.ports.sessions_port import SessionsPort
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.ports.financial_entity_fetcher import FinancialEntityFetcher
from application.ports.position_port import PositionPort
from application.ports.auto_contributions_port import AutoContributionsPort
from application.ports.transaction_port import TransactionPort
from application.ports.historic_port import HistoricPort
from application.ports.last_fetches_port import LastFetchesPort
from application.ports.crypto_asset_port import CryptoAssetRegistryPort
from application.ports.crypto_price_provider import CryptoAssetInfoProvider
from application.ports.config_port import ConfigPort
from application.ports.backup_local_registry import BackupLocalRegistry
from application.ports.backup_repository import BackupRepository
from application.ports.backup_processor import BackupProcessor
from application.ports.datasource_backup_port import Backupable
from application.ports.datasource_initiator import DatasourceInitiator
from application.ports.public_keychain_loader import PublicKeychainLoader
from application.ports.entity_account_port import EntityAccountPort
from application.ports.crypto_wallet_port import CryptoWalletPort
from application.ports.crypto_entity_fetcher import CryptoEntityFetcher
from application.ports.external_integration_port import ExternalIntegrationPort
from application.ports.public_key_derivation import PublicKeyDerivation
from application.ports.entity_port import EntityPort
from application.ports.external_entity_port import ExternalEntityPort
from application.ports.loan_calculator_port import LoanCalculatorPort
from application.ports.manual_position_data_port import ManualPositionDataPort
from application.ports.virtual_import_registry import VirtualImportRegistry
from application.ports.real_estate_port import RealEstatePort
from application.ports.periodic_flow_port import PeriodicFlowPort
from application.ports.file_storage_port import FileStoragePort
from domain.public_keychain import PublicKeychain

from application.use_cases.register_user import RegisterUserImpl
from application.use_cases.user_login import UserLoginImpl
from application.use_cases.user_logout import UserLogoutImpl
from application.use_cases.change_user_password import ChangeUserPasswordImpl
from application.use_cases.get_status import GetStatusImpl
from application.use_cases.get_settings import GetSettingsImpl
from application.use_cases.update_settings import UpdateSettingsImpl
from application.use_cases.add_entity_credentials import AddEntityCredentialsImpl
from application.use_cases.fetch_financial_data import FetchFinancialDataImpl
from application.use_cases.get_backups import GetBackupsImpl
from application.use_cases.upload_backup import UploadBackupImpl
from application.use_cases.import_backup import ImportBackupImpl
from application.use_cases.connect_crypto_wallet import ConnectCryptoWalletImpl
from application.use_cases.update_crypto_wallet import UpdateCryptoWalletConnectionImpl
from application.use_cases.delete_crypto_wallet import DeleteCryptoWalletConnectionImpl
from application.use_cases.fetch_crypto_data import FetchCryptoDataImpl
from application.use_cases.update_position import UpdatePositionImpl
from application.use_cases.add_manual_transaction import AddManualTransactionImpl
from application.use_cases.update_manual_transaction import UpdateManualTransactionImpl
from application.use_cases.delete_manual_transaction import DeleteManualTransactionImpl
from application.use_cases.update_contributions import UpdateContributionsImpl
from application.use_cases.get_position import GetPositionImpl
from application.use_cases.get_transactions import GetTransactionsImpl
from application.use_cases.get_contributions import GetContributionsImpl
from application.use_cases.get_available_entities import GetAvailableEntitiesImpl
from application.use_cases.create_real_estate import CreateRealEstateImpl
from application.use_cases.update_real_estate import UpdateRealEstateImpl
from application.use_cases.delete_real_estate import DeleteRealEstateImpl
from application.use_cases.list_real_estate import ListRealEstateImpl

from domain.entity import Entity
from domain.backup import BackupFileType
from domain.platform import OS
from domain.status import BackendDetails, BackendOptions


@pytest_asyncio.fixture
async def app(tmp_path):
    db_client = DBClient()
    db_manager = DBManager(db_client)
    data_manager = UserDataManager(str(tmp_path))
    config_loader = ConfigLoader()

    sheets_initiator = MagicMock(spec=SheetsInitiator)

    cloud_register = MagicMock(spec=CloudRegister)
    cloud_register.connect = AsyncMock()
    cloud_register.disconnect = AsyncMock()

    server_details_port = MagicMock(spec=ServerDetailsPort)
    server_details_port.get_backend_details = AsyncMock(
        return_value=BackendDetails(
            version="0.0.0-test",
            platform_type=OS.MACOS,
            options=BackendOptions(),
        )
    )

    feature_flag_port = MagicMock(spec=FeatureFlagPort)
    feature_flag_port.get_all.return_value = {}

    credentials_port = AsyncMock(spec=CredentialsPort)
    sessions_port = AsyncMock(spec=SessionsPort)

    transaction_handler_port = MagicMock(spec=TransactionHandlerPort)
    transaction_ctx = MagicMock()
    transaction_ctx.__aenter__ = AsyncMock(return_value=None)
    transaction_ctx.__aexit__ = AsyncMock(return_value=None)
    transaction_handler_port.start = MagicMock(return_value=transaction_ctx)

    entity_fetchers: dict[Entity, FinancialEntityFetcher] = {}

    position_port = AsyncMock(spec=PositionPort)
    position_port.get_account_iban_index = AsyncMock(return_value={})
    position_port.get_portfolio_name_index = AsyncMock(return_value={})
    auto_contr_port = AsyncMock(spec=AutoContributionsPort)
    transaction_port = AsyncMock(spec=TransactionPort)
    historic_port = AsyncMock(spec=HistoricPort)
    last_fetches_port = AsyncMock(spec=LastFetchesPort)
    crypto_asset_registry_port = AsyncMock(spec=CryptoAssetRegistryPort)
    crypto_asset_info_provider = AsyncMock(spec=CryptoAssetInfoProvider)
    config_port = AsyncMock(spec=ConfigPort)

    backup_local_registry = AsyncMock(spec=BackupLocalRegistry)
    backup_repository = AsyncMock(spec=BackupRepository)
    backup_processor = AsyncMock(spec=BackupProcessor)
    data_initiator = MagicMock(spec=DatasourceInitiator)
    data_initiator.get_hashed_password = AsyncMock(return_value="hashed-password")

    backupable_data = AsyncMock(spec=Backupable)
    backupable_config = AsyncMock(spec=Backupable)
    backupable_ports = {
        BackupFileType.DATA: backupable_data,
        BackupFileType.CONFIG: backupable_config,
    }

    keychain_loader = AsyncMock(spec=PublicKeychainLoader)
    keychain_loader.load = AsyncMock(return_value=PublicKeychain({}))

    entity_account_port = AsyncMock(spec=EntityAccountPort)
    loan_calculator = AsyncMock(spec=LoanCalculatorPort)

    crypto_wallet_port = AsyncMock(spec=CryptoWalletPort)
    crypto_entity_fetchers: dict[Entity, CryptoEntityFetcher] = {}
    external_integration_port = AsyncMock(spec=ExternalIntegrationPort)
    public_key_derivation = MagicMock(spec=PublicKeyDerivation)

    entity_port = AsyncMock(spec=EntityPort)
    entity_port.get_disabled_entities = AsyncMock(return_value=[])
    manual_position_data_port = AsyncMock(spec=ManualPositionDataPort)
    virtual_import_registry = AsyncMock(spec=VirtualImportRegistry)
    external_entity_port = AsyncMock(spec=ExternalEntityPort)
    external_entity_fetchers = {}

    real_estate_port = AsyncMock(spec=RealEstatePort)
    periodic_flow_port = AsyncMock(spec=PeriodicFlowPort)
    file_storage_port = AsyncMock(spec=FileStoragePort)
    file_storage_port.get_url = MagicMock(return_value="/static/real_estate/test.jpg")

    register_user_uc = RegisterUserImpl(
        db_manager, data_manager, config_loader, sheets_initiator, cloud_register
    )
    user_login_uc = UserLoginImpl(
        db_manager, data_manager, config_loader, sheets_initiator, cloud_register
    )
    user_logout_uc = UserLogoutImpl(
        db_manager, config_loader, sheets_initiator, cloud_register
    )
    change_password_uc = ChangeUserPasswordImpl(db_manager, data_manager)
    get_status_uc = GetStatusImpl(
        db_manager, data_manager, server_details_port, feature_flag_port
    )
    get_settings_uc = GetSettingsImpl(config_loader)
    update_settings_uc = UpdateSettingsImpl(config_loader)
    add_entity_credentials_uc = AddEntityCredentialsImpl(
        entity_fetchers,
        credentials_port,
        sessions_port,
        transaction_handler_port,
        keychain_loader,
        entity_account_port,
    )
    fetch_financial_data_uc = FetchFinancialDataImpl(
        position_port,
        auto_contr_port,
        transaction_port,
        historic_port,
        entity_fetchers,
        config_port,
        credentials_port,
        sessions_port,
        last_fetches_port,
        crypto_asset_registry_port,
        crypto_asset_info_provider,
        transaction_handler_port,
        keychain_loader,
        entity_account_port,
        loan_calculator,
    )
    get_backups_uc = GetBackupsImpl(
        backupable_ports,
        backup_repository,
        backup_local_registry,
        cloud_register,
    )
    upload_backup_uc = UploadBackupImpl(
        data_initiator,
        backupable_ports,
        backup_processor,
        backup_repository,
        backup_local_registry,
        cloud_register,
    )
    import_backup_uc = ImportBackupImpl(
        data_initiator,
        backupable_ports,
        backup_processor,
        backup_repository,
        backup_local_registry,
        cloud_register,
    )
    connect_crypto_wallet_uc = ConnectCryptoWalletImpl(
        crypto_wallet_port,
        crypto_entity_fetchers,
        external_integration_port,
        public_key_derivation,
        transaction_handler_port,
    )
    update_crypto_wallet_uc = UpdateCryptoWalletConnectionImpl(crypto_wallet_port)
    delete_crypto_wallet_uc = DeleteCryptoWalletConnectionImpl(crypto_wallet_port)
    fetch_crypto_data_uc = FetchCryptoDataImpl(
        position_port,
        crypto_entity_fetchers,
        crypto_wallet_port,
        crypto_asset_registry_port,
        crypto_asset_info_provider,
        last_fetches_port,
        external_integration_port,
        transaction_handler_port,
        public_key_derivation,
    )
    update_position_uc = UpdatePositionImpl(
        entity_port=entity_port,
        position_port=position_port,
        manual_position_data_port=manual_position_data_port,
        virtual_import_registry=virtual_import_registry,
        crypto_asset_registry_port=crypto_asset_registry_port,
        crypto_asset_info_provider=crypto_asset_info_provider,
        transaction_handler_port=transaction_handler_port,
    )
    add_manual_transaction_uc = AddManualTransactionImpl(
        entity_port,
        transaction_port,
        virtual_import_registry,
        transaction_handler_port,
    )
    update_manual_transaction_uc = UpdateManualTransactionImpl(
        entity_port,
        transaction_port,
        virtual_import_registry,
        transaction_handler_port,
    )
    delete_manual_transaction_uc = DeleteManualTransactionImpl(
        transaction_port,
        virtual_import_registry,
        transaction_handler_port,
    )
    update_contributions_uc = UpdateContributionsImpl(
        entity_port,
        auto_contr_port,
        virtual_import_registry,
        transaction_handler_port,
    )
    get_position_uc = GetPositionImpl(position_port, entity_port)
    get_transactions_uc = GetTransactionsImpl(transaction_port, entity_port)
    get_contributions_uc = GetContributionsImpl(auto_contr_port, entity_port)
    get_available_entities_uc = GetAvailableEntitiesImpl(
        entity_port,
        external_entity_port,
        credentials_port,
        crypto_wallet_port,
        last_fetches_port,
        virtual_import_registry,
        entity_fetchers,
        external_entity_fetchers,
        entity_account_port,
    )
    create_real_estate_uc = CreateRealEstateImpl(
        real_estate_port,
        periodic_flow_port,
        transaction_handler_port,
        file_storage_port,
    )
    update_real_estate_uc = UpdateRealEstateImpl(
        real_estate_port,
        periodic_flow_port,
        transaction_handler_port,
        file_storage_port,
    )
    delete_real_estate_uc = DeleteRealEstateImpl(
        real_estate_port,
        periodic_flow_port,
        transaction_handler_port,
        file_storage_port,
    )
    list_real_estate_uc = ListRealEstateImpl(real_estate_port, position_port)

    static_dir = tmp_path / "static"
    static_dir.mkdir()
    test_app = quart(static_dir)

    register_exception_handlers(test_app)

    @test_app.route("/api/v1/signup", methods=["POST"])
    async def register_user_route():
        return await register_user(register_user_uc)

    @test_app.route("/api/v1/login", methods=["POST"])
    async def user_login_route():
        return await user_login(user_login_uc)

    @test_app.route("/api/v1/logout", methods=["POST"])
    async def logout_route():
        return await logout(user_logout_uc)

    @test_app.route("/api/v1/change-password", methods=["POST"])
    async def change_password_route():
        return await change_user_password(change_password_uc)

    @test_app.route("/api/v1/status", methods=["GET"])
    async def get_status_route():
        return await status(get_status_uc)

    @test_app.route("/api/v1/settings", methods=["GET"])
    async def settings_route():
        return await get_settings(get_settings_uc)

    @test_app.route("/api/v1/settings", methods=["POST"])
    async def update_settings_route():
        return await update_settings(update_settings_uc)

    @test_app.route("/api/v1/entities/login", methods=["POST"])
    async def entity_login_route():
        return await add_entity_login(add_entity_credentials_uc)

    @test_app.route("/api/v1/data/fetch/financial", methods=["POST"])
    async def fetch_financial_data_route():
        return await fetch_financial_data(fetch_financial_data_uc)

    @test_app.route("/api/v1/cloud/backup", methods=["GET"])
    async def get_backups_route():
        return await get_backups(get_backups_uc)

    @test_app.route("/api/v1/cloud/backup/upload", methods=["POST"])
    async def upload_backup_route():
        return await upload_backup(upload_backup_uc)

    @test_app.route("/api/v1/cloud/backup/import", methods=["POST"])
    async def import_backup_route():
        return await import_backup(import_backup_uc)

    @test_app.route("/api/v1/crypto-wallet", methods=["POST"])
    async def connect_crypto_wallet_route():
        return await connect_crypto_wallet(connect_crypto_wallet_uc)

    @test_app.route("/api/v1/crypto-wallet", methods=["PUT"])
    async def update_crypto_wallet_route():
        return await update_crypto_wallet(update_crypto_wallet_uc)

    @test_app.route("/api/v1/crypto-wallet/<wallet_connection_id>", methods=["DELETE"])
    async def delete_crypto_wallet_route(wallet_connection_id: str):
        return await delete_crypto_wallet(delete_crypto_wallet_uc, wallet_connection_id)

    @test_app.route("/api/v1/data/fetch/crypto", methods=["POST"])
    async def fetch_crypto_data_route_handler():
        return await fetch_crypto_data_route(fetch_crypto_data_uc)

    @test_app.route("/api/v1/data/manual/positions", methods=["POST"])
    async def update_position_route():
        return await update_position(update_position_uc)

    @test_app.route("/api/v1/data/manual/transactions", methods=["POST"])
    async def add_manual_transaction_route():
        return await add_manual_transaction(add_manual_transaction_uc)

    @test_app.route("/api/v1/data/manual/transactions/<tx_id>", methods=["PUT"])
    async def update_manual_transaction_route(tx_id: str):
        return await update_manual_transaction(update_manual_transaction_uc, tx_id)

    @test_app.route("/api/v1/data/manual/transactions/<tx_id>", methods=["DELETE"])
    async def delete_manual_transaction_route(tx_id: str):
        return await delete_manual_transaction(delete_manual_transaction_uc, tx_id)

    @test_app.route("/api/v1/data/manual/contributions", methods=["POST"])
    async def update_contributions_route():
        return await update_contributions(update_contributions_uc)

    @test_app.route("/api/v1/positions", methods=["GET"])
    async def get_positions_route():
        return await positions_route(get_position_uc)

    @test_app.route("/api/v1/transactions", methods=["GET"])
    async def get_transactions_route():
        return await transactions_route(get_transactions_uc)

    @test_app.route("/api/v1/contributions", methods=["GET"])
    async def get_contributions_route():
        return await contributions_route(get_contributions_uc)

    @test_app.route("/api/v1/entities", methods=["GET"])
    async def get_available_source_route():
        return await get_available_sources(get_available_entities_uc)

    @test_app.route("/api/v1/real-estate", methods=["GET"])
    async def list_re_route():
        return await list_real_estate_route(list_real_estate_uc)

    @test_app.route("/api/v1/real-estate", methods=["POST"])
    async def create_re_route():
        return await create_real_estate_route(create_real_estate_uc)

    @test_app.route("/api/v1/real-estate", methods=["PUT"])
    async def update_re_route():
        return await update_real_estate_route(update_real_estate_uc)

    @test_app.route("/api/v1/real-estate/<real_estate_id>", methods=["DELETE"])
    async def delete_re_route(real_estate_id: str):
        return await delete_real_estate_route(delete_real_estate_uc, real_estate_id)

    yield (
        test_app,
        db_client,
        entity_fetchers,
        credentials_port,
        sessions_port,
        position_port,
        last_fetches_port,
        transaction_port,
        cloud_register,
        backup_local_registry,
        backup_repository,
        backup_processor,
        backupable_ports,
        data_initiator,
        entity_account_port,
        crypto_wallet_port,
        crypto_entity_fetchers,
        external_integration_port,
        public_key_derivation,
        entity_port,
        manual_position_data_port,
        virtual_import_registry,
        crypto_asset_registry_port,
        crypto_asset_info_provider,
        auto_contr_port,
        external_entity_port,
        loan_calculator,
        real_estate_port,
        periodic_flow_port,
        file_storage_port,
    )

    await db_client.silent_close()


@pytest_asyncio.fixture
async def client(app):
    test_app, *_ = app
    async with test_app.test_client() as c:
        yield c


@pytest_asyncio.fixture
async def db_client(app):
    return app[1]


@pytest_asyncio.fixture
async def entity_fetchers(app):
    return app[2]


@pytest_asyncio.fixture
async def credentials_port(app):
    return app[3]


@pytest_asyncio.fixture
async def sessions_port(app):
    return app[4]


@pytest_asyncio.fixture
async def position_port(app):
    return app[5]


@pytest_asyncio.fixture
async def last_fetches_port(app):
    return app[6]


@pytest_asyncio.fixture
async def transaction_port(app):
    return app[7]


@pytest_asyncio.fixture
async def cloud_register(app):
    return app[8]


@pytest_asyncio.fixture
async def backup_local_registry(app):
    return app[9]


@pytest_asyncio.fixture
async def backup_repository(app):
    return app[10]


@pytest_asyncio.fixture
async def backup_processor(app):
    return app[11]


@pytest_asyncio.fixture
async def backupable_ports(app):
    return app[12]


@pytest_asyncio.fixture
async def data_initiator(app):
    return app[13]


@pytest_asyncio.fixture
async def entity_account_port(app):
    return app[14]


@pytest_asyncio.fixture
async def crypto_wallet_port(app):
    return app[15]


@pytest_asyncio.fixture
async def crypto_entity_fetchers(app):
    return app[16]


@pytest_asyncio.fixture
async def external_integration_port(app):
    return app[17]


@pytest_asyncio.fixture
async def public_key_derivation(app):
    return app[18]


@pytest_asyncio.fixture
async def entity_port(app):
    return app[19]


@pytest_asyncio.fixture
async def manual_position_data_port(app):
    return app[20]


@pytest_asyncio.fixture
async def virtual_import_registry(app):
    return app[21]


@pytest_asyncio.fixture
async def crypto_asset_registry_port(app):
    return app[22]


@pytest_asyncio.fixture
async def crypto_asset_info_provider(app):
    return app[23]


@pytest_asyncio.fixture
async def auto_contr_port(app):
    return app[24]


@pytest_asyncio.fixture
async def external_entity_port(app):
    return app[25]


@pytest_asyncio.fixture
async def loan_calculator(app):
    return app[26]


@pytest_asyncio.fixture
async def real_estate_port(app):
    return app[27]


@pytest_asyncio.fixture
async def periodic_flow_port(app):
    return app[28]


@pytest_asyncio.fixture
async def file_storage_port(app):
    return app[29]
