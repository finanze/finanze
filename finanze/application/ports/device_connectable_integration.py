import abc

from application.ports.connectable_integration import ConnectableIntegration
from domain.external_integration import (
    DeviceAuthorizationPollResult,
    ExternalIntegrationDeviceAuthorization,
    ExternalIntegrationPayload,
)


class DeviceConnectableIntegration(ConnectableIntegration, metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def start_device_authorization(
        self, payload: ExternalIntegrationPayload
    ) -> ExternalIntegrationDeviceAuthorization:
        raise NotImplementedError

    @abc.abstractmethod
    async def poll_device_authorization(
        self, flow_id: str
    ) -> DeviceAuthorizationPollResult:
        raise NotImplementedError
