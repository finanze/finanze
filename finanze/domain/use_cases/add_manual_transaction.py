import abc
from typing import Optional
from uuid import UUID

from domain.transactions import BaseTx


class AddManualTransaction(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(
        self, tx: BaseTx, historic_entry_id: Optional[UUID] = None
    ) -> UUID:
        raise NotImplementedError
