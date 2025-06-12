import logging

from application.ports.data_manager import DataManager
from application.ports.datasource_initiator import DatasourceInitiator
from domain.login import LoginStatus, LoginStatusCode
from domain.use_cases.get_login_status import GetLoginStatus


class GetLoginStatusImpl(GetLoginStatus):
    def __init__(
        self, source_initiator: DatasourceInitiator, data_manager: DataManager
    ):
        self._source_initiator = source_initiator
        self._data_manager = data_manager
        self._log = logging.getLogger(__name__)

    def execute(self) -> LoginStatus:
        status = (
            LoginStatusCode.UNLOCKED
            if self._source_initiator.unlocked
            else LoginStatusCode.LOCKED
        )

        last_logged = self._data_manager.get_last_user()
        if last_logged:
            return LoginStatus(status=status, last_logged=last_logged.username)

        return LoginStatus(status=status)
