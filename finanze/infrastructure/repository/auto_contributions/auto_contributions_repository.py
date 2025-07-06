from datetime import datetime
from uuid import UUID

from application.ports.auto_contributions_port import AutoContributionsPort
from dateutil.tz import tzlocal
from domain.auto_contributions import (
    AutoContributions,
    ContributionFrequency,
    ContributionQueryRequest,
    ContributionTargetType,
    PeriodicContribution,
)
from domain.dezimal import Dezimal
from domain.entity import Entity
from infrastructure.repository.db.client import DBClient


class AutoContributionsSQLRepository(AutoContributionsPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    def save(self, entity_id: UUID, data: AutoContributions):
        with self._db_client.tx() as cursor:
            # Delete existing contributions for this entity
            cursor.execute(
                "DELETE FROM periodic_contributions WHERE entity_id = ?",
                (str(entity_id),),
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
                        datetime.now(tzlocal()).isoformat(),
                    ),
                )

    def get_all_grouped_by_entity(
        self, query: ContributionQueryRequest
    ) -> dict[Entity, AutoContributions]:
        with self._db_client.read() as cursor:
            params = []
            sql = """
                  SELECT e.id as entity_id, e.name as entity_name, e.type as entity_type, e.is_real as entity_is_real, pc.id as pc_id, pc.*
                  FROM periodic_contributions pc
                           JOIN entities e ON pc.entity_id = e.id
                  """

            conditions = []
            if query.real is not None:
                conditions.append("pc.is_real = ?")
                params.append(query.real)
            if query.entities:
                placeholders = ", ".join("?" for _ in query.entities)
                conditions.append(f"pc.entity_id IN ({placeholders})")
                params.extend([str(e) for e in query.entities])
            if query.excluded_entities:
                placeholders = ", ".join("?" for _ in query.excluded_entities)
                conditions.append(f"pc.entity_id NOT IN ({placeholders})")
                params.extend([str(e) for e in query.excluded_entities])

            if conditions:
                sql += " WHERE " + " AND ".join(conditions)

            cursor.execute(sql, tuple(params))

            entities = {}
            for row in cursor.fetchall():
                if not row["entity_id"] or not row["pc_id"]:
                    continue

                entity = Entity(
                    id=UUID(row["entity_id"]),
                    name=row["entity_name"],
                    type=row["entity_type"],
                    is_real=row["entity_is_real"],
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
                        until=datetime.fromisoformat(row["until"]).date()
                        if row["until"]
                        else None,
                        frequency=ContributionFrequency[row["frequency"]],
                        active=bool(row["active"]),
                        is_real=bool(row["is_real"]),
                    )
                )

            return {
                entity: AutoContributions(periodic=contribs)
                for entity, contribs in entities.items()
            }
