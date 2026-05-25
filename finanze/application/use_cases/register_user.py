import logging
import os
import re
from uuid import uuid4

from application.ports.cloud_register import CloudRegister
from application.ports.config_port import ConfigPort
from application.ports.data_manager import DataManager
from application.ports.datasource_initiator import DatasourceInitiator
from application.ports.sheets_initiator import SheetsInitiator
from domain.data_init import DatasourceInitContext, DatasourceInitParams
from domain.exception.exceptions import InvalidPassword, InvalidUsername
from domain.use_cases.register_user import RegisterUser
from domain.user import UserRegistration
from domain.user_login import LoginRequest

USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_\-.$€#]{2,}$")
PASSWORD_PATTERN = re.compile(r"^[\x21-\x7e]{8,}$")


class RegisterUserImpl(RegisterUser):
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

    async def execute(self, login_request: LoginRequest):
        if not USERNAME_PATTERN.match(login_request.username):
            raise InvalidUsername()

        existing_user = await self._data_manager.get_user(login_request.username)
        is_guest_flow = login_request.guest or (
            existing_user is not None and existing_user.guest
        )

        if not is_guest_flow:
            if not login_request.password or not PASSWORD_PATTERN.match(
                login_request.password
            ):
                raise InvalidPassword()

        if self._source_initiator.unlocked:
            raise ValueError("Cannot register users while logged in")

        existing_users = await self._data_manager.get_users()

        if existing_user and existing_user.guest:
            user = existing_user
        else:
            if len(existing_users) > 0 and os.environ.get("MULTI_USER") != "1":
                raise ValueError("Currently, only one user is supported.")

            user_reg = UserRegistration(
                id=uuid4(),
                username=login_request.username,
                guest=login_request.guest,
            )
            user = await self._data_manager.create_user(user_reg)

        await self._data_manager.set_last_user(user)

        await self._config_port.connect(user)
        self._sheets_initiator.connect(user)
        await self._cloud_register.connect(user)

        if login_request.guest:
            self._source_initiator.set_user(user)
            return

        if existing_user and existing_user.guest:
            user.guest = False
            await self._data_manager.update_user(user)

        params = DatasourceInitParams(
            user=user,
            password=login_request.password,
            context=DatasourceInitContext(config=self._config_port),
        )
        await self._source_initiator.initialize(params)
