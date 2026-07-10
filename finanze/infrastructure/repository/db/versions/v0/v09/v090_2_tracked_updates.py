from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

DDL = """
      CREATE TABLE tracked_updates
      (
          id               CHAR(36)     NOT NULL PRIMARY KEY,
          use_case_name    VARCHAR(255) NOT NULL UNIQUE,
          last_executed_at TIMESTAMP    NOT NULL
      );
      """


class V0902TrackedUpdates(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.9.0:2_tracked_updates"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(DDL)
        for statement in statements:
            await cursor.execute(statement)
