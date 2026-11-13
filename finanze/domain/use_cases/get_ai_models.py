import abc
from typing import Optional

from domain.ai import AIModels, AITask


class GetAIModels(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, provider_id: str, task: Optional[AITask]) -> AIModels:
        raise NotImplementedError
