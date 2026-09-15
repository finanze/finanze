import logging
from typing import Optional

from application.ports.cloud_register import CloudRegister
from application.ports.config_port import ConfigPort
from application.ports.datasource_initiator import DatasourceInitiator
from application.ports.error_reporter_port import ErrorReporterPort
from application.ports.sheets_initiator import SheetsInitiator
from domain.use_cases.user_logout import UserLogout


class UserLogoutImpl(UserLogout):
    def __init__(
        self,
        source_initiator: DatasourceInitiator,
        config_port: ConfigPort,
        sheets_initiator: SheetsInitiator,
        cloud_register: CloudRegister,
        error_reporter: Optional[ErrorReporterPort] = None,
    ):
        self._source_initiator = source_initiator
        self._config_port = config_port
        self._sheets_initiator = sheets_initiator
        self._cloud_register = cloud_register
        self._error_reporter = error_reporter
        self._log = logging.getLogger(__name__)

    async def execute(self):
        await self._config_port.disconnect()
        self._sheets_initiator.disconnect()
        await self._cloud_register.disconnect()
        await self._source_initiator.lock()

        if self._error_reporter:
            self._error_reporter.set_user(None)

        self._log.info("User logged out successfully")
