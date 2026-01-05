from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.upgrader import DBVersionMigration

SQL = """
      ALTER TABLE periodic_contributions
          ADD COLUMN target_subtype VARCHAR(32);
      """


class V0700ContribTargetSubtype(DBVersionMigration):
    @property
    def name(self):
        return "v0.7.0:0_add_contrib_target_subtype"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        await cursor.execute(SQL)
