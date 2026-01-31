from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

SQL = """
      CREATE TABLE templates
      (
          id         CHAR(36) PRIMARY KEY,
          name       TEXT        NOT NULL,
          feature    VARCHAR(20) NOT NULL,
          type       VARCHAR(20) NOT NULL,
          fields     JSON        NOT NULL,
          products   JSON,
          created_at TIMESTAMP   NOT NULL,
          updated_at TIMESTAMP   NOT NULL
      );
      """


class V0705Templates(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.7.0:5_templates"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(SQL)
        for statement in statements:
            await cursor.execute(statement)
