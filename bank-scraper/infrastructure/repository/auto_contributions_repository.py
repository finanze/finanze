from datetime import datetime, timezone

from dateutil.tz import tzlocal
from pymongo import MongoClient

from application.ports.auto_contributions_port import AutoContributionsPort
from domain.auto_contributions import AutoContributions, PeriodicContribution
from infrastructure.repository.position_repository import map_serializable


def map_contributions_to_domain(data: dict) -> AutoContributions:
    periodic_contributions = []

    periodic_contributions_data = data.get("periodic", [])
    for contribution_data in periodic_contributions_data:
        periodic_contributions.append(
            PeriodicContribution(**contribution_data)
        )

    return AutoContributions(
        periodic=periodic_contributions,
    )


class AutoContributionsRepository(AutoContributionsPort):

    def __init__(self, client: MongoClient, db_name: str):
        self._client = client
        self._db = self._client[db_name]
        self._collection = self._db["auto_contributions"]

    def save(self, entity: str, data: AutoContributions):
        data = {**map_serializable(data), "updatedAt": datetime.now(tzlocal())}
        self._collection.update_one(
            {"entity": entity},
            {"$set": data},
            upsert=True,
        )

    def get_all_grouped_by_entity(self) -> dict[str, AutoContributions]:
        pipeline = [
            {
                "$group": {
                    "_id": "$entity",
                    "data": {"$first": "$$ROOT"}
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "entity": "$_id",
                    "data": {
                        "$arrayToObject": {
                            "$filter": {
                                "input": {"$objectToArray": "$data"},
                                "cond": {"$ne": ["$$this.k", "_id"]}
                            }
                        }
                    }
                }
            }
        ]
        result = list(self._collection.aggregate(pipeline))

        mapped_result = {}
        for entry in result:
            entity_name = entry["entity"]
            raw_data = entry["data"]

            entity_data = map_contributions_to_domain(raw_data)

            mapped_result[entity_name] = entity_data

        return mapped_result

    def get_last_update_grouped_by_entity(self) -> dict[str, datetime]:
        pipeline = [
            {
                "$group": {
                    "_id": "$entity",
                    "lastUpdate": {"$max": "$updatedAt"}
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "entity": "$_id",
                    "lastUpdate": "$lastUpdate"
                }
            }
        ]
        result = list(self._collection.aggregate(pipeline))

        return {entry["entity"]: entry["lastUpdate"].replace(tzinfo=timezone.utc) for entry in result}
