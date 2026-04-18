import json
from datetime import date, datetime
from typing import Callable, Optional
from uuid import UUID, uuid4

from application.ports.position_port import PositionPort
from domain.commodity import CommodityType, WeightUnit
from domain.crypto import CryptoAsset, CryptoCurrencyType, CryptoWallet
from domain.dezimal import Dezimal
from domain.entity import Entity
from domain.fetch_record import DataSource
from domain.global_position import (
    Account,
    Accounts,
    AccountType,
    AssetType,
    Card,
    Cards,
    CardType,
    Commodities,
    Commodity,
    Crowdlending,
    CryptoCurrencies,
    CryptoCurrencyPosition,
    CryptoCurrencyWallet,
    Deposit,
    Deposits,
    DerivativeContractType,
    DerivativeDetail,
    DerivativePositions,
    EquityType,
    FactoringDetail,
    FactoringInvestments,
    FundDetail,
    FundInvestments,
    FundPortfolio,
    FundPortfolios,
    FundType,
    GlobalPosition,
    InstallmentFrequency,
    InterestType,
    Loan,
    Loans,
    LoanType,
    ManualEntryData,
    MarginType,
    PositionDirection,
    PositionQueryRequest,
    ProductType,
    RealEstateCFDetail,
    RealEstateCFInvestments,
    StockDetail,
    StockInvestments,
)
from infrastructure.repository.common.json_serialization import DezimalJSONEncoder
from infrastructure.repository.crypto.crypto_wallet_repository import (
    CryptoWalletRepository,
)
from infrastructure.repository.crypto.queries import CryptoWalletQueries
from infrastructure.repository.db.client import DBClient, DBCursor
from infrastructure.repository.position.queries import (
    PositionQueries,
    PositionWriteQueries,
)

_AND = " AND "


async def _save_loans(cursor, position: GlobalPosition, loans: Loans):
    for loan in loans.entries:
        loan_hash = loan.compute_hash(str(position.entity.id))
        await cursor.execute(
            PositionWriteQueries.INSERT_LOAN_POSITION,
            (
                str(loan.id),
                str(position.id),
                loan.type,
                loan.currency,
                loan.name,
                str(loan.current_installment),
                loan.installment_frequency,
                str(loan.interest_rate),
                loan.interest_type,
                str(loan.installment_interests)
                if loan.installment_interests is not None
                else None,
                str(loan.loan_amount),
                loan.next_payment_date.isoformat() if loan.next_payment_date else None,
                str(loan.principal_outstanding),
                str(loan.euribor_rate) if loan.euribor_rate is not None else None,
                str(loan.fixed_years) if loan.fixed_years else None,
                str(loan.fixed_interest_rate)
                if loan.fixed_interest_rate is not None
                else None,
                loan.creation.isoformat(),
                loan.maturity.isoformat(),
                str(loan.unpaid) if loan.unpaid else None,
                loan_hash,
            ),
        )


async def _save_cards(cursor, position: GlobalPosition, cards: Cards):
    for card in cards.entries:
        await cursor.execute(
            PositionWriteQueries.INSERT_CARD_POSITION,
            (
                str(card.id),
                str(position.id),
                card.type.value,
                card.name,
                card.currency,
                str(card.ending),
                str(card.limit) if card.limit else None,
                str(card.used),
                card.active,
                str(card.related_account) if card.related_account else None,
            ),
        )


async def _save_accounts(cursor, position: GlobalPosition, accounts: Accounts):
    for account in accounts.entries:
        await cursor.execute(
            PositionWriteQueries.INSERT_ACCOUNT_POSITION,
            (
                str(account.id),
                str(position.id),
                account.type,
                account.currency,
                account.name,
                account.iban,
                str(account.total),
                str(account.interest) if account.interest else None,
                str(account.retained) if account.retained else None,
                str(account.pending_transfers) if account.pending_transfers else None,
            ),
        )


async def _save_crowdlending(
    cursor, position: GlobalPosition, crowdlending: Crowdlending
):
    await cursor.execute(
        PositionWriteQueries.INSERT_CROWDLENDING_POSITION,
        (
            str(crowdlending.id),
            str(position.id),
            str(crowdlending.total),
            str(crowdlending.weighted_interest_rate),
            crowdlending.currency,
            (
                json.dumps(crowdlending.distribution, cls=DezimalJSONEncoder)
                if crowdlending.distribution
                else "{}"
            ),
        ),
    )


async def _save_commodities(cursor, position: GlobalPosition, commodities: Commodities):
    for commodity in commodities.entries:
        await cursor.execute(
            PositionWriteQueries.INSERT_COMMODITY_POSITION,
            (
                str(commodity.id),
                str(position.id),
                commodity.name,
                commodity.type.value,
                str(commodity.amount),
                commodity.unit.value,
                str(commodity.market_value),
                commodity.currency,
                (
                    str(commodity.initial_investment)
                    if commodity.initial_investment
                    else None
                ),
                (
                    str(commodity.average_buy_price)
                    if commodity.average_buy_price
                    else None
                ),
            ),
        )


async def _save_derivatives(
    cursor, position: GlobalPosition, derivatives: DerivativePositions
):
    for detail in derivatives.entries:
        await cursor.execute(
            PositionWriteQueries.INSERT_DERIVATIVE_POSITION,
            (
                str(detail.id),
                str(position.id),
                detail.symbol,
                detail.underlying_asset.value,
                detail.contract_type.value,
                detail.direction.value,
                str(detail.size),
                str(detail.entry_price),
                detail.currency,
                str(detail.mark_price) if detail.mark_price is not None else None,
                str(detail.market_value) if detail.market_value is not None else None,
                str(detail.unrealized_pnl)
                if detail.unrealized_pnl is not None
                else None,
                str(detail.leverage) if detail.leverage is not None else None,
                str(detail.margin) if detail.margin is not None else None,
                detail.margin_type.value if detail.margin_type else None,
                str(detail.liquidation_price)
                if detail.liquidation_price is not None
                else None,
                detail.isin,
                str(detail.strike_price) if detail.strike_price is not None else None,
                str(detail.knock_out_price)
                if detail.knock_out_price is not None
                else None,
                str(detail.ratio) if detail.ratio is not None else None,
                detail.issuer,
                detail.underlying_symbol,
                detail.underlying_isin,
                detail.expiry.isoformat() if detail.expiry else None,
                detail.name,
                str(detail.initial_investment)
                if detail.initial_investment is not None
                else None,
            ),
        )


