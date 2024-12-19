import abc
from datetime import datetime
from typing import Union, Optional

from domain.global_position import GlobalPosition


class SheetsUpdatePort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def update_summary(
            self,
            global_positions: dict[str, GlobalPosition],
            sheet_name: str):
        raise NotImplementedError

    @abc.abstractmethod
    def update_sheet(
            self,
            data: Union[object, dict[str, object]],
            sheet_name: str,
            field_paths: list[str],
            last_update: Optional[dict[str, datetime]] = None):
        raise NotImplementedError
