from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

DDL = """
      CREATE TABLE last_fetches
      (
          entity_id CHAR(36)     NOT NULL REFERENCES entities (id) ON DELETE CASCADE ON UPDATE CASCADE,
          feature   VARCHAR(255) NOT NULL,
          date      TIMESTAMP    NOT NULL,

          PRIMARY KEY (entity_id, feature)
      );

      CREATE INDEX idx_lfetches_entity_id ON last_fetches (entity_id);
      """


class V0201(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.2.0:1_fetches"

    def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(DDL)
        for statement in statements:
            cursor.execute(statement)
