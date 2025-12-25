from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from application.ports.virtual_import_registry import VirtualImportRegistry
from domain.entity import Feature
from domain.virtual_data import VirtualDataImport, VirtualDataSource
from infrastructure.repository.db.client import DBClient


class VirtualImportRepository(VirtualImportRegistry):
    def __init__(self, client: DBClient):
        self._db_client = client

    def insert(self, entries: list[VirtualDataImport]):
        with self._db_client.tx() as cursor:
            for e in entries:
                cursor.execute(
                    """
                    INSERT INTO virtual_data_imports (id, import_id, global_position_id, source, date, feature, entity_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
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
        params = []
        where = ""
        if source:
            where = " WHERE source = ? "
            params.append(source)

        query = f"""
                WITH latest_import_details AS (SELECT import_id
                                               FROM virtual_data_imports
                                               {where}
                                               ORDER BY date DESC
                                               LIMIT 1)
                SELECT vdi.*
                FROM virtual_data_imports vdi
                         JOIN latest_import_details lid
                              ON vdi.import_id = lid.import_id
                """

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
                """
                DELETE
                FROM virtual_data_imports
                WHERE import_id = ?
                  AND feature = ?
                """,
                (str(import_id), feature),
            )

    def delete_by_import_feature_and_entity(
        self, import_id: UUID, feature: Feature, entity_id: UUID
    ):
        with self._db_client.tx() as cursor:
            cursor.execute(
                """
                DELETE FROM virtual_data_imports
                WHERE import_id = ? AND feature = ? AND entity_id = ?
                """,
                (str(import_id), feature, str(entity_id)),
            )
