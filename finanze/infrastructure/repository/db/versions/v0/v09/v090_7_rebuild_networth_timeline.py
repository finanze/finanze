from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

DDL = """
      -- Rebuild the memoized net worth timeline from scratch: the memoization no
      -- longer keys on the set of imports, so clear the cached points and state
      -- to force a full recomputation on the next read.
      DELETE FROM networth_timeline_points;
      DELETE FROM networth_timeline_meta;
      """


class V0907RebuildNetworthTimeline(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.9.0:7_rebuild_networth_timeline"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        for statement in self.parse_block(DDL):
            await cursor.execute(statement)
