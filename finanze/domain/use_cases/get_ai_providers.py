import abc
from typing import Optional

from domain.ai import AIProviders, AITask


class GetAIProviders(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, task: Optional[AITask]) -> AIProviders:
        raise NotImplementedError