async def _save_crypto_currencies(
    cursor, position: GlobalPosition, cryptocurrencies: CryptoCurrencies
):
    for wallet_entry in cryptocurrencies.entries:
        for crypto_position in wallet_entry.assets:
            await cursor.execute(
                PositionWriteQueries.INSERT_CRYPTO_CURRENCY_POSITION,
                (
                    str(crypto_position.id),
                    str(position.id),
                    str(wallet_entry.id) if wallet_entry.id else None,
                    crypto_position.name,
                    crypto_position.symbol,
                    crypto_position.type.value,
                    str(crypto_position.amount),
                    (
                        str(crypto_position.market_value)
                        if crypto_position.market_value
                        else None
                    ),
                    crypto_position.currency,
                    crypto_position.contract_address,
                    (
                        str(crypto_position.crypto_asset.id)
                        if crypto_position.crypto_asset
                        else None
                    ),
                ),
            )

            initial_investment = crypto_position.initial_investment
            avg_buy_price = crypto_position.average_buy_price
            investment_currency = crypto_position.investment_currency
            if (
                initial_investment is not None
                and avg_buy_price is not None
                and investment_currency is not None
            ):
                await cursor.execute(
                    PositionWriteQueries.INSERT_CRYPTO_CURRENCY_INITIAL_INVESTMENT,
                    (
                        str(uuid4()),
                        str(crypto_position.id),
                        investment_currency,
                        str(initial_investment),
                        str(avg_buy_price),
                    ),
                )


async def _save_deposits(cursor, position: GlobalPosition, deposits: Deposits):
    for detail in deposits.entries:
        await cursor.execute(
            PositionWriteQueries.INSERT_DEPOSIT_POSITION,
            (
                str(detail.id),
                str(position.id),
                detail.name,
                str(detail.amount),
                str(detail.currency),
                str(detail.expected_interests),
                str(detail.interest_rate),
                detail.creation.isoformat(),
                detail.maturity.isoformat(),
            ),
        )


async def _save_real_estate_cf(
    cursor, position: GlobalPosition, real_estate: RealEstateCFInvestments
):
    for detail in real_estate.entries:
        await cursor.execute(
            PositionWriteQueries.INSERT_REAL_ESTATE_CF_POSITION,
            (
                str(detail.id),
                str(position.id),
                detail.name,
                str(detail.amount),
                str(detail.pending_amount),
                detail.currency,
                str(detail.interest_rate),
                str(detail.profitability),
                detail.last_invest_date.isoformat(),
                detail.start.isoformat(),
                detail.maturity.isoformat(),
                detail.type,
                detail.business_type,
                detail.state,
                (
                    detail.extended_maturity.isoformat()
                    if detail.extended_maturity
                    else None
                ),
                (
                    str(detail.extended_interest_rate)
                    if detail.extended_interest_rate
                    else None
                ),
            ),
        )


async def _save_factoring(
    cursor, position: GlobalPosition, factoring: FactoringInvestments
):
    for detail in factoring.entries:
        await cursor.execute(
            PositionWriteQueries.INSERT_FACTORING_POSITION,
            (
                str(detail.id),
                str(position.id),
                detail.name,
                str(detail.amount),
                detail.currency,
                str(detail.interest_rate),
                str(detail.profitability),
                str(detail.gross_interest_rate),
                str(detail.late_interest_rate) if detail.late_interest_rate else None,
                (
                    str(detail.gross_late_interest_rate)
                    if detail.gross_late_interest_rate
                    else None
                ),
                (
                    detail.last_invest_date.isoformat()
                    if detail.last_invest_date
                    else None
                ),
                detail.start.isoformat(),
                detail.maturity.isoformat(),
                detail.type,
                detail.state,
            ),
        )


async def _save_fund_portfolios(
    cursor, position: GlobalPosition, portfolios: FundPortfolios
):
    for portfolio in portfolios.entries:
        await cursor.execute(
            PositionWriteQueries.INSERT_FUND_PORTFOLIO,
            (
                str(portfolio.id),
                str(position.id),
                portfolio.name,
                portfolio.currency,
                (
                    str(portfolio.initial_investment)
                    if portfolio.initial_investment
                    else None
                ),
                str(portfolio.market_value) if portfolio.market_value else None,
                str(portfolio.account_id) if portfolio.account_id else None,
            ),
        )


async def _save_funds(cursor, position: GlobalPosition, funds: FundInvestments):
    for detail in funds.entries:
        await cursor.execute(
            PositionWriteQueries.INSERT_FUND_POSITION,
            (
                str(detail.id),
                str(position.id),
                detail.name,
                detail.isin,
                detail.market if detail.market else None,
                str(detail.shares),
                str(detail.initial_investment),
                str(detail.average_buy_price),
                str(detail.market_value),
                detail.type,
                detail.asset_type if detail.asset_type else None,
                detail.currency,
                str(detail.portfolio.id) if detail.portfolio else None,
                detail.info_sheet_url,
                detail.issuer,
            ),
        )


async def _save_stocks(cursor, position: GlobalPosition, stocks: StockInvestments):
    for detail in stocks.entries:
        await cursor.execute(
            PositionWriteQueries.INSERT_STOCK_POSITION,
            (
                str(detail.id),
                str(position.id),
                detail.name,
                detail.ticker,
                detail.isin,
                detail.market,
                str(detail.shares),
                str(detail.initial_investment),
                str(detail.average_buy_price),
                str(detail.market_value),
                detail.currency,
                detail.type.value,
                detail.subtype,
                detail.info_sheet_url,
                detail.issuer,
            ),
        )


async def _save_position(
    cursor, position: GlobalPosition, product_type: ProductType, save_fn: Callable
):
    product_position = position.products.get(product_type)
    if product_position:
        await save_fn(cursor, position, product_position)


async def _save_product_positions(cursor, position: GlobalPosition):
    await _save_position(cursor, position, ProductType.ACCOUNT, _save_accounts)
    await _save_position(cursor, position, ProductType.CARD, _save_cards)
    await _save_position(cursor, position, ProductType.LOAN, _save_loans)
    await _save_position(cursor, position, ProductType.STOCK_ETF, _save_stocks)
    await _save_position(
        cursor, position, ProductType.FUND_PORTFOLIO, _save_fund_portfolios
    )
    await _save_position(cursor, position, ProductType.FUND, _save_funds)
    await _save_position(cursor, position, ProductType.FACTORING, _save_factoring)
    await _save_position(
        cursor, position, ProductType.REAL_ESTATE_CF, _save_real_estate_cf
    )
    await _save_position(cursor, position, ProductType.DEPOSIT, _save_deposits)
    await _save_position(cursor, position, ProductType.CROWDLENDING, _save_crowdlending)
    await _save_position(cursor, position, ProductType.CRYPTO, _save_crypto_currencies)
    await _save_position(cursor, position, ProductType.COMMODITY, _save_commodities)
    await _save_position(cursor, position, ProductType.DERIVATIVE, _save_derivatives)


