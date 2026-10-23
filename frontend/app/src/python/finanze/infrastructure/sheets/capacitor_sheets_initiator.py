import logging
from typing import Optional

from application.ports.sheets_initiator import SheetsInitiator
from domain.exception.exceptions import FeatureNotSupported
from domain.external_integration import (
    CompleteExternalIntegrationConnectionRequest,
    ExternalIntegrationPayload,
)
from domain.user import User


class CapacitorSheetsInitiator(SheetsInitiator):
    def __init__(self):
        self._log = logging.getLogger(__name__)
        self._user: Optional[User] = None
        self._payload: Optional[ExternalIntegrationPayload] = None

    async def setup(self, payload: ExternalIntegrationPayload):
        self._payload = payload

    async def start_authorization(
        self, payload: ExternalIntegrationPayload, completion_url: Optional[str]
    ) -> str:
        raise FeatureNotSupported()

    async def complete_authorization(
        self, request: CompleteExternalIntegrationConnectionRequest
    ) -> ExternalIntegrationPayload:
        raise FeatureNotSupported()

    def connect(self, user: User):
        self._user = user

    def disconnect(self):
        self._user = None
        self._payload = None
