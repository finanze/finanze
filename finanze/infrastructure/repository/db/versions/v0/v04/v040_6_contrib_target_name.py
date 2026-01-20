from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

DDL = """
      -- Add target_name to periodic contributions
      ALTER TABLE periodic_contributions
          ADD COLUMN target_name TEXT;

      -- Backfill existing records: prefer alias, fallback to target
      UPDATE periodic_contributions
      SET target_name = COALESCE(alias, target)
      WHERE target_name IS NULL;
      """


class V0406ContribTargetName(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.4.0:6_contrib_target_name"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(DDL)
        for statement in statements:
            await cursor.execute(statement)
