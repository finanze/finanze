import json
from datetime import datetime
from typing import Callable, Dict, Optional
from uuid import UUID

from application.ports.position_port import PositionPort
from domain.commodity import CommodityType, WeightUnit
from domain.dezimal import Dezimal
from domain.entity import Entity
from domain.global_position import (
    Account,
    Accounts,
    AccountType,
    Card,
    Cards,
    CardType,
    Commodities,
    Commodity,
    Crowdlending,
    CryptoCurrencies,
    CryptoCurrency,
    CryptoCurrencyToken,
    CryptoCurrencyWallet,
    CryptoToken,
    Deposit,
    Deposits,
    FactoringDetail,
    FactoringInvestments,
    FundDetail,
    FundInvestments,
    FundPortfolio,
    FundPortfolios,
    GlobalPosition,
    InterestType,
    Loan,
    Loans,
    LoanType,
    PositionQueryRequest,
    ProductPositions,
    ProductType,
    RealEstateCFDetail,
    RealEstateCFInvestments,
    StockDetail,
    StockInvestments,
)
from infrastructure.repository.common.json_serialization import DezimalJSONEncoder
from infrastructure.repository.db.client import DBClient, DBCursor


def _save_loans(cursor, position: GlobalPosition, loans: Loans):
    for loan in loans.entries:
        cursor.execute(
            """
            INSERT INTO loan_positions (id, global_position_id, type, currency, name, current_installment,
                                        interest_rate, interest_type, loan_amount, next_payment_date,
                                        principal_outstanding, principal_paid, euribor_rate, fixed_years,
                                        creation, maturity, unpaid)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(loan.id),
                str(position.id),
                loan.type,
                loan.currency,
                loan.name,
                str(loan.current_installment),
                str(loan.interest_rate),
                loan.interest_type,
                str(loan.loan_amount),
                loan.next_payment_date.isoformat(),
                str(loan.principal_outstanding),
                str(loan.principal_paid),
                str(loan.euribor_rate) if loan.euribor_rate else None,
                str(loan.fixed_years) if loan.fixed_years else None,
                loan.creation.isoformat() if loan.creation else None,
                loan.maturity.isoformat() if loan.maturity else None,
                str(loan.unpaid) if loan.unpaid else None,
            ),
        )


def _save_cards(cursor, position: GlobalPosition, cards: Cards):
    for card in cards.entries:
        cursor.execute(
            """
            INSERT INTO card_positions (id, global_position_id, type, name, currency,
                                        ending, card_limit, used, active, related_account)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
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


def _save_accounts(cursor, position: GlobalPosition, accounts: Accounts):
    for account in accounts.entries:
        cursor.execute(
            """
            INSERT INTO account_positions (id, global_position_id, type, currency, name, iban, total,
                                           interest, retained, pending_transfers)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
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


def _save_crowdlending(cursor, position: GlobalPosition, crowdlending: Crowdlending):
    cursor.execute(
        """
        INSERT INTO crowdlending_positions (id, global_position_id, total, weighted_interest_rate, currency, distribution)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            str(crowdlending.id),
            str(position.id),
            str(crowdlending.total),
            str(crowdlending.weighted_interest_rate),
            crowdlending.currency,
            json.dumps(crowdlending.distribution, cls=DezimalJSONEncoder)
            if crowdlending.distribution
            else "{}",
        ),
    )


def _save_commodities(cursor, position: GlobalPosition, commodities: Commodities):
    for commodity in commodities.entries:
        cursor.execute(
            """
            INSERT INTO commodity_positions (id, global_position_id, name, type, amount, unit,
                                           market_value, currency, initial_investment, average_buy_price)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(commodity.id),
                str(position.id),
                commodity.name,
                commodity.type.value,
                str(commodity.amount),
                commodity.unit.value,
                str(commodity.market_value),
                commodity.currency,
                str(commodity.initial_investment)
                if commodity.initial_investment
                else None,
                str(commodity.average_buy_price)
                if commodity.average_buy_price
                else None,
            ),
        )


def _save_crypto_currency_token_positions(cursor, wallet_detail: CryptoCurrencyWallet):
    for token_detail in wallet_detail.tokens:
        cursor.execute(
            """
            INSERT INTO crypto_currency_token_positions (id, wallet_id, token_id, name, symbol, token, amount,
                                               market_value, currency, type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(token_detail.id),
                str(wallet_detail.id),
                token_detail.token_id,
                token_detail.name,
                token_detail.symbol,
                token_detail.token,
                str(token_detail.amount),
                str(token_detail.market_value),
                token_detail.currency,
                token_detail.type,
            ),
        )


