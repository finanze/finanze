from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

DDL = """
      CREATE TABLE networth_timeline_points
      (
          date      TEXT PRIMARY KEY,
          currency  VARCHAR(10) NOT NULL,
          total     TEXT        NOT NULL,
          breakdown TEXT        NOT NULL
      );

      CREATE TABLE networth_timeline_meta
      (
          id                 INTEGER PRIMARY KEY CHECK (id = 1),
          inputs_signature   TEXT,
          last_computed_date TEXT
      );
      """


class V0900NetworthTimeline(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.9.0:0_networth_timeline"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(DDL)
        for statement in statements:
            await cursor.execute(statement)
