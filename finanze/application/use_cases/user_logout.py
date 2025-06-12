import logging

from application.ports.config_port import ConfigPort
from application.ports.datasource_initiator import DatasourceInitiator
from application.ports.sheets_initiator import SheetsInitiator
from domain.use_cases.user_logout import UserLogout


class UserLogoutImpl(UserLogout):
    def __init__(
        self,
        source_initiator: DatasourceInitiator,
        config_port: ConfigPort,
        sheets_initiator: SheetsInitiator,
    ):
        self._source_initiator = source_initiator
        self._config_port = config_port
        self._sheets_initiator = sheets_initiator
        self._log = logging.getLogger(__name__)

    def execute(self):
        self._config_port.disconnect()
        self._sheets_initiator.disconnect()
        self._source_initiator.lock()
