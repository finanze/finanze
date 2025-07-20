import logging

from application.ports.data_manager import DataManager
from application.ports.datasource_initiator import DatasourceInitiator
from domain.data_init import DatasourceInitParams
from domain.exception.exceptions import UserAlreadyLoggedIn, UserNotFound
from domain.use_cases.change_user_password import ChangeUserPassword
from domain.user_login import ChangePasswordRequest


class ChangeUserPasswordImpl(ChangeUserPassword):
    def __init__(
        self,
        source_initiator: DatasourceInitiator,
        data_manager: DataManager,
    ):
        self._source_initiator = source_initiator
        self._data_manager = data_manager
        self._log = logging.getLogger(__name__)

    def execute(self, change_password_request: ChangePasswordRequest):
        if self._source_initiator.unlocked:
            raise UserAlreadyLoggedIn("Cannot change password while logged in.")

        if change_password_request.old_password == change_password_request.new_password:
            raise ValueError("New password must be different from the old password.")

        user = self._data_manager.get_user(change_password_request.username)
        if not user:
            raise UserNotFound()

        params = DatasourceInitParams(
            user=user, password=change_password_request.old_password
        )
        self._source_initiator.change_password(
            params, new_password=change_password_request.new_password
        )