def _save_crypto_currencies(
    cursor, position: GlobalPosition, cryptocurrencies: CryptoCurrencies
):
    for wallet_detail in cryptocurrencies.entries:
        cursor.execute(
            """
            INSERT INTO crypto_currency_wallet_positions (id, global_position_id, wallet_connection_id, symbol, amount,
                                                          market_value, currency,
                                                          crypto)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(wallet_detail.id),
                str(position.id),
                str(wallet_detail.wallet_connection_id),
                wallet_detail.symbol,
                str(wallet_detail.amount),
                str(wallet_detail.market_value),
                wallet_detail.currency,
                wallet_detail.crypto.value,
            ),
        )
        _save_crypto_currency_token_positions(cursor, wallet_detail)


def _save_deposits(cursor, position: GlobalPosition, deposits: Deposits):
    for detail in deposits.entries:
        cursor.execute(
            """
            INSERT INTO deposit_positions (id, global_position_id, name, amount, currency,
                                           expected_interests, interest_rate, creation, maturity)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
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


def _save_real_estate_cf(
    cursor, position: GlobalPosition, real_estate: RealEstateCFInvestments
):
    for detail in real_estate.entries:
        cursor.execute(
            """
            INSERT INTO real_estate_cf_positions (id, global_position_id, name, amount, pending_amount, currency,
                                                 interest_rate, profitability, last_invest_date, maturity, type,
                                                 business_type, state, extended_maturity)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
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
                detail.maturity.isoformat(),
                detail.type,
                detail.business_type,
                detail.state,
                detail.extended_maturity.isoformat()
                if detail.extended_maturity
                else None,
            ),
        )


def _save_factoring(cursor, position: GlobalPosition, factoring: FactoringInvestments):
    for detail in factoring.entries:
        cursor.execute(
            """
            INSERT INTO factoring_positions (id, global_position_id, name, amount, currency,
                                             interest_rate, profitability, gross_interest_rate, last_invest_date,
                                             maturity, type, state)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(detail.id),
                str(position.id),
                detail.name,
                str(detail.amount),
                detail.currency,
                str(detail.interest_rate),
                str(detail.profitability),
                str(detail.gross_interest_rate),
                detail.last_invest_date.isoformat()
                if detail.last_invest_date
                else None,
                detail.maturity.isoformat(),
                detail.type,
                detail.state,
            ),
        )


def _save_fund_portfolios(cursor, position: GlobalPosition, portfolios: FundPortfolios):
    for portfolio in portfolios.entries:
        cursor.execute(
            """
            INSERT INTO fund_portfolios (id, global_position_id, name, currency, initial_investment, market_value)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(portfolio.id),
                str(position.id),
                portfolio.name,
                portfolio.currency,
                str(portfolio.initial_investment)
                if portfolio.initial_investment
                else None,
                str(portfolio.market_value) if portfolio.market_value else None,
            ),
        )


def _save_funds(cursor, position: GlobalPosition, funds: FundInvestments):
    for detail in funds.entries:
        cursor.execute(
            """
            INSERT INTO fund_positions (id, global_position_id, name, isin, market,
                                        shares, initial_investment, average_buy_price,
                                        market_value, currency, portfolio_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(detail.id),
                str(position.id),
                detail.name,
                detail.isin,
                detail.market,
                str(detail.shares),
                str(detail.initial_investment),
                str(detail.average_buy_price),
                str(detail.market_value),
                detail.currency,
                str(detail.portfolio.id) if detail.portfolio else None,
            ),
        )


