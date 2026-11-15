import logging
from typing import Optional

from application.ports.api_session_port import ApiSessionPort
from application.ports.cloud_register import CloudRegister
from application.ports.config_port import ConfigPort
from application.ports.data_manager import DataManager
from application.ports.datasource_initiator import DatasourceInitiator
from application.ports.error_reporter_port import ErrorReporterPort
from application.ports.sheets_initiator import SheetsInitiator
from domain.data_init import DatasourceInitContext, DatasourceInitParams
from domain.exception.exceptions import (
    InvalidUserCredentials,
    UserAlreadyLoggedIn,
    UserNotFound,
)
from domain.use_cases.user_login import UserLogin
from domain.user_login import LoginRequest, LoginResult


class UserLoginImpl(UserLogin):
    def __init__(
        self,
        source_initiator: DatasourceInitiator,
        data_manager: DataManager,
        config_port: ConfigPort,
        sheets_initiator: SheetsInitiator,
        cloud_register: CloudRegister,
        error_reporter: Optional[ErrorReporterPort] = None,
        api_session_port: Optional[ApiSessionPort] = None,
    ):
        self._source_initiator = source_initiator
        self._data_manager = data_manager
        self._config_port = config_port
        self._sheets_initiator = sheets_initiator
        self._cloud_register = cloud_register
        self._error_reporter = error_reporter
        self._api_session_port = api_session_port
        self._log = logging.getLogger(__name__)

    async def execute(self, login_request: LoginRequest) -> LoginResult:
        if self._source_initiator.unlocked:
            return await self._start_session(login_request)

        user = await self._data_manager.get_user(login_request.username)
        if not user:
            raise UserNotFound()

        await self._config_port.connect(user)
        try:
            self._sheets_initiator.connect(user)
            await self._cloud_register.connect(user)
        except:
            await self._config_port.disconnect()
            self._sheets_initiator.disconnect()
            raise

        await self._data_manager.set_last_user(user)

        params = DatasourceInitParams(
            user=user,
            password=login_request.password,
            context=DatasourceInitContext(config=self._config_port),
        )
        try:
            await self._source_initiator.initialize(params)
        except:
            await self._config_port.disconnect()
            self._sheets_initiator.disconnect()
            await self._cloud_register.disconnect()
            raise

        if self._error_reporter:
            self._error_reporter.set_user(user.hashed_id())

        self._log.info(
            f"User '{login_request.username} {user.hashed_id()}' ({str(user.id)} - {str(user.path)}) logged in successfully"
        )

        return LoginResult(session_token=self._new_session_token(login_request))

    async def _start_session(self, login_request: LoginRequest) -> LoginResult:
        if self._api_session_port is None:
            raise UserAlreadyLoggedIn()

        current_user = self._source_initiator.get_user()
        if (
            current_user is None
            or current_user.username != login_request.username
            or not await self._source_initiator.verify_password(login_request.password)
        ):
            raise InvalidUserCredentials()

        return LoginResult(session_token=self._new_session_token(login_request))

    def _new_session_token(self, login_request: LoginRequest) -> Optional[str]:
        if self._api_session_port is None:
            return None
        return self._api_session_port.create(remember=login_request.remember)
