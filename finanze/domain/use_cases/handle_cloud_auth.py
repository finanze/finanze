import abc
from domain.cloud_auth import CloudAuthRequest, CloudAuthResponse


class HandleCloudAuth(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, request: CloudAuthRequest) -> CloudAuthResponse:
        raise NotImplementedError
