import abc
from typing import Optional

from domain.status import GlobalStatus


class GetStatus(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, session_token: Optional[str] = None) -> GlobalStatus:
        raise NotImplementedError
