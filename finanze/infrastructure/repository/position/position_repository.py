import json
from datetime import datetime
from typing import Dict, Optional, Tuple
from uuid import UUID

from application.ports.position_port import PositionPort
from domain.dezimal import Dezimal
from domain.entity import Entity
from domain.global_position import (
    Account,
    AccountType,
    Card,
    CardType,
    Crowdlending,
    CryptoCurrencies,
    CryptoCurrency,
    CryptoCurrencyToken,
    CryptoCurrencyWallet,
    Deposit,
    Deposits,
    FactoringDetail,
    FactoringInvestments,
    FundDetail,
    FundInvestments,
    FundPortfolio,
    GlobalPosition,
    Investments,
    Loan,
    LoanType,
    PositionQueryRequest,
    RealStateCFDetail,
    RealStateCFInvestments,
    StockDetail,
    StockInvestments,
)
from infrastructure.repository.common.json_serialization import DezimalJSONEncoder
from infrastructure.repository.db.client import DBClient, DBCursor

KPIs = Optional[dict[str, Tuple[Dezimal, str | None]]]
PositionInvestmentKPIs = dict[str, KPIs]

MARKET_VALUE = "MARKET_VALUE"
INVESTMENT = "INVESTMENT"
WEIGHTED_INTEREST_RATE = "WEIGHTED_INTEREST_RATE"
TOTAL = "TOTAL"
EXPECTED_INTERESTS = "EXPECTED_INTERESTS"

STOCKS = "STOCKS"
FUNDS = "FUNDS"
FACTORING = "FACTORING"
REAL_STATE_CF = "REAL_STATE_CF"
DEPOSITS = "DEPOSITS"
CROWDLENDING = "CROWDLENDING"
CRYPTOCURRENCIES = "CRYPTOCURRENCIES"


def _save_investment_kpis(
    cursor, position: GlobalPosition, product_type: str, kpis: KPIs
):
    for metric, kpi in kpis.items():
        if kpi is None:
            continue

        value, currency = kpi

        cursor.execute(
            "INSERT INTO investment_position_kpis "
            "(global_position_id, entity_id, investment_type, metric, value, currency, date) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(position.id),
                str(position.entity.id),
                product_type,
                metric,
                str(value),
                currency,
                position.date.isoformat(),
            ),
        )


def _save_crowdlending(cursor, position: GlobalPosition, crowdlending: Crowdlending):
    cursor.execute(
        """
        INSERT INTO crowdlending_positions (id, global_position_id, currency, distribution)
        VALUES (?, ?, ?, ?)
        """,
        (
            str(crowdlending.id),
            str(position.id),
            crowdlending.currency,
            json.dumps(crowdlending.distribution, cls=DezimalJSONEncoder),
        ),
    )

    kpis = {
        TOTAL: (crowdlending.total, crowdlending.currency),
        WEIGHTED_INTEREST_RATE: (crowdlending.weighted_interest_rate, None),
    }

    _save_investment_kpis(cursor, position, CROWDLENDING, kpis)


