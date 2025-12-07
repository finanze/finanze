from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration


DDL = """
      -- PERIODIC FLOWS
      CREATE TABLE periodic_flows
      (
          id        CHAR(36) PRIMARY KEY,
          name      TEXT        NOT NULL,
          amount    TEXT        NOT NULL,
          currency  CHAR(3)     NOT NULL,
          flow_type VARCHAR(16) NOT NULL,
          frequency VARCHAR(32) NOT NULL,
          category  TEXT,
          enabled   BOOLEAN     NOT NULL DEFAULT TRUE,
          since     DATE        NOT NULL,
          until     DATE
      );

      -- PENDING FLOWS
      CREATE TABLE pending_flows
      (
          id        CHAR(36) PRIMARY KEY,
          name      TEXT        NOT NULL,
          amount    TEXT        NOT NULL,
          currency  CHAR(3)     NOT NULL,
          flow_type VARCHAR(16) NOT NULL,
          category  TEXT,
          enabled   BOOLEAN     NOT NULL DEFAULT TRUE,
          date      DATE
      );

      CREATE INDEX idx_periodic_flows_enabled ON periodic_flows (enabled);
      CREATE INDEX idx_periodic_flows_flow_type ON periodic_flows (flow_type);
      CREATE INDEX idx_pending_flows_enabled ON pending_flows (enabled);
      CREATE INDEX idx_pending_flows_flow_type ON pending_flows (flow_type);
      """


class V0400EarningsExpenses(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.4.0:0_earnings_expenses"

    def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(DDL)
        for statement in statements:
            cursor.execute(statement)
