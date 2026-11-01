import abc
from typing import Optional
from warnings import deprecated

from domain.user import User


@deprecated(
    "Only for migrating settings from pre-database config storage.",
    category=None,
)
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
