import logging

from application.ports.datasource_initiator import DatasourceInitiator
from domain.use_cases.user_logout import UserLogout


class UserLogoutImpl(UserLogout):
    def __init__(self, source_initiator: DatasourceInitiator):
        self._source_initiator = source_initiator
        self._log = logging.getLogger(__name__)

    def execute(self):
        self._source_initiator.lock()
