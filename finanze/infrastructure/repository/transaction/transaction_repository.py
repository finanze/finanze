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
    CryptoCurrencyTx,
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
from infrastructure.repository.transaction.queries import TransactionQueries


def _map_account_row(row) -> AccountTx:
    entity = Entity(
        id=UUID(row["entity_id"]),
        name=row["entity_name"],
        natural_id=row["entity_natural_id"],
        type=row["entity_type"],
        origin=row["entity_origin"],
        icon_url=row["icon_url"],
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
            icon_url=row["icon_url"],
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
            net_amount=Dezimal(row["net_amount"]) if row["net_amount"] else None,
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
    elif row["product_type"] == ProductType.CRYPTO.value:
        return CryptoCurrencyTx(
            **common,
            symbol=row["ticker"],
            currency_amount=Dezimal(row["shares"]),
            price=Dezimal(row["price"]),
            net_amount=Dezimal(row["net_amount"]) if row["net_amount"] else None,
            fees=Dezimal(row["fees"]),
            retentions=Dezimal(row["retentions"]) if row["retentions"] else None,
            order_date=datetime.fromisoformat(row["order_date"])
            if row["order_date"]
            else None,
            contract_address=row["asset_contract_address"],
        )
    elif row["product_type"] == ProductType.FUND.value:
        return FundTx(
            **common,
            isin=row["isin"] if row["isin"] else None,
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
                    "asset_contract_address": None,
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
                elif isinstance(tx, CryptoCurrencyTx):
                    entry.update(
                        {
                            "ticker": tx.symbol,
                            "shares": str(tx.currency_amount),
                            "price": str(tx.price),
                            "net_amount": str(tx.net_amount),
                            "fees": str(tx.fees),
                            "retentions": str(tx.retentions) if tx.retentions else None,
                            "order_date": tx.order_date.isoformat()
                            if tx.order_date
                            else None,
                            "asset_contract_address": tx.contract_address,
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
                    TransactionQueries.INSERT_INVESTMENT,
                    entry,
                )

    def _save_account(self, txs: List[AccountTx]):
        with self._db_client.tx() as cursor:
            for tx in txs:
                cursor.execute(
                    TransactionQueries.INSERT_ACCOUNT,
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

    def get_all(
        self,
        real: Optional[bool] = None,
        excluded_entities: Optional[list[UUID]] = None,
    ) -> Transactions:
        return Transactions(
            investment=self._get_investment_txs(real, excluded_entities),
            account=self._get_account_txs(real, excluded_entities),
        )

    def _get_investment_txs(
        self,
        real: Optional[bool] = None,
        excluded_entities: Optional[list[UUID]] = None,
    ) -> List[BaseInvestmentTx]:
        with self._db_client.read() as cursor:
            params: list[str] = []
            query = TransactionQueries.INVESTMENT_SELECT_BASE.value

            conditions: list[str] = []
            if real is not None:
                if real:
                    conditions.append("it.source = 'REAL'")
                else:
                    conditions.append("it.source IN ('MANUAL', 'SHEETS')")

            if excluded_entities:
                placeholders = ", ".join("?" for _ in excluded_entities)
                conditions.append(f"it.entity_id NOT IN ({placeholders})")
                params.extend([str(e) for e in excluded_entities])

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY it.date ASC"
            cursor.execute(query, tuple(params))

            return [_map_investment_row(row) for row in cursor.fetchall()]

    def _get_account_txs(
        self,
        real: Optional[bool] = None,
        excluded_entities: Optional[list[UUID]] = None,
    ) -> List[AccountTx]:
        with self._db_client.read() as cursor:
            params: list[str] = []
            query = TransactionQueries.ACCOUNT_SELECT_BASE.value

            conditions: list[str] = []
            if real is not None:
                if real:
                    conditions.append("at.source = 'REAL'")
                else:
                    conditions.append("at.source IN ('MANUAL', 'SHEETS')")

            if excluded_entities:
                placeholders = ", ".join("?" for _ in excluded_entities)
                conditions.append(f"at.entity_id NOT IN ({placeholders})")
                params.extend([str(e) for e in excluded_entities])

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY at.date ASC"

            cursor.execute(query, tuple(params))
            return [_map_account_row(row) for row in cursor.fetchall()]

    def _get_investment_txs_by_entity(self, entity_id: UUID) -> List[BaseInvestmentTx]:
        with self._db_client.read() as cursor:
            cursor.execute(
                TransactionQueries.INVESTMENT_SELECT_BY_ENTITY,
                (str(entity_id),),
            )
            return [_map_investment_row(row) for row in cursor.fetchall()]

    def _get_account_txs_by_entity(self, entity_id: UUID) -> List[AccountTx]:
        with self._db_client.read() as cursor:
            cursor.execute(
                TransactionQueries.ACCOUNT_SELECT_BY_ENTITY,
                (str(entity_id),),
            )
            return [_map_account_row(row) for row in cursor.fetchall()]

    def get_refs_by_entity(self, entity_id: UUID) -> Set[str]:
        with self._db_client.read() as cursor:
            cursor.execute(
                TransactionQueries.GET_REFS_BY_ENTITY,
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
                TransactionQueries.INVESTMENT_AND_ACCOUNT_BY_ENTITY_AND_SOURCE,
                (str(entity_id), source.value),
            )
            investment = [_map_investment_row(row) for row in cursor.fetchall()]

            cursor.execute(
                TransactionQueries.ACCOUNT_BY_ENTITY_AND_SOURCE,
                (str(entity_id), source.value),
            )
            account = [_map_account_row(row) for row in cursor.fetchall()]

        return Transactions(investment=investment, account=account)

    def get_refs_by_source_type(self, real: bool) -> Set[str]:
        with self._db_client.read() as cursor:
            cursor.execute(
                TransactionQueries.GET_REFS_BY_SOURCE_TYPE,
                (real, real),
            )
            return {row[0] for row in cursor.fetchall()}

    def get_by_filters(self, query: TransactionQueryRequest) -> list[BaseTx]:
        params = []
        base_sql = TransactionQueries.GET_BY_FILTERS_BASE.value

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
                TransactionQueries.DELETE_INVESTMENT_BY_SOURCE,
                (source,),
            )
            cursor.execute(
                TransactionQueries.DELETE_ACCOUNT_BY_SOURCE,
                (source,),
            )

    def delete_by_entity_source(self, entity_id: UUID, source: DataSource):
        with self._db_client.tx() as cursor:
            cursor.execute(
                TransactionQueries.DELETE_INVESTMENT_BY_ENTITY_SOURCE,
                (
                    str(entity_id),
                    source,
                ),
            )
            cursor.execute(
                TransactionQueries.DELETE_ACCOUNT_BY_ENTITY_SOURCE,
                (str(entity_id), source),
            )

    def get_by_id(self, tx_id: UUID) -> Optional[BaseTx]:
        with self._db_client.read() as cursor:
            cursor.execute(
                TransactionQueries.GET_INVESTMENT_BY_ID,
                (str(tx_id),),
            )
            row = cursor.fetchone()
            if row:
                return _map_investment_row(row)

            cursor.execute(
                TransactionQueries.GET_ACCOUNT_BY_ID,
                (str(tx_id),),
            )
            row = cursor.fetchone()
            if row:
                return _map_account_row(row)
        return None

    def delete_by_id(self, tx_id: UUID):
        with self._db_client.tx() as cursor:
            cursor.execute(
                TransactionQueries.DELETE_BY_ID_INVESTMENT,
                (str(tx_id),),
            )
            cursor.execute(
                TransactionQueries.DELETE_BY_ID_ACCOUNT,
                (str(tx_id),),
            )
