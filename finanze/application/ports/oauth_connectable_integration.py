import abc
from typing import Optional

from application.ports.connectable_integration import ConnectableIntegration
from domain.external_integration import (
    CompleteExternalIntegrationConnectionRequest,
    ExternalIntegrationPayload,
)


class OAuthConnectableIntegration(ConnectableIntegration, metaclass=abc.ABCMeta):
    async def setup(self, payload: ExternalIntegrationPayload):
        pass

    @abc.abstractmethod
    async def start_authorization(
        self, payload: ExternalIntegrationPayload, completion_url: Optional[str]
    ) -> str:
        raise NotImplementedError

    @abc.abstractmethod
    async def complete_authorization(
        self, request: CompleteExternalIntegrationConnectionRequest
    ) -> ExternalIntegrationPayload:
        raise NotImplementedError
