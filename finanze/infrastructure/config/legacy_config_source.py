import abc
from typing import Optional

from domain.user import User


class LegacyConfigSource(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def connect(self, user: User):
        raise NotImplementedError

    @abc.abstractmethod
    async def disconnect(self):
        raise NotImplementedError

    @abc.abstractmethod
    async def load(self) -> Optional[dict]:
        raise NotImplementedError
