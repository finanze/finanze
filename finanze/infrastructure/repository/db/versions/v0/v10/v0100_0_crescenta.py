from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

SQL = """
      -- Fallback to update id of existing Crescenta financial entity if manually added and set it to native
      WITH to_update AS (SELECT id
                         FROM entities
                         WHERE name = 'Crescenta'
                           AND id != 'e0000000-0000-0000-0000-000000000015'
                           AND NOT EXISTS (SELECT 1
                                           FROM entities
                                           WHERE id = 'e0000000-0000-0000-0000-000000000015')
                         LIMIT 1)
      UPDATE entities
      SET id     = 'e0000000-0000-0000-0000-000000000015',
          origin = 'NATIVE',
          name   = 'Crescenta'
      WHERE id IN (SELECT id FROM to_update);

      -- Add Crescenta as financial entity (skip if already exists)
      INSERT OR IGNORE INTO entities (id, name, natural_id, type, origin)
      VALUES ('e0000000-0000-0000-0000-000000000015', 'Crescenta', NULL, 'FINANCIAL_INSTITUTION', 'NATIVE');
      """


class V0100Crescenta(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.10.0:0_crescenta"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        for statement in self.parse_block(SQL):
            await cursor.execute(statement)
