from datetime import datetime
from typing import Optional
from uuid import uuid4

from dateutil.tz import tzlocal

from application.ports.historic_port import HistoricPort
from application.ports.transaction_port import TransactionPort
from application.ports.virtual_import_registry import VirtualImportRegistry
from application.use_cases.manual_transaction_common import (
    ManualTransactionVirtualImportHelper,
)
from domain.dezimal import Dezimal
from domain.entity import Entity, Feature
from domain.fetch_record import DataSource
from domain.global_position import (
    GlobalPosition,
    ProductType,
    compute_investment_hash,
)
from domain.historic import (
    FINAL_HISTORIC_STATES,
    BaseHistoricEntry,
    FactoringEntry,
    RealEstateCFEntry,
)
from domain.investment_returns import compute_return_values
from domain.transactions import (
    BaseInvestmentTx,
    FactoringTx,
    RealEstateCFTx,
    Transactions,
    TxType,
)
from domain.virtual_data import VirtualDataSource

MANUAL_HISTORIC_PRODUCT_TYPES = {ProductType.FACTORING, ProductType.REAL_ESTATE_CF}

SETTLEMENT_TX_REF_PREFIX = "manual-settlement-"


def settlement_tx_ref() -> str:
    return f"{SETTLEMENT_TX_REF_PREFIX}{uuid4().hex}"


def is_settlement_tx(tx) -> bool:
    ref = getattr(tx, "ref", None)
    return bool(ref) and ref.startswith(SETTLEMENT_TX_REF_PREFIX)


class ManualHistoricWriter:
    """Keeps a single persistent historic row in sync for each manual factoring
    and real-estate-CF investment entry.

    While the investment is ongoing the row is upserted (keyed by a deterministic
    manual key) on every manual snapshot save. Rows already in a final state
    (settled) are owned by the settlement flow and left untouched here.
    """

    def __init__(
        self,
        historic_port: HistoricPort,
        transaction_port: Optional[TransactionPort] = None,
        virtual_import_registry: Optional[VirtualImportRegistry] = None,
    ):
        self._historic_port = historic_port
        self._transaction_port = transaction_port
        self._tx_helper = (
            ManualTransactionVirtualImportHelper(virtual_import_registry)
            if virtual_import_registry is not None
            else None
        )

    @staticmethod
    def manual_key_for(entity_id, entry) -> str:
        start = entry.start
        start_iso = (
            start.date().isoformat() if hasattr(start, "date") else start.isoformat()
        )
        return compute_investment_hash(
            str(entity_id), str(entry.amount), start_iso, entry.name
        )

    async def sync_position(
        self,
        entity: Entity,
        position: GlobalPosition,
        create_investment_txs: bool = True,
    ):
        current_keys: set[str] = set()
        created_txs: list = []
        for product_type in MANUAL_HISTORIC_PRODUCT_TYPES:
            container = position.products.get(product_type)
            if not (container and hasattr(container, "entries")):
                continue
            for entry in container.entries:
                current_keys.add(self.manual_key_for(entity.id, entry))
                await self.upsert_ongoing(
                    entity,
                    entry,
                    product_type,
                    created_txs=created_txs,
                    create_investment_txs=create_investment_txs,
                )

        await self._reconcile_orphans(entity, current_keys)

        if created_txs and self._tx_helper is not None:
            manual_remaining = await self._transaction_port.get_by_entity_and_source(
                entity.id, DataSource.MANUAL
            )
            has_transactions = bool(
                manual_remaining.account + manual_remaining.investment
            )
            await self._tx_helper.refresh(entity.id, has_transactions=has_transactions)

    async def _reconcile_orphans(self, entity: Entity, current_keys: set[str]):
        existing_rows = await self._historic_port.get_manual_by_entity(entity.id)
        for row in existing_rows:
            if row.state in FINAL_HISTORIC_STATES:
                continue
            if row.manual_key not in current_keys:
                await self._historic_port.delete_by_id(row.id)

    async def upsert_ongoing(
        self,
        entity: Entity,
        entry,
        product_type: ProductType,
        created_txs: Optional[list] = None,
        create_investment_txs: bool = True,
    ) -> BaseHistoricEntry | None:
        manual_key = self.manual_key_for(entity.id, entry)
        existing = await self._historic_port.get_by_manual_key(
            manual_key, fetch_related_txs=True
        )

        if existing and existing.state in FINAL_HISTORIC_STATES:
            return existing

        entry_id = existing.id if existing else uuid4()
        related_txs = existing.related_txs if existing else []

        initial_txs = self._build_initial_txs(
            entity,
            entry,
            product_type,
            is_new=existing is None,
            create_investment_txs=create_investment_txs,
        )
        if initial_txs:
            related_txs = list(related_txs) + initial_txs

        historic_entry = self.build_entry(
            entity,
            entry,
            product_type,
            entry_id=entry_id,
            state=entry.state,
            effective_maturity=None,
            related_txs=related_txs,
            manual_key=manual_key,
        )

        if initial_txs:
            await self._transaction_port.save(Transactions(investment=initial_txs))
            if created_txs is not None:
                created_txs.extend(initial_txs)

        await self._historic_port.upsert(historic_entry)
        return historic_entry

    def _build_initial_txs(
        self,
        entity: Entity,
        entry,
        product_type: ProductType,
        *,
        is_new: bool,
        create_investment_txs: bool,
    ) -> list:
        if (
            not is_new
            or not create_investment_txs
            or self._transaction_port is None
            or self._tx_helper is None
        ):
            return []

        txs: list = []

        investment_tx = make_investment_tx(
            entity,
            entry,
            product_type,
            TxType.INVESTMENT,
            entry.amount,
            Dezimal(0),
            Dezimal(0),
            entry.last_invest_date or entry.start,
        )
        self._tx_helper.update_derived_fields(investment_tx)
        txs.append(investment_tx)

        pending = getattr(entry, "pending_amount", None)
        if pending is not None:
            repaid_amount = entry.amount - pending
            if repaid_amount > Dezimal(0):
                repaid_tx = make_investment_tx(
                    entity,
                    entry,
                    product_type,
                    TxType.REPAYMENT,
                    repaid_amount,
                    Dezimal(0),
                    Dezimal(0),
                    datetime.now(tzlocal()),
                )
                self._tx_helper.update_derived_fields(repaid_tx)
                txs.append(repaid_tx)

        return txs

    @staticmethod
    def build_entry(
        entity: Entity,
        entry,
        product_type: ProductType,
        *,
        entry_id,
        state: Optional[str],
        effective_maturity: Optional[datetime],
        related_txs: list,
        manual_key: Optional[str],
        last_tx_date: Optional[datetime] = None,
    ) -> BaseHistoricEntry:
        now = datetime.now(tzlocal())
        last_invest_date = entry.last_invest_date or entry.start

        if related_txs:
            fees, interests, net_return, repaid, retentions, returned, _ = (
                compute_return_values(related_txs)
            )
        else:
            fees = interests = net_return = repaid = retentions = returned = None

        common = dict(
            id=entry_id,
            name=entry.name,
            invested=entry.amount,
            repaid=repaid,
            returned=returned,
            currency=entry.currency,
            last_invest_date=last_invest_date,
            last_tx_date=last_tx_date or now,
            effective_maturity=effective_maturity,
            net_return=net_return,
            fees=fees,
            retentions=retentions,
            interests=interests,
            state=state,
            entity=entity,
            product_type=product_type,
            related_txs=related_txs,
            entity_account_id=None,
            source=DataSource.MANUAL,
            manual_key=manual_key,
        )

        if product_type == ProductType.FACTORING:
            return FactoringEntry(
                **common,
                interest_rate=entry.interest_rate,
                gross_interest_rate=entry.gross_interest_rate or entry.interest_rate,
                maturity=entry.maturity,
                type=entry.type,
            )
        return RealEstateCFEntry(
            **common,
            interest_rate=entry.interest_rate,
            maturity=entry.maturity,
            extended_maturity=entry.extended_maturity,
            type=entry.type,
            business_type=entry.business_type,
        )


