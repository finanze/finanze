from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

SQL = """
      INSERT OR IGNORE INTO external_integrations (id, name, type, status)
      VALUES ('GITHUB_COPILOT', 'GitHub Copilot', 'AI_PROVIDER', 'OFF');
      """


class V01200GitHubCopilotIntegration(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.12.0:0_github_copilot_integration"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        for statement in self.parse_block(SQL):
            await cursor.execute(statement)
