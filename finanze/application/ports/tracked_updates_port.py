import abc
from datetime import datetime
from typing import Optional


class TrackedUpdatesPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def get_last_executed(self, use_case_name: str) -> Optional[datetime]:
        raise NotImplementedError

    @abc.abstractmethod
    async def update_last_executed(
        self, use_case_name: str, executed_at: datetime
    ) -> None:
        raise NotImplementedError
