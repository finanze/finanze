import abc
from datetime import datetime
from typing import Union, Optional

from domain.global_position import GlobalPosition


class SheetsUpdatePort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def update_summary(
            self,
            global_positions: dict[str, GlobalPosition],
            config: dict):
        raise NotImplementedError

    @abc.abstractmethod
    def update_sheet(
            self,
            data: Union[object, dict[str, object]],
            config: dict,
            last_update: Optional[dict[str, datetime]] = None):
        raise NotImplementedError
