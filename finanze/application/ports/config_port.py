import abc
from typing import Optional

from domain.settings import PartialSettings, Settings, SettingsSection
from domain.user import User


class ConfigPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def connect(self, user: User):
        raise NotImplementedError

    @abc.abstractmethod
    async def disconnect(self):
        raise NotImplementedError

    @abc.abstractmethod
    async def load(self) -> Settings:
        raise NotImplementedError

    @abc.abstractmethod
    async def load_sections(self, sections: set[SettingsSection]) -> PartialSettings:
        raise NotImplementedError

    @abc.abstractmethod
    async def load_legacy(self) -> Optional[dict]:
        raise NotImplementedError

    @abc.abstractmethod
    async def save(self, new_config: Settings | PartialSettings) -> None:
        raise NotImplementedError