def _save_cryptocurrency_tokens(cursor, wallet_detail: CryptoCurrencyWallet):
    for token_detail in wallet_detail.tokens:
        cursor.execute(
            """
            INSERT INTO cryptocurrency_tokens (id, wallet_id, token_id, name, symbol, amount,
                                               initial_investment, average_buy_price, market_value, currency, type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(token_detail.id),
                str(wallet_detail.id),
                token_detail.token_id,
                token_detail.name,
                token_detail.symbol,
                str(token_detail.amount),
                str(token_detail.initial_investment)
                if token_detail.initial_investment
                else None,
                str(token_detail.average_buy_price)
                if token_detail.average_buy_price
                else None,
                str(token_detail.market_value),
                token_detail.currency,
                token_detail.type,
            ),
        )


def _save_cryptocurrencies(
    cursor, position: GlobalPosition, cryptocurrencies: CryptoCurrencies
):
    for wallet_detail in cryptocurrencies.details:
        cursor.execute(
            """
            INSERT INTO cryptocurrency_wallets (id, global_position_id, address, name, symbol, amount,
                                                initial_investment, average_buy_price, market_value, currency, crypto)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(wallet_detail.id),
                str(position.id),
                wallet_detail.address,
                wallet_detail.name,
                wallet_detail.symbol,
                str(wallet_detail.amount),
                str(wallet_detail.initial_investment)
                if wallet_detail.initial_investment
                else None,
                str(wallet_detail.average_buy_price)
                if wallet_detail.average_buy_price
                else None,
                str(wallet_detail.market_value),
                wallet_detail.currency,
                wallet_detail.crypto.value,
            ),
        )
        _save_cryptocurrency_tokens(cursor, wallet_detail)

    kpis = {MARKET_VALUE: (cryptocurrencies.market_value, cryptocurrencies.currency)}
    _save_investment_kpis(cursor, position, CRYPTOCURRENCIES, kpis)


def _save_deposits(cursor, position: GlobalPosition, deposits: Deposits):
    for detail in deposits.details:
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

    kpis = {
        TOTAL: (deposits.total, deposits.currency),
        EXPECTED_INTERESTS: (deposits.expected_interests, deposits.currency),
        WEIGHTED_INTEREST_RATE: (deposits.weighted_interest_rate, None),
    }

    _save_investment_kpis(cursor, position, DEPOSITS, kpis)


def _save_real_state_cf(
    cursor, position: GlobalPosition, real_state: RealStateCFInvestments
):
    for detail in real_state.details:
        cursor.execute(
            """
            INSERT INTO real_state_cf_positions (id, global_position_id, name, amount, pending_amount, currency,
                                                 interest_rate, last_invest_date, maturity, type,
                                                 business_type, state, extended_maturity)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(detail.id),
                str(position.id),
                detail.name,
                str(detail.amount),
                str(detail.pending_amount),
                detail.currency,
                str(detail.interest_rate),
                detail.last_invest_date.isoformat(),
                detail.maturity.isoformat(),
                detail.type,
                detail.business_type,
                detail.state,
                detail.extended_maturity,
            ),
        )

    kpis = {
        TOTAL: (real_state.total, real_state.currency),
        WEIGHTED_INTEREST_RATE: (real_state.weighted_interest_rate, None),
    }

    _save_investment_kpis(cursor, position, REAL_STATE_CF, kpis)


def _save_factoring(cursor, position: GlobalPosition, factoring: FactoringInvestments):
    for detail in factoring.details:
        cursor.execute(
            """
            INSERT INTO factoring_positions (id, global_position_id, name, amount, currency,
                                             interest_rate, gross_interest_rate, last_invest_date,
                                             maturity, type, state)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(detail.id),
                str(position.id),
                detail.name,
                str(detail.amount),
                detail.currency,
                str(detail.interest_rate),
                str(detail.gross_interest_rate),
                detail.last_invest_date.isoformat()
                if detail.last_invest_date
                else None,
                detail.maturity.isoformat(),
                detail.type,
                detail.state,
            ),
        )

    kpis = {
        TOTAL: (factoring.total, factoring.currency),
        WEIGHTED_INTEREST_RATE: (factoring.weighted_interest_rate, None),
    }

    _save_investment_kpis(cursor, position, FACTORING, kpis)


def _save_fund_portfolios(
    cursor, position: GlobalPosition, portfolios: list[FundPortfolio]
):
    for portfolio in portfolios:
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
                str(portfolio.initial_investment),
                str(portfolio.market_value),
            ),
        )


def _save_funds(cursor, position: GlobalPosition, funds: FundInvestments):
    for detail in funds.details:
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

    kpis = {
        INVESTMENT: (funds.investment, funds.currency),
        MARKET_VALUE: (funds.market_value, funds.currency),
    }

    _save_investment_kpis(cursor, position, FUNDS, kpis)


