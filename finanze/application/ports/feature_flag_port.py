import abc
from typing import Optional

from domain.status import FeatureFlags, FFValue


class FeatureFlagPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def get_all(self) -> FeatureFlags:
        raise NotImplementedError

    @abc.abstractmethod
    def get_value(self, ff_name: str) -> Optional[FFValue]:
        raise NotImplementedError
