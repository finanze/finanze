from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.upgrader import DBVersionMigration

SQL = """
      INSERT INTO external_integrations (id, name, type, status)
      VALUES ('ENABLE_BANKING', 'Enable Banking', 'ENTITY_PROVIDER', 'OFF');
      """


class V0904EnableBankingProvider(DBVersionMigration):
    @property
    def name(self):
        return "v0.9.0:4_enable_banking_provider"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        await cursor.execute(SQL)