def _aggregate_positions(positions: list[GlobalPosition]) -> GlobalPosition:
    aggregated_position = None

    for position in positions:
        if aggregated_position is None:
            aggregated_position = position
        else:
            aggregated_position += position

    return aggregated_position


def _map_manual_entry_data(row) -> Optional[ManualEntryData]:
    if row["track_ticker"] is None and row["track_loan"] is None:
        return None

    return ManualEntryData(
        tracker_key=row["tracker_key"],
        track=bool(row["track_loan"]),
    )


class PositionSQLRepository(PositionPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    async def save(self, position: GlobalPosition):
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                PositionQueries.INSERT_GLOBAL_POSITION,
                (
                    str(position.id),
                    position.date.isoformat(),
                    str(position.entity.id),
                    position.source.value,
                    str(position.entity_account_id)
                    if position.entity_account_id
                    else None,
                ),
            )

            await _save_product_positions(cursor, position)

    async def get_last_grouped_by_entity(
        self, query: Optional[PositionQueryRequest] = None
    ) -> dict[Entity, GlobalPosition]:
        real_global_position_by_entity, manual_global_positions_by_entity = {}, {}

        if not query or query.real is None or query.real:
            real_global_position_by_entity = await self._get_real_grouped_by_entity(
                query
            )
        if not query or query.real is None or not query.real:
            manual_global_positions_by_entity: dict[
                Entity, list[GlobalPosition]
            ] = await self._get_non_real_grouped_by_entity(query)

        global_position_by_entity = {}
        for entity, positions in real_global_position_by_entity.items():
            aggregated_real = _aggregate_positions(positions)
            if entity in manual_global_positions_by_entity:
                manual_positions = manual_global_positions_by_entity[entity]
                aggregated_manual = _aggregate_positions(manual_positions)
                global_position_by_entity[entity] = aggregated_real + aggregated_manual
                del manual_global_positions_by_entity[entity]
            else:
                global_position_by_entity[entity] = aggregated_real

        for entity, manual_positions in manual_global_positions_by_entity.items():
            global_position_by_entity[entity] = _aggregate_positions(manual_positions)

        return global_position_by_entity

    async def get_last_by_entity_broken_down(
        self, query: Optional[PositionQueryRequest] = None
    ) -> dict[Entity, list[GlobalPosition]]:
        real_global_positions_by_entity, manual_global_positions_by_entity = {}, {}

        if not query or query.real is None or query.real:
            real_global_positions_by_entity = await self._get_real_grouped_by_entity(
                query
            )
        if not query or query.real is None or not query.real:
            manual_global_positions_by_entity = (
                await self._get_non_real_grouped_by_entity(query)
            )

        global_position_by_entity = {}
        for entity, positions in real_global_positions_by_entity.items():
            if entity not in global_position_by_entity:
                global_position_by_entity[entity] = list(positions)
            else:
                global_position_by_entity[entity].extend(positions)

        for entity, manual_positions in manual_global_positions_by_entity.items():
            if entity not in global_position_by_entity:
                global_position_by_entity[entity] = manual_positions
            else:
                global_position_by_entity[entity].extend(manual_positions)

        return global_position_by_entity

    async def _get_real_grouped_by_entity(
        self, query: Optional[PositionQueryRequest]
    ) -> dict[Entity, list[GlobalPosition]]:
        async with self._db_client.read() as cursor:
            sql = PositionQueries.REAL_GROUPED_BY_ENTITY_BASE.value
            params = []
            conditions = []
            if query and query.entities:
                placeholders = ", ".join("?" for _ in query.entities)
                conditions.append(f"gp.entity_id IN ({placeholders})")
                params.extend([str(e) for e in query.entities])
            if query and query.excluded_entities:
                placeholders = ", ".join("?" for _ in query.excluded_entities)
                conditions.append(f"gp.entity_id NOT IN ({placeholders})")
                params.extend([str(e) for e in query.excluded_entities])

            if conditions:
                sql += _AND + _AND.join(conditions)

            await cursor.execute(sql, tuple(params))

            products = query.products if query else None

            return await self._map_position_rows(cursor, products=products)

    async def _map_position_rows(
        self, cursor: DBCursor, products: list[ProductType] = None
    ) -> dict[Entity, list[GlobalPosition]]:
        rows = await cursor.fetchall()

        entities: dict[UUID, Entity] = {}
        result: dict[Entity, list[GlobalPosition]] = {}
        all_positions: list[GlobalPosition] = []

        for row in rows:
            ent_id = UUID(row["entity_id"])
            if ent_id not in entities:
                entities[ent_id] = Entity(
                    id=ent_id,
                    name=row["entity_name"],
                    natural_id=row["entity_natural_id"],
                    type=row["entity_type"],
                    origin=row["entity_origin"],
                    icon_url=row["icon_url"],
                )
            entity = entities[ent_id]

            pos_id = UUID(row["id"])
            source = DataSource(row["source"])
            entity_account_id = (
                UUID(row["entity_account_id"]) if row["entity_account_id"] else None
            )
            position = GlobalPosition(
                id=pos_id,
                entity=entity,
                date=datetime.fromisoformat(row["date"]),
                source=source,
                entity_account_id=entity_account_id,
            )
            position.products = {}
            all_positions.append(position)

            lst = result.get(entity)
            if lst is None:
                result[entity] = [position]
            else:
                lst.append(position)

        await self._batch_load_all_products(all_positions, products)

        return result

    async def _get_non_real_grouped_by_entity(
        self, query: Optional[PositionQueryRequest]
    ) -> dict[Entity, list[GlobalPosition]]:
        async with self._db_client.read() as cursor:
            sql = PositionQueries.NON_REAL_GROUPED_BY_ENTITY_BASE.value

            params = []
            conditions = []
            if query and query.entities:
                placeholders = ", ".join("?" for _ in query.entities)
                conditions.append(f"gp.entity_id IN ({placeholders})")
                params.extend([str(e) for e in query.entities])

            if conditions:
                sql += " WHERE " + " AND ".join(conditions)

            await cursor.execute(sql, tuple(params))

            products = query.products if query else None

            return await self._map_position_rows(cursor, products=products)

    async def _get_all_accounts(
        self, positions: list[GlobalPosition]
    ) -> dict[UUID, Accounts]:
        gp_ids = [str(p.id) for p in positions]
        source_map = {str(p.id): p.source for p in positions}
        async with self._db_client.read() as cursor:
            sql = PositionQueries.GET_ACCOUNTS_BY_GLOBAL_POSITION_IDS.value.format(
                placeholders=",".join("?" for _ in gp_ids)
            )
            await cursor.execute(sql, tuple(gp_ids))
            grouped: dict[str, list[Account]] = {}
            for row in cursor:
                gp_id = row["global_position_id"]
                grouped.setdefault(gp_id, []).append(
                    Account(
                        id=UUID(row["id"]),
                        total=Dezimal(row["total"]),
                        currency=row["currency"],
                        type=AccountType(row["type"]),
                        name=row["name"],
                        iban=row["iban"],
                        interest=Dezimal(row["interest"]) if row["interest"] else None,
                        retained=Dezimal(row["retained"]) if row["retained"] else None,
                        pending_transfers=(
                            Dezimal(row["pending_transfers"])
                            if row["pending_transfers"]
                            else None
                        ),
                        source=source_map[gp_id],
                    )
                )
            return {UUID(k): Accounts(v) for k, v in grouped.items()}

    async def _get_all_cards(
        self, positions: list[GlobalPosition]
    ) -> dict[UUID, Cards]:
        gp_ids = [str(p.id) for p in positions]
        source_map = {str(p.id): p.source for p in positions}
        async with self._db_client.read() as cursor:
            sql = PositionQueries.GET_CARDS_BY_GLOBAL_POSITION_IDS.value.format(
                placeholders=",".join("?" for _ in gp_ids)
            )
            await cursor.execute(sql, tuple(gp_ids))
            grouped: dict[str, list[Card]] = {}
            for row in cursor:
                gp_id = row["global_position_id"]
                grouped.setdefault(gp_id, []).append(
                    Card(
                        id=UUID(row["id"]),
                        name=row["name"],
                        currency=row["currency"],
                        ending=row["ending"],
                        type=CardType(row["type"]),
                        limit=Dezimal(row["card_limit"]) if row["card_limit"] else None,
                        used=Dezimal(row["used"]),
                        active=bool(row["active"]),
                        related_account=row["related_account"],
                        source=source_map[gp_id],
                    )
                )
            return {UUID(k): Cards(v) for k, v in grouped.items()}

    async def _get_all_loans(
        self, positions: list[GlobalPosition]
    ) -> dict[UUID, Loans]:
        gp_ids = [str(p.id) for p in positions]
        source_map = {str(p.id): p.source for p in positions}
        async with self._db_client.read() as cursor:
            sql = PositionQueries.GET_LOANS_BY_GLOBAL_POSITION_IDS.value.format(
                placeholders=",".join("?" for _ in gp_ids)
            )
            await cursor.execute(sql, tuple(gp_ids))
            grouped: dict[str, list[Loan]] = {}
            for row in cursor:
                gp_id = row["global_position_id"]
                grouped.setdefault(gp_id, []).append(
                    Loan(
                        id=UUID(row["id"]),
                        type=LoanType(row["type"]),
                        currency=row["currency"],
                        name=row["name"],
                        current_installment=Dezimal(row["current_installment"]),
                        interest_rate=Dezimal(row["interest_rate"]),
                        interest_type=InterestType(row["interest_type"]),
                        installment_frequency=InstallmentFrequency(
                            row["installment_frequency"]
                        ),
                        installment_interests=(
                            Dezimal(row["installment_interests"])
                            if row["installment_interests"]
                            else None
                        ),
                        fixed_interest_rate=(
                            Dezimal(row["fixed_interest_rate"])
                            if row["fixed_interest_rate"]
                            else None
                        ),
                        loan_amount=Dezimal(row["loan_amount"]),
                        next_payment_date=(
                            datetime.fromisoformat(row["next_payment_date"]).date()
                            if row["next_payment_date"]
                            else None
                        ),
                        principal_outstanding=Dezimal(row["principal_outstanding"]),
                        euribor_rate=(
                            Dezimal(row["euribor_rate"])
                            if row["euribor_rate"]
                            else None
                        ),
                        fixed_years=int(row["fixed_years"])
                        if row["fixed_years"]
                        else None,
                        creation=datetime.fromisoformat(row["creation"]).date(),
                        maturity=datetime.fromisoformat(row["maturity"]).date(),
                        unpaid=Dezimal(row["unpaid"]) if row["unpaid"] else None,
                        hash=row["hash"] or "",
                        manual_data=_map_manual_entry_data(row),
                        source=source_map[gp_id],
                    )
                )
            return {UUID(k): Loans(v) for k, v in grouped.items()}

    async def _get_all_stocks(
        self, positions: list[GlobalPosition]
    ) -> dict[UUID, StockInvestments]:
        gp_ids = [str(p.id) for p in positions]
        source_map = {str(p.id): p.source for p in positions}
        async with self._db_client.read() as cursor:
            sql = PositionQueries.GET_STOCKS_BY_GLOBAL_POSITION_IDS.value.format(
                placeholders=",".join("?" for _ in gp_ids)
            )
            await cursor.execute(sql, tuple(gp_ids))
            grouped: dict[str, list[StockDetail]] = {}
            for row in cursor:
                gp_id = row["global_position_id"]
                grouped.setdefault(gp_id, []).append(
                    StockDetail(
                        id=UUID(row["id"]),
                        name=row["name"],
                        ticker=row["ticker"],
                        isin=row["isin"],
                        market=row["market"],
                        shares=Dezimal(row["shares"]),
                        initial_investment=Dezimal(row["initial_investment"]),
                        average_buy_price=Dezimal(row["average_buy_price"]),
                        market_value=Dezimal(row["market_value"]),
                        currency=row["currency"],
                        type=EquityType(row["type"]),
                        subtype=row["subtype"],
                        info_sheet_url=row["info_sheet_url"],
                        issuer=row["issuer"],
                        source=source_map[gp_id],
                        manual_data=_map_manual_entry_data(row),
                    )
                )
            return {UUID(k): StockInvestments(v) for k, v in grouped.items()}

    async def _get_all_fund_portfolios(
        self, positions: list[GlobalPosition]
    ) -> dict[UUID, FundPortfolios]:
        gp_ids = [str(p.id) for p in positions]
        source_map = {str(p.id): p.source for p in positions}
        async with self._db_client.read() as cursor:
            sql = (
                PositionQueries.GET_FUND_PORTFOLIOS_BY_GLOBAL_POSITION_IDS.value.format(
                    placeholders=",".join("?" for _ in gp_ids)
                )
            )
            await cursor.execute(sql, tuple(gp_ids))
            grouped: dict[str, list[FundPortfolio]] = {}
            for row in cursor:
                gp_id = row["global_position_id"]
                currency = row["currency"]
                grouped.setdefault(gp_id, []).append(
                    FundPortfolio(
                        id=UUID(row["id"]),
                        name=row["name"],
                        currency=currency,
                        initial_investment=(
                            Dezimal(row["initial_investment"])
                            if row["initial_investment"]
                            else None
                        ),
                        market_value=(
                            Dezimal(row["market_value"])
                            if row["market_value"]
                            else None
                        ),
                        account=(
                            Account(
                                id=UUID(row["account_id"]),
                                total=Dezimal(0),
                                currency=currency,
                                type=AccountType.FUND_PORTFOLIO,
                                name=row["account_name"],
                                iban=row["iban"],
                            )
                            if row["account_id"]
                            else None
                        ),
                        source=source_map[gp_id],
                    )
                )
            return {UUID(k): FundPortfolios(v) for k, v in grouped.items()}

    async def _get_all_funds(
        self, positions: list[GlobalPosition]
    ) -> dict[UUID, FundInvestments]:
        gp_ids = [str(p.id) for p in positions]
        source_map = {str(p.id): p.source for p in positions}
        async with self._db_client.read() as cursor:
            sql = PositionQueries.GET_FUNDS_BY_GLOBAL_POSITION_IDS.value.format(
                placeholders=",".join("?" for _ in gp_ids)
            )
            await cursor.execute(sql, tuple(gp_ids))
            grouped: dict[str, list[FundDetail]] = {}
            for row in cursor:
                gp_id = row["global_position_id"]
                grouped.setdefault(gp_id, []).append(
                    FundDetail(
                        id=UUID(row["id"]),
                        name=row["name"],
                        isin=row["isin"],
                        market=row["market"] if row["market"] else None,
                        shares=Dezimal(row["shares"]),
                        initial_investment=Dezimal(row["initial_investment"]),
                        average_buy_price=Dezimal(row["average_buy_price"]),
                        market_value=Dezimal(row["market_value"]),
                        type=FundType(row["type"]),
                        asset_type=(
                            AssetType(row["asset_type"]) if row["asset_type"] else None
                        ),
                        currency=row["currency"],
                        portfolio=(
                            FundPortfolio(
                                id=UUID(row["portfolio_id"]),
                                name=row["portfolio_name"],
                                currency=(
                                    row["portfolio_currency"]
                                    if row["portfolio_currency"]
                                    else None
                                ),
                                initial_investment=(
                                    Dezimal(row["portfolio_investment"])
                                    if row["portfolio_investment"]
                                    else None
                                ),
                                market_value=(
                                    Dezimal(row["portfolio_value"])
                                    if row["portfolio_value"]
                                    else None
                                ),
                                source=source_map[gp_id],
                            )
                            if row["portfolio_id"]
                            else None
                        ),
                        source=source_map[gp_id],
                        info_sheet_url=row["info_sheet_url"],
                        issuer=row["issuer"],
                        manual_data=_map_manual_entry_data(row),
                    )
                )
            return {UUID(k): FundInvestments(v) for k, v in grouped.items()}

    async def _get_all_factoring(
        self, positions: list[GlobalPosition]
    ) -> dict[UUID, FactoringInvestments]:
        gp_ids = [str(p.id) for p in positions]
        source_map = {str(p.id): p.source for p in positions}
        async with self._db_client.read() as cursor:
            sql = PositionQueries.GET_FACTORING_BY_GLOBAL_POSITION_IDS.value.format(
                placeholders=",".join("?" for _ in gp_ids)
            )
            await cursor.execute(sql, tuple(gp_ids))
            grouped: dict[str, list[FactoringDetail]] = {}
            for row in cursor:
                gp_id = row["global_position_id"]
                grouped.setdefault(gp_id, []).append(
                    FactoringDetail(
                        id=UUID(row["id"]),
                        name=row["name"],
                        amount=Dezimal(row["amount"]),
                        currency=row["currency"],
                        interest_rate=Dezimal(row["interest_rate"]),
                        gross_interest_rate=Dezimal(row["gross_interest_rate"]),
                        late_interest_rate=(
                            Dezimal(row["late_interest_rate"])
                            if row["late_interest_rate"]
                            else None
                        ),
                        gross_late_interest_rate=(
                            Dezimal(row["gross_late_interest_rate"])
                            if row["gross_late_interest_rate"]
                            else None
                        ),
                        last_invest_date=datetime.fromisoformat(
                            row["last_invest_date"]
                        ),
                        start=datetime.fromisoformat(row["start"]),
                        maturity=datetime.fromisoformat(row["maturity"]).date(),
                        type=row["type"],
                        state=row["state"],
                        source=source_map[gp_id],
                    )
                )
            return {UUID(k): FactoringInvestments(v) for k, v in grouped.items()}

    async def _get_all_real_estate_cf(
        self, positions: list[GlobalPosition]
    ) -> dict[UUID, RealEstateCFInvestments]:
        gp_ids = [str(p.id) for p in positions]
        source_map = {str(p.id): p.source for p in positions}
        async with self._db_client.read() as cursor:
            sql = (
                PositionQueries.GET_REAL_ESTATE_CF_BY_GLOBAL_POSITION_IDS.value.format(
                    placeholders=",".join("?" for _ in gp_ids)
                )
            )
            await cursor.execute(sql, tuple(gp_ids))
            grouped: dict[str, list[RealEstateCFDetail]] = {}
            for row in cursor:
                gp_id = row["global_position_id"]
                grouped.setdefault(gp_id, []).append(
                    RealEstateCFDetail(
                        id=UUID(row["id"]),
                        name=row["name"],
                        amount=Dezimal(row["amount"]),
                        pending_amount=Dezimal(row["pending_amount"]),
                        currency=row["currency"],
                        interest_rate=Dezimal(row["interest_rate"]),
                        last_invest_date=datetime.fromisoformat(
                            row["last_invest_date"]
                        ),
                        start=datetime.fromisoformat(row["start"]),
                        maturity=datetime.fromisoformat(row["maturity"]).date(),
                        type=row["type"],
                        business_type=row["business_type"],
                        state=row["state"],
                        extended_maturity=(
                            datetime.fromisoformat(row["extended_maturity"]).date()
                            if row["extended_maturity"]
                            else None
                        ),
                        extended_interest_rate=(
                            Dezimal(row["extended_interest_rate"])
                            if row["extended_interest_rate"]
                            else None
                        ),
                        source=source_map[gp_id],
                    )
                )
            return {UUID(k): RealEstateCFInvestments(v) for k, v in grouped.items()}

    async def _get_all_deposits(
        self, positions: list[GlobalPosition]
    ) -> dict[UUID, Deposits]:
        gp_ids = [str(p.id) for p in positions]
        source_map = {str(p.id): p.source for p in positions}
        async with self._db_client.read() as cursor:
            sql = PositionQueries.GET_DEPOSITS_BY_GLOBAL_POSITION_IDS.value.format(
                placeholders=",".join("?" for _ in gp_ids)
            )
            await cursor.execute(sql, tuple(gp_ids))
            grouped: dict[str, list[Deposit]] = {}
            for row in cursor:
                gp_id = row["global_position_id"]
                grouped.setdefault(gp_id, []).append(
                    Deposit(
                        id=UUID(row["id"]),
                        name=row["name"],
                        amount=Dezimal(row["amount"]),
                        currency=row["currency"],
                        expected_interests=Dezimal(row["expected_interests"]),
                        interest_rate=Dezimal(row["interest_rate"]),
                        creation=datetime.fromisoformat(row["creation"]),
                        maturity=datetime.fromisoformat(row["maturity"]).date(),
                        source=source_map[gp_id],
                    )
                )
            return {UUID(k): Deposits(v) for k, v in grouped.items()}

    async def _get_all_crowdlending(
        self, positions: list[GlobalPosition]
    ) -> dict[UUID, Crowdlending]:
        gp_ids = [str(p.id) for p in positions]
        async with self._db_client.read() as cursor:
            sql = PositionQueries.GET_CROWDLENDING_BY_GLOBAL_POSITION_IDS.value.format(
                placeholders=",".join("?" for _ in gp_ids)
            )
            await cursor.execute(sql, tuple(gp_ids))
            result: dict[UUID, Crowdlending] = {}
            for row in cursor:
                gp_id = row["global_position_id"]
                result[UUID(gp_id)] = Crowdlending(
                    id=UUID(row["id"]),
                    total=Dezimal(row["total"]),
                    weighted_interest_rate=Dezimal(row["weighted_interest_rate"]),
                    currency=row["currency"],
                    distribution=(
                        json.loads(row["distribution"]) if row["distribution"] else None
                    ),
                    entries=[],
                )
            return result

    async def _get_all_cryptocurrency(
        self, positions: list[GlobalPosition]
    ) -> dict[UUID, CryptoCurrencies]:
        gp_ids = [str(p.id) for p in positions]
        source_map = {str(p.id): p.source for p in positions}
        entity_map = {str(p.id): p.entity for p in positions}
        async with self._db_client.read() as cursor:
            sql = PositionQueries.GET_CRYPTO_BY_GLOBAL_POSITION_IDS.value.format(
                placeholders=",".join("?" for _ in gp_ids)
            )
            await cursor.execute(sql, tuple(gp_ids))

            per_gp: dict[str, dict[UUID | None, list[CryptoCurrencyPosition]]] = {}
            for row in cursor:
                gp_id = row["global_position_id"]
                raw_wallet_id = row["wallet_id"]
                wallet_id = UUID(raw_wallet_id) if raw_wallet_id else None

                crypto_asset = None
                if row["crypto_asset_id"]:
                    icon_urls = []
                    if row["asset_icon_urls"]:
                        try:
                            icon_urls = json.loads(row["asset_icon_urls"]) or []
                        except Exception:
                            icon_urls = []
                    external_ids = {}
                    if row["asset_external_ids"]:
                        try:
                            external_ids = json.loads(row["asset_external_ids"]) or {}
                        except Exception:
                            external_ids = {}
                    crypto_asset = CryptoAsset(
                        id=UUID(row["asset_id"]),
                        name=row["asset_name"],
                        symbol=row["asset_symbol"],
                        icon_urls=icon_urls,
                        external_ids=external_ids,
                    )

                crypto_pos = CryptoCurrencyPosition(
                    id=UUID(row["position_id"]),
                    symbol=row["symbol"],
                    name=row["position_name"],
                    amount=Dezimal(row["amount"]),
                    type=CryptoCurrencyType(row["type"]),
                    market_value=(
                        Dezimal(row["market_value"]) if row["market_value"] else None
                    ),
                    currency=row["currency"],
                    contract_address=row["contract_address"],
                    crypto_asset=crypto_asset,
                    initial_investment=(
                        Dezimal(row["initial_investment"])
                        if row["initial_investment"]
                        else None
                    ),
                    average_buy_price=(
                        Dezimal(row["average_buy_price"])
                        if row["average_buy_price"]
                        else None
                    ),
                    investment_currency=(
                        row["investment_currency"]
                        if row["investment_currency"]
                        else None
                    ),
                    source=source_map[gp_id],
                )
                per_gp.setdefault(gp_id, {}).setdefault(wallet_id, []).append(
                    crypto_pos
                )

            if not per_gp:
                return {}

            all_entity_ids = set()
            for gp_id, wallet_positions in per_gp.items():
                for wid in wallet_positions:
                    if wid is not None:
                        all_entity_ids.add(str(entity_map[gp_id].id))

            wallets_by_id: dict[UUID, CryptoWallet] = {}
            if all_entity_ids:
                entity_id_list = list(all_entity_ids)
                sql_w = CryptoWalletQueries.GET_BY_ENTITY_IDS.value.format(
                    placeholders=",".join("?" for _ in entity_id_list)
                )
                await cursor.execute(sql_w, tuple(entity_id_list))
                crypto_wallets = await CryptoWalletRepository._map_crypto_rows(
                    cursor, await cursor.fetchall(), False
                )
                wallets_by_id = {w.id: w for w in crypto_wallets}

            result: dict[UUID, CryptoCurrencies] = {}
            for gp_id, wallet_positions in per_gp.items():
                result_wallets = []
                for wallet_id, crypto_positions in wallet_positions.items():
                    if wallet_id is not None and wallet_id in wallets_by_id:
                        w = wallets_by_id[wallet_id]
                        wallet = CryptoCurrencyWallet(
                            id=w.id,
                            name=w.name,
                            address_source=w.address_source,
                            addresses=w.addresses,
                            assets=crypto_positions,
                            hd_wallet=w.hd_wallet,
                        )
                    else:
                        wallet = CryptoCurrencyWallet(assets=crypto_positions)
                    result_wallets.append(wallet)
                result[UUID(gp_id)] = CryptoCurrencies(result_wallets)
            return result

    async def _get_all_commodities(
        self, positions: list[GlobalPosition]
    ) -> dict[UUID, Commodities]:
        gp_ids = [str(p.id) for p in positions]
        async with self._db_client.read() as cursor:
            sql = PositionQueries.GET_COMMODITIES_BY_GLOBAL_POSITION_IDS.value.format(
                placeholders=",".join("?" for _ in gp_ids)
            )
            await cursor.execute(sql, tuple(gp_ids))
            grouped: dict[str, list[Commodity]] = {}
            for row in cursor:
                gp_id = row["global_position_id"]
                grouped.setdefault(gp_id, []).append(
                    Commodity(
                        id=UUID(row["id"]),
                        name=row["name"],
                        type=CommodityType(row["type"]),
                        amount=Dezimal(row["amount"]),
                        unit=WeightUnit(row["unit"]),
                        market_value=Dezimal(row["market_value"]),
                        currency=row["currency"],
                        initial_investment=(
                            Dezimal(row["initial_investment"])
                            if row["initial_investment"]
                            else None
                        ),
                        average_buy_price=(
                            Dezimal(row["average_buy_price"])
                            if row["average_buy_price"]
                            else None
                        ),
                    )
                )
            return {UUID(k): Commodities(v) for k, v in grouped.items()}

    async def _get_all_derivatives(
        self, positions: list[GlobalPosition]
    ) -> dict[UUID, DerivativePositions]:
        gp_ids = [str(p.id) for p in positions]
        source_map = {str(p.id): p.source for p in positions}
        async with self._db_client.read() as cursor:
            sql = PositionQueries.GET_DERIVATIVES_BY_GLOBAL_POSITION_IDS.value.format(
                placeholders=",".join("?" for _ in gp_ids)
            )
            await cursor.execute(sql, tuple(gp_ids))
            grouped: dict[str, list[DerivativeDetail]] = {}
            for row in cursor:
                gp_id = row["global_position_id"]
                grouped.setdefault(gp_id, []).append(
                    DerivativeDetail(
                        id=UUID(row["id"]),
                        symbol=row["symbol"],
                        underlying_asset=ProductType(row["underlying_asset"]),
                        contract_type=DerivativeContractType(row["contract_type"]),
                        direction=PositionDirection(row["direction"]),
                        size=Dezimal(row["size"]),
                        entry_price=Dezimal(row["entry_price"]),
                        currency=row["currency"],
                        mark_price=Dezimal(row["mark_price"])
                        if row["mark_price"]
                        else None,
                        market_value=Dezimal(row["market_value"])
                        if row["market_value"]
                        else None,
                        unrealized_pnl=Dezimal(row["unrealized_pnl"])
                        if row["unrealized_pnl"]
                        else None,
                        leverage=Dezimal(row["leverage"]) if row["leverage"] else None,
                        margin=Dezimal(row["margin"]) if row["margin"] else None,
                        margin_type=MarginType(row["margin_type"])
                        if row["margin_type"]
                        else None,
                        liquidation_price=Dezimal(row["liquidation_price"])
                        if row["liquidation_price"]
                        else None,
                        isin=row["isin"],
                        strike_price=Dezimal(row["strike_price"])
                        if row["strike_price"]
                        else None,
                        knock_out_price=Dezimal(row["knock_out_price"])
                        if row["knock_out_price"]
                        else None,
                        ratio=Dezimal(row["ratio"]) if row["ratio"] else None,
                        issuer=row["issuer"],
                        underlying_symbol=row["underlying_symbol"],
                        underlying_isin=row["underlying_isin"],
                        expiry=date.fromisoformat(row["expiry"])
                        if row["expiry"]
                        else None,
                        name=row["name"],
                        initial_investment=Dezimal(row["initial_investment"])
                        if row["initial_investment"]
                        else None,
                        source=source_map[gp_id],
                    )
                )
            return {UUID(k): DerivativePositions(v) for k, v in grouped.items()}

    async def _batch_load_all_products(
        self,
        positions: list[GlobalPosition],
        products: list[ProductType] | None = None,
    ) -> None:
        if not positions:
            return

        batch_loaders: list[tuple[ProductType, Callable]] = [
            (ProductType.ACCOUNT, self._get_all_accounts),
            (ProductType.CARD, self._get_all_cards),
            (ProductType.LOAN, self._get_all_loans),
            (ProductType.STOCK_ETF, self._get_all_stocks),
            (ProductType.FUND, self._get_all_funds),
            (ProductType.FUND_PORTFOLIO, self._get_all_fund_portfolios),
            (ProductType.FACTORING, self._get_all_factoring),
            (ProductType.REAL_ESTATE_CF, self._get_all_real_estate_cf),
            (ProductType.DEPOSIT, self._get_all_deposits),
            (ProductType.CROWDLENDING, self._get_all_crowdlending),
            (ProductType.CRYPTO, self._get_all_cryptocurrency),
            (ProductType.COMMODITY, self._get_all_commodities),
            (ProductType.DERIVATIVE, self._get_all_derivatives),
        ]

        for product_type, loader in batch_loaders:
            if products and product_type not in products:
                continue
            results = await loader(positions)
            for pos in positions:
                product = results.get(pos.id)
                if product:
                    pos.products[product_type] = product

    async def _get_entity_id_from_global(self, global_position_id: UUID) -> int:
        async with self._db_client.read() as cursor:
            await cursor.execute(
                PositionQueries.GET_ENTITY_ID_FROM_GLOBAL_POSITION_ID,
                (str(global_position_id),),
            )
            return await cursor.fetchone()[0]

    async def delete_position_for_date(
        self, entity_id: UUID, date: date, source: DataSource
    ):
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                PositionQueries.DELETE_POSITION_FOR_DATE,
                (str(entity_id), date.isoformat(), source.value),
            )

    async def get_by_id(self, position_id: UUID) -> Optional[GlobalPosition]:
        async with self._db_client.read() as cursor:
            await cursor.execute(
                PositionQueries.GET_GLOBAL_POSITION_BY_ID,
                (str(position_id),),
            )
            row = await cursor.fetchone()
            if not row:
                return None
            entity = Entity(
                id=UUID(row["entity_id"]),
                name=row["entity_name"],
                natural_id=row["entity_natural_id"],
                type=row["entity_type"],
                origin=row["entity_origin"],
                icon_url=row["icon_url"],
            )

            pos_id = UUID(row["id"])
            source = DataSource(row["source"])
            position = GlobalPosition(
                id=pos_id,
                entity=entity,
                date=datetime.fromisoformat(row["date"]),
                source=source,
                entity_account_id=UUID(row["entity_account_id"])
                if row["entity_account_id"]
                else None,
            )
            position.products = {}
            await self._batch_load_all_products([position])
            return position

    async def delete_by_id(self, position_id: UUID):
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                PositionQueries.DELETE_GLOBAL_POSITION_BY_ID,
                (str(position_id),),
            )

    async def get_stock_detail(self, entry_id: UUID) -> Optional[StockDetail]:
        async with self._db_client.read() as cursor:
            await cursor.execute(
                PositionQueries.GET_STOCK_DETAIL,
                (str(entry_id),),
            )
            row = await cursor.fetchone()
            if not row:
                return None
            return StockDetail(
                id=UUID(row["id"]),
                name=row["name"],
                ticker=row["ticker"],
                isin=row["isin"],
                market=row["market"],
                shares=Dezimal(row["shares"]),
                initial_investment=Dezimal(row["initial_investment"]),
                average_buy_price=Dezimal(row["average_buy_price"]),
                market_value=Dezimal(row["market_value"]),
                currency=row["currency"],
                type=EquityType(row["type"]),
                subtype=row["subtype"],
                info_sheet_url=row["info_sheet_url"],
                issuer=row["issuer"],
                source=DataSource(row["source"]),
            )

    async def get_fund_detail(self, entry_id: UUID) -> Optional[FundDetail]:
        async with self._db_client.read() as cursor:
            await cursor.execute(
                PositionQueries.GET_FUND_DETAIL,
                (str(entry_id),),
            )
            row = await cursor.fetchone()
            if not row:
                return None

            return FundDetail(
                id=UUID(row["id"]),
                name=row["name"],
                isin=row["isin"],
                market=row["market"],
                shares=Dezimal(row["shares"]),
                initial_investment=Dezimal(row["initial_investment"]),
                average_buy_price=Dezimal(row["average_buy_price"]),
                market_value=Dezimal(row["market_value"]),
                currency=row["currency"],
                type=FundType(row["type"]),
                asset_type=AssetType(row["asset_type"]) if row["asset_type"] else None,
                info_sheet_url=row["info_sheet_url"],
                issuer=row["issuer"],
                source=DataSource(row["source"]),
            )

    async def update_market_value(
        self, entry_id: UUID, product_type: ProductType, market_value: Dezimal
    ):
        if product_type == ProductType.STOCK_ETF:
            sql = PositionQueries.UPDATE_STOCK_MARKET_VALUE
        elif product_type == ProductType.FUND:
            sql = PositionQueries.UPDATE_FUND_MARKET_VALUE
        else:
            return
        async with self._db_client.tx() as cursor:
            await cursor.execute(sql, (str(market_value), str(entry_id)))

    def _row_to_loan(self, row) -> Loan:
        return Loan(
            id=UUID(row["id"]),
            type=LoanType(row["type"]),
            currency=row["currency"],
            name=row["name"],
            current_installment=Dezimal(row["current_installment"]),
            interest_rate=Dezimal(row["interest_rate"]),
            interest_type=InterestType(row["interest_type"]),
            installment_frequency=InstallmentFrequency(row["installment_frequency"]),
            installment_interests=(
                Dezimal(row["installment_interests"])
                if row["installment_interests"]
                else None
            ),
            fixed_interest_rate=(
                Dezimal(row["fixed_interest_rate"])
                if row["fixed_interest_rate"]
                else None
            ),
            loan_amount=Dezimal(row["loan_amount"]),
            next_payment_date=(
                datetime.fromisoformat(row["next_payment_date"]).date()
                if row["next_payment_date"]
                else None
            ),
            principal_outstanding=Dezimal(row["principal_outstanding"]),
            euribor_rate=(
                Dezimal(row["euribor_rate"]) if row["euribor_rate"] else None
            ),
            fixed_years=int(row["fixed_years"]) if row["fixed_years"] else None,
            creation=datetime.fromisoformat(row["creation"]).date(),
            maturity=datetime.fromisoformat(row["maturity"]).date(),
            unpaid=Dezimal(row["unpaid"]) if row["unpaid"] else None,
            hash=row["hash"] or "",
            source=DataSource(row["source"]),
        )

    async def get_loans_by_hash(self, hashes: list[str]) -> dict[str, Loan]:
        if not hashes:
            return {}
        placeholders = ",".join("?" for _ in hashes)
        query = PositionQueries.GET_LOANS_BY_HASHES.replace(
            "{placeholders}", placeholders
        )
        async with self._db_client.read() as cursor:
            await cursor.execute(query, tuple(hashes))
            result = {}
            for row in cursor:
                loan = self._row_to_loan(row)
                result[loan.hash] = loan
            return result

    async def get_loan_by_entry_id(self, entry_id: UUID) -> Optional[Loan]:
        async with self._db_client.read() as cursor:
            await cursor.execute(PositionQueries.GET_LOAN_BY_ENTRY_ID, (str(entry_id),))
            row = None
            for r in cursor:
                row = r
                break
            if not row:
                return None
            return self._row_to_loan(row)

    async def update_loan_position(
        self,
        entry_id: UUID,
        current_installment: Dezimal,
        installment_interests: Optional[Dezimal],
        principal_outstanding: Dezimal,
        next_payment_date: Optional[date],
    ):
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                PositionQueries.UPDATE_LOAN_POSITION,
                (
                    str(current_installment),
                    str(installment_interests)
                    if installment_interests is not None
                    else None,
                    str(principal_outstanding),
                    next_payment_date.isoformat() if next_payment_date else None,
                    str(entry_id),
                ),
            )

    # --- Stale reference migration ---

    async def get_latest_real_position_id(
        self, entity_account_id: UUID
    ) -> Optional[UUID]:
        async with self._db_client.read() as cursor:
            await cursor.execute(
                PositionQueries.GET_LATEST_REAL_POSITION_ID_FOR_ENTITY_ACCOUNT,
                (str(entity_account_id),),
            )
            row = await cursor.fetchone()
            if not row:
                return None
            return UUID(row["id"])

    async def get_account_iban_index(
        self, global_position_id: UUID
    ) -> dict[UUID, Optional[str]]:
        async with self._db_client.read() as cursor:
            await cursor.execute(
                PositionQueries.GET_ACCOUNTS_LIGHTWEIGHT,
                (str(global_position_id),),
            )
            rows = await cursor.fetchall()
            return {UUID(r["id"]): r["iban"] for r in rows}

    async def get_portfolio_name_index(
        self, global_position_id: UUID
    ) -> dict[UUID, Optional[str]]:
        async with self._db_client.read() as cursor:
            await cursor.execute(
                PositionQueries.GET_FUND_PORTFOLIOS_LIGHTWEIGHT,
                (str(global_position_id),),
            )
            rows = await cursor.fetchall()
            return {UUID(r["id"]): r["name"] for r in rows}

    async def migrate_references(
        self,
        account_mapping: dict[UUID, UUID],
        portfolio_mapping: dict[UUID, UUID],
    ):
        async with self._db_client.tx() as cursor:
            for old_id, new_id in account_mapping.items():
                await cursor.execute(
                    PositionQueries.MIGRATE_CARD_RELATED_ACCOUNTS,
                    (str(new_id), str(old_id)),
                )
                await cursor.execute(
                    PositionQueries.MIGRATE_FUND_PORTFOLIO_ACCOUNTS,
                    (str(new_id), str(old_id)),
                )
            for old_id, new_id in portfolio_mapping.items():
                await cursor.execute(
                    PositionQueries.MIGRATE_FUND_PORTFOLIO_REFERENCES,
                    (str(new_id), str(old_id)),
                )

    async def account_exists(self, entry_id: UUID) -> bool:
        async with self._db_client.read() as cursor:
            await cursor.execute(
                PositionQueries.ACCOUNT_EXISTS,
                (str(entry_id),),
            )
            return await cursor.fetchone() is not None

    async def fund_portfolio_exists(self, entry_id: UUID) -> bool:
        async with self._db_client.read() as cursor:
            await cursor.execute(
                PositionQueries.FUND_PORTFOLIO_EXISTS,
                (str(entry_id),),
            )
            return await cursor.fetchone() is not None
