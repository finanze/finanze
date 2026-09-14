from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

SQL = """
      WITH to_update AS (SELECT id
                         FROM entities
                         WHERE name IN ('Trading 212', 'Trading212')
                           AND id != 'e0000000-0000-0000-0000-000000000016'
                           AND NOT EXISTS (SELECT 1
                                           FROM entities
                                           WHERE id = 'e0000000-0000-0000-0000-000000000016')
                         LIMIT 1)
      UPDATE entities
      SET id     = 'e0000000-0000-0000-0000-000000000016',
          origin = 'NATIVE',
          name   = 'Trading 212'
      WHERE id IN (SELECT id FROM to_update);

      INSERT OR IGNORE INTO entities (id, name, natural_id, type, origin)
      VALUES ('e0000000-0000-0000-0000-000000000016', 'Trading 212', NULL, 'FINANCIAL_INSTITUTION', 'NATIVE');
      """


class V01007Trading212(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.10.0:7_trading212"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        for statement in self.parse_block(SQL):
            await cursor.execute(statement)
