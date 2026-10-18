import logging
import re

from application.ports.config_port import ConfigPort
from application.ports.data_manager import DataManager
from application.ports.datasource_initiator import DatasourceInitiator
from domain.data_init import DatasourceInitContext, DatasourceInitParams
from domain.exception.exceptions import (
    InvalidPassword,
    UserAlreadyLoggedIn,
    UserNotFound,
)
from domain.use_cases.change_user_password import ChangeUserPassword
from domain.user_login import ChangePasswordRequest

PASSWORD_PATTERN = re.compile(r"^[\x21-\x7e]{8,}$")


class ChangeUserPasswordImpl(ChangeUserPassword):
    def __init__(
        self,
        source_initiator: DatasourceInitiator,
        data_manager: DataManager,
        config_port: ConfigPort,
    ):
        self._source_initiator = source_initiator
        self._data_manager = data_manager
        self._config_port = config_port
        self._log = logging.getLogger(__name__)

    async def execute(self, change_password_request: ChangePasswordRequest):
        if self._source_initiator.unlocked:
            raise UserAlreadyLoggedIn("Cannot change password while logged in.")

        if change_password_request.old_password == change_password_request.new_password:
            raise ValueError("New password must be different from the old password.")

        if not PASSWORD_PATTERN.match(change_password_request.new_password):
            raise InvalidPassword()

        user = await self._data_manager.get_user(change_password_request.username)
        if not user:
            raise UserNotFound()

        params = DatasourceInitParams(
            user=user,
            password=change_password_request.old_password,
            context=DatasourceInitContext(config=self._config_port),
        )
        await self._config_port.connect(user)
        try:
            await self._source_initiator.change_password(
                params, new_password=change_password_request.new_password
            )
        finally:
            await self._config_port.disconnect()
