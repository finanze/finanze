import abc
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from domain.fetch_record import DataSource
from domain.transactions import (
    AccountTx,
    AccountTxSelection,
    BaseInvestmentTx,
    BaseTx,
    TransactionQueryRequest,
    Transactions,
)


class TransactionPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def save(self, data: Transactions):
        raise NotImplementedError

    @abc.abstractmethod
    async def get_all(
        self,
        real: Optional[bool] = None,
        excluded_entities: Optional[list[UUID]] = None,
    ) -> Transactions:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_refs_by_entity_account(self, entity_account_id: UUID) -> set[str]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_by_entity(self, entity_id: UUID) -> Transactions:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_by_entity_and_source(
        self, entity_id: UUID, source: DataSource
    ) -> Transactions:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_refs_by_source_type(self, real: bool) -> set[str]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_by_filters(self, query: TransactionQueryRequest) -> list[BaseTx]:
        raise NotImplementedError

    @abc.abstractmethod
    async def delete_by_source(self, source: DataSource):
        raise NotImplementedError

    @abc.abstractmethod
    async def delete_by_entity_account_id(self, entity_account_id: UUID):
        raise NotImplementedError

    @abc.abstractmethod
    async def get_by_id(self, tx_id: UUID) -> Optional[BaseTx]:
        raise NotImplementedError

    @abc.abstractmethod
    async def delete_by_id(self, tx_id: UUID):
        raise NotImplementedError

    @abc.abstractmethod
    async def get_account_txs(
        self, selection: AccountTxSelection, limit: Optional[int] = None
    ) -> list[AccountTx]:
        raise NotImplementedError

    @abc.abstractmethod
    async def count_account_txs(self, selection: AccountTxSelection) -> int:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_refs_by_entity(self, entity_id: UUID) -> set[str]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_latest_account_tx_date(self, entity_id: UUID) -> Optional[datetime]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_investment_txs_in_range(
        self, entity_ids: list[UUID], from_date: date, to_date: date
    ) -> list[BaseInvestmentTx]:
        raise NotImplementedError
