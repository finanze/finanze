import abc
from typing import Optional


class AuthorizeApiAccess(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, token: Optional[str]) -> bool:
        raise NotImplementedError
