import json
from datetime import datetime, timezone
from typing import Dict, Optional
from uuid import UUID

from application.ports.position_port import PositionPort
from domain.dezimal import Dezimal
from domain.financial_entity import FinancialEntity
from domain.global_position import (
    GlobalPosition, Account, Card, Mortgage,
    Investments, StockInvestments, StockDetail, CardType, FundDetail, FundInvestments, FactoringDetail,
    FactoringInvestments, RealStateCFDetail, RealStateCFInvestments, Deposits, Deposit, Crowdlending, AccountType
)
from infrastructure.repository.common.json_serialization import DezimalJSONEncoder
from infrastructure.repository.db.client import DBClient

KPIs = Optional[dict[str, Dezimal]]
PositionInvestmentKPIs = dict[str, KPIs]

MARKET_VALUE = 'MARKET_VALUE'
INVESTMENT = 'INVESTMENT'
WEIGHTED_INTEREST_RATE = 'WEIGHTED_INTEREST_RATE'
TOTAL = 'TOTAL'
EXPECTED_INTERESTS = 'EXPECTED_INTERESTS'

STOCKS = 'STOCKS'
FUNDS = 'FUNDS'
FACTORING = 'FACTORING'
REAL_STATE_CF = 'REAL_STATE_CF'
DEPOSITS = 'DEPOSITS'
CROWDLENDING = 'CROWDLENDING'


def _save_investment_kpis(cursor, position: GlobalPosition, product_type: str, kpis: KPIs):
    for metric, value in kpis.items():
        if value is None:
            continue

        cursor.execute(
            "INSERT INTO investment_position_kpis "
            "(global_position_id, entity_id, investment_type, metric, value, date) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (str(position.id), position.entity.id, product_type, metric, str(value), position.date.isoformat())
        )


def _save_crowdlending(cursor, position: GlobalPosition, crowdlending: Crowdlending):
    cursor.execute(
        """
        INSERT INTO crowdlending_positions (
            id, global_position_id, currency, distribution
        ) VALUES (?, ?, ?, ?)
        """,
        (
            str(crowdlending.id),
            str(position.id),
            crowdlending.currency,
            json.dumps(crowdlending.distribution, cls=DezimalJSONEncoder)
        )
    )

    kpis = {
        TOTAL: crowdlending.total,
        WEIGHTED_INTEREST_RATE: crowdlending.weighted_interest_rate
    }

    _save_investment_kpis(cursor, position, CROWDLENDING, kpis)


def _save_deposits(cursor, position: GlobalPosition, deposits: Deposits):
    for detail in deposits.details:
        cursor.execute(
            """
            INSERT INTO deposit_positions (
                id, global_position_id, name, amount, currency,
                expected_interests, interest_rate, creation, maturity
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                detail.maturity.isoformat()
            )
        )

    kpis = {
        TOTAL: deposits.total,
        EXPECTED_INTERESTS: deposits.expected_interests,
        WEIGHTED_INTEREST_RATE: deposits.weighted_interest_rate
    }

    _save_investment_kpis(cursor, position, DEPOSITS, kpis)


def _save_real_state_cf(cursor, position: GlobalPosition, real_state: RealStateCFInvestments):
    for detail in real_state.details:
        cursor.execute(
            """
            INSERT INTO real_state_cf_positions (
                id, global_position_id, name, amount, currency,
                interest_rate, last_invest_date, maturity, type,
                business_type, state, extended_maturity
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(detail.id),
                str(position.id),
                detail.name,
                str(detail.amount),
                detail.currency,
                str(detail.interest_rate),
                detail.last_invest_date.isoformat(),
                detail.maturity.isoformat(),
                detail.type,
                detail.business_type,
                detail.state,
                detail.extended_maturity
            )
        )

    kpis = {
        TOTAL: real_state.total,
        WEIGHTED_INTEREST_RATE: real_state.weighted_interest_rate
    }

    _save_investment_kpis(cursor, position, REAL_STATE_CF, kpis)


def _save_factoring(cursor, position: GlobalPosition, factoring: FactoringInvestments):
    for detail in factoring.details:
        cursor.execute(
            """
            INSERT INTO factoring_positions (
                id, global_position_id, name, amount, currency,
                interest_rate, net_interest_rate, last_invest_date,
                maturity, type, state
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(detail.id),
                str(position.id),
                detail.name,
                str(detail.amount),
                detail.currency,
                str(detail.interest_rate),
                str(detail.net_interest_rate),
                detail.last_invest_date.isoformat() if detail.last_invest_date else None,
                detail.maturity.isoformat(),
                detail.type,
                detail.state
            )
        )

    kpis = {
        TOTAL: factoring.total,
        WEIGHTED_INTEREST_RATE: factoring.weighted_interest_rate
    }

    _save_investment_kpis(cursor, position, FACTORING, kpis)


def _save_funds(cursor, position: GlobalPosition, funds: FundInvestments):
    for detail in funds.details:
        cursor.execute(
            """
            INSERT INTO fund_positions (
                id, global_position_id, name, isin, market,
                shares, initial_investment, average_buy_price,
                market_value, currency
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                detail.currency
            )
        )

    kpis = {
        INVESTMENT: funds.investment,
        MARKET_VALUE: funds.market_value
    }

    _save_investment_kpis(cursor, position, FUNDS, kpis)


