from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.upgrader import DBVersionMigration

SQL = """
      ALTER TABLE entities
          ADD COLUMN icon_url TEXT;
      """


class V0801AddEntityImage(DBVersionMigration):
    @property
    def name(self):
        return "v0.8.0:1_add_entity_icon_url"

    def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        cursor.execute(SQL)
