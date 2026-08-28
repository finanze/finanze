from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.upgrader import DBVersionMigration

SQL = """
      INSERT OR IGNORE INTO entities (id, name, natural_id, type, origin)
      VALUES ('c0000000-0000-0000-0000-000000000006', 'Zerion', NULL, 'CRYPTO_WALLET', 'NATIVE');
      """


class V01008ZerionEntity(DBVersionMigration):
    @property
    def name(self):
        return "v0.10.0:8_zerion_entity"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        await cursor.execute(SQL)