def make_investment_tx(
    entity: Entity,
    entry,
    product_type: ProductType,
    tx_type: TxType,
    amount: Dezimal,
    fees: Dezimal,
    retentions: Dezimal,
    tx_date: datetime,
    name: Optional[str] = None,
    ref: Optional[str] = None,
) -> BaseInvestmentTx:
    common = dict(
        id=uuid4(),
        ref=ref or f"manual-{uuid4().hex}",
        name=name or entry.name,
        amount=amount,
        currency=entry.currency,
        type=tx_type,
        date=tx_date,
        entity=entity,
        source=DataSource.MANUAL,
        product_type=product_type,
        fees=fees,
        retentions=retentions,
    )
    if product_type == ProductType.FACTORING:
        return FactoringTx(**common)
    return RealEstateCFTx(**common)


async def load_manual_position(
    virtual_import_registry, position_port, entity_id
) -> Optional[GlobalPosition]:
    last_manual_imports = await virtual_import_registry.get_last_import_records(
        source=VirtualDataSource.MANUAL
    )
    position_entry = next(
        (
            entry
            for entry in last_manual_imports
            if entry.feature == Feature.POSITION and entry.entity_id == entity_id
        ),
        None,
    )
    if not position_entry:
        return None
    return await position_port.get_by_id(position_entry.global_position_id)


def find_investment_entry(
    position: GlobalPosition, product_type: ProductType, entry_id
):
    container = position.products.get(product_type)
    if not (container and getattr(container, "entries", None)):
        return None
    return next((e for e in container.entries if e.id == entry_id), None)
