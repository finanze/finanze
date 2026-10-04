from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

DDL = """
      CREATE TABLE ignored_recurring_movements
      (
          id         CHAR(36)    NOT NULL PRIMARY KEY,
          key        TEXT        NOT NULL,
          type       VARCHAR(32) NOT NULL,
          currency   CHAR(3)     NOT NULL,
          amount     TEXT        NOT NULL,
          created_at DATETIME    NOT NULL
      );
      """


class V01102IgnoredRecurringMovements(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.11.0:2_ignored_recurring_movements"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        for statement in self.parse_block(DDL):
            await cursor.execute(statement)
