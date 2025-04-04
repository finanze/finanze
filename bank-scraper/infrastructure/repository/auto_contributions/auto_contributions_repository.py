import json
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from application.ports.auto_contributions_port import AutoContributionsPort
from domain.auto_contributions import AutoContributions, PeriodicContribution, ContributionFrequency
from domain.dezimal import Dezimal
from domain.financial_entity import FinancialEntity
from infrastructure.repository.db.client import DBClient


class AutoContributionsSQLRepository(AutoContributionsPort):

    def __init__(self, client: DBClient):
        self._db_client = client

    def _get_entity_info(self, entity_name: str) -> Optional[dict]:
        with self._db_client.read() as cursor:
            cursor.execute(
                "SELECT id, is_real, properties FROM financial_entities WHERE name = ?",
                (entity_name,)
            )
            result = cursor.fetchone()
            if not result:
                return None
            return {
                "id": result[0],
                "is_real": bool(result[1]),
                "properties": json.loads(result[2])
            }

    def save(self, entity_id: int, data: AutoContributions):
        with self._db_client.tx() as cursor:
            # Delete existing contributions for this entity
            cursor.execute(
                "DELETE FROM periodic_contributions WHERE entity_id = ?",
                (entity_id,)
            )

            # Insert new contributions
            for contrib in data.periodic:
                cursor.execute(
                    """
                    INSERT INTO periodic_contributions (
                        id, entity_id, isin, alias, amount, currency, since, until, frequency, active, is_real
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid4()),
                        entity_id,
                        contrib.isin,
                        contrib.alias,
                        str(contrib.amount),
                        "EUR",
                        contrib.since.isoformat(),
                        contrib.until.isoformat() if contrib.until else None,
                        contrib.frequency.name,
                        contrib.active,
                        True
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
                    id=row["entity_id"],
                    features=row["features"],
                    name=row["name"],
                    is_real=row["is_real"]
                )
                if entity not in entities:
                    entities[entity] = []

                entities[entity].append(
                    PeriodicContribution(
                        id=row["pc_id"],
                        alias=row["alias"],
                        isin=row["isin"],
                        amount=Dezimal(row["amount"]),
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
                    id=row["id"],
                    features=row["features"],
                    name=row["name"],
                    is_real=row["is_real"]
                )
                last_update = datetime.fromisoformat(row["last_update"]).astimezone(timezone.utc)
                result[entity] = last_update

            return result
