from typing import Optional

from application.ports.api_session_port import ApiSessionPort
from application.ports.datasource_initiator import DatasourceInitiator
from domain.use_cases.authorize_api_access import AuthorizeApiAccess


class AuthorizeApiAccessImpl(AuthorizeApiAccess):
    def __init__(
        self,
        api_session_port: ApiSessionPort,
        source_initiator: DatasourceInitiator,
    ):
        self._api_session_port = api_session_port
        self._source_initiator = source_initiator

    async def execute(self, token: Optional[str]) -> bool:
        if not self._source_initiator.unlocked:
            return True

        return self._api_session_port.is_valid(token)
