import logging

from application.ports.config_port import ConfigPort
from application.ports.data_manager import DataManager
from application.ports.datasource_initiator import DatasourceInitiator
from application.ports.sheets_initiator import SheetsInitiator
from domain.data_init import DatasourceInitParams
from domain.exception.exceptions import UserNotFound
from domain.use_cases.user_login import UserLogin
from domain.user_login import LoginRequest


class UserLoginImpl(UserLogin):
    def __init__(
        self,
        source_initiator: DatasourceInitiator,
        data_manager: DataManager,
        config_port: ConfigPort,
        sheets_initiator: SheetsInitiator,
    ):
        self._source_initiator = source_initiator
        self._data_manager = data_manager
        self._config_port = config_port
        self._sheets_initiator = sheets_initiator
        self._log = logging.getLogger(__name__)

    def execute(self, login_request: LoginRequest):
        if self._source_initiator.unlocked:
            raise ValueError("Already logged in")

        user = self._data_manager.get_user(login_request.username)
        if not user:
            raise UserNotFound()

        self._data_manager.set_last_user(user)

        self._config_port.connect(user)
        self._sheets_initiator.connect(user)
        params = DatasourceInitParams(user=user, password=login_request.password)
        self._source_initiator.initialize(params)
