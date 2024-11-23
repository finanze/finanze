from pymongo import MongoClient

from application.ports.transaction_port import TransactionPort
from domain.bank import Bank
from domain.transactions import Transactions
from infrastructure.repository.bank_data_repository import map_serializable


class TransactionRepository(TransactionPort):

    def __init__(self, client: MongoClient, db_name: str):
        self.client = client
        self.db = self.client[db_name]
        self.collection = self.db["transactions"]

    def save(self, source: Bank, data: Transactions):
        txs = data.investment
        if not txs:
            return
        self.collection.insert_many(
            [
                map_serializable(tx)
                for tx in txs
            ]
        )

    def get_all(self) -> Transactions:
        pass

    def get_ids_by_source(self, source: Bank) -> set[str]:
        pipeline = [
            {"$match": {"source": source.name}},
            {"$project": {"_id": 0, "id": 1}},
        ]
        result = self.collection.aggregate(pipeline)
        return {doc["id"] for doc in result}