def _save_stocks(cursor, position: GlobalPosition, stocks: StockInvestments):
    for detail in stocks.details:
        cursor.execute(
            """
            INSERT INTO stock_positions (
                id, global_position_id, name, ticker, isin, market,
                shares, initial_investment, average_buy_price,
                market_value, currency, type, subtype
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                detail.subtype
            )
        )

    kpis = {
        INVESTMENT: stocks.investment,
        MARKET_VALUE: stocks.market_value
    }

    _save_investment_kpis(cursor, position, STOCKS, kpis)


def _save_investments(cursor, position: GlobalPosition, investments: Investments):
    if investments.stocks:
        _save_stocks(cursor, position, investments.stocks)
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


def _save_mortgage(cursor, position: GlobalPosition, mortgage: Mortgage):
    cursor.execute(
        """
        INSERT INTO mortgage_positions (
            id, global_position_id, currency, name, current_installment,
            interest_rate, loan_amount, next_payment_date,
            principal_outstanding, principal_paid
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(mortgage.id),
            str(position.id),
            mortgage.currency,
            mortgage.name,
            str(mortgage.current_installment),
            str(mortgage.interest_rate),
            str(mortgage.loan_amount),
            mortgage.next_payment_date.isoformat(),
            str(mortgage.principal_outstanding),
            str(mortgage.principal_paid)
        )
    )


def _save_card(cursor, position: GlobalPosition, card: Card):
    cursor.execute(
        """
        INSERT INTO card_positions (
            id, global_position_id, type, name, currency,
            ending, card_limit, used, active, related_account
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            str(card.related_account) if card.related_account else None
        )
    )


def _save_account(cursor, position: GlobalPosition, account: Account):
    cursor.execute(
        """
        INSERT INTO account_positions (
            id, global_position_id, type, currency, name, iban, total,
            interest, retained, pending_transfers
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            str(account.pending_transfers) if account.pending_transfers else None
        )
    )


