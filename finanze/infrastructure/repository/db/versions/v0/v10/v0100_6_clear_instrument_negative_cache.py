from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

# a throttled provider used to be cached as a definitive absence of prices
SQL = """
      DELETE
      FROM instrument_no_result;

      DELETE
      FROM instrument_price_gap;
      """


class V01006ClearInstrumentNegativeCache(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.10.0:6_clear_instrument_negative_cache"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(SQL)
        for statement in statements:
            await cursor.execute(statement)
