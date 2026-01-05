from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.upgrader import DBVersionMigration

DML = """
      UPDATE investment_historic
      SET product_type = 'REAL_ESTATE_CF'
      WHERE product_type = 'REAL_STATE_CF';
      """


class V0302(DBVersionMigration):
    @property
    def name(self):
        return "v0.3.0:2_re_rename_historic"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        await cursor.execute(DML)
