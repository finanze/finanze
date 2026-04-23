from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

DDL = """
      ALTER TABLE hd_addresses ADD COLUMN balance TEXT NOT NULL DEFAULT '0';
      """


class V0815HdAddressBalance(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.8.0:15_hd_address_balance"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(DDL)
        for statement in statements:
            await cursor.execute(statement)
