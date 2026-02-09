from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.upgrader import DBVersionMigration

SQL = """
      INSERT INTO external_integrations (id, name, type, status)
      VALUES ('ETHPLORER', 'Ethplorer', 'CRYPTO_PROVIDER', 'OFF');
      """


class V0704Ethplorer(DBVersionMigration):
    @property
    def name(self):
        return "v0.7.0:4_ethplorer_integration"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        await cursor.execute(SQL)
