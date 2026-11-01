from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

SQL = """
      INSERT OR IGNORE INTO external_integrations (id, name, type, status)
      VALUES ('OPENAI_COMPATIBLE', 'Custom endpoint', 'AI_PROVIDER', 'OFF');

      INSERT OR IGNORE INTO external_integrations (id, name, type, status)
      VALUES ('LOCAL_MODELS', 'Local models', 'AI_PROVIDER', 'OFF');
      """


class V01106LocalAIIntegrations(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.11.0:6_local_ai_integrations"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        for statement in self.parse_block(SQL):
            await cursor.execute(statement)
