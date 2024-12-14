from datetime import datetime, timezone

from dateutil.tz import tzlocal
from pymongo import MongoClient

from application.ports.transaction_port import TransactionPort
from domain.global_position import SourceType
from domain.transactions import Transactions, StockTx, FundTx, BaseInvestmentTx, FactoringTx, TxProductType, \
    RealStateCFTx, AccountTx
from infrastructure.repository.position_repository import map_serializable


def map_transactions(investment_result, account_result) -> Transactions:
    return Transactions(
        investment=[
            map_investment_tx(doc)
            for doc in investment_result
        ],
        account=[
            map_account_tx(doc)
            for doc in account_result
        ]
    )


def map_investment_tx(doc: dict) -> BaseInvestmentTx:
    if doc["productType"] == "STOCK_ETF":
        return StockTx(
            **{**doc,
               'retentions': doc.get("retentions", None)}
        )
    elif doc["productType"] == "FUND":
        return FundTx(
            **{**doc,
               'retentions': doc.get("retentions", None)}
        )
    elif doc["productType"] == "REAL_STATE_CF":
        return RealStateCFTx(**doc)

    elif doc["productType"] == "FACTORING":
        return FactoringTx(**doc)

    raise ValueError(f"Unknown product type: {doc['productType']}")


def map_account_tx(doc: dict) -> AccountTx:
    return AccountTx(**doc)


class TransactionRepository(TransactionPort):
    INVESTMENT_CATEGORY = "INVESTMENT"
    ACCOUNT_CATEGORY = "ACCOUNT"

    def __init__(self, client: MongoClient, db_name: str):
        self.client = client
        self.db = self.client[db_name]
        self.collection = self.db["transactions"]

    def save(self, data: Transactions) -> None:
        self._save(data.investment, self.INVESTMENT_CATEGORY)
        self._save(data.account, self.ACCOUNT_CATEGORY)

    def _save(self, txs, category):
        if txs:
            self.collection.insert_many(
                [
                    {
                        **map_serializable(tx),
                        "createdAt": datetime.now(tzlocal()),
                        "category": category
                    }
                    for tx in txs
                ]
            )

    def get_all(self) -> Transactions:
        investment_result = (self.collection.find(
            {"category": self.INVESTMENT_CATEGORY},
            {"_id": 0, "createdAt": 0, "category": 0}
        ).sort("date", 1))

        account_result = (self.collection.find(
            {"category": self.ACCOUNT_CATEGORY},
            {"_id": 0, "createdAt": 0, "category": 0}
        ).sort("date", 1))

        return map_transactions(investment_result, account_result)

    def get_by_product(self, product_types: list[TxProductType]) -> Transactions:
        product_types = [product_type.value for product_type in product_types]

        investment_result = self.collection.find(
            {"productType": {"$in": product_types}, "category": self.INVESTMENT_CATEGORY},
            {"_id": 0, "createdAt": 0, "category": 0}
        ).sort("date", 1)

        account_result = self.collection.find(
            {"productType": {"$in": product_types}, "category": self.ACCOUNT_CATEGORY},
            {"_id": 0, "createdAt": 0, "category": 0}
        ).sort("date", 1)

        return map_transactions(investment_result, account_result)

    def get_ids_by_entity(self, entity: str) -> set[str]:
        pipeline = [
            {"$match": {"entity": entity}},
            {"$project": {"_id": 0, "id": 1}},
        ]
        result = self.collection.aggregate(pipeline)
        return {doc["id"] for doc in result}

    def get_ids_by_source_type(self, source_type: SourceType) -> set[str]:
        pipeline = [
            {"$match": {"sourceType": source_type.value}},
            {"$project": {"_id": 0, "id": 1}},
        ]
        result = self.collection.aggregate(pipeline)
        return {doc["id"] for doc in result}

    def get_last_created_grouped_by_entity(self) -> dict[str, datetime]:
        pipeline = [
            {"$sort": {"createdAt": -1}},
            {
                "$group": {
                    "_id": "$entity",
                    "lastCreatedAt": {"$first": "$createdAt"}
                }
            },
            {"$project": {"_id": 0, "entity": "$_id", "lastCreatedAt": 1}}
        ]
        result = list(self.collection.aggregate(pipeline))
        return {doc["entity"]: doc["lastCreatedAt"].replace(tzinfo=timezone.utc) for doc in result}
