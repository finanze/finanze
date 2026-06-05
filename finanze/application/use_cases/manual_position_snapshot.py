import logging
from datetime import date
from typing import Optional
from uuid import uuid4

from application.ports.loan_calculator_port import LoanCalculatorPort
from application.ports.manual_position_data_port import ManualPositionDataPort
from application.ports.position_port import PositionPort
from application.ports.real_estate_port import RealEstatePort
from application.ports.virtual_import_registry import VirtualImportRegistry
from domain.entity import Entity, Feature
from domain.global_position import (
    CryptoCurrencies,
    FundInvestments,
    GlobalPosition,
    ManualPositionData,
    ProductType,
    StockInvestments,
)
from domain.virtual_data import VirtualDataImport, VirtualDataSource


class ManualPositionSnapshotWriter:
    """Shared persistence for manual position snapshots.

    Encapsulates the snapshot id regeneration, manual tracking metadata
    extraction and the same-day / new-day virtual import versioning used both
    by manual position edits and by automated refreshes (tracked quotes and,
    in the future, tracked loans).
    """

    def __init__(
        self,
        position_port: PositionPort,
        manual_position_data_port: ManualPositionDataPort,
        virtual_import_registry: VirtualImportRegistry,
        real_estate_port: RealEstatePort,
        loan_calculator: LoanCalculatorPort,
    ):
        self._position_port = position_port
        self._manual_position_data_port = manual_position_data_port
        self._virtual_import_registry = virtual_import_registry
        self._real_estate_port = real_estate_port
        self._loan_calculator = loan_calculator

        self._log = logging.getLogger(__name__)

    @staticmethod
    def _assign_nested_component_ids(position: GlobalPosition):
        funds_container = position.products.get(ProductType.FUND)
        if funds_container and hasattr(funds_container, "entries"):
            for fund in funds_container.entries:
                portfolio = getattr(fund, "portfolio", None)
                if portfolio and getattr(portfolio, "id", None) is None:
                    portfolio.id = uuid4()

    def _adjust_investment_costs(self, position: GlobalPosition):
        funds_container = position.products.get(ProductType.FUND)
        if isinstance(funds_container, FundInvestments):
            for d in funds_container.entries:
                if (
                    d.market_value is None or d.market_value == 0
                ) and d.initial_investment is not None:
                    d.market_value = d.initial_investment

        stocks_container = position.products.get(ProductType.STOCK_ETF)
        if isinstance(stocks_container, StockInvestments):
            for d in stocks_container.entries:
                if (
                    d.market_value is None or d.market_value == 0
                ) and d.initial_investment is not None:
                    d.market_value = d.initial_investment

    @staticmethod
    def _ensure_unique(container) -> None:
        if not (container and hasattr(container, "entries")):
            return
        container_entries = container.entries
        if isinstance(container, CryptoCurrencies):
            if container_entries and hasattr(container_entries[0], "assets"):
                container_entries = container_entries[0].assets
            else:
                container_entries = []
        seen = set()
        for e in container_entries:
            if hasattr(e, "id"):
                i = getattr(e, "id", None)
                if i is None:
                    continue
                if i in seen:
                    raise ValueError(
                        "Duplicate ID detected inside single product container before regeneration"
                    )
                seen.add(i)

    def _ensure_all_unique(self, position: GlobalPosition):
        for product_type, container in position.products.items():
            self._ensure_unique(container)

    @staticmethod
    def _regenerate_snapshot_ids(position: GlobalPosition):
        products = position.products
        accounts_container = products.get(ProductType.ACCOUNT)
        portfolios_container = products.get(ProductType.FUND_PORTFOLIO)
        account_id_map: dict = {}
        portfolio_id_map: dict = {}
        if accounts_container and hasattr(accounts_container, "entries"):
            for acc in accounts_container.entries:
                if hasattr(acc, "id"):
                    old = getattr(acc, "id", None)
                    new_id = uuid4()
                    acc.id = new_id
                    if old:
                        account_id_map[old] = new_id
        if portfolios_container and hasattr(portfolios_container, "entries"):
            for pf in portfolios_container.entries:
                if hasattr(pf, "id"):
                    old = getattr(pf, "id", None)
                    new_id = uuid4()
                    pf.id = new_id
                    if old:
                        portfolio_id_map[old] = new_id
        cards_container = products.get(ProductType.CARD)
        if cards_container and hasattr(cards_container, "entries"):
            for card in cards_container.entries:
                ra = getattr(card, "related_account", None)
                if ra in account_id_map:
                    card.related_account = account_id_map[ra]
        if portfolios_container and hasattr(portfolios_container, "entries"):
            for pf in portfolios_container.entries:
                acc_id = getattr(pf, "account_id", None)
                if acc_id in account_id_map:
                    pf.account_id = account_id_map[acc_id]
        funds_container = products.get(ProductType.FUND)
        if funds_container and hasattr(funds_container, "entries"):
            for fund in funds_container.entries:
                portfolio = getattr(fund, "portfolio", None)
                if portfolio and getattr(portfolio, "id", None) in portfolio_id_map:
                    portfolio.id = portfolio_id_map[portfolio.id]
                acc_id = getattr(fund, "account_id", None)
                if acc_id in account_id_map:
                    fund.account_id = account_id_map[acc_id]
        for product_type, container in products.items():
            if product_type in (ProductType.ACCOUNT, ProductType.FUND_PORTFOLIO):
                continue
            if not (container and hasattr(container, "entries")):
                continue
            container_entries = container.entries
            if isinstance(container, CryptoCurrencies):
                if container_entries and hasattr(container_entries[0], "assets"):
                    container_entries = container_entries[0].assets
                else:
                    container_entries = []
            for entry in container_entries:
                if hasattr(entry, "id"):
                    entry.id = uuid4()

    @staticmethod
    def _map_manual_position_data(
        entry, position: GlobalPosition, product_type: ProductType
    ) -> Optional[ManualPositionData]:
        if (
            entry is None
            or not hasattr(entry, "manual_data")
            or entry.manual_data is None
        ):
            return None

        return ManualPositionData(
            entry_id=entry.id,
            global_position_id=position.id,
            product_type=product_type,
            data=entry.manual_data,
        )

    def _create_manual_position_data_entries(
        self, position: GlobalPosition, compute_loan_refs: bool = True
    ) -> list[ManualPositionData]:
        entries = []
        for product_type, container in position.products.items():
            if not (container and hasattr(container, "entries")):
                continue
            container_entries = container.entries
            if isinstance(container, CryptoCurrencies):
                if container_entries and hasattr(container_entries[0], "assets"):
                    container_entries = container_entries[0].assets
                else:
                    container_entries = []
            for entry in container_entries:
                manual_pos_data = self._map_manual_position_data(
                    entry, position, product_type
                )
                if manual_pos_data:
                    if (
                        compute_loan_refs
                        and product_type == ProductType.LOAN
                        and manual_pos_data.data
                        and manual_pos_data.data.track
                        and hasattr(entry, "principal_outstanding")
                    ):
                        manual_pos_data.data.tracking_ref_outstanding = (
                            entry.principal_outstanding
                        )
                        manual_pos_data.data.tracking_ref_date = (
                            self._loan_calculator.next_installment_date(
                                entry.creation,
                                entry.maturity,
                                entry.installment_frequency,
                                date.today(),
                            )
                        )
                    entries.append(manual_pos_data)

        return entries

    async def _sync_linked_loan_flows(self, position: GlobalPosition):
        loan_container = position.products.get(ProductType.LOAN)
        if not loan_container:
            return
        for loan in loan_container.entries:
            await self._real_estate_port.sync_linked_loan_flows(loan)

    async def write(
        self,
        entity: Entity,
        base_position: GlobalPosition,
        compute_loan_refs: bool = True,
    ):
        """Persist ``base_position`` as the latest manual snapshot for ``entity``.

        Keeps at most one manual snapshot per entity per local day: a same-day
        write replaces the current-day snapshot, a new-day write preserves the
        prior snapshot and starts a fresh manual import batch (cloning the other
        entities' last records forward). ``base_position`` must already carry the
        fully built product set, a fresh ``id`` and its ``date`` set to now.

        When ``compute_loan_refs`` is False, tracked loans' tracking-ref fields
        are persisted as-is from each loan's ``manual_data`` instead of being
        re-anchored to the current outstanding/next installment date.
        """
        now = base_position.date
        req_entity_id = entity.id

        last_manual_imports = (
            await self._virtual_import_registry.get_last_import_records(
                source=VirtualDataSource.MANUAL
            )
        )

        prior_position_entry = None
        for entry in last_manual_imports:
            if entry.feature == Feature.POSITION and entry.entity_id == req_entity_id:
                prior_position_entry = entry
                break

        if prior_position_entry:
            await self._manual_position_data_port.delete_by_position_id(
                prior_position_entry.global_position_id
            )

        self._assign_nested_component_ids(base_position)
        self._adjust_investment_costs(base_position)
        self._ensure_all_unique(base_position)
        self._regenerate_snapshot_ids(base_position)
        manual_data_entries = self._create_manual_position_data_entries(
            base_position, compute_loan_refs=compute_loan_refs
        )

        today = now.date()
        is_same_day = (
            last_manual_imports and last_manual_imports[0].date.date() == today
        )

        if is_same_day:
            import_id = last_manual_imports[0].import_id
            await self._virtual_import_registry.delete_by_import_feature_and_entity(
                import_id, Feature.POSITION, req_entity_id
            )
            if prior_position_entry:
                is_shared = await self._virtual_import_registry.is_position_shared(
                    prior_position_entry.global_position_id, import_id
                )
                if not is_shared:
                    await self._position_port.delete_by_id(
                        prior_position_entry.global_position_id
                    )
            await self._position_port.save(base_position)
            await self._manual_position_data_port.save(manual_data_entries)
            await self._sync_linked_loan_flows(base_position)

            await self._virtual_import_registry.insert(
                [
                    VirtualDataImport(
                        import_id=import_id,
                        global_position_id=base_position.id,
                        source=VirtualDataSource.MANUAL,
                        date=now,
                        feature=Feature.POSITION,
                        entity_id=req_entity_id,
                    )
                ]
            )
            return

        import_id = uuid4()
        await self._position_port.save(base_position)
        await self._manual_position_data_port.save(manual_data_entries)
        await self._sync_linked_loan_flows(base_position)
        cloned_entries = []

        for entry in last_manual_imports:
            if entry.feature == Feature.POSITION and entry.entity_id == req_entity_id:
                continue
            cloned_entries.append(
                VirtualDataImport(
                    import_id=import_id,
                    global_position_id=entry.global_position_id,
                    source=entry.source,
                    date=now,
                    feature=entry.feature,
                    entity_id=entry.entity_id,
                )
            )

        cloned_entries.append(
            VirtualDataImport(
                import_id=import_id,
                global_position_id=base_position.id,
                source=VirtualDataSource.MANUAL,
                date=now,
                feature=Feature.POSITION,
                entity_id=req_entity_id,
            )
        )

        await self._virtual_import_registry.insert(cloned_entries)
