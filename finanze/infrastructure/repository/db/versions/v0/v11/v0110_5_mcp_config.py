from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

DDL = """
      CREATE TABLE mcp_config
      (
          id           INTEGER   NOT NULL PRIMARY KEY CHECK (id = 1),
          enabled      BOOLEAN   NOT NULL DEFAULT 0,
          allow_writes BOOLEAN   NOT NULL DEFAULT 0,
          token        TEXT,
          updated_at   TIMESTAMP NOT NULL
      );
      """


class V01105McpConfig(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.11.0:5_mcp_config"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        for statement in self.parse_block(DDL):
            await cursor.execute(statement)
