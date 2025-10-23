from datetime import datetime
from typing import List, Optional, Set
from uuid import UUID

from application.ports.transaction_port import TransactionPort
from dateutil.tz import tzlocal
from domain.dezimal import Dezimal
from domain.entity import Entity
from domain.fetch_record import DataSource
from domain.global_position import EquityType, FundType, ProductType
from domain.transactions import (
    AccountTx,
    BaseInvestmentTx,
    BaseTx,
    DepositTx,
    FactoringTx,
    FundPortfolioTx,
    FundTx,
    RealEstateCFTx,
    StockTx,
    TransactionQueryRequest,
    Transactions,
    TxType,
)
from infrastructure.repository.db.client import DBClient


def _map_account_row(row) -> AccountTx:
    entity = Entity(
        id=UUID(row["entity_id"]),
        name=row["entity_name"],
        natural_id=row["entity_natural_id"],
        type=row["entity_type"],
        origin=row["entity_origin"],
    )

    return AccountTx(
        id=UUID(row["id"]),
        ref=row["ref"],
        name=row["name"],
        amount=Dezimal(row["amount"]),
        currency=row["currency"],
        type=TxType(row["type"]),
        date=datetime.fromisoformat(row["date"]),
        entity=entity,
        source=DataSource(row["source"]),
        product_type=ProductType.ACCOUNT,
        fees=Dezimal(row["fees"]),
        retentions=Dezimal(row["retentions"]),
        interest_rate=Dezimal(row["interest_rate"]) if row["interest_rate"] else None,
        avg_balance=Dezimal(row["avg_balance"]) if row["avg_balance"] else None,
        net_amount=Dezimal(row["net_amount"]) if row["net_amount"] else None,
    )


def _map_investment_row(
    row, fallback_entity: Optional[Entity] = None
) -> BaseInvestmentTx:
    entity = (
        Entity(
            id=UUID(row["entity_id"]),
            name=row["entity_name"],
            natural_id=row["entity_natural_id"],
            type=row["entity_type"],
            origin=row["entity_origin"],
        )
        if row["entity_id"]
        else fallback_entity
    )

    common = {
        "id": UUID(row["id"]),
        "ref": row["ref"],
        "name": row["name"],
        "amount": Dezimal(row["amount"]),
        "currency": row["currency"],
        "type": TxType(row["type"]),
        "date": datetime.fromisoformat(row["date"]),
        "entity": entity,
        "source": DataSource(row["source"]),
        "product_type": ProductType(row["product_type"]),
    }

    if row["product_type"] == ProductType.STOCK_ETF.value:
        return StockTx(
            **common,
            isin=row["isin"] if row["isin"] else None,
            ticker=row["ticker"],
            market=row["market"],
            shares=Dezimal(row["shares"]),
            price=Dezimal(row["price"]),
            net_amount=Dezimal(row["net_amount"]),
            fees=Dezimal(row["fees"]),
            retentions=Dezimal(row["retentions"]) if row["retentions"] else None,
            order_date=datetime.fromisoformat(row["order_date"])
            if row["order_date"]
            else None,
            linked_tx=row["linked_tx"],
            equity_type=EquityType(row["product_subtype"])
            if row["product_subtype"]
            else None,
        )
    elif row["product_type"] == ProductType.FUND.value:
        return FundTx(
            **common,
            isin=row["isin"],
            market=row["market"],
            shares=Dezimal(row["shares"]),
            price=Dezimal(row["price"]),
            net_amount=Dezimal(row["net_amount"]),
            fees=Dezimal(row["fees"]),
            retentions=Dezimal(row["retentions"]) if row["retentions"] else None,
            order_date=datetime.fromisoformat(row["order_date"])
            if row["order_date"]
            else None,
            fund_type=FundType(row["product_subtype"])
            if row["product_subtype"]
            else None,
        )
    elif row["product_type"] == ProductType.FUND_PORTFOLIO.value:
        return FundPortfolioTx(
            **common,
            fees=Dezimal(row["fees"]),
            portfolio_name=row["portfolio_name"] if row["portfolio_name"] else None,
            iban=row["iban"] if row["iban"] else None,
        )
    elif row["product_type"] == ProductType.FACTORING.value:
        return FactoringTx(
            **common,
            net_amount=Dezimal(row["net_amount"]),
            fees=Dezimal(row["fees"]),
            retentions=Dezimal(row["retentions"]),
        )
    elif row["product_type"] == ProductType.REAL_ESTATE_CF.value:
        return RealEstateCFTx(
            **common,
            net_amount=Dezimal(row["net_amount"]),
            fees=Dezimal(row["fees"]),
            retentions=Dezimal(row["retentions"]),
        )
    elif row["product_type"] == ProductType.DEPOSIT.value:
        return DepositTx(
            **common,
            net_amount=Dezimal(row["net_amount"]),
            fees=Dezimal(row["fees"]),
            retentions=Dezimal(row["retentions"]),
        )
    else:
        raise ValueError(f"Unknown product type: {row['product_type']}")