class PositionSQLRepository(PositionPort):

    def __init__(self, client: DBClient):
        self._db_client = client

    def save(self, position: GlobalPosition):
        with self._db_client.tx() as cursor:
            cursor.execute(
                "INSERT INTO global_positions (id, date, entity_id) VALUES (?, ?, ?)",
                (str(position.id),
                 position.date.isoformat(),
                 position.entity.id)
            )

            # Save accounts
            for account in position.account:
                _save_account(cursor, position, account)

            # Save cards
            for card in position.cards:
                _save_card(cursor, position, card)

            # Save mortgages
            for mortgage in position.mortgage:
                _save_mortgage(cursor, position, mortgage)

            # Save investments
            if position.investments:
                _save_investments(cursor, position, position.investments)

    def get_last_grouped_by_entity(self) -> Dict[FinancialEntity, GlobalPosition]:
        with self._db_client.read() as cursor:
            cursor.execute("""
                WITH latest_positions AS (
                    SELECT entity_id, MAX(date) as latest_date
                    FROM global_positions
                    GROUP BY entity_id
                )
                SELECT gp.*, e.name AS entity_name, e.id AS entity_id, e.is_real AS entity_is_real
                FROM global_positions gp
                JOIN latest_positions lp 
                    ON gp.entity_id = lp.entity_id AND gp.date = lp.latest_date
                JOIN financial_entities e ON gp.entity_id = e.id
            """)

            positions = {}
            for row in cursor.fetchall():
                entity = FinancialEntity(
                    id=row["entity_id"],
                    name=row["entity_name"],
                    is_real=row["entity_is_real"]
                )

                position = GlobalPosition(
                    id=UUID(row['id']),
                    entity=entity,
                    date=datetime.fromisoformat(row['date']),
                    account=self._get_account_position(row['id']),
                    cards=self._get_card_positions(row['id']),
                    mortgage=self._get_mortgage_position(row['id']),
                    investments=self._get_investments(row['id']),
                )
                positions[entity] = position

            return positions

    def _get_account_position(self, global_position_id: str) -> list[Account]:
        with self._db_client.read() as cursor:
            cursor.execute("""
                SELECT * FROM account_positions WHERE global_position_id = ?
            """, (global_position_id,))

            accounts = [
                Account(
                    id=UUID(row['id']),
                    total=Dezimal(row['total']),
                    currency=row['currency'],
                    type=AccountType[row['type']],
                    name=row['name'],
                    interest=Dezimal(row['interest']) if row['interest'] else None,
                    retained=Dezimal(row['retained']) if row['retained'] else None,
                    pending_transfers=Dezimal(row['pending_transfers']) if row['pending_transfers'] else None,
                ) for row in cursor
            ]

            return accounts

    def _get_card_positions(self, global_position_id: str) -> list[Card]:
        with self._db_client.read() as cursor:
            cursor.execute(
                "SELECT * FROM card_positions WHERE global_position_id = ?",
                (global_position_id,)
            )

            cards = [
                Card(
                    id=UUID(row['id']),
                    name=row['name'],
                    currency=row['currency'],
                    ending=row['ending'],
                    type=CardType[row['type']],
                    limit=Dezimal(row['card_limit']) if row['card_limit'] else None,
                    used=Dezimal(row['used']),
                    active=bool(row['active']),
                    related_account=row['related_account']
                ) for row in cursor
            ]

            return cards

    def _get_mortgage_position(self, global_position_id: str) -> list[Mortgage]:
        with self._db_client.read() as cursor:
            cursor.execute(
                "SELECT * FROM mortgage_positions WHERE global_position_id = ?",
                (global_position_id,)
            )

            mortgages = [
                Mortgage(
                    id=UUID(row['id']),
                    currency=row['currency'],
                    name=row['name'],
                    current_installment=Dezimal(row['current_installment']),
                    interest_rate=Dezimal(row['interest_rate']),
                    loan_amount=Dezimal(row['loan_amount']),
                    next_payment_date=datetime.fromisoformat(row['next_payment_date']).date(),
                    principal_outstanding=Dezimal(row['principal_outstanding']),
                    principal_paid=Dezimal(row['principal_paid'])
                ) for row in cursor
            ]

            return mortgages

    def _get_investments(self, global_position_id: str) -> Optional[Investments]:
        kpis = self._get_investment_kpis(global_position_id)
        return Investments(
            stocks=self._get_stock_investments(global_position_id, kpis.get(STOCKS)),
            funds=self._get_fund_investments(global_position_id, kpis.get(FUNDS)),
            factoring=self._get_factoring_investments(global_position_id, kpis.get(FACTORING)),
            real_state_cf=self._get_real_state_cf_investments(global_position_id, kpis.get(REAL_STATE_CF)),
            deposits=self._get_deposit_investments(global_position_id, kpis.get(DEPOSITS)),
            crowdlending=self._get_crowdlending_investments(global_position_id, kpis.get(CROWDLENDING))
        )

    def _get_investment_kpis(self, global_position_id: str) -> Optional[PositionInvestmentKPIs]:
        with self._db_client.read() as cursor:
            cursor.execute(
                "SELECT * FROM investment_position_kpis WHERE global_position_id = ?",
                (global_position_id,)
            )

            kpis = {}
            for row in cursor:
                kpis.setdefault(row['investment_type'], {})[row['metric']] = Dezimal(row['value'])
            return kpis

    def _get_stock_investments(self, global_position_id: str, kpis: KPIs) -> Optional[StockInvestments]:
        with self._db_client.read() as cursor:
            cursor.execute(
                "SELECT * FROM stock_positions WHERE global_position_id = ?",
                (global_position_id,)
            )

            details = [
                StockDetail(
                    id=UUID(row['id']),
                    name=row['name'],
                    ticker=row['ticker'],
                    isin=row['isin'],
                    market=row['market'],
                    shares=Dezimal(row['shares']),
                    initial_investment=Dezimal(row['initial_investment']),
                    average_buy_price=Dezimal(row['average_buy_price']),
                    market_value=Dezimal(row['market_value']),
                    currency=row['currency'],
                    type=row['type'],
                    subtype=row['subtype']
                )
                for row in cursor
            ]

            if not details:
                return None

            return StockInvestments(
                investment=kpis.get(INVESTMENT) if kpis else None,
                market_value=kpis.get(MARKET_VALUE) if kpis else None,
                details=details
            )

    def _get_fund_investments(self, global_position_id: str, kpis: KPIs) -> Optional[FundInvestments]:
        with self._db_client.read() as cursor:
            cursor.execute(
                "SELECT * FROM fund_positions WHERE global_position_id = ?",
                (global_position_id,)
            )

            details = [
                FundDetail(
                    id=UUID(row['id']),
                    name=row['name'],
                    isin=row['isin'],
                    market=row['market'],
                    shares=Dezimal(row['shares']),
                    initial_investment=Dezimal(row['initial_investment']),
                    average_buy_price=Dezimal(row['average_buy_price']),
                    market_value=Dezimal(row['market_value']),
                    currency=row['currency']
                )
                for row in cursor
            ]

            if not details:
                return None

            return FundInvestments(
                investment=kpis.get(INVESTMENT) if kpis else None,
                market_value=kpis.get(MARKET_VALUE) if kpis else None,
                details=details
            )

    def _get_factoring_investments(self, global_position_id: str, kpis: KPIs) -> Optional[FactoringInvestments]:
        with self._db_client.read() as cursor:
            cursor.execute(
                "SELECT * FROM factoring_positions WHERE global_position_id = ?",
                (global_position_id,)
            )

            details = [
                FactoringDetail(
                    id=UUID(row['id']),
                    name=row['name'],
                    amount=Dezimal(row['amount']),
                    currency=row['currency'],
                    interest_rate=Dezimal(row['interest_rate']),
                    net_interest_rate=Dezimal(row['net_interest_rate']),
                    last_invest_date=datetime.fromisoformat(row['last_invest_date']) if row[
                        'last_invest_date'] else None,
                    maturity=datetime.fromisoformat(row['maturity']).date(),
                    type=row['type'],
                    state=row['state']
                )
                for row in cursor
            ]

            if not details:
                return None

            return FactoringInvestments(
                total=kpis.get(TOTAL),
                weighted_interest_rate=kpis.get(WEIGHTED_INTEREST_RATE),
                details=details
            )

    def _get_real_state_cf_investments(self, global_position_id: str, kpis: KPIs) -> Optional[RealStateCFInvestments]:
        with self._db_client.read() as cursor:
            cursor.execute(
                "SELECT * FROM real_state_cf_positions WHERE global_position_id = ?",
                (global_position_id,)
            )

            details = [
                RealStateCFDetail(
                    id=UUID(row['id']),
                    name=row['name'],
                    amount=Dezimal(row['amount']),
                    currency=row['currency'],
                    interest_rate=Dezimal(row['interest_rate']),
                    last_invest_date=datetime.fromisoformat(row['last_invest_date']),
                    maturity=row['maturity'],
                    type=row['type'],
                    business_type=row['business_type'],
                    state=row['state'],
                    extended_maturity=row['extended_maturity']
                )
                for row in cursor
            ]

            if not details:
                return None

            return RealStateCFInvestments(
                total=kpis.get(TOTAL),
                weighted_interest_rate=kpis.get(WEIGHTED_INTEREST_RATE),
                details=details
            )

    def _get_deposit_investments(self, global_position_id: str, kpis: KPIs) -> Optional[Deposits]:
        with self._db_client.read() as cursor:
            cursor.execute(
                "SELECT * FROM deposit_positions WHERE global_position_id = ?",
                (global_position_id,)
            )

            details = [
                Deposit(
                    id=UUID(row['id']),
                    name=row['name'],
                    amount=Dezimal(row['amount']),
                    currency=row['currency'],
                    expected_interests=Dezimal(row['expected_interests']),
                    interest_rate=Dezimal(row['interest_rate']),
                    creation=datetime.fromisoformat(row['creation']),
                    maturity=datetime.fromisoformat(row['maturity']).date()
                )
                for row in cursor
            ]

            if not details:
                return None

            return Deposits(
                total=kpis.get(TOTAL),
                weighted_interest_rate=kpis.get(WEIGHTED_INTEREST_RATE),
                expected_interests=kpis.get(EXPECTED_INTERESTS),
                details=details
            )

    def _get_crowdlending_investments(self, global_position_id: str, kpis: KPIs) -> Optional[Crowdlending]:
        with self._db_client.read() as cursor:
            cursor.execute(
                "SELECT * FROM crowdlending_positions WHERE global_position_id = ?",
                (global_position_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None

            return Crowdlending(
                id=UUID(row['id']),
                total=kpis.get(TOTAL),
                weighted_interest_rate=kpis.get(WEIGHTED_INTEREST_RATE),
                currency=row['currency'],
                distribution=json.loads(row['distribution']),
                details=[]
            )

    def get_last_updated(self, entity_id: int) -> Optional[datetime]:
        with self._db_client.read() as cursor:
            cursor.execute("""
                SELECT MAX(date) as last_date
                FROM global_positions
                WHERE entity_id = ?
            """, (entity_id,))

            result = cursor.fetchone()
            if not result or not result['last_date']:
                return None

            return datetime.fromisoformat(result['last_date']).replace(tzinfo=timezone.utc)

    def _get_entity_id_from_global(self, global_position_id: str) -> int:
        with self._db_client.read() as cursor:
            cursor.execute(
                "SELECT entity_id FROM global_positions WHERE id = ?",
                (global_position_id,)
            )
            return cursor.fetchone()[0]
