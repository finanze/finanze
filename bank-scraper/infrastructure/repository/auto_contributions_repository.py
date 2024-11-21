from pymongo import MongoClient

from application.ports.auto_contributions_port import AutoContributionsPort
from domain.auto_contributions import AutoContributions, PeriodicContribution, ContributionFrequency
from domain.bank import Bank
from infrastructure.repository.bank_data_repository import map_serializable


def map_contributions_to_domain(data: dict) -> AutoContributions:
    periodic_contributions = []

    periodic_contributions_data = data.get("periodic", [])
    for contribution_data in periodic_contributions_data:
        periodic_contributions.append(
            PeriodicContribution(
                alias=contribution_data["alias"],
                isin=contribution_data["isin"],
                amount=contribution_data["amount"],
                since=contribution_data["since"],
                until=contribution_data["until"],
                frequency=ContributionFrequency[contribution_data["frequency"]],
                active=contribution_data["active"]
            )
        )

    return AutoContributions(
        periodic=periodic_contributions,
    )


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

    def get_all(self) -> dict[str, AutoContributions]:
        pipeline = [
            {
                "$group": {
                    "_id": "$bank",
                    "data": {"$first": "$$ROOT"}
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "bank": "$_id",
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
        result = list(self.collection.aggregate(pipeline))

        mapped_result = {}
        for entry in result:
            bank_name = entry["bank"]
            raw_data = entry["data"]

            bank_data = map_contributions_to_domain(raw_data)

            mapped_result[bank_name] = bank_data

        return mapped_result
