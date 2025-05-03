import logging

from application.ports.datasource_initiator import DatasourceInitiator
from domain.login import LoginStatus, LoginStatusCode
from domain.use_cases.get_login_status import GetLoginStatus


class GetLoginStatusImpl(GetLoginStatus):

    def __init__(self, source_initiator: DatasourceInitiator):
        self._source_initiator = source_initiator
        self._log = logging.getLogger(__name__)

    def execute(self) -> LoginStatus:
        status = LoginStatusCode.UNLOCKED if self._source_initiator.unlocked else LoginStatusCode.LOCKED
        return LoginStatus(status=status)
