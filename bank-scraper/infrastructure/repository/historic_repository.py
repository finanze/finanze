from datetime import datetime

from dateutil.tz import tzlocal
from pymongo import MongoClient

from application.ports.historic_port import HistoricPort
from domain.historic import Historic, FactoringEntry, RealStateCFEntry
from infrastructure.repository.position_repository import map_serializable


def map_transactions(entries) -> Historic:
    factoring_entries = [FactoringEntry(**doc) for doc in entries if doc["productType"] == "FACTORING"]
    real_state_entries = [RealStateCFEntry(**doc) for doc in entries if doc["productType"] == "REAL_STATE_CF"]

    return Historic(entries=factoring_entries + real_state_entries)


class HistoricRepository(HistoricPort):
    def __init__(self, client: MongoClient, db_name: str):
        self.client = client
        self.db = self.client[db_name]
        self.collection = self.db["historic"]

    def save(self, historic: Historic):
        self.collection.insert_many(
            [
                {
                    **map_serializable(entry),
                    "createdAt": datetime.now(tzlocal())
                }
                for entry in historic.entries
            ]
        )

    def get_all(self) -> Historic:
        entries = (self.collection.find(
            {},
            {"_id": 0, "createdAt": 0}
        ).sort("date", 1))

        return map_transactions(entries)

    def delete_by_entity(self, entity: str):
        self.collection.delete_many({"entity": entity})
