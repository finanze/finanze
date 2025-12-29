import logging

from application.ports.cloud_register import CloudRegister
from application.ports.config_port import ConfigPort
from application.ports.data_manager import DataManager
from application.ports.datasource_initiator import DatasourceInitiator
from application.ports.sheets_initiator import SheetsInitiator
from domain.data_init import DatasourceInitContext, DatasourceInitParams
from domain.exception.exceptions import UserAlreadyLoggedIn, UserNotFound
from domain.use_cases.user_login import UserLogin
from domain.user_login import LoginRequest


class UserLoginImpl(UserLogin):
    def __init__(
        self,
        source_initiator: DatasourceInitiator,
        data_manager: DataManager,
        config_port: ConfigPort,
        sheets_initiator: SheetsInitiator,
        cloud_register: CloudRegister,
    ):
        self._source_initiator = source_initiator
        self._data_manager = data_manager
        self._config_port = config_port
        self._sheets_initiator = sheets_initiator
        self._cloud_register = cloud_register
        self._log = logging.getLogger(__name__)

    def execute(self, login_request: LoginRequest):
        if self._source_initiator.unlocked:
            raise UserAlreadyLoggedIn()

        user = self._data_manager.get_user(login_request.username)
        if not user:
            raise UserNotFound()

        self._config_port.connect(user)
        try:
            self._sheets_initiator.connect(user)
            self._cloud_register.connect(user)
        except:
            self._config_port.disconnect()
            self._sheets_initiator.disconnect()
            raise

        self._data_manager.set_last_user(user)

        params = DatasourceInitParams(
            user=user,
            password=login_request.password,
            context=DatasourceInitContext(config=self._config_port),
        )
        try:
            self._source_initiator.initialize(params)
        except:
            self._config_port.disconnect()
            self._sheets_initiator.disconnect()
            self._cloud_register.disconnect()
            raise

        self._log.info(
            f"User '{login_request.username} {user.hashed_id()}' ({str(user.id)} - {str(user.path)}) logged in successfully"
        )
