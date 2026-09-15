from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

SQL = """
      DELETE
      FROM investment_transactions
      WHERE entity_id = 'e0000000-0000-0000-0000-000000000006'
        AND source = 'REAL';
      """


class V01002ClearSegoRealTransactions(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.10.0:2_clear_sego_real_transactions"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(SQL)
        for statement in statements:
            await cursor.execute(statement)
