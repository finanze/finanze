from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.upgrader import DBVersionMigration

SQL = """
      INSERT INTO external_integrations (id, name, type, status)
      VALUES ('ZERION', 'Zerion', 'CRYPTO_PROVIDER', 'OFF');
      """


class V01006ZerionIntegration(DBVersionMigration):
    @property
    def name(self):
        return "v0.10.0:6_zerion_integration"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        await cursor.execute(SQL)
