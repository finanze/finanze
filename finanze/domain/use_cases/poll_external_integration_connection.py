import abc

from domain.external_integration import (
    ExternalIntegrationConnectionPoll,
    PollExternalIntegrationConnectionRequest,
)


class PollExternalIntegrationConnection(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(
        self, request: PollExternalIntegrationConnectionRequest
    ) -> ExternalIntegrationConnectionPoll:
        raise NotImplementedError
