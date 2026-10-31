import abc
from typing import Optional

from domain.external_integration import ExternalIntegrationPayload
from domain.local_model import LocalModelsCapabilities, LocalRouterConnection


class LocalModelRuntime(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def capabilities(self) -> LocalModelsCapabilities:
        raise NotImplementedError

    @abc.abstractmethod
    async def resolve(
        self, credentials: Optional[ExternalIntegrationPayload]
    ) -> LocalRouterConnection:
        raise NotImplementedError

    @abc.abstractmethod
    async def stop(self):
        raise NotImplementedError

    @abc.abstractmethod
    def free_space(self) -> Optional[int]:
        raise NotImplementedError
