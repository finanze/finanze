from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

DDL = """
      -- EARNINGS/EXPENSES ICONS
      ALTER TABLE periodic_flows
          ADD COLUMN icon TEXT;

      ALTER TABLE pending_flows
          ADD COLUMN icon TEXT;
      """


class V0405FlowsIcon(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.4.0:5_flows_icon"

    def upgrade(self, cursor: DBCursor):
        statements = self.parse_block(DDL)
        for statement in statements:
            cursor.execute(statement)
