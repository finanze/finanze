import logging

from application.ports.data_manager import DataManager
from application.ports.datasource_initiator import DatasourceInitiator
from application.ports.server_details_port import ServerDetailsPort
from domain.status import GlobalStatus, LoginStatusCode
from domain.use_cases.get_status import GetStatus


class GetStatusImpl(GetStatus):
    def __init__(
        self,
        source_initiator: DatasourceInitiator,
        data_manager: DataManager,
        server_details_port: ServerDetailsPort,
    ):
        self._source_initiator = source_initiator
        self._data_manager = data_manager
        self._server_details_port = server_details_port
        self._log = logging.getLogger(__name__)

    def execute(self) -> GlobalStatus:
        status = (
            LoginStatusCode.UNLOCKED
            if self._source_initiator.unlocked
            else LoginStatusCode.LOCKED
        )

        server_details = self._server_details_port.get_backend_details()

        last_logged = self._data_manager.get_last_user()
        if last_logged:
            return GlobalStatus(
                status=status,
                last_logged=last_logged.username,
                server=server_details,
            )

        return GlobalStatus(status=status, server=server_details)
