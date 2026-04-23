import abc
import datetime
from typing import Optional
from uuid import UUID

from domain.dezimal import Dezimal
from domain.entity import Entity
from domain.fetch_record import DataSource
from domain.global_position import (
    FundDetail,
    GlobalPosition,
    Loan,
    PositionQueryRequest,
    ProductType,
    StockDetail,
)


class PositionPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def save(self, position: GlobalPosition):
        raise NotImplementedError

    @abc.abstractmethod
    async def get_last_grouped_by_entity(
        self, query: Optional[PositionQueryRequest] = None
    ) -> dict[Entity, GlobalPosition]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_last_by_entity_broken_down(
        self, query: Optional[PositionQueryRequest] = None
    ) -> dict[Entity, list[GlobalPosition]]:
        raise NotImplementedError

    @abc.abstractmethod
    async def delete_position_for_date(
        self, entity_id: UUID, date: datetime.date, source: DataSource
    ):
        raise NotImplementedError

    @abc.abstractmethod
    async def get_by_id(self, position_id: UUID) -> Optional[GlobalPosition]:
        raise NotImplementedError

    @abc.abstractmethod
    async def delete_by_id(self, position_id: UUID):
        raise NotImplementedError

    @abc.abstractmethod
    async def get_stock_detail(self, entry_id: UUID) -> Optional[StockDetail]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_fund_detail(self, entry_id: UUID) -> Optional[FundDetail]:
        raise NotImplementedError

    @abc.abstractmethod
    async def update_market_value(
        self, entry_id: UUID, product_type: ProductType, market_value: Dezimal
    ):
        raise NotImplementedError

    @abc.abstractmethod
    async def get_loans_by_hash(self, hashes: list[str]) -> dict[str, Loan]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_loan_by_entry_id(self, entry_id: UUID) -> Optional[Loan]:
        raise NotImplementedError

    @abc.abstractmethod
    async def update_loan_position(
        self,
        entry_id: UUID,
        current_installment: Dezimal,
        installment_interests: Optional[Dezimal],
        principal_outstanding: Dezimal,
        next_payment_date: Optional[datetime.date],
    ):
        raise NotImplementedError

    # --- Stale reference migration ---

    @abc.abstractmethod
    async def get_latest_real_position_id(
        self, entity_account_id: UUID
    ) -> Optional[UUID]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_account_iban_index(
        self, global_position_id: UUID
    ) -> dict[UUID, Optional[str]]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_portfolio_name_index(
        self, global_position_id: UUID
    ) -> dict[UUID, Optional[str]]:
        raise NotImplementedError

    @abc.abstractmethod
    async def migrate_references(
        self,
        account_mapping: dict[UUID, UUID],
        portfolio_mapping: dict[UUID, UUID],
    ):
        raise NotImplementedError

    @abc.abstractmethod
    async def account_exists(self, entry_id: UUID) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    async def fund_portfolio_exists(self, entry_id: UUID) -> bool:
        raise NotImplementedError
