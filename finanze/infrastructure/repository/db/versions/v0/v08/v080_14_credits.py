from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

DDL = """
      CREATE TABLE credit_positions
      (
          id                 CHAR(36) PRIMARY KEY,
          global_position_id CHAR(36)    NOT NULL REFERENCES global_positions (id) ON DELETE CASCADE ON UPDATE CASCADE,
          currency           VARCHAR(10) NOT NULL,
          credit_limit       TEXT        NOT NULL,
          drawn_amount       TEXT        NOT NULL,
          interest_rate      TEXT        NOT NULL,
          name               TEXT,
          pledged_amount     TEXT,
          creation           DATE
      );

      CREATE INDEX idx_crp_global_position_id ON credit_positions (global_position_id);
      """


class V0814Credits(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.8.0:14_credits"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(DDL)
        for statement in statements:
            await cursor.execute(statement)
