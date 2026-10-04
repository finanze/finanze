from datetime import date, datetime, timedelta
from typing import List, Optional, Set
from uuid import UUID

from dateutil.tz import tzlocal

from application.ports.transaction_port import TransactionPort
from domain.dezimal import Dezimal
from domain.entity import Entity
from domain.fetch_record import DataSource
from domain.global_position import (
    EquityType,
    FundType,
    ProductType,
)
from domain.transactions import (
    AccountTx,
    AccountTxSelection,
    BaseInvestmentTx,
    BaseTx,
    CryptoCurrencyTx,
    DepositTx,
    FactoringTx,
    FundPortfolioTx,
    FundTx,
    MarketForecastTx,
    RealEstateCFTx,
    StockTx,
    TransactionQueryRequest,
    Transactions,
    TxType,
)
from infrastructure.repository.db.client import DBClient, DBCursor
from infrastructure.repository.labeling.common import (
    load_transfer_pairs,
    load_tx_labels,
    placeholders as sql_placeholders,
)
from infrastructure.repository.transaction.queries import TransactionQueries


def _like_pattern(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _day_after(value: date) -> str:
    return (value + timedelta(days=1)).isoformat()


def map_account_row(row) -> AccountTx:
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
        entity_account_id=UUID(row["entity_account_id"])
        if row["entity_account_id"]
        else None,
        fees=Dezimal(row["fees"]),
        retentions=Dezimal(row["retentions"]),
        interest_rate=Dezimal(row["interest_rate"]) if row["interest_rate"] else None,
        avg_balance=Dezimal(row["avg_balance"]) if row["avg_balance"] else None,
        net_amount=Dezimal(row["net_amount"]) if row["net_amount"] else None,
        counterparty=row["counterparty"],
        iban=row["iban"],
        linked_tx=row["linked_tx"],
        labels_locked=bool(row["labels_locked"]),
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
        "entity_account_id": UUID(row["entity_account_id"])
        if row["entity_account_id"]
        else None,
    }

    if row["product_type"] == ProductType.STOCK_ETF.value:
        return StockTx(
            **common,
            isin=row["isin"] if row["isin"] else None,
            ticker=row["ticker"],
            market=row["market"] if row["market"] else None,
            shares=Dezimal(row["shares"]) if row["shares"] is not None else None,
            price=Dezimal(row["price"]),
            net_amount=Dezimal(row["net_amount"]) if row["net_amount"] else None,
            fees=Dezimal(row["fees"]),
            retentions=Dezimal(row["retentions"]) if row["retentions"] else None,
            order_date=(
                datetime.fromisoformat(row["order_date"]) if row["order_date"] else None
            ),
            linked_tx=row["linked_tx"],
            equity_type=(
                EquityType(row["product_subtype"]) if row["product_subtype"] else None
            ),
            split_ratio=(
                Dezimal(row["split_ratio"]) if row["split_ratio"] is not None else None
            ),
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
            order_date=(
                datetime.fromisoformat(row["order_date"]) if row["order_date"] else None
            ),
            contract_address=row["asset_contract_address"],
        )
    elif row["product_type"] == ProductType.MARKET_FORECAST.value:
        return MarketForecastTx(
            **common,
            symbol=row["ticker"] or row["name"],
            size=Dezimal(row["shares"]),
            price=Dezimal(row["price"]),
            net_amount=Dezimal(row["net_amount"]) if row["net_amount"] else None,
            fees=Dezimal(row["fees"]),
            retentions=Dezimal(row["retentions"]) if row["retentions"] else None,
            order_date=(
                datetime.fromisoformat(row["order_date"]) if row["order_date"] else None
            ),
        )
    elif row["product_type"] == ProductType.FUND.value:
        return FundTx(
            **common,
            isin=row["isin"] if row["isin"] else None,
            market=row["market"] if row["market"] else None,
            shares=Dezimal(row["shares"]) if row["shares"] is not None else None,
            price=Dezimal(row["price"]),
            net_amount=Dezimal(row["net_amount"]),
            fees=Dezimal(row["fees"]),
            retentions=Dezimal(row["retentions"]) if row["retentions"] else None,
            order_date=(
                datetime.fromisoformat(row["order_date"]) if row["order_date"] else None
            ),
            fund_type=(
                FundType(row["product_subtype"]) if row["product_subtype"] else None
            ),
            split_ratio=(
                Dezimal(row["split_ratio"]) if row["split_ratio"] is not None else None
            ),
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

    async def save(self, data: Transactions):
        if data.investment:
            await self._save_investment(data.investment)
        if data.account:
            await self._save_account(data.account)

    async def _save_investment(self, txs: List[BaseInvestmentTx]):
        async with self._db_client.tx() as cursor:
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
                    "split_ratio": None,
                    "entity_account_id": str(tx.entity_account_id)
                    if tx.entity_account_id
                    else None,
                }

                if isinstance(tx, StockTx):
                    entry.update(
                        {
                            "isin": tx.isin,
                            "ticker": tx.ticker,
                            "market": tx.market if tx.market else None,
                            "shares": str(tx.shares) if tx.shares is not None else None,
                            "price": str(tx.price),
                            "net_amount": str(tx.net_amount)
                            if tx.net_amount is not None
                            else None,
                            "fees": str(tx.fees),
                            "retentions": str(tx.retentions) if tx.retentions else None,
                            "order_date": (
                                tx.order_date.isoformat() if tx.order_date else None
                            ),
                            "linked_tx": tx.linked_tx,
                            "split_ratio": (
                                str(tx.split_ratio)
                                if tx.split_ratio is not None
                                else None
                            ),
                            "product_subtype": (
                                tx.equity_type.value if tx.equity_type else None
                            ),
                        }
                    )
                elif isinstance(tx, CryptoCurrencyTx):
                    entry.update(
                        {
                            "ticker": tx.symbol,
                            "shares": str(tx.currency_amount),
                            "price": str(tx.price),
                            "net_amount": str(tx.net_amount)
                            if tx.net_amount is not None
                            else None,
                            "fees": str(tx.fees),
                            "retentions": str(tx.retentions) if tx.retentions else None,
                            "order_date": (
                                tx.order_date.isoformat() if tx.order_date else None
                            ),
                            "asset_contract_address": tx.contract_address,
                        }
                    )
                elif isinstance(tx, MarketForecastTx):
                    entry.update(
                        {
                            "ticker": tx.symbol,
                            "shares": str(tx.size),
                            "price": str(tx.price),
                            "net_amount": str(tx.net_amount)
                            if tx.net_amount is not None
                            else None,
                            "fees": str(tx.fees),
                            "retentions": str(tx.retentions) if tx.retentions else None,
                            "order_date": (
                                tx.order_date.isoformat() if tx.order_date else None
                            ),
                        }
                    )
                elif isinstance(tx, FundTx):
                    entry.update(
                        {
                            "isin": tx.isin,
                            "market": tx.market if tx.market else None,
                            "shares": str(tx.shares) if tx.shares is not None else None,
                            "price": str(tx.price),
                            "net_amount": str(tx.net_amount)
                            if tx.net_amount is not None
                            else None,
                            "fees": str(tx.fees),
                            "retentions": str(tx.retentions) if tx.retentions else None,
                            "order_date": (
                                tx.order_date.isoformat() if tx.order_date else None
                            ),
                            "product_subtype": (
                                tx.fund_type.value if tx.fund_type else None
                            ),
                            "split_ratio": (
                                str(tx.split_ratio)
                                if tx.split_ratio is not None
                                else None
                            ),
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
                            "net_amount": str(tx.net_amount)
                            if tx.net_amount is not None
                            else None,
                            "fees": str(tx.fees),
                            "retentions": str(tx.retentions),
                        }
                    )

                await cursor.execute(
                    TransactionQueries.INSERT_INVESTMENT,
                    entry,
                )

    async def _save_account(self, txs: List[AccountTx]):
        async with self._db_client.tx() as cursor:
            for tx in txs:
                await cursor.execute(
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
                        str(tx.entity_account_id) if tx.entity_account_id else None,
                        tx.counterparty,
                        tx.iban,
                        tx.linked_tx,
                        tx.labels_locked,
                    ),
                )

    async def get_all(
        self,
        real: Optional[bool] = None,
        excluded_entities: Optional[list[UUID]] = None,
    ) -> Transactions:
        return Transactions(
            investment=await self._get_investment_txs(real, excluded_entities),
            account=await self._get_account_txs(real, excluded_entities),
        )

    async def _get_investment_txs(
        self,
        real: Optional[bool] = None,
        excluded_entities: Optional[list[UUID]] = None,
    ) -> List[BaseInvestmentTx]:
        async with self._db_client.read() as cursor:
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
                query += " AND " + " AND ".join(conditions)

            query += " ORDER BY it.date ASC"
            await cursor.execute(query, tuple(params))

            return [_map_investment_row(row) for row in await cursor.fetchall()]

    async def _get_account_txs(
        self,
        real: Optional[bool] = None,
        excluded_entities: Optional[list[UUID]] = None,
    ) -> List[AccountTx]:
        async with self._db_client.read() as cursor:
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
                query += " AND " + " AND ".join(conditions)

            query += " ORDER BY at.date ASC"

            await cursor.execute(query, tuple(params))
            return [map_account_row(row) for row in await cursor.fetchall()]

    async def _get_investment_txs_by_entity(
        self, entity_id: UUID
    ) -> List[BaseInvestmentTx]:
        async with self._db_client.read() as cursor:
            await cursor.execute(
                TransactionQueries.INVESTMENT_SELECT_BY_ENTITY,
                (str(entity_id),),
            )
            return [_map_investment_row(row) for row in await cursor.fetchall()]

    async def _get_account_txs_by_entity(self, entity_id: UUID) -> List[AccountTx]:
        async with self._db_client.read() as cursor:
            await cursor.execute(
                TransactionQueries.ACCOUNT_SELECT_BY_ENTITY,
                (str(entity_id),),
            )
            return [map_account_row(row) for row in await cursor.fetchall()]

    async def get_refs_by_entity_account(self, entity_account_id: UUID) -> Set[str]:
        async with self._db_client.read() as cursor:
            await cursor.execute(
                TransactionQueries.GET_REFS_BY_ENTITY_ACCOUNT,
                (str(entity_account_id), str(entity_account_id)),
            )
            return {row[0] for row in await cursor.fetchall()}

    async def get_by_entity(self, entity_id: UUID) -> Transactions:
        return Transactions(
            investment=await self._get_investment_txs_by_entity(entity_id),
            account=await self._get_account_txs_by_entity(entity_id),
        )

    async def get_by_entity_and_source(
        self, entity_id: UUID, source: DataSource
    ) -> Transactions:
        async with self._db_client.read() as cursor:
            await cursor.execute(
                TransactionQueries.INVESTMENT_AND_ACCOUNT_BY_ENTITY_AND_SOURCE,
                (str(entity_id), source.value),
            )
            investment = [_map_investment_row(row) for row in await cursor.fetchall()]

            await cursor.execute(
                TransactionQueries.ACCOUNT_BY_ENTITY_AND_SOURCE,
                (str(entity_id), source.value),
            )
            account = [map_account_row(row) for row in await cursor.fetchall()]

        return Transactions(investment=investment, account=account)

    async def get_refs_by_source_type(self, real: bool) -> Set[str]:
        async with self._db_client.read() as cursor:
            await cursor.execute(
                TransactionQueries.GET_REFS_BY_SOURCE_TYPE,
                (real, real),
            )
            return {row[0] for row in await cursor.fetchall()}

    async def get_by_filters(self, query: TransactionQueryRequest) -> list[BaseTx]:
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
        if query.labels:
            conditions.append(
                f"EXISTS (SELECT 1 FROM account_transaction_labels l WHERE l.tx_id = tx.id AND l.label_id IN ({sql_placeholders(query.labels)}))"
            )
            params.extend([str(label_id) for label_id in query.labels])
        if query.excluded_labels:
            conditions.append(
                f"NOT EXISTS (SELECT 1 FROM account_transaction_labels l WHERE l.tx_id = tx.id AND l.label_id IN ({sql_placeholders(query.excluded_labels)}))"
            )
            params.extend([str(label_id) for label_id in query.excluded_labels])
        if query.unlabeled:
            conditions.append(
                "tx.product_type = 'ACCOUNT' AND tx.linked_tx IS NULL AND NOT EXISTS (SELECT 1 FROM account_transaction_labels l WHERE l.tx_id = tx.id)"
            )
        if query.search and query.search.strip():
            pattern = _like_pattern(query.search.strip())
            conditions.append(
                "(tx.name LIKE ? ESCAPE '\\' OR tx.counterparty LIKE ? ESCAPE '\\')"
            )
            params.extend([pattern, pattern])

        where_clause = f"AND {' AND '.join(conditions)}" if conditions else ""
        order_pagination = "ORDER BY tx.date DESC LIMIT ? OFFSET ?"
        offset = (query.page - 1) * query.limit
        params.extend([query.limit, offset])
        sql = f"{base_sql} {where_clause} {order_pagination}"

        async with self._db_client.read() as cursor:
            await cursor.execute(sql, tuple(params))
            rows = await cursor.fetchall()

            tx_list = []
            account_txs = []
            for row in rows:
                if row["product_type"] == "ACCOUNT":
                    tx = map_account_row(row)
                    account_txs.append(tx)
                else:
                    tx = _map_investment_row(row)
                tx_list.append(tx)

            await self._hydrate_labels(cursor, account_txs)

        return tx_list

    async def delete_by_source(self, source: DataSource):
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                TransactionQueries.DELETE_INVESTMENT_BY_SOURCE,
                (source,),
            )
            await cursor.execute(
                TransactionQueries.DELETE_ACCOUNT_BY_SOURCE,
                (source,),
            )

    async def get_by_id(self, tx_id: UUID) -> Optional[BaseTx]:
        async with self._db_client.read() as cursor:
            await cursor.execute(
                TransactionQueries.GET_INVESTMENT_BY_ID,
                (str(tx_id),),
            )
            row = await cursor.fetchone()
            if row:
                return _map_investment_row(row)

            await cursor.execute(
                TransactionQueries.GET_ACCOUNT_BY_ID,
                (str(tx_id),),
            )
            row = await cursor.fetchone()
            if row:
                account_tx = map_account_row(row)
                await self._hydrate_labels(cursor, [account_tx])
                return account_tx
        return None

    async def delete_by_id(self, tx_id: UUID):
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                TransactionQueries.DELETE_BY_ID_INVESTMENT,
                (str(tx_id),),
            )
            await cursor.execute(
                TransactionQueries.DELETE_BY_ID_ACCOUNT,
                (str(tx_id),),
            )

    async def delete_by_entity_account_id(self, entity_account_id: UUID):
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                TransactionQueries.DELETE_INVESTMENT_BY_ENTITY_ACCOUNT,
                (str(entity_account_id),),
            )
            await cursor.execute(
                TransactionQueries.DELETE_ACCOUNT_BY_ENTITY_ACCOUNT,
                (str(entity_account_id),),
            )

    @staticmethod
    async def _hydrate_labels(cursor: DBCursor, txs: list[AccountTx]):
        if not txs:
            return
        labels = await load_tx_labels(cursor, [tx.id for tx in txs])
        pairs = await load_transfer_pairs(cursor, [tx.id for tx in txs])
        for tx in txs:
            tx.labels = labels.get(tx.id, [])
            tx.transfer_pair = pairs.get(tx.id)

    @staticmethod
    def _selection_conditions(
        selection: AccountTxSelection,
    ) -> tuple[list[str], list]:
        conditions: list[str] = []
        params: list = []
        if selection.ids is not None:
            if not selection.ids:
                conditions.append("1 = 0")
            else:
                conditions.append(f"at.id IN ({sql_placeholders(selection.ids)})")
                params.extend([str(tx_id) for tx_id in selection.ids])
        if selection.from_date:
            conditions.append("at.date >= ?")
            params.append(selection.from_date.isoformat())
        if selection.to_date:
            conditions.append("at.date < ?")
            params.append(_day_after(selection.to_date))
        if selection.entities:
            conditions.append(
                f"at.entity_id IN ({sql_placeholders(selection.entities)})"
            )
            params.extend([str(e) for e in selection.entities])
        if selection.types:
            conditions.append(f"at.type IN ({sql_placeholders(selection.types)})")
            params.extend([t.value for t in selection.types])
        if selection.with_labels:
            conditions.append(
                f"EXISTS (SELECT 1 FROM account_transaction_labels l WHERE l.tx_id = at.id AND l.label_id IN ({sql_placeholders(selection.with_labels)}))"
            )
            params.extend([str(label_id) for label_id in selection.with_labels])
        if selection.without_labels:
            conditions.append(
                f"NOT EXISTS (SELECT 1 FROM account_transaction_labels l WHERE l.tx_id = at.id AND l.label_id IN ({sql_placeholders(selection.without_labels)}))"
            )
            params.extend([str(label_id) for label_id in selection.without_labels])
        if selection.unlabeled_only:
            conditions.append(
                "NOT EXISTS (SELECT 1 FROM account_transaction_labels l WHERE l.tx_id = at.id)"
            )
        if not selection.include_locked:
            conditions.append("at.labels_locked = FALSE")
        if not selection.include_linked:
            conditions.append("at.linked_tx IS NULL")
        if selection.exclude_external_unmatched:
            conditions.append("at.external_unmatched_at IS NULL")
        if selection.search and selection.search.strip():
            pattern = _like_pattern(selection.search.strip())
            conditions.append(
                "(at.name LIKE ? ESCAPE '\\' OR at.counterparty LIKE ? ESCAPE '\\')"
            )
            params.extend([pattern, pattern])
        return conditions, params

    async def get_account_txs(
        self, selection: AccountTxSelection, limit: Optional[int] = None
    ) -> list[AccountTx]:
        conditions, params = self._selection_conditions(selection)
        query = TransactionQueries.ACCOUNT_SELECT_BASE.value
        if conditions:
            query += " AND " + " AND ".join(conditions)
        query += " ORDER BY at.date DESC, at.id"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        async with self._db_client.read() as cursor:
            await cursor.execute(query, tuple(params))
            txs = [map_account_row(row) for row in await cursor.fetchall()]
            await self._hydrate_labels(cursor, txs)
        return txs

    async def count_account_txs(self, selection: AccountTxSelection) -> int:
        conditions, params = self._selection_conditions(selection)
        query = TransactionQueries.ACCOUNT_COUNT_BASE.value
        if conditions:
            query += " AND " + " AND ".join(conditions)

        async with self._db_client.read() as cursor:
            await cursor.execute(query, tuple(params))
            row = await cursor.fetchone()
            return int(row[0]) if row else 0

    async def get_refs_by_entity(self, entity_id: UUID) -> set[str]:
        async with self._db_client.read() as cursor:
            await cursor.execute(
                TransactionQueries.GET_REFS_BY_ENTITY,
                (str(entity_id), str(entity_id)),
            )
            return {row[0] for row in await cursor.fetchall()}

    async def get_latest_account_tx_date(self, entity_id: UUID) -> Optional[datetime]:
        async with self._db_client.read() as cursor:
            await cursor.execute(
                TransactionQueries.GET_LATEST_REAL_ACCOUNT_TX_DATE,
                (str(entity_id),),
            )
            row = await cursor.fetchone()
            if not row or not row[0]:
                return None
            return datetime.fromisoformat(row[0])

    async def get_investment_txs_in_range(
        self, entity_ids: list[UUID], from_date: date, to_date: date
    ) -> list[BaseInvestmentTx]:
        if not entity_ids:
            return []
        query = (
            TransactionQueries.INVESTMENT_SELECT_BASE.value
            + f" AND it.entity_id IN ({sql_placeholders(entity_ids)})"
            + " AND it.date >= ? AND it.date < ?"
            + " ORDER BY it.date ASC"
        )
        params = [str(e) for e in entity_ids] + [
            from_date.isoformat(),
            _day_after(to_date),
        ]
        async with self._db_client.read() as cursor:
            await cursor.execute(query, tuple(params))
            return [_map_investment_row(row) for row in await cursor.fetchall()]
