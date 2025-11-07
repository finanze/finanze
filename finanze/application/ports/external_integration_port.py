import abc
from typing import Optional

from domain.external_integration import (
    ExternalIntegration,
    ExternalIntegrationId,
    ExternalIntegrationPayload,
    ExternalIntegrationType,
)


class ExternalIntegrationPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def deactivate(self, integration: ExternalIntegrationId):
        raise NotImplementedError

    @abc.abstractmethod
    def activate(
        self, integration: ExternalIntegrationId, payload: ExternalIntegrationPayload
    ):
        raise NotImplementedError

    @abc.abstractmethod
    def get_payload(
        self, integration: ExternalIntegrationId
    ) -> Optional[ExternalIntegrationPayload]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_payloads_by_type(
        self, integration_type: ExternalIntegrationType
    ) -> dict[ExternalIntegrationId, ExternalIntegrationPayload]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_all(self) -> list[ExternalIntegration]:
        raise NotImplementedError
