from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

DDL = """
      ALTER TABLE fund_positions
          ADD COLUMN asset_type VARCHAR(32);
      """


class V0505(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.5.0:5_add_fund_asset_type"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(DDL)
        for statement in statements:
            await cursor.execute(statement)