class TransactionSQLRepository(TransactionPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    def save(self, data: Transactions):
        if data.investment:
            self._save_investment(data.investment)
        if data.account:
            self._save_account(data.account)

    def _save_investment(self, txs: List[BaseInvestmentTx]):
        with self._db_client.tx() as cursor:
            for tx in txs:
                entry = {
                    "id": str(tx.id),
                    "ref": tx.ref,
                    "name": tx.name,
                    "amount": str(tx.amount),
                    "currency": tx.currency,
                    "type": tx.type.value,
                    "date": tx.date.isoformat(),
                    "entity_id": str(tx.entity.id),
                    "is_real": tx.source == DataSource.REAL,
                    "source": tx.source.value,
                    "product_type": tx.product_type.value,
                    "created_at": datetime.now(tzlocal()).isoformat(),
                    "isin": None,
                    "ticker": None,
                    "market": None,
                    "shares": None,
                    "price": None,
                    "net_amount": None,
                    "fees": None,
                    "retentions": None,
                    "order_date": None,
                    "linked_tx": None,
                    "interests": None,
                    "iban": None,
                    "portfolio_name": None,
                    "product_subtype": None,
                }

                if isinstance(tx, StockTx):
                    entry.update(
                        {
                            "isin": tx.isin,
                            "ticker": tx.ticker,
                            "market": tx.market,
                            "shares": str(tx.shares),
                            "price": str(tx.price),
                            "net_amount": str(tx.net_amount),
                            "fees": str(tx.fees),
                            "retentions": str(tx.retentions) if tx.retentions else None,
                            "order_date": tx.order_date.isoformat()
                            if tx.order_date
                            else None,
                            "linked_tx": tx.linked_tx,
                            "product_subtype": tx.equity_type.value
                            if tx.equity_type
                            else None,
                        }
                    )
                elif isinstance(tx, FundTx):
                    entry.update(
                        {
                            "isin": tx.isin,
                            "market": tx.market,
                            "shares": str(tx.shares),
                            "price": str(tx.price),
                            "net_amount": str(tx.net_amount),
                            "fees": str(tx.fees),
                            "retentions": str(tx.retentions) if tx.retentions else None,
                            "order_date": tx.order_date.isoformat()
                            if tx.order_date
                            else None,
                            "product_subtype": tx.fund_type.value
                            if tx.fund_type
                            else None,
                        }
                    )
                elif isinstance(tx, FundPortfolioTx):
                    entry.update(
                        {
                            "fees": str(tx.fees),
                            "portfolio_name": tx.portfolio_name,
                            "iban": str(tx.iban) if tx.iban else None,
                        }
                    )
                elif isinstance(tx, (FactoringTx, RealEstateCFTx, DepositTx)):
                    entry.update(
                        {
                            "net_amount": str(tx.net_amount),
                            "fees": str(tx.fees),
                            "retentions": str(tx.retentions),
                        }
                    )

                cursor.execute(
                    """
                    INSERT INTO investment_transactions (id, ref, name, amount, currency, type, date,
                                                         entity_id, is_real, source, product_type, created_at,
                                                         isin, ticker, market, shares, price, net_amount,
                                                         fees, retentions, order_date, linked_tx, interests,
                                                         iban, portfolio_name, product_subtype)
                    VALUES (:id, :ref, :name, :amount, :currency, :type, :date,
                            :entity_id, :is_real, :source, :product_type, :created_at,
                            :isin, :ticker, :market, :shares, :price, :net_amount,
                            :fees, :retentions, :order_date, :linked_tx, :interests,
                            :iban, :portfolio_name, :product_subtype)
                    """,
                    entry,
                )

    def _save_account(self, txs: List[AccountTx]):
        with self._db_client.tx() as cursor:
            for tx in txs:
                cursor.execute(
                    """
                    INSERT INTO account_transactions (id, ref, name, amount, currency, type, date,
                                                      entity_id, is_real, source, created_at,
                                                      fees, retentions, interest_rate, avg_balance, net_amount)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(tx.id),
                        tx.ref,
                        tx.name,
                        str(tx.amount),
                        tx.currency,
                        tx.type.value,
                        tx.date.isoformat(),
                        str(tx.entity.id),
                        tx.source == DataSource.REAL,
                        tx.source.value,
                        datetime.now(tzlocal()).isoformat(),
                        str(tx.fees),
                        str(tx.retentions),
                        str(tx.interest_rate) if tx.interest_rate else None,
                        str(tx.avg_balance) if tx.avg_balance else None,
                        str(tx.net_amount) if tx.net_amount else None,
                    ),
                )

    def get_all(self, real: Optional[bool] = None) -> Transactions:
        return Transactions(
            investment=self._get_investment_txs(real),
            account=self._get_account_txs(real),
        )

    def _get_investment_txs(
        self, real: Optional[bool] = None
    ) -> List[BaseInvestmentTx]:
        with self._db_client.read() as cursor:
            params = []
            query = """
                    SELECT it.*,
                           e.id         AS entity_id,
                           e.name       AS entity_name,
                           e.type       as entity_type,
                           e.origin     as entity_origin,
                           e.natural_id AS entity_natural_id
                    FROM investment_transactions it
                             JOIN entities e ON it.entity_id = e.id
                    """
            if real is not None:
                if real:
                    query += " WHERE it.source = 'REAL'"
                else:
                    query += " WHERE it.source IN ('MANUAL', 'SHEETS')"

            query += " ORDER BY it.date ASC"

            cursor.execute(query, tuple(params))
            return [_map_investment_row(row) for row in cursor.fetchall()]

    def _get_account_txs(self, real: Optional[bool] = None) -> List[AccountTx]:
        with self._db_client.read() as cursor:
            params = []
            query = """
                    SELECT at.*,
                           e.id         AS entity_id,
                           e.name       AS entity_name,
                           e.natural_id AS entity_natural_id,
                           e.type       as entity_type,
                           e.origin     as entity_origin
                    FROM account_transactions at
                             JOIN entities e ON at.entity_id = e.id
                    """

            if real is not None:
                if real:
                    query += " WHERE at.source = 'REAL'"
                else:
                    query += " WHERE at.source IN ('MANUAL', 'SHEETS')"

            query += " ORDER BY at.date ASC"

            cursor.execute(query, tuple(params))
            return [_map_account_row(row) for row in cursor.fetchall()]

    def _get_investment_txs_by_entity(self, entity_id: UUID) -> List[BaseInvestmentTx]:
        with self._db_client.read() as cursor:
            cursor.execute(
                """
                SELECT it.*,
                       e.name       AS entity_name,
                       e.id         AS entity_id,
                       e.type       as entity_type,
                       e.origin     AS entity_origin,
                       e.natural_id AS entity_natural_id
                FROM investment_transactions it
                         JOIN entities e ON it.entity_id = e.id
                WHERE it.entity_id = ?
                """,
                (str(entity_id),),
            )
            return [_map_investment_row(row) for row in cursor.fetchall()]

    def _get_account_txs_by_entity(self, entity_id: UUID) -> List[AccountTx]:
        with self._db_client.read() as cursor:
            cursor.execute(
                """
                SELECT at.*,
                       e.id         AS entity_id,
                       e.name       AS entity_name,
                       e.natural_id AS entity_natural_id,
                       e.type       AS entity_type,
                       e.origin     AS entity_origin
                FROM account_transactions at
                         JOIN entities e ON at.entity_id = e.id
                WHERE at.entity_id = ?
                """,
                (str(entity_id),),
            )
            return [_map_account_row(row) for row in cursor.fetchall()]

    def get_refs_by_entity(self, entity_id: UUID) -> Set[str]:
        with self._db_client.read() as cursor:
            cursor.execute(
                """
                           SELECT ref
                           FROM investment_transactions
                           WHERE entity_id = ?
                           UNION
                           SELECT ref
                           FROM account_transactions
                           WHERE entity_id = ?
                           """,
                (str(entity_id), str(entity_id)),
            )
            return {row[0] for row in cursor.fetchall()}

    def get_by_entity(self, entity_id: UUID) -> Transactions:
        return Transactions(
            investment=self._get_investment_txs_by_entity(entity_id),
            account=self._get_account_txs_by_entity(entity_id),
        )

    def get_by_entity_and_source(
        self, entity_id: UUID, source: DataSource
    ) -> Transactions:
        with self._db_client.read() as cursor:
            cursor.execute(
                """
                SELECT it.*,
                       e.name       AS entity_name,
                       e.id         AS entity_id,
                       e.type       as entity_type,
                       e.origin     AS entity_origin,
                       e.natural_id AS entity_natural_id
                FROM investment_transactions it
                         JOIN entities e ON it.entity_id = e.id
                WHERE it.entity_id = ? AND it.source = ?
                """,
                (str(entity_id), source.value),
            )
            investment = [_map_investment_row(row) for row in cursor.fetchall()]

            cursor.execute(
                """
                SELECT at.*,
                       e.id         AS entity_id,
                       e.name       AS entity_name,
                       e.natural_id AS entity_natural_id,
                       e.type       AS entity_type,
                       e.origin     AS entity_origin
                FROM account_transactions at
                         JOIN entities e ON at.entity_id = e.id
                WHERE at.entity_id = ? AND at.source = ?
                """,
                (str(entity_id), source.value),
            )
            account = [_map_account_row(row) for row in cursor.fetchall()]

        return Transactions(investment=investment, account=account)

    def get_refs_by_source_type(self, real: bool) -> Set[str]:
        with self._db_client.read() as cursor:
            cursor.execute(
                """
                           SELECT ref
                           FROM investment_transactions
                           WHERE is_real = ?
                           UNION
                           SELECT ref
                           FROM account_transactions
                           WHERE is_real = ?
                           """,
                (real, real),
            )
            return {row[0] for row in cursor.fetchall()}

    def get_by_filters(self, query: TransactionQueryRequest) -> list[BaseTx]:
        params = []
        base_sql = """
                   SELECT tx.*,
                          e.name       AS entity_name,
                          e.type       as entity_type,
                          e.origin     as entity_origin,
                          e.natural_id as entity_natural_id
                   FROM (SELECT id,
                                ref,
                                name,
                                amount,
                                currency,
                                type,
                                date,
                                entity_id,
                                is_real,
                                source,
                                product_type,
                                fees,
                                retentions,
                                NULL AS interest_rate,
                                NULL AS avg_balance,
                                isin,
                                ticker,
                                market,
                                shares,
                                price,
                                net_amount,
                                order_date,
                                linked_tx,
                                interests,
                                iban,
                                portfolio_name,
                                product_subtype
                         FROM investment_transactions
                         UNION ALL
                         SELECT id,
                                ref,
                                name,
                                amount,
                                currency,
                                type,
                                date,
                                entity_id,
                                is_real,
                                source,
                                'ACCOUNT' AS product_type,
                                fees,
                                retentions,
                                interest_rate,
                                avg_balance,
                                NULL      AS isin,
                                NULL      AS ticker,
                                NULL      AS market,
                                NULL      AS shares,
                                NULL      AS price,
                                net_amount,
                                NULL      AS order_date,
                                NULL      AS linked_tx,
                                NULL      AS interests,
                                NULL      AS iban,
                                NULL      AS portfolio_name,
                                NULL      AS product_subtype
                         FROM account_transactions) tx
                            JOIN entities e ON tx.entity_id = e.id
                   """

        conditions = []
        if query.entities:
            placeholders = ", ".join("?" for _ in query.entities)
            conditions.append(f"tx.entity_id IN ({placeholders})")
            params.extend([str(e) for e in query.entities])
        if query.excluded_entities:
            placeholders = ", ".join("?" for _ in query.excluded_entities)
            conditions.append(
                f"(tx.entity_id NOT IN ({placeholders}) OR tx.is_real = FALSE)"
            )
            params.extend([str(e) for e in query.excluded_entities])
        if query.product_types:
            placeholders = ", ".join("?" for _ in query.product_types)
            conditions.append(f"tx.product_type IN ({placeholders})")
            params.extend([pt.value for pt in query.product_types])
        if query.types:
            placeholders = ", ".join("?" for _ in query.types)
            conditions.append(f"tx.type IN ({placeholders})")
            params.extend([t.value for t in query.types])
        if query.from_date:
            conditions.append("tx.date >= ?")
            params.append(query.from_date.isoformat())
        if query.to_date:
            conditions.append("tx.date <= ?")
            params.append(query.to_date.isoformat())
        if query.historic_entry_id:
            conditions.append(
                "EXISTS (SELECT 1 FROM investment_historic_txs ht WHERE ht.tx_id = tx.id AND ht.historic_entry_id = ?)"
            )
            params.append(str(query.historic_entry_id))

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        order_pagination = "ORDER BY tx.date DESC LIMIT ? OFFSET ?"
        offset = (query.page - 1) * query.limit
        params.extend([query.limit, offset])
        sql = f"{base_sql} {where_clause} {order_pagination}"

        with self._db_client.read() as cursor:
            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()

        tx_list = []
        for row in rows:
            if row["product_type"] == "ACCOUNT":
                tx = _map_account_row(row)
            else:
                tx = _map_investment_row(row)
            tx_list.append(tx)

        return tx_list

    def delete_by_source(self, source: DataSource):
        with self._db_client.tx() as cursor:
            cursor.execute(
                "DELETE FROM investment_transactions WHERE source = ?", (source,)
            )
            cursor.execute(
                "DELETE FROM account_transactions WHERE source = ?", (source,)
            )

    def delete_by_entity_source(self, entity_id: UUID, source: DataSource):
        with self._db_client.tx() as cursor:
            cursor.execute(
                "DELETE FROM investment_transactions WHERE entity_id = ? AND source = ?",
                (
                    str(entity_id),
                    source,
                ),
            )
            cursor.execute(
                "DELETE FROM account_transactions WHERE entity_id = ? AND source = ?",
                (str(entity_id), source),
            )

    def get_by_id(self, tx_id: UUID) -> Optional[BaseTx]:
        with self._db_client.read() as cursor:
            cursor.execute(
                """
                SELECT it.*,
                       e.id         AS entity_id,
                       e.name       AS entity_name,
                       e.type       AS entity_type,
                       e.origin     AS entity_origin,
                       e.natural_id AS entity_natural_id
                FROM investment_transactions it
                         JOIN entities e ON it.entity_id = e.id
                WHERE it.id = ?
                """,
                (str(tx_id),),
            )
            row = cursor.fetchone()
            if row:
                return _map_investment_row(row)

            cursor.execute(
                """
                SELECT at.*,
                       e.id         AS entity_id,
                       e.name       AS entity_name,
                       e.type       AS entity_type,
                       e.origin     AS entity_origin,
                       e.natural_id AS entity_natural_id
                FROM account_transactions at
                         JOIN entities e ON at.entity_id = e.id
                WHERE at.id = ?
                """,
                (str(tx_id),),
            )
            row = cursor.fetchone()
            if row:
                return _map_account_row(row)
        return None

    def delete_by_id(self, tx_id: UUID):
        with self._db_client.tx() as cursor:
            cursor.execute(
                "DELETE FROM investment_transactions WHERE id = ?",
                (str(tx_id),),
            )
            cursor.execute(
                "DELETE FROM account_transactions WHERE id = ?",
                (str(tx_id),),
            )
