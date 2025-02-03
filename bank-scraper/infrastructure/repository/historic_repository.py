from datetime import datetime

from dateutil.tz import tzlocal
from pymongo import MongoClient

from application.ports.historic_port import HistoricPort
from domain.historic import Historic, FactoringEntry, RealStateCFEntry
from infrastructure.repository.position_repository import map_serializable


def map_transactions(raw_entries) -> Historic:
    entries = []
    for doc in raw_entries:
        if doc["productType"] == "FACTORING":
            entries.append(FactoringEntry(**doc))
        elif doc["productType"] == "REAL_STATE_CF":
            entries.append(RealStateCFEntry(**doc))

    return Historic(entries=entries)


class HistoricRepository(HistoricPort):

    def __init__(self, client: MongoClient, db_name: str):
        self._client = client
        self._db = self._client[db_name]
        self._collection = self._db["historic"]

    def save(self, historic: Historic):
        self._collection.insert_many(
            [
                {
                    **map_serializable(entry),
                    "createdAt": datetime.now(tzlocal())
                }
                for entry in historic.entries
            ]
        )

    def get_all(self) -> Historic:
        entries = (self._collection.find(
            {},
            {"_id": 0, "createdAt": 0}
        ).sort("lastInvestDate", 1))

        return map_transactions(entries)

    def delete_by_entity(self, entity: str):
        self._collection.delete_many({"entity": entity})
