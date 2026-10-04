from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from application.ports.label_port import LabelPort
from dateutil.tz import tzlocal
from domain.labeling import Label, LabelCategory
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.labeling.queries import LabelQueries


def _map_label_row(row) -> Label:
    return Label(
        id=UUID(row["id"]),
        key=row["key"],
        name=row["name"],
        description=row["description"],
        color=row["color"],
        icon=row["icon"],
        category=LabelCategory(row["category"]),
    )


class LabelRepository(LabelPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    async def get_all(self) -> list[Label]:
        async with self._db_client.read() as cursor:
            await cursor.execute(LabelQueries.GET_ALL)
            return [_map_label_row(row) for row in await cursor.fetchall()]

    async def get_by_id(self, label_id: UUID) -> Optional[Label]:
        async with self._db_client.read() as cursor:
            await cursor.execute(LabelQueries.GET_BY_ID, (str(label_id),))
            row = await cursor.fetchone()
            return _map_label_row(row) if row else None

    async def get_usage(self) -> dict[UUID, int]:
        async with self._db_client.read() as cursor:
            await cursor.execute(LabelQueries.GET_USAGE)
            return {
                UUID(row["label_id"]): int(row["usage"])
                for row in await cursor.fetchall()
            }

    async def save(self, label: Label) -> Label:
        if label.id is None:
            label.id = uuid4()
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                LabelQueries.INSERT,
                (
                    str(label.id),
                    label.key,
                    label.name,
                    label.description,
                    label.color,
                    label.icon,
                    label.category.value,
                    datetime.now(tzlocal()).isoformat(),
                ),
            )
        return label

    async def update(self, label: Label):
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                LabelQueries.UPDATE,
                (
                    label.name,
                    label.description,
                    label.color,
                    label.icon,
                    label.category.value,
                    str(label.id),
                ),
            )

    async def delete(self, label_id: UUID):
        async with self._db_client.tx() as cursor:
            await cursor.execute(LabelQueries.DELETE, (str(label_id),))
