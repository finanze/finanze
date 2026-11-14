import logging
from typing import Optional

from application.ports.api_session_port import ApiSessionPort
from application.ports.data_manager import DataManager
from application.ports.datasource_initiator import DatasourceInitiator
from application.ports.feature_flag_port import FeatureFlagPort
from application.ports.server_details_port import ServerDetailsPort
from domain.status import GlobalStatus, LoginStatusCode
from domain.use_cases.get_status import GetStatus


class GetStatusImpl(GetStatus):
    def __init__(
        self,
        source_initiator: DatasourceInitiator,
        data_manager: DataManager,
        server_details_port: ServerDetailsPort,
        feature_flag_port: FeatureFlagPort,
        api_session_port: Optional[ApiSessionPort] = None,
    ):
        self._source_initiator = source_initiator
        self._data_manager = data_manager
        self._server_details_port = server_details_port
        self._feature_flag_port = feature_flag_port
        self._api_session_port = api_session_port
        self._log = logging.getLogger(__name__)

    async def execute(self, session_token: Optional[str] = None) -> GlobalStatus:
        unlocked = self._source_initiator.unlocked
        authorized = (
            not unlocked
            or self._api_session_port is None
            or self._api_session_port.is_valid(session_token)
        )
        status = (
            LoginStatusCode.UNLOCKED
            if unlocked and authorized
            else LoginStatusCode.LOCKED
        )

        server_details = await self._server_details_port.get_backend_details()
        features = self._feature_flag_port.get_all()

        last_logged = await self._data_manager.get_last_user()
        current_user = self._source_initiator.get_user() if authorized else None
        return GlobalStatus(
            status=status,
            last_logged=last_logged.username if last_logged else None,
            server=server_details,
            features=features,
            user=current_user,
            pending_register=last_logged.guest if last_logged else False,
        )
