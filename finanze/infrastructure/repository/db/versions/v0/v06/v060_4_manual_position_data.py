from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

SQL = """
      CREATE TABLE manual_position_data
      (
          entry_id           CHAR(36)    NOT NULL PRIMARY KEY,
          global_position_id CHAR(36)    NOT NULL REFERENCES global_positions (id) ON DELETE CASCADE ON UPDATE CASCADE,
          product_type       VARCHAR(32) NOT NULL,
          track_ticker       BOOLEAN     NOT NULL,
          tracker_key        TEXT
      );
      """


class V0604ManualPositionData(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.6.0:4_manual_position_data"

    def upgrade(self, cursor: DBCursor):
        statements = self.parse_block(SQL)
        for statement in statements:
            cursor.execute(statement)