def _save_stocks(cursor, position: GlobalPosition, stocks: StockInvestments):
    for detail in stocks.details:
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

    kpis = {
        INVESTMENT: (stocks.investment, stocks.currency),
        MARKET_VALUE: (stocks.market_value, stocks.currency),
    }

    _save_investment_kpis(cursor, position, STOCKS, kpis)


def _save_investments(cursor, position: GlobalPosition, investments: Investments):
    if investments.stocks:
        _save_stocks(cursor, position, investments.stocks)
    if investments.fund_portfolios:
        _save_fund_portfolios(cursor, position, investments.fund_portfolios)
    if investments.funds:
        _save_funds(cursor, position, investments.funds)
    if investments.factoring:
        _save_factoring(cursor, position, investments.factoring)
    if investments.real_state_cf:
        _save_real_state_cf(cursor, position, investments.real_state_cf)
    if investments.deposits:
        _save_deposits(cursor, position, investments.deposits)
    if investments.crowdlending:
        _save_crowdlending(cursor, position, investments.crowdlending)
    if investments.cryptocurrencies:
        _save_cryptocurrencies(cursor, position, investments.cryptocurrencies)


def _save_loan(cursor, position: GlobalPosition, loan: Loan):
    cursor.execute(
        """
        INSERT INTO loan_positions (id, global_position_id, type, currency, name, current_installment,
                                    interest_rate, loan_amount, next_payment_date,
                                    principal_outstanding, principal_paid)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(loan.id),
            str(position.id),
            loan.type,
            loan.currency,
            loan.name,
            str(loan.current_installment),
            str(loan.interest_rate),
            str(loan.loan_amount),
            loan.next_payment_date.isoformat(),
            str(loan.principal_outstanding),
            str(loan.principal_paid),
        ),
    )


def _save_card(cursor, position: GlobalPosition, card: Card):
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
            card.ending,
            str(card.limit) if card.limit else None,
            str(card.used),
            card.active,
            str(card.related_account) if card.related_account else None,
        ),
    )


def _save_account(cursor, position: GlobalPosition, account: Account):
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


def _get_kpi_currency(kpis: KPIs, key: str) -> Optional[str]:
    try:
        return kpis.get(key)[1]
    except Exception:
        return None


def _get_kpi_value(kpis: KPIs, key: str) -> Optional[Dezimal]:
    try:
        return kpis.get(key)[0] if kpis else None
    except Exception:
        return None


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

            # Save accounts
            for account in position.accounts:
                _save_account(cursor, position, account)

            # Save cards
            for card in position.cards:
                _save_card(cursor, position, card)

            # Save loans
            for loan in position.loans:
                _save_loan(cursor, position, loan)

            # Save investments
            if position.investments:
                _save_investments(cursor, position, position.investments)

    def get_last_grouped_by_entity(
        self, query: Optional[PositionQueryRequest] = None
    ) -> Dict[Entity, GlobalPosition]:
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
                  WHERE gp.is_real = TRUE \
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
                accounts=self._get_account_position(row["id"]),
                cards=self._get_card_positions(row["id"]),
                loans=self._get_loans_position(row["id"]),
                investments=self._get_investments(row["id"]),
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

    def _get_account_position(self, global_position_id: UUID) -> list[Account]:
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

            return accounts

    def _get_card_positions(self, global_position_id: UUID) -> list[Card]:
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

            return cards

    def _get_loans_position(self, global_position_id: UUID) -> list[Loan]:
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
                    loan_amount=Dezimal(row["loan_amount"]),
                    next_payment_date=datetime.fromisoformat(
                        row["next_payment_date"]
                    ).date(),
                    principal_outstanding=Dezimal(row["principal_outstanding"]),
                    principal_paid=Dezimal(row["principal_paid"]),
                )
                for row in cursor
            ]

            return loans

    def _get_investments(self, global_position_id: UUID) -> Optional[Investments]:
        kpis = self._get_investment_kpis(global_position_id)
        return Investments(
            stocks=self._get_stock_investments(global_position_id, kpis.get(STOCKS)),
            funds=self._get_fund_investments(global_position_id, kpis.get(FUNDS)),
            fund_portfolios=self._get_fund_portfolios(global_position_id),
            factoring=self._get_factoring_investments(
                global_position_id, kpis.get(FACTORING)
            ),
            real_state_cf=self._get_real_state_cf_investments(
                global_position_id, kpis.get(REAL_STATE_CF)
            ),
            deposits=self._get_deposit_investments(
                global_position_id, kpis.get(DEPOSITS)
            ),
            crowdlending=self._get_crowdlending_investments(
                global_position_id, kpis.get(CROWDLENDING)
            ),
            cryptocurrencies=self._get_cryptocurrency_investments(
                global_position_id, kpis.get(CRYPTOCURRENCIES)
            ),
        )

    def _get_investment_kpis(
        self, global_position_id: UUID
    ) -> Optional[PositionInvestmentKPIs]:
        with self._db_client.read() as cursor:
            cursor.execute(
                "SELECT * FROM investment_position_kpis WHERE global_position_id = ?",
                (str(global_position_id),),
            )

            kpis = {}
            for row in cursor:
                kpis.setdefault(row["investment_type"], {})[row["metric"]] = (
                    Dezimal(row["value"]),
                    row["currency"] if row["currency"] else None,
                )
            return kpis

    def _get_stock_investments(
        self, global_position_id: UUID, kpis: KPIs
    ) -> Optional[StockInvestments]:
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

            return StockInvestments(
                currency=_get_kpi_currency(kpis, INVESTMENT),
                investment=_get_kpi_value(kpis, INVESTMENT),
                market_value=_get_kpi_value(kpis, MARKET_VALUE),
                details=details,
            )

    def _get_fund_portfolios(self, global_position_id: UUID) -> list[FundPortfolio]:
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
                        initial_investment=Dezimal(row["initial_investment"]),
                        market_value=Dezimal(row["market_value"]),
                    )
                )

            return portfolios

    def _get_fund_investments(
        self, global_position_id: UUID, kpis: KPIs
    ) -> Optional[FundInvestments]:
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
                        currency=row["portfolio_currency"],
                        initial_investment=Dezimal(row["portfolio_investment"]),
                        market_value=Dezimal(row["portfolio_value"]),
                    )
                    if row["portfolio_id"]
                    else None,
                )
                for row in cursor
            ]

            if not details:
                return None

            return FundInvestments(
                currency=_get_kpi_currency(kpis, INVESTMENT),
                investment=_get_kpi_value(kpis, INVESTMENT),
                market_value=_get_kpi_value(kpis, MARKET_VALUE),
                details=details,
            )

    def _get_factoring_investments(
        self, global_position_id: UUID, kpis: KPIs
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

            return FactoringInvestments(
                currency=_get_kpi_currency(kpis, TOTAL),
                total=_get_kpi_value(kpis, TOTAL),
                weighted_interest_rate=_get_kpi_value(kpis, WEIGHTED_INTEREST_RATE),
                details=details,
            )

    def _get_real_state_cf_investments(
        self, global_position_id: UUID, kpis: KPIs
    ) -> Optional[RealStateCFInvestments]:
        with self._db_client.read() as cursor:
            cursor.execute(
                "SELECT * FROM real_state_cf_positions WHERE global_position_id = ?",
                (str(global_position_id),),
            )

            details = [
                RealStateCFDetail(
                    id=UUID(row["id"]),
                    name=row["name"],
                    amount=Dezimal(row["amount"]),
                    pending_amount=Dezimal(row["pending_amount"]),
                    currency=row["currency"],
                    interest_rate=Dezimal(row["interest_rate"]),
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

            return RealStateCFInvestments(
                currency=_get_kpi_currency(kpis, TOTAL),
                total=_get_kpi_value(kpis, TOTAL),
                weighted_interest_rate=_get_kpi_value(kpis, WEIGHTED_INTEREST_RATE),
                details=details,
            )

    def _get_deposit_investments(
        self, global_position_id: UUID, kpis: KPIs
    ) -> Optional[Deposits]:
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

            return Deposits(
                currency=_get_kpi_currency(kpis, TOTAL),
                total=_get_kpi_value(kpis, TOTAL),
                weighted_interest_rate=_get_kpi_value(kpis, WEIGHTED_INTEREST_RATE),
                expected_interests=_get_kpi_value(kpis, EXPECTED_INTERESTS),
                details=details,
            )

    def _get_crowdlending_investments(
        self, global_position_id: UUID, kpis: KPIs
    ) -> Optional[Crowdlending]:
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
                total=_get_kpi_value(kpis, TOTAL),
                weighted_interest_rate=_get_kpi_value(kpis, WEIGHTED_INTEREST_RATE),
                currency=row["currency"],
                distribution=json.loads(row["distribution"]),
                details=[],
            )

    def _get_cryptocurrency_tokens(self, wallet_id: UUID) -> list[CryptoCurrencyToken]:
        with self._db_client.read() as cursor:
            cursor.execute(
                "SELECT * FROM cryptocurrency_tokens WHERE wallet_id = ?",
                (str(wallet_id),),
            )
            return [
                CryptoCurrencyToken(
                    id=UUID(row["id"]),
                    token_id=row["token_id"],
                    name=row["name"],
                    symbol=row["symbol"],
                    amount=Dezimal(row["amount"]),
                    initial_investment=Dezimal(row["initial_investment"])
                    if row["initial_investment"]
                    else None,
                    average_buy_price=Dezimal(row["average_buy_price"])
                    if row["average_buy_price"]
                    else None,
                    market_value=Dezimal(row["market_value"]),
                    currency=row["currency"],
                    type=row["type"],
                )
                for row in cursor
            ]

    def _get_cryptocurrency_investments(
        self, global_position_id: UUID, kpis: KPIs
    ) -> Optional[CryptoCurrencies]:
        with self._db_client.read() as cursor:
            cursor.execute(
                "SELECT * FROM cryptocurrency_wallets WHERE global_position_id = ?",
                (str(global_position_id),),
            )
            wallets = []
            for row in cursor:
                wallet_id = UUID(row["id"])
                tokens = self._get_cryptocurrency_tokens(wallet_id)
                wallets.append(
                    CryptoCurrencyWallet(
                        id=wallet_id,
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
                        market_value=Dezimal(row["market_value"]),
                        currency=row["currency"],
                        crypto=CryptoCurrency(row["crypto"]),
                        tokens=tokens,
                    )
                )

            if not wallets:
                return None

            return CryptoCurrencies(
                currency=_get_kpi_currency(kpis, MARKET_VALUE),
                market_value=_get_kpi_value(kpis, MARKET_VALUE),
                details=wallets,
            )

    def get_last_updated(self, entity_id: UUID) -> Optional[datetime]:
        with self._db_client.read() as cursor:
            cursor.execute(
                """
                           SELECT MAX(date) as last_date
                           FROM global_positions
                           WHERE entity_id = ?
                           """,
                (str(entity_id),),
            )

            result = cursor.fetchone()
            if not result or not result["last_date"]:
                return None

            return datetime.fromisoformat(result["last_date"])

    def _get_entity_id_from_global(self, global_position_id: UUID) -> int:
        with self._db_client.read() as cursor:
            cursor.execute(
                "SELECT entity_id FROM global_positions WHERE id = ?",
                (str(global_position_id),),
            )
            return cursor.fetchone()[0]
