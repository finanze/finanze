from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

DDL = """
      CREATE TABLE fetch_pointers
      (
          entity_account_id CHAR(36) NOT NULL
              REFERENCES entity_accounts(id) ON DELETE CASCADE ON UPDATE CASCADE,
          entity_id         CHAR(36) NOT NULL
              REFERENCES entities(id) ON DELETE CASCADE ON UPDATE CASCADE,
          key               VARCHAR(255) NOT NULL,
          threshold         DATE NOT NULL,
          PRIMARY KEY (entity_account_id, key)
      );

      CREATE INDEX idx_fetch_pointers_entity_id
          ON fetch_pointers (entity_id);
      """


class V01010FetchPointers(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.10.1:0_fetch_pointers"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(DDL)
        for statement in statements:
            await cursor.execute(statement)
