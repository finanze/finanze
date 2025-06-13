import abc
from typing import Optional

from domain.user import User, UserRegistration


class DataManager(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def get_last_user(self) -> Optional[User]:
        raise NotImplementedError

    @abc.abstractmethod
    def set_last_user(self, user: User):
        raise NotImplementedError

    @abc.abstractmethod
    def get_users(self) -> list[User]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_user(self, username: str) -> Optional[User]:
        raise NotImplementedError

    @abc.abstractmethod
    def create_user(self, user: UserRegistration) -> User:
        raise NotImplementedError

    @abc.abstractmethod
    def update_user(self, user: User):
        raise NotImplementedError