def _save_stocks(cursor, position: GlobalPosition, stocks: StockInvestments):
    for detail in stocks.entries:
        cursor.execute(
            """
            INSERT INTO stock_positions (id, global_position_id, name, ticker, isin, market,
                                         shares, initial_investment, average_buy_price,
                                         market_value, currency, type, subtype)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
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
                detail.type,
                detail.subtype,
            ),
        )


def _save_position(
    cursor, position: GlobalPosition, product_type: ProductType, save_fn: Callable
):
    product_position = position.products.get(product_type)
    if product_position:
        save_fn(cursor, position, product_position)


def _save_product_positions(cursor, position: GlobalPosition):
    _save_position(cursor, position, ProductType.ACCOUNT, _save_accounts)
    _save_position(cursor, position, ProductType.CARD, _save_cards)
    _save_position(cursor, position, ProductType.LOAN, _save_loans)
    _save_position(cursor, position, ProductType.STOCK_ETF, _save_stocks)
    _save_position(cursor, position, ProductType.FUND_PORTFOLIO, _save_fund_portfolios)
    _save_position(cursor, position, ProductType.FUND, _save_funds)
    _save_position(cursor, position, ProductType.FACTORING, _save_factoring)
    _save_position(cursor, position, ProductType.REAL_ESTATE_CF, _save_real_estate_cf)
    _save_position(cursor, position, ProductType.DEPOSIT, _save_deposits)
    _save_position(cursor, position, ProductType.CROWDLENDING, _save_crowdlending)
    _save_position(cursor, position, ProductType.CRYPTO, _save_crypto_currencies)
    _save_position(cursor, position, ProductType.COMMODITY, _save_commodities)


def _store_position(
    positions: ProductPositions,
    global_position_id: UUID,
    product_type: ProductType,
    get_fc: Callable,
):
    position = get_fc(global_position_id)
    if position:
        positions[product_type] = position


class PositionSQLRepository(PositionPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    def save(self, position: GlobalPosition):
        with self._db_client.tx() as cursor:
            cursor.execute(
                "INSERT INTO global_positions (id, date, entity_id, is_real) VALUES (?, ?, ?, ?)",
                (
                    str(position.id),
                    position.date.isoformat(),
                    str(position.entity.id),
                    position.is_real,
                ),
            )

            _save_product_positions(cursor, position)

    def get_last_grouped_by_entity(
        self, query: Optional[PositionQueryRequest] = None
    ) -> dict[Entity, GlobalPosition]:
        real_global_position_by_entity, manual_global_position_by_entity = {}, {}

        if not query or query.real is None or query.real:
            real_global_position_by_entity = self._get_real_grouped_by_entity(query)
        if not query or query.real is None or not query.real:
            manual_global_position_by_entity = self._get_non_real_grouped_by_entity(
                query
            )

        global_position_by_entity = {}
        for entity, position in real_global_position_by_entity.items():
            if entity in manual_global_position_by_entity:
                manual = manual_global_position_by_entity[entity]
                global_position_by_entity[entity] = position + manual
                del manual_global_position_by_entity[entity]
            else:
                global_position_by_entity[entity] = position

        for entity, position in manual_global_position_by_entity.items():
            global_position_by_entity[entity] = position

        return global_position_by_entity

    def _get_real_grouped_by_entity(
        self, query: Optional[PositionQueryRequest]
    ) -> Dict[Entity, GlobalPosition]:
        with self._db_client.read() as cursor:
            sql = """
                  WITH latest_positions AS (SELECT entity_id, MAX(date) as latest_date
                                            FROM global_positions
                                            WHERE is_real = TRUE
                                            GROUP BY entity_id)
                  SELECT gp.*,
                         e.name    AS entity_name,
                         e.id      AS entity_id,
                         e.type    as entity_type,
                         e.is_real AS entity_is_real
                  FROM global_positions gp
                           JOIN latest_positions lp
                                ON gp.entity_id = lp.entity_id AND gp.date = lp.latest_date
                           JOIN entities e ON gp.entity_id = e.id
                  WHERE gp.is_real = TRUE
                  """

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
                sql += " AND " + " AND ".join(conditions)

            cursor.execute(sql, tuple(params))

            return self._map_position_rows(cursor)

    def _map_position_rows(self, cursor: DBCursor):
        positions = {}
        for row in cursor.fetchall():
            entity = Entity(
                id=UUID(row["entity_id"]),
                name=row["entity_name"],
                type=row["entity_type"],
                is_real=row["entity_is_real"],
            )

            position = GlobalPosition(
                id=UUID(row["id"]),
                entity=entity,
                date=datetime.fromisoformat(row["date"]),
                products=self._get_product_positions(row["id"]),
                is_real=row["is_real"],
            )
            positions[entity] = position
        return positions

    def _get_non_real_grouped_by_entity(
        self, query: Optional[PositionQueryRequest]
    ) -> Dict[Entity, GlobalPosition]:
        with self._db_client.read() as cursor:
            sql = """
                  WITH latest_import_details AS (SELECT import_id
                                                 FROM virtual_data_imports
                                                 ORDER BY date DESC
                                                 LIMIT 1),
                       last_imported_position_ids AS (SELECT vdi.global_position_id
                                                      FROM virtual_data_imports vdi
                                                               JOIN latest_import_details lid
                                                                    ON vdi.import_id = lid.import_id),
                       latest_positions AS (SELECT entity_id, MAX(date) as latest_date
                                            FROM global_positions gp
                                                     INNER JOIN last_imported_position_ids lp
                                                                ON gp.id = lp.global_position_id
                                            WHERE gp.is_real = FALSE
                                            GROUP BY gp.entity_id)
                  SELECT gp.*,
                         e.name    AS entity_name,
                         e.id      AS entity_id,
                         e.type    AS entity_type,
                         e.is_real AS entity_is_real
                  FROM global_positions gp
                           JOIN latest_positions lp
                                ON gp.entity_id = lp.entity_id AND gp.date = lp.latest_date
                           JOIN entities e ON gp.entity_id = e.id
                  WHERE gp.is_real = FALSE \
                  """

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
                sql += " AND " + " AND ".join(conditions)

            cursor.execute(sql, tuple(params))

            return self._map_position_rows(cursor)

    def _get_accounts(self, global_position_id: UUID) -> Optional[Accounts]:
        with self._db_client.read() as cursor:
            cursor.execute(
                """
                           SELECT *
                           FROM account_positions
                           WHERE global_position_id = ?
                           """,
                (str(global_position_id),),
            )

            accounts = [
                Account(
                    id=UUID(row["id"]),
                    total=Dezimal(row["total"]),
                    currency=row["currency"],
                    type=AccountType[row["type"]],
                    name=row["name"],
                    iban=row["iban"],
                    interest=Dezimal(row["interest"]) if row["interest"] else None,
                    retained=Dezimal(row["retained"]) if row["retained"] else None,
                    pending_transfers=Dezimal(row["pending_transfers"])
                    if row["pending_transfers"]
                    else None,
                )
                for row in cursor
            ]

            if not accounts:
                return None

            return Accounts(accounts)

    def _get_cards(self, global_position_id: UUID) -> Optional[Cards]:
        with self._db_client.read() as cursor:
            cursor.execute(
                "SELECT * FROM card_positions WHERE global_position_id = ?",
                (str(global_position_id),),
            )

            cards = [
                Card(
                    id=UUID(row["id"]),
                    name=row["name"],
                    currency=row["currency"],
                    ending=row["ending"],
                    type=CardType[row["type"]],
                    limit=Dezimal(row["card_limit"]) if row["card_limit"] else None,
                    used=Dezimal(row["used"]),
                    active=bool(row["active"]),
                    related_account=row["related_account"],
                )
                for row in cursor
            ]

            if not cards:
                return None

            return Cards(cards)

    def _get_loans(self, global_position_id: UUID) -> Optional[Loans]:
        with self._db_client.read() as cursor:
            cursor.execute(
                "SELECT * FROM loan_positions WHERE global_position_id = ?",
                (str(global_position_id),),
            )

            loans = [
                Loan(
                    id=UUID(row["id"]),
                    type=LoanType[row["type"]],
                    currency=row["currency"],
                    name=row["name"],
                    current_installment=Dezimal(row["current_installment"]),
                    interest_rate=Dezimal(row["interest_rate"]),
                    interest_type=row["interest_type"]
                    if row["interest_type"]
                    else InterestType.FIXED,
                    loan_amount=Dezimal(row["loan_amount"]),
                    next_payment_date=datetime.fromisoformat(
                        row["next_payment_date"]
                    ).date(),
                    principal_outstanding=Dezimal(row["principal_outstanding"]),
                    principal_paid=Dezimal(row["principal_paid"]),
                    euribor_rate=Dezimal(row["euribor_rate"])
                    if row["euribor_rate"]
                    else None,
                    fixed_years=int(row["fixed_years"]) if row["fixed_years"] else None,
                    creation=datetime.fromisoformat(row["creation"]).date()
                    if row["creation"]
                    else None,
                    maturity=datetime.fromisoformat(row["maturity"]).date()
                    if row["maturity"]
                    else None,
                    unpaid=Dezimal(row["unpaid"]) if row["unpaid"] else None,
                )
                for row in cursor
            ]

            if not loans:
                return None

            return Loans(loans)

    def _get_stocks(self, global_position_id: UUID) -> Optional[StockInvestments]:
        with self._db_client.read() as cursor:
            cursor.execute(
                "SELECT * FROM stock_positions WHERE global_position_id = ?",
                (str(global_position_id),),
            )

            details = [
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
                    type=row["type"],
                    subtype=row["subtype"],
                )
                for row in cursor
            ]

            if not details:
                return None

            return StockInvestments(details)

    def _get_fund_portfolios(
        self, global_position_id: UUID
    ) -> Optional[FundPortfolios]:
        with self._db_client.read() as cursor:
            cursor.execute(
                "SELECT * FROM fund_portfolios WHERE global_position_id = ?",
                (str(global_position_id),),
            )

            portfolios = []
            for row in cursor:
                portfolios.append(
                    FundPortfolio(
                        id=UUID(row["id"]),
                        name=row["name"],
                        currency=row["currency"],
                        initial_investment=Dezimal(row["initial_investment"])
                        if row["initial_investment"]
                        else None,
                        market_value=Dezimal(row["market_value"])
                        if row["market_value"]
                        else None,
                    )
                )

            if not portfolios:
                return None

            return FundPortfolios(portfolios)

    def _get_funds(self, global_position_id: UUID) -> Optional[FundInvestments]:
        with self._db_client.read() as cursor:
            cursor.execute(
                """
                           SELECT f.*,
                                  p.id                 AS portfolio_id,
                                  p.name               AS portfolio_name,
                                  p.currency           AS portfolio_currency,
                                  p.initial_investment AS portfolio_investment,
                                  p.market_value       AS portfolio_value
                           FROM fund_positions f
                                    LEFT JOIN fund_portfolios p ON p.id = f.portfolio_id
                           WHERE f.global_position_id = ?
                           """,
                (str(global_position_id),),
            )

            details = [
                FundDetail(
                    id=UUID(row["id"]),
                    name=row["name"],
                    isin=row["isin"],
                    market=row["market"],
                    shares=Dezimal(row["shares"]),
                    initial_investment=Dezimal(row["initial_investment"]),
                    average_buy_price=Dezimal(row["average_buy_price"]),
                    market_value=Dezimal(row["market_value"]),
                    currency=row["currency"],
                    portfolio=FundPortfolio(
                        id=UUID(row["portfolio_id"]),
                        name=row["portfolio_name"],
                        currency=row["portfolio_currency"]
                        if row["portfolio_currency"]
                        else None,
                        initial_investment=Dezimal(row["portfolio_investment"])
                        if row["portfolio_investment"]
                        else None,
                        market_value=Dezimal(row["portfolio_value"])
                        if row["portfolio_value"]
                        else None,
                    )
                    if row["portfolio_id"]
                    else None,
                )
                for row in cursor
            ]

            if not details:
                return None

            return FundInvestments(details)

    def _get_factoring(
        self, global_position_id: UUID
    ) -> Optional[FactoringInvestments]:
        with self._db_client.read() as cursor:
            cursor.execute(
                "SELECT * FROM factoring_positions WHERE global_position_id = ?",
                (str(global_position_id),),
            )

            details = [
                FactoringDetail(
                    id=UUID(row["id"]),
                    name=row["name"],
                    amount=Dezimal(row["amount"]),
                    currency=row["currency"],
                    interest_rate=Dezimal(row["interest_rate"]),
                    profitability=Dezimal(row["profitability"]),
                    gross_interest_rate=Dezimal(row["gross_interest_rate"]),
                    last_invest_date=datetime.fromisoformat(row["last_invest_date"]),
                    maturity=datetime.fromisoformat(row["maturity"]).date(),
                    type=row["type"],
                    state=row["state"],
                )
                for row in cursor
            ]

            if not details:
                return None

            return FactoringInvestments(details)

    def _get_real_estate_cf(
        self, global_position_id: UUID
    ) -> Optional[RealEstateCFInvestments]:
        with self._db_client.read() as cursor:
            cursor.execute(
                "SELECT * FROM real_estate_cf_positions WHERE global_position_id = ?",
                (str(global_position_id),),
            )

            details = [
                RealEstateCFDetail(
                    id=UUID(row["id"]),
                    name=row["name"],
                    amount=Dezimal(row["amount"]),
                    pending_amount=Dezimal(row["pending_amount"]),
                    currency=row["currency"],
                    interest_rate=Dezimal(row["interest_rate"]),
                    profitability=Dezimal(row["profitability"]),
                    last_invest_date=datetime.fromisoformat(row["last_invest_date"]),
                    maturity=row["maturity"],
                    type=row["type"],
                    business_type=row["business_type"],
                    state=row["state"],
                    extended_maturity=row["extended_maturity"],
                )
                for row in cursor
            ]

            if not details:
                return None

            return RealEstateCFInvestments(details)

    def _get_deposits(self, global_position_id: UUID) -> Optional[Deposits]:
        with self._db_client.read() as cursor:
            cursor.execute(
                "SELECT * FROM deposit_positions WHERE global_position_id = ?",
                (str(global_position_id),),
            )

            details = [
                Deposit(
                    id=UUID(row["id"]),
                    name=row["name"],
                    amount=Dezimal(row["amount"]),
                    currency=row["currency"],
                    expected_interests=Dezimal(row["expected_interests"]),
                    interest_rate=Dezimal(row["interest_rate"]),
                    creation=datetime.fromisoformat(row["creation"]),
                    maturity=datetime.fromisoformat(row["maturity"]).date(),
                )
                for row in cursor
            ]

            if not details:
                return None

            return Deposits(details)

    def _get_crowdlending(self, global_position_id: UUID) -> Optional[Crowdlending]:
        with self._db_client.read() as cursor:
            cursor.execute(
                "SELECT * FROM crowdlending_positions WHERE global_position_id = ?",
                (str(global_position_id),),
            )
            row = cursor.fetchone()
            if not row:
                return None

            return Crowdlending(
                id=UUID(row["id"]),
                total=Dezimal(row["total"]),
                weighted_interest_rate=Dezimal(row["weighted_interest_rate"]),
                currency=row["currency"],
                distribution=json.loads(row["distribution"])
                if row["distribution"]
                else None,
                entries=[],
            )

    def _get_crypto_currency_token_positions(
        self, wallet_id: UUID, wallet_connection_id: UUID
    ) -> list[CryptoCurrencyToken]:
        with self._db_client.read() as cursor:
            cursor.execute(
                """
                SELECT p.*,
                       cii.currency AS investment_currency,
                       cii.initial_investment,
                       cii.average_buy_price
                FROM crypto_currency_token_positions p
                         LEFT JOIN crypto_initial_investments cii ON cii.wallet_connection_id = ? AND p.symbol = cii.symbol AND cii.type = 'TOKEN'
                WHERE p.wallet_id = ?
                """,
                (
                    str(wallet_connection_id),
                    str(wallet_id),
                ),
            )
            return [
                CryptoCurrencyToken(
                    id=UUID(row["id"]),
                    token_id=row["token_id"],
                    name=row["name"],
                    symbol=row["symbol"],
                    token=CryptoToken(row["token"]),
                    amount=Dezimal(row["amount"]),
                    initial_investment=Dezimal(row["initial_investment"])
                    if row["initial_investment"]
                    else None,
                    average_buy_price=Dezimal(row["average_buy_price"])
                    if row["average_buy_price"]
                    else None,
                    investment_currency=row["investment_currency"]
                    if row["investment_currency"]
                    else None,
                    market_value=Dezimal(row["market_value"]),
                    currency=row["currency"],
                    type=row["type"],
                )
                for row in cursor
            ]

    def _get_cryptocurrency(
        self, global_position_id: UUID
    ) -> Optional[CryptoCurrencies]:
        with self._db_client.read() as cursor:
            cursor.execute(
                """
                SELECT p.*,
                       c.address,
                       c.name,
                       cii.currency AS investment_currency,
                       cii.initial_investment,
                       cii.average_buy_price
                FROM crypto_currency_wallet_positions p
                         JOIN crypto_wallet_connections c ON p.wallet_connection_id = c.id
                         LEFT JOIN crypto_initial_investments cii ON cii.wallet_connection_id = c.id AND p.symbol = cii.symbol AND cii.type = 'CRYPTO'
                WHERE global_position_id = ?
                """,
                (str(global_position_id),),
            )
            wallets = []
            for row in cursor:
                wallet_id = UUID(row["id"])
                wallet_connection_id = UUID(row["wallet_connection_id"])
                tokens = self._get_crypto_currency_token_positions(
                    wallet_id, wallet_connection_id
                )
                wallets.append(
                    CryptoCurrencyWallet(
                        id=wallet_id,
                        wallet_connection_id=wallet_connection_id,
                        address=row["address"],
                        name=row["name"],
                        symbol=row["symbol"],
                        amount=Dezimal(row["amount"]),
                        initial_investment=Dezimal(row["initial_investment"])
                        if row["initial_investment"]
                        else None,
                        average_buy_price=Dezimal(row["average_buy_price"])
                        if row["average_buy_price"]
                        else None,
                        investment_currency=row["investment_currency"]
                        if row["investment_currency"]
                        else None,
                        market_value=Dezimal(row["market_value"]),
                        currency=row["currency"],
                        crypto=CryptoCurrency(row["crypto"]),
                        tokens=tokens,
                    )
                )

            if not wallets:
                return None

            return CryptoCurrencies(wallets)

    def _get_commodities(self, global_position_id: UUID) -> Optional[Commodities]:
        with self._db_client.read() as cursor:
            cursor.execute(
                "SELECT * FROM commodity_positions WHERE global_position_id = ?",
                (str(global_position_id),),
            )

            commodities = [
                Commodity(
                    id=UUID(row["id"]),
                    name=row["name"],
                    type=CommodityType(row["type"]),
                    amount=Dezimal(row["amount"]),
                    unit=WeightUnit(row["unit"]),
                    market_value=Dezimal(row["market_value"]),
                    currency=row["currency"],
                    initial_investment=Dezimal(row["initial_investment"])
                    if row["initial_investment"]
                    else None,
                    average_buy_price=Dezimal(row["average_buy_price"])
                    if row["average_buy_price"]
                    else None,
                )
                for row in cursor
            ]

            if not commodities:
                return None

            return Commodities(commodities)

    def _get_product_positions(self, g_position_id: UUID) -> ProductPositions:
        positions = {}
        _store_position(
            positions, g_position_id, ProductType.ACCOUNT, self._get_accounts
        )
        _store_position(positions, g_position_id, ProductType.CARD, self._get_cards)
        _store_position(positions, g_position_id, ProductType.LOAN, self._get_loans)
        _store_position(
            positions, g_position_id, ProductType.STOCK_ETF, self._get_stocks
        )
        _store_position(positions, g_position_id, ProductType.FUND, self._get_funds)
        _store_position(
            positions,
            g_position_id,
            ProductType.FUND_PORTFOLIO,
            self._get_fund_portfolios,
        )
        _store_position(
            positions, g_position_id, ProductType.FACTORING, self._get_factoring
        )
        _store_position(
            positions,
            g_position_id,
            ProductType.REAL_ESTATE_CF,
            self._get_real_estate_cf,
        )
        _store_position(
            positions, g_position_id, ProductType.DEPOSIT, self._get_deposits
        )
        _store_position(
            positions, g_position_id, ProductType.CROWDLENDING, self._get_crowdlending
        )
        _store_position(
            positions, g_position_id, ProductType.CRYPTO, self._get_cryptocurrency
        )
        _store_position(
            positions, g_position_id, ProductType.COMMODITY, self._get_commodities
        )
        return positions

    def _get_entity_id_from_global(self, global_position_id: UUID) -> int:
        with self._db_client.read() as cursor:
            cursor.execute(
                "SELECT entity_id FROM global_positions WHERE id = ?",
                (str(global_position_id),),
            )
            return cursor.fetchone()[0]

    def delete_position_for_date(
        self, entity_id: UUID, date: datetime.date, is_real: bool
    ):
        with self._db_client.tx() as cursor:
            cursor.execute(
                """
                DELETE
                FROM global_positions
                WHERE entity_id = ?
                  AND DATE(date) = ?
                  AND is_real = ?
                """,
                (str(entity_id), date.isoformat(), is_real),
            )
