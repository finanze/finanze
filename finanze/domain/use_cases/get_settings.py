import abc
from typing import Optional

from domain.settings import PartialSettings, SettingsSection


class GetSettings(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(
        self, sections: Optional[set[SettingsSection]] = None
    ) -> PartialSettings:
        raise NotImplementedError
