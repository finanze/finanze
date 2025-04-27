from datetime import datetime
from uuid import UUID

from dateutil.tz import tzlocal

from application.ports.auto_contributions_port import AutoContributionsPort
from domain.auto_contributions import AutoContributions, PeriodicContribution, ContributionFrequency, \
    ContributionTargetType
from domain.dezimal import Dezimal
from domain.financial_entity import FinancialEntity
from infrastructure.repository.db.client import DBClient


class AutoContributionsSQLRepository(AutoContributionsPort):

    def __init__(self, client: DBClient):
        self._db_client = client

    def save(self, entity_id: UUID, data: AutoContributions):
        with self._db_client.tx() as cursor:
            # Delete existing contributions for this entity
            cursor.execute(
                "DELETE FROM periodic_contributions WHERE entity_id = ?",
                (str(entity_id),)
            )

            # Insert new contributions
            for contrib in data.periodic:
                cursor.execute(
                    """
                    INSERT INTO periodic_contributions (id, entity_id, target, target_type, alias, amount, currency,
                                                        since, until, frequency, active, is_real, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(contrib.id),
                        str(entity_id),
                        contrib.target,
                        contrib.target_type,
                        contrib.alias,
                        str(contrib.amount),
                        contrib.currency,
                        contrib.since.isoformat(),
                        contrib.until.isoformat() if contrib.until else None,
                        contrib.frequency.name,
                        contrib.active,
                        contrib.is_real,
                        datetime.now(tzlocal()).isoformat()
                    )
                )

    def get_all_grouped_by_entity(self) -> dict[FinancialEntity, AutoContributions]:
        with self._db_client.read() as cursor:
            cursor.execute("""
                           SELECT e.id as entity_id, e.*, pc.id as pc_id, pc.*
                           FROM periodic_contributions pc
                                    JOIN financial_entities e ON pc.entity_id = e.id
                           """)

            entities = {}
            for row in cursor.fetchall():
                entity = FinancialEntity(
                    id=UUID(row["entity_id"]),
                    name=row["name"],
                    is_real=row["is_real"]
                )
                if entity not in entities:
                    entities[entity] = []

                entities[entity].append(
                    PeriodicContribution(
                        id=UUID(row["pc_id"]),
                        alias=row["alias"],
                        target=row["target"],
                        target_type=ContributionTargetType[row["target_type"]],
                        amount=Dezimal(row["amount"]),
                        currency=row["currency"],
                        since=datetime.fromisoformat(row["since"]).date(),
                        until=datetime.fromisoformat(row["until"]).date() if row["until"] else None,
                        frequency=ContributionFrequency[row["frequency"]],
                        active=bool(row["active"]),
                        is_real=bool(row["is_real"])
                    )
                )

            return {
                entity: AutoContributions(periodic=contribs)
                for entity, contribs in entities.items()
            }

    def get_last_update_grouped_by_entity(self) -> dict[FinancialEntity, datetime]:
        with self._db_client.read() as cursor:
            cursor.execute("""
                           SELECT e.*, MAX(pc.created_at) AS last_update
                           FROM periodic_contributions pc
                                    JOIN financial_entities e ON pc.entity_id = e.id
                           GROUP BY entity_id
                           """)

            result = {}
            for row in cursor.fetchall():
                entity = FinancialEntity(
                    id=UUID(row["id"]),
                    name=row["name"],
                    is_real=row["is_real"]
                )
                last_update = datetime.fromisoformat(row["last_update"])
                result[entity] = last_update

            return result
