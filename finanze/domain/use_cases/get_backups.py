import abc
from typing import Optional

from domain.backup import FullBackupsInfo, BackupsInfoRequest
from domain.cloud_auth import CloudAuthToken


class GetBackups(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(
        self,
        request: BackupsInfoRequest,
        cloud_token: Optional[CloudAuthToken] = None,
    ) -> FullBackupsInfo:
        raise NotImplementedError
