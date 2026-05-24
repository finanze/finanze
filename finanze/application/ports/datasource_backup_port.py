import abc
from datetime import datetime
from typing import Optional

from domain.user import User


class Backupable(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def export(self) -> bytes:
        raise NotImplementedError

    @abc.abstractmethod
    async def import_data(
        self,
        data: bytes,
        initialize: bool = False,
        user: Optional[User] = None,
        password: Optional[str] = None,
    ):
        raise NotImplementedError

    @abc.abstractmethod
    async def get_last_updated(self) -> datetime:
        raise NotImplementedError
