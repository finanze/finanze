from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

SQL = """
      -- Update id of existing ING financial entity if manually added and set is to real
      UPDATE entities
      SET id = 'e0000000-0000-0000-0000-000000000010', is_real = TRUE
      WHERE name = 'ING'
        AND id != 'e0000000-0000-0000-0000-000000000010';

      -- Add ING as financial entity (skip if already exists)
      INSERT OR IGNORE INTO entities (id, name, is_real)
      VALUES ('e0000000-0000-0000-0000-000000000010', 'ING', TRUE);
      """


class V0500ING(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.5.0:0_ing"

    def upgrade(self, cursor: DBCursor):
        statements = self.parse_block(SQL)
        for statement in statements:
            cursor.execute(statement)
