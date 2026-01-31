from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

SQL = """
      -- We do a little trick in order to achieve the foreign_keys disable in a TX
      COMMIT TRANSACTION;
      PRAGMA foreign_keys = OFF;
      BEGIN TRANSACTION;

      DROP INDEX IF EXISTS idx_global_positions_date;
      DROP INDEX IF EXISTS idx_gp_entity_id;
      
      CREATE TABLE global_positions_new
      (
          id        CHAR(36) PRIMARY KEY,
          entity_id CHAR(36)     NOT NULL REFERENCES entities (id) ON DELETE CASCADE ON UPDATE CASCADE,
          date      DATETIME     NOT NULL,
          source    VARCHAR(255) NOT NULL
      );

      INSERT INTO global_positions_new (id, entity_id, date, source)
      SELECT id, entity_id, date, CASE WHEN is_real = 1 THEN 'REAL' ELSE 'SHEETS' END AS source
      FROM global_positions;

      DROP TABLE global_positions;

      ALTER TABLE global_positions_new RENAME TO global_positions;

      CREATE INDEX idx_global_positions_date ON global_positions (date desc);
      CREATE INDEX idx_gp_entity_id ON global_positions (entity_id);

      PRAGMA foreign_key_check;
      COMMIT TRANSACTION;
      PRAGMA foreign_keys = ON;
      BEGIN TRANSACTION;
      -- End of trick, let the normal TX continue
      """


class V0602Source(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.6.0:2_use_source_positions"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(SQL)
        for statement in statements:
            await cursor.execute(statement)
