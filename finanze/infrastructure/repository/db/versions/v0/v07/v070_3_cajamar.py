from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

SQL = """
      -- Checkout if external_entities LINKED for Cajamar related entity and set to status ORPHAN
      UPDATE external_entities
      SET status = 'ORPHAN'
      WHERE status = 'LINKED'
        AND entity_id IN (SELECT id
                          FROM entities
                          WHERE name IN ('Grupo Cajamar', 'Cajamar', 'Cajamar Caja Rural'));

      -- Update Cajamar entity that originated from external entity if exists
      UPDATE entities
      SET id     = 'e0000000-0000-0000-0000-000000000011',
          origin = 'NATIVE',
          name   = 'Grupo Cajamar'
      WHERE id IN (SELECT entity_id
                   FROM external_entities
                   WHERE status = 'ORPHAN')
        AND id != 'e0000000-0000-0000-0000-000000000011';

      -- Fallback to update id of existing Cajamar financial entity if manually added and set is to real
      WITH to_update AS (SELECT id
                         FROM entities
                         WHERE name IN ('Grupo Cajamar', 'Cajamar', 'Cajamar Caja Rural')
                           AND id != 'e0000000-0000-0000-0000-000000000011'
                           AND NOT EXISTS (SELECT 1
                                           FROM entities
                                           WHERE id = 'e0000000-0000-0000-0000-000000000011')
                         LIMIT 1)
      UPDATE entities
      SET id     = 'e0000000-0000-0000-0000-000000000011',
          origin = 'NATIVE',
          name   = 'Grupo Cajamar'
      WHERE id IN (SELECT id FROM to_update);

      -- Add Cajamar as financial entity (skip if already exists)
      INSERT OR IGNORE INTO entities (id, name, natural_id, type, origin)
      VALUES ('e0000000-0000-0000-0000-000000000011', 'Grupo Cajamar', 'BCCAESMM', 'FINANCIAL_INSTITUTION', 'NATIVE');
      """


class V0703Cajamar(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.7.0:3_cajamar"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(SQL)
        for statement in statements:
            await cursor.execute(statement)
