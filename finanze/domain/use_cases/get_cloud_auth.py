import abc
from typing import Optional

from domain.cloud_auth import CloudAuthData


class GetCloudAuth(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self) -> Optional[CloudAuthData]:
        raise NotImplementedError
