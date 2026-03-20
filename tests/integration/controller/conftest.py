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
