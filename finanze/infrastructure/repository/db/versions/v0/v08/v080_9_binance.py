from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

SQL = """
      INSERT OR IGNORE INTO entities (id, name, natural_id, type, origin)
      VALUES ('ce000000-0000-0000-0000-000000000001', 'Binance', NULL, 'CRYPTO_EXCHANGE', 'NATIVE');
      """


class V0809Binance(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.8.0:9_binance"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(SQL)
        for statement in statements:
            await cursor.execute(statement)
