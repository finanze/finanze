import abc
from typing import Optional

from domain.cloud_auth import CloudAuthData, CloudAuthToken, CloudAuthTokenData
from domain.user import User


class CloudRegister(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def connect(self, user: User):
        raise NotImplementedError

    @abc.abstractmethod
    def disconnect(self):
        raise NotImplementedError

    @abc.abstractmethod
    def save_auth(self, token: CloudAuthToken):
        raise NotImplementedError

    @abc.abstractmethod
    def get_auth_token(self) -> Optional[CloudAuthToken]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_auth(self) -> Optional[CloudAuthData]:
        raise NotImplementedError

    @abc.abstractmethod
    def clear_auth(self):
        raise NotImplementedError

    @abc.abstractmethod
    def decode_token(self, token: str) -> Optional[CloudAuthTokenData]:
        raise NotImplementedError
