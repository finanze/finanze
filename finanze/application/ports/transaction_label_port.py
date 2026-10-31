import abc
from datetime import datetime
from typing import Optional
from uuid import UUID

from domain.fetch_record import DataSource
from domain.transactions import AccountTx, LabelOrigin, TxClassification, TxLabel


class TransactionLabelPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def get_by_tx_ids(self, tx_ids: list[UUID]) -> dict[UUID, list[TxLabel]]:
        raise NotImplementedError

    @abc.abstractmethod
    async def add(self, tx_id: UUID, labels: list[TxLabel]):
        raise NotImplementedError

    @abc.abstractmethod
    async def delete(
        self, tx_ids: list[UUID], origins: Optional[list[LabelOrigin]] = None
    ):
        raise NotImplementedError

    @abc.abstractmethod
    async def delete_by_rule(self, rule_id: UUID):
        raise NotImplementedError

    @abc.abstractmethod
    async def set_locked(self, tx_ids: list[UUID], locked: bool):
        raise NotImplementedError

    @abc.abstractmethod
    async def set_linked_tx(self, tx_id: UUID, linked_tx: Optional[str]):
        raise NotImplementedError

    @abc.abstractmethod
    async def set_external_unmatched(
        self, tx_ids: list[UUID], unmatched_at: Optional[datetime]
    ):
        raise NotImplementedError

    @abc.abstractmethod
    async def get_linked_refs(self, entity_ids: list[UUID]) -> set[tuple[UUID, str]]:
        raise NotImplementedError

    @abc.abstractmethod
    async def add_transfer_pair(
        self, tx_id: UUID, paired_tx_id: UUID, rule_id: Optional[UUID]
    ):
        raise NotImplementedError

    @abc.abstractmethod
    async def delete_transfer_pair(self, tx_id: UUID):
        raise NotImplementedError

    @abc.abstractmethod
    async def delete_transfer_pairs_by_rule(self, rule_id: UUID):
        raise NotImplementedError

    @abc.abstractmethod
    async def delete_unpaired_rule_labels(self, rule_ids: list[UUID]):
        raise NotImplementedError

    @abc.abstractmethod
    async def get_classifications_by_entity_account(
        self, entity_account_id: UUID
    ) -> dict[tuple[UUID, str], TxClassification]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_classifications_by_source(
        self, source: DataSource
    ) -> dict[tuple[UUID, str], TxClassification]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_classifications_by_ids(
        self, tx_ids: list[UUID]
    ) -> dict[UUID, TxClassification]:
        raise NotImplementedError

    @abc.abstractmethod
    async def restore(self, classifications: dict[UUID, TxClassification]):
        raise NotImplementedError

    @abc.abstractmethod
    async def get_examples(
        self, origins: list[LabelOrigin], per_label: int, limit: int
    ) -> list[AccountTx]:
        raise NotImplementedError
