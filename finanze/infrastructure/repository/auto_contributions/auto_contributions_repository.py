from datetime import datetime
from uuid import UUID

from dateutil.tz import tzlocal

from application.ports.auto_contributions_port import AutoContributionsPort
from domain.auto_contributions import (
    AutoContributions,
    ContributionFrequency,
    ContributionQueryRequest,
    ContributionTargetSubtype,
    ContributionTargetType,
    PeriodicContribution,
)
from domain.dezimal import Dezimal
from domain.entity import Entity
from domain.fetch_record import DataSource
from infrastructure.repository.auto_contributions.queries import (
    AutoContributionsQueries,
)
from infrastructure.repository.db.client import DBClient


class AutoContributionsSQLRepository(AutoContributionsPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    async def save(self, entity_id: UUID, data: AutoContributions, source: DataSource):
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                AutoContributionsQueries.DELETE_BY_ENTITY_AND_SOURCE,
                (str(entity_id), source.value),
            )

            for contrib in data.periodic:
                await cursor.execute(
                    AutoContributionsQueries.INSERT_PERIODIC_CONTRIBUTION,
                    (
                        str(contrib.id),
                        str(entity_id),
                        contrib.target,
                        contrib.target_type,
                        contrib.target_subtype.name if contrib.target_subtype else None,
                        contrib.alias,
                        contrib.target_name,
                        str(contrib.amount),
                        contrib.currency,
                        contrib.since.isoformat(),
                        contrib.until.isoformat() if contrib.until else None,
                        contrib.frequency.name,
                        contrib.active,
                        contrib.source == DataSource.REAL,
                        contrib.source,
                        datetime.now(tzlocal()).isoformat(),
                    ),
                )

    async def get_all_grouped_by_entity(
        self, query: ContributionQueryRequest
    ) -> dict[Entity, AutoContributions]:
        async with self._db_client.read() as cursor:
            params: list[str] = []
            sql = AutoContributionsQueries.GET_ALL_GROUPED_BY_ENTITY_BASE.value

            conditions: list[str] = []
            if query.real is not None:
                if query.real:
                    conditions.append("pc.source = 'REAL'")
                else:
                    conditions.append("pc.source IN ('MANUAL', 'SHEETS')")
            if query.entities:
                placeholders = ", ".join("?" for _ in query.entities)
                conditions.append(f"pc.entity_id IN ({placeholders})")
                params.extend([str(e) for e in query.entities])
            if query.excluded_entities:
                placeholders = ", ".join("?" for _ in query.excluded_entities)
                conditions.append(
                    f"(pc.entity_id NOT IN ({placeholders}) OR pc.is_real = FALSE)"
                )
                params.extend([str(e) for e in query.excluded_entities])

            if conditions:
                sql += " WHERE " + " AND ".join(conditions)

            await cursor.execute(sql, tuple(params))

            entities = {}
            for row in await cursor.fetchall():
                if not row["entity_id"] or not row["pc_id"]:
                    continue

                entity = Entity(
                    id=UUID(row["entity_id"]),
                    name=row["entity_name"],
                    natural_id=row["entity_natural_id"],
                    type=row["entity_type"],
                    origin=row["entity_origin"],
                    icon_url=row["icon_url"],
                )
                if entity not in entities:
                    entities[entity] = []

                entities[entity].append(
                    PeriodicContribution(
                        id=UUID(row["pc_id"]),
                        alias=row["alias"],
                        target=row["target"],
                        target_name=row["target_name"],
                        target_type=ContributionTargetType[row["target_type"]],
                        target_subtype=(
                            ContributionTargetSubtype[row["target_subtype"]]
                            if row["target_subtype"]
                            else None
                        ),
                        amount=Dezimal(row["amount"]),
                        currency=row["currency"],
                        since=datetime.fromisoformat(row["since"]).date(),
                        until=datetime.fromisoformat(row["until"]).date()
                        if row["until"]
                        else None,
                        frequency=ContributionFrequency[row["frequency"]],
                        active=bool(row["active"]),
                        source=row["source"],
                        entity=entity,
                    )
                )

            return {
                entity: AutoContributions(periodic=contribs)
                for entity, contribs in entities.items()
            }

    async def delete_by_source(self, source: DataSource):
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                AutoContributionsQueries.DELETE_BY_SOURCE, (source.value,)
            )
