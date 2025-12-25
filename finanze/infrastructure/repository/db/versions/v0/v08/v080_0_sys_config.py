from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.upgrader import DBVersionMigration

SQL = """
      CREATE TABLE sys_config
      (
          "key" VARCHAR(128) PRIMARY KEY,
          value TEXT
      );
      """


class V0800SysConfig(DBVersionMigration):
    @property
    def name(self):
        return "v0.8.0:0_sys_config"

    def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        cursor.execute(SQL)
