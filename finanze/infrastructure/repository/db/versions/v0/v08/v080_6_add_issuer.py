from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

SQL = """
      ALTER TABLE stock_positions
          ADD COLUMN issuer VARCHAR(50);

      ALTER TABLE fund_positions
          ADD COLUMN issuer VARCHAR(50);
      """


class V0806AddIssuer(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.8.0:6_add_issuer"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(SQL)
        for statement in statements:
            await cursor.execute(statement)
