from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional, Set
from uuid import uuid4

from application.mixins.atomic_use_case import AtomicUCMixin
from application.ports.entity_port import EntityPort
from application.ports.manual_position_data_port import ManualPositionDataPort
from application.ports.position_port import PositionPort
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.ports.virtual_import_registry import VirtualImportRegistry
from dateutil.tz import tzlocal
from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType, Feature
from domain.exception.exceptions import (
    EntityNameAlreadyExists,
    EntityNotFound,
    MissingFieldsError,
    RelatedAccountNotFound,
    RelatedFundPortfolioNotFound,
)
from domain.fetch_record import DataSource
from domain.global_position import (
    AccountType,
    Deposits,
    FactoringInvestments,
    FundInvestments,
    GlobalPosition,
    ManualPositionData,
    PositionQueryRequest,
    ProductType,
    RealEstateCFInvestments,
    StockInvestments,
    UpdatePositionRequest,
)
from domain.use_cases.update_position import UpdatePosition
from domain.virtual_fetch import VirtualDataImport, VirtualDataSource


class UpdatePositionImpl(UpdatePosition, AtomicUCMixin):
    def __init__(
        self,
        entity_port: EntityPort,
        position_port: PositionPort,
        manual_position_data_port: ManualPositionDataPort,
        virtual_import_registry: VirtualImportRegistry,
        transaction_handler_port: TransactionHandlerPort,
    ):
        AtomicUCMixin.__init__(self, transaction_handler_port)
        self._entity_port = entity_port
        self._position_port = position_port
        self._manual_position_data_port = manual_position_data_port
        self._virtual_import_registry = virtual_import_registry

    @staticmethod
    def _build_base_position(
        entity,
        prior_position,
        now: datetime,
        request: UpdatePositionRequest,
    ) -> GlobalPosition:
        if prior_position is None:
            base_position = GlobalPosition(
                id=uuid4(),
                entity=entity,
                date=now,
                products={},
                source=DataSource.MANUAL,
            )
        else:
            base_position = GlobalPosition(
                id=uuid4(),
                entity=prior_position.entity,
                date=now,
                products=dict(prior_position.products),
                source=DataSource.MANUAL,
            )
        for product_type, product_value in request.products.items():
            base_position.products[product_type] = product_value
        return base_position

    @staticmethod
    def _collect_real_account_ids(real_position: GlobalPosition | None) -> Set:
        ids: Set = set()
        if not (real_position and real_position.products):
            return ids
        accounts_container = real_position.products.get(ProductType.ACCOUNT)
        if accounts_container and hasattr(accounts_container, "entries"):
            for acc in accounts_container.entries:
                acc_id = getattr(acc, "id", None)
                if acc_id:
                    ids.add(acc_id)
        return ids

    @staticmethod
    def _collect_real_portfolio_ids(real_position: GlobalPosition | None) -> Set:
        ids: Set = set()
        if not (real_position and real_position.products):
            return ids
        portfolios_container = real_position.products.get(ProductType.FUND_PORTFOLIO)
        if portfolios_container and hasattr(portfolios_container, "entries"):
            for pf in portfolios_container.entries:
                pf_id = getattr(pf, "id", None)
                if pf_id:
                    ids.add(pf_id)
        return ids

    def _collect_real_relationship_ids(
        self, real_position: GlobalPosition | None
    ) -> tuple[Set, Set]:
        return (
            self._collect_real_account_ids(real_position),
            self._collect_real_portfolio_ids(real_position),
        )

    @staticmethod
    def _index_container_entries(container) -> dict:
        index: dict = {}
        if container and hasattr(container, "entries"):
            for entry in container.entries:
                entry_id = getattr(entry, "id", None)
                if entry_id:
                    index[entry_id] = entry
        return index

    def _prepare_relationship_mappings(
        self,
        entity: Entity,
        base_position: GlobalPosition,
        request: UpdatePositionRequest,
    ) -> tuple[dict, dict]:
        ctx = self._build_relationship_context(entity, base_position, request)

        new_account_id_map: dict = {}
        new_portfolio_id_map: dict = {}

        self._process_card_account_links(ctx, new_account_id_map)
        self._process_portfolio_account_links(ctx, new_account_id_map)
        self._process_fund_portfolio_links(ctx, new_portfolio_id_map)

        if new_account_id_map:
            self._apply_new_account_ids(ctx, new_account_id_map)
        if new_portfolio_id_map:
            self._apply_new_portfolio_ids(ctx, new_portfolio_id_map)
        return new_account_id_map, new_portfolio_id_map

    @dataclass
    class _RelCtx:
        accounts_container_req: Any | None
        portfolios_container_req: Any | None
        funds_container: Any | None
        cards_container: Any | None
        real_position: GlobalPosition | None
        real_account_ids: Set
        real_portfolio_ids: Set
        req_accounts_by_id: dict
        req_portfolios_by_id: dict
        validation_accounts: dict
        validation_portfolios: dict

    def _build_relationship_context(
        self,
        entity: Entity,
        base_position: GlobalPosition,
        request: UpdatePositionRequest,
    ) -> "UpdatePositionImpl._RelCtx":
        accounts_container_req = request.products.get(ProductType.ACCOUNT)
        portfolios_container_req = request.products.get(ProductType.FUND_PORTFOLIO)
        funds_container = request.products.get(ProductType.FUND)
        cards_container = request.products.get(ProductType.CARD)

        real_position = self._position_port.get_last_grouped_by_entity(
            PositionQueryRequest(entities=[entity.id], real=True)
        ).get(entity)

        real_account_ids, real_portfolio_ids = self._collect_real_relationship_ids(
            real_position
        )

        req_accounts_by_id = self._index_container_entries(accounts_container_req)
        req_portfolios_by_id = self._index_container_entries(portfolios_container_req)
        base_accounts_by_id = self._index_container_entries(
            base_position.products.get(ProductType.ACCOUNT)
        )
        base_portfolios_by_id = self._index_container_entries(
            base_position.products.get(ProductType.FUND_PORTFOLIO)
        )

        validation_accounts = {**base_accounts_by_id, **req_accounts_by_id}
        validation_portfolios = {**base_portfolios_by_id, **req_portfolios_by_id}

        return UpdatePositionImpl._RelCtx(
            accounts_container_req=accounts_container_req,
            portfolios_container_req=portfolios_container_req,
            funds_container=funds_container,
            cards_container=cards_container,
            real_position=real_position,
            real_account_ids=real_account_ids,
            real_portfolio_ids=real_portfolio_ids,
            req_accounts_by_id=req_accounts_by_id,
            req_portfolios_by_id=req_portfolios_by_id,
            validation_accounts=validation_accounts,
            validation_portfolios=validation_portfolios,
        )

    @staticmethod
    def _process_card_account_links(
        ctx: "UpdatePositionImpl._RelCtx", new_account_id_map: dict
    ):
        if not (ctx.cards_container and hasattr(ctx.cards_container, "entries")):
            return
        for card in ctx.cards_container.entries:
            rel_acc_id = getattr(card, "related_account", None)
            if not rel_acc_id:
                continue
            if rel_acc_id in ctx.real_account_ids:
                continue
            if rel_acc_id in ctx.validation_accounts:
                if (
                    rel_acc_id in ctx.req_accounts_by_id
                    and rel_acc_id not in new_account_id_map
                ):
                    new_account_id_map[rel_acc_id] = uuid4()
            else:
                raise RelatedAccountNotFound(rel_acc_id)

    @staticmethod
    def _process_portfolio_account_links(
        ctx: "UpdatePositionImpl._RelCtx", new_account_id_map: dict
    ):
        if not (
            ctx.portfolios_container_req
            and hasattr(ctx.portfolios_container_req, "entries")
        ):
            return
        for pf in ctx.portfolios_container_req.entries:
            acc_id = getattr(pf, "account_id", None)
            if not acc_id:
                continue
            acc_obj = ctx.validation_accounts.get(acc_id)
            if acc_id in ctx.real_account_ids and acc_obj is None and ctx.real_position:
                real_accounts_container = ctx.real_position.products.get(
                    ProductType.ACCOUNT
                )
                if real_accounts_container and hasattr(
                    real_accounts_container, "entries"
                ):
                    for a in real_accounts_container.entries:
                        if getattr(a, "id", None) == acc_id:
                            acc_obj = a
                            break
            if not acc_obj and acc_id in ctx.validation_accounts:
                acc_obj = ctx.validation_accounts[acc_id]
            if (
                acc_obj is None
                and acc_id not in ctx.validation_accounts
                and acc_id not in ctx.real_account_ids
            ):
                raise RelatedAccountNotFound(acc_id)
            if acc_obj and acc_obj.type != AccountType.FUND_PORTFOLIO:
                raise ValueError(
                    f"Account {acc_id} linked to portfolio {pf.id} is not of type FUND_PORTFOLIO"
                )
            if acc_id in ctx.real_account_ids:
                continue
            if (
                acc_id in ctx.validation_accounts
                and acc_id in ctx.req_accounts_by_id
                and acc_id not in new_account_id_map
            ):
                new_account_id_map[acc_id] = uuid4()

    @staticmethod
    def _process_fund_portfolio_links(
        ctx: "UpdatePositionImpl._RelCtx", new_portfolio_id_map: dict
    ):
        if not (
            ctx.funds_container
            and hasattr(ctx.funds_container, "entries")
            and ctx.portfolios_container_req
        ):
            return
        for fund in ctx.funds_container.entries:
            portfolio = getattr(fund, "portfolio", None)
            port_id = getattr(portfolio, "id", None) if portfolio else None
            if not port_id:
                continue
            if port_id in ctx.real_portfolio_ids:
                continue
            if (
                port_id in ctx.validation_portfolios
                and port_id in ctx.req_portfolios_by_id
                and port_id not in new_portfolio_id_map
            ):
                new_portfolio_id_map[port_id] = uuid4()
            elif port_id not in ctx.validation_portfolios:
                raise RelatedFundPortfolioNotFound(port_id)

    @staticmethod
    def _apply_new_account_ids(
        ctx: "UpdatePositionImpl._RelCtx", new_account_id_map: dict
    ):
        for old_id, new_id in new_account_id_map.items():
            acc = ctx.req_accounts_by_id.get(old_id)
            if acc:
                acc.id = new_id
        if ctx.cards_container and hasattr(ctx.cards_container, "entries"):
            for card in ctx.cards_container.entries:
                if getattr(card, "related_account", None) in new_account_id_map:
                    card.related_account = new_account_id_map[card.related_account]
        if ctx.portfolios_container_req and hasattr(
            ctx.portfolios_container_req, "entries"
        ):
            for pf in ctx.portfolios_container_req.entries:
                if getattr(pf, "account_id", None) in new_account_id_map:
                    pf.account_id = new_account_id_map[pf.account_id]

    @staticmethod
    def _apply_new_portfolio_ids(
        ctx: "UpdatePositionImpl._RelCtx", new_portfolio_id_map: dict
    ):
        for old_id, new_id in new_portfolio_id_map.items():
            pf = ctx.req_portfolios_by_id.get(old_id)
            if pf:
                pf.id = new_id
        if ctx.funds_container and hasattr(ctx.funds_container, "entries"):
            for fund in ctx.funds_container.entries:
                portfolio = getattr(fund, "portfolio", None)
                if portfolio and getattr(portfolio, "id", None) in new_portfolio_id_map:
                    portfolio.id = new_portfolio_id_map[portfolio.id]

    @staticmethod
    def _assign_nested_component_ids(request: UpdatePositionRequest):
        funds_container = request.products.get(ProductType.FUND)
        if funds_container and hasattr(funds_container, "entries"):
            for fund in funds_container.entries:
                portfolio = getattr(fund, "portfolio", None)
                if portfolio and getattr(portfolio, "id", None) is None:
                    portfolio.id = uuid4()

    @staticmethod
    def _normalize_rate(rate: Dezimal | None) -> Dezimal | None:
        if rate is None:
            return None
        return rate if rate <= Dezimal(1) else round(rate / Dezimal(100), 10)

    @staticmethod
    def _annualized_profitability(
        interest_rate: Dezimal | None, start_dt: datetime | None, end_date: date | None
    ) -> Dezimal:
        if not (interest_rate is not None and start_dt and end_date):
            return Dezimal(0)
        days = (end_date - start_dt.date()).days
        if days <= 0:
            return Dezimal(0)
        profit = interest_rate * Dezimal(days) / Dezimal(365)
        return Dezimal(round(profit, 4))

    def _compute_derived_financials(self, position: GlobalPosition):
        recf_container = position.products.get(ProductType.REAL_ESTATE_CF)
        if isinstance(recf_container, RealEstateCFInvestments):
            for d in recf_container.entries:
                d.interest_rate = self._normalize_rate(d.interest_rate)
                end_date = d.extended_maturity or d.maturity
                d.profitability = self._annualized_profitability(
                    d.interest_rate, d.last_invest_date, end_date
                )
        factoring_container = position.products.get(ProductType.FACTORING)
        if isinstance(factoring_container, FactoringInvestments):
            for d in factoring_container.entries:
                d.interest_rate = self._normalize_rate(d.interest_rate)
                d.profitability = self._annualized_profitability(
                    d.interest_rate, d.last_invest_date, d.maturity
                )
        deposits_container = position.products.get(ProductType.DEPOSIT)
        if isinstance(deposits_container, Deposits):
            for d in deposits_container.entries:
                d.interest_rate = self._normalize_rate(d.interest_rate)
                prof = self._annualized_profitability(
                    d.interest_rate, d.creation, d.maturity
                )
                if d.amount is not None:
                    d.expected_interests = Dezimal(str(round(d.amount * prof, 2)))

    def _adjust_investment_costs(self, position: GlobalPosition):
        funds_container = position.products.get(ProductType.FUND)
        if isinstance(funds_container, FundInvestments):
            for d in funds_container.entries:
                shares = d.shares
                ii = d.initial_investment
                abp = d.average_buy_price
                if (ii is None or ii == 0) and (abp is None or abp == 0):
                    raise MissingFieldsError(
                        ["initial_investment", "average_buy_price"]
                    )
                if ii and ii != 0 and abp and abp != 0 and shares and shares != 0:
                    d.average_buy_price = ii / shares
                if (d.market_value is None or d.market_value == 0) and ii and ii != 0:
                    d.market_value = ii
        stocks_container = position.products.get(ProductType.STOCK_ETF)
        if isinstance(stocks_container, StockInvestments):
            for d in stocks_container.entries:
                shares = d.shares
                ii = d.initial_investment
                abp = d.average_buy_price
                if (ii is None or ii == 0) and (abp is None or abp == 0):
                    raise MissingFieldsError(
                        ["initial_investment", "average_buy_price"]
                    )
                if ii and ii != 0 and abp and abp != 0 and shares and shares != 0:
                    d.average_buy_price = ii / shares
                if (d.market_value is None or d.market_value == 0) and ii and ii != 0:
                    d.market_value = ii

    @staticmethod
    def _ensure_unique(container) -> None:
        if not (container and hasattr(container, "entries")):
            return
        seen = set()
        for e in container.entries:
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
            for entry in container.entries:
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
        self, position: GlobalPosition, request: UpdatePositionRequest
    ) -> list[ManualPositionData]:
        entries = []
        for product_type, container in request.products.items():
            if not (container and hasattr(container, "entries")):
                continue
            for entry in container.entries:
                entries.append(
                    self._map_manual_position_data(entry, position, product_type)
                )

        return entries

    async def execute(self, request: UpdatePositionRequest):
        if request.entity_id:
            entity = self._entity_port.get_by_id(request.entity_id)
            if entity is None:
                raise EntityNotFound(request.entity_id)

        elif request.new_entity_name:
            name = request.new_entity_name.strip()
            if not name:
                raise MissingFieldsError(["new_entity_name"])
            existing = self._entity_port.get_by_name(name)
            if existing:
                raise EntityNameAlreadyExists(name)

            entity = Entity(
                id=uuid4(),
                name=name,
                natural_id=None,
                type=EntityType.FINANCIAL_INSTITUTION,
                origin=EntityOrigin.MANUAL,
            )
            self._entity_port.insert(entity)
        else:
            raise MissingFieldsError(["entity_id", "new_entity_name"])

        req_entity_id = entity.id
        now = datetime.now(tzlocal())
        last_manual_imports = self._virtual_import_registry.get_last_import_records(
            source=VirtualDataSource.MANUAL
        )

        prior_position_entry = None
        for entry in last_manual_imports:
            if entry.feature == Feature.POSITION and entry.entity_id == req_entity_id:
                prior_position_entry = entry
                break

        prior_position = None
        if prior_position_entry:
            prior_position = self._position_port.get_by_id(
                prior_position_entry.global_position_id
            )

        if prior_position_entry:
            for product_type in request.products.keys():
                self._manual_position_data_port.delete_by_position_id_and_type(
                    prior_position_entry.global_position_id, product_type
                )

        base_position = self._build_base_position(entity, prior_position, now, request)
        self._prepare_relationship_mappings(entity, base_position, request)
        self._assign_nested_component_ids(request)
        self._adjust_investment_costs(base_position)
        self._compute_derived_financials(base_position)
        self._ensure_all_unique(base_position)
        self._regenerate_snapshot_ids(base_position)
        manual_data_entries = self._create_manual_position_data_entries(
            base_position, request
        )

        today = now.date()
        is_same_day = (
            last_manual_imports and last_manual_imports[0].date.date() == today
        )

        if is_same_day:
            import_id = last_manual_imports[0].import_id
            self._virtual_import_registry.delete_by_import_feature_and_entity(
                import_id, Feature.POSITION, req_entity_id
            )
            if prior_position_entry:
                self._position_port.delete_by_id(
                    prior_position_entry.global_position_id
                )
            self._position_port.save(base_position)
            self._manual_position_data_port.save(manual_data_entries)

            new_entries = [
                VirtualDataImport(
                    import_id=import_id,
                    global_position_id=base_position.id,
                    source=VirtualDataSource.MANUAL,
                    date=now,
                    feature=Feature.POSITION,
                    entity_id=req_entity_id,
                )
            ]
            self._virtual_import_registry.insert(new_entries)
            return

        import_id = uuid4()
        self._position_port.save(base_position)
        self._manual_position_data_port.save(manual_data_entries)
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

        self._virtual_import_registry.insert(cloned_entries)
