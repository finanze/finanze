from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from application.ports.virtual_import_registry import VirtualImportRegistry
from domain.entity import Feature
from domain.virtual_data import VirtualDataImport, VirtualDataSource
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.virtual.queries import VirtualImportQueries


class VirtualImportRepository(VirtualImportRegistry):
    def __init__(self, client: DBClient):
        self._db_client = client

    def insert(self, entries: list[VirtualDataImport]):
        with self._db_client.tx() as cursor:
            for e in entries:
                cursor.execute(
                    VirtualImportQueries.INSERT,
                    (
                        str(uuid4()),
                        str(e.import_id),
                        str(e.global_position_id) if e.global_position_id else None,
                        e.source,
                        e.date.isoformat(),
                        e.feature,
                        str(e.entity_id) if e.entity_id else None,
                    ),
                )

    def get_last_import_records(
        self, source: Optional[VirtualDataSource] = None
    ) -> list[VirtualDataImport]:
        params: list[str] = []
        where = ""
        if source:
            where = " WHERE source = ? "
            params.append(source)

        query = VirtualImportQueries.GET_LAST_IMPORT_RECORDS_BASE.value.format(
            where=where
        )

        with self._db_client.read() as cursor:
            cursor.execute(query, params)

            rows = cursor.fetchall()
            return [
                VirtualDataImport(
                    import_id=UUID(row["import_id"]),
                    global_position_id=UUID(row["global_position_id"])
                    if row["global_position_id"]
                    else None,
                    source=VirtualDataSource(row["source"]),
                    date=datetime.fromisoformat(row["date"]),
                    feature=Feature[row["feature"]] if row["feature"] else None,
                    entity_id=UUID(row["entity_id"]) if row["entity_id"] else None,
                )
                for row in rows
            ]

    def delete_by_import_and_feature(self, import_id: UUID, feature: Feature):
        with self._db_client.tx() as cursor:
            cursor.execute(
                VirtualImportQueries.DELETE_BY_IMPORT_AND_FEATURE,
                (str(import_id), feature),
            )

    def delete_by_import_feature_and_entity(
        self, import_id: UUID, feature: Feature, entity_id: UUID
    ):
        with self._db_client.tx() as cursor:
            cursor.execute(
                VirtualImportQueries.DELETE_BY_IMPORT_FEATURE_AND_ENTITY,
                (str(import_id), feature, str(entity_id)),
            )
