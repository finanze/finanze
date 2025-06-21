from application.ports.virtual_import_registry import VirtualImportRegistry
from domain.virtual_fetch import VirtualDataImport
from infrastructure.repository.db.client import DBClient


class VirtualImportRepository(VirtualImportRegistry):
    def __init__(self, client: DBClient):
        self._db_client = client

    def insert(self, entry: VirtualDataImport):
        with self._db_client.tx() as cursor:
            cursor.execute(
                "INSERT INTO virtual_data_imports (import_id, global_position_id, source, date) VALUES (?, ?, ?, ?)",
                (
                    str(entry.import_id),
                    str(entry.global_position_id),
                    entry.source,
                    entry.date.isoformat(),
                ),
            )
