from pymongo import MongoClient

from application.ports.auto_contributions_port import AutoContributionsPort
from domain.auto_contributions import AutoContributions
from domain.bank import Bank
from infrastructure.repository.bank_data_repository import map_serializable


class AutoContributionsRepository(AutoContributionsPort):
    def __init__(self, uri: str, db_name: str):
        self.client = MongoClient(uri)
        self.db = self.client[db_name]
        self.collection = self.db["auto_contributions"]

    def upsert(self, bank: Bank, data: AutoContributions):
        self.collection.update_one(
            {"bank": bank.name},
            {"$set": map_serializable(data)},
            upsert=True,
        )
