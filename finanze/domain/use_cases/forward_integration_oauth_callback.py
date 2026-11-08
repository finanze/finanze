import abc
from typing import Optional

from domain.external_integration import ForwardIntegrationOAuthCallbackRequest


class ForwardIntegrationOAuthCallback(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(
        self, request: ForwardIntegrationOAuthCallbackRequest
    ) -> Optional[str]:
        raise NotImplementedError
