from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

DDL = """
      -- PENDING FLOWS STATUS: recreate table replacing `enabled` with `status` + `status_changed_at`
      CREATE TABLE pending_flows_new
      (
          id                CHAR(36) PRIMARY KEY,
          name              TEXT        NOT NULL,
          amount            TEXT        NOT NULL,
          currency          CHAR(3)     NOT NULL,
          flow_type         VARCHAR(16) NOT NULL,
          category          TEXT,
          status            VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
          status_changed_at DATETIME,
          date              DATE,
          icon              TEXT
      );

      INSERT INTO pending_flows_new (id, name, amount, currency, flow_type, category, status, status_changed_at, date, icon)
      SELECT id,
             name,
             amount,
             currency,
             flow_type,
             NULLIF(TRIM(category), ''),
             CASE enabled WHEN 0 THEN 'DISABLED' ELSE 'ACTIVE' END,
             strftime('%Y-%m-%dT%H:%M:%S+00:00', 'now'),
             date,
             icon
      FROM pending_flows;

      DROP TABLE pending_flows;

      ALTER TABLE pending_flows_new RENAME TO pending_flows;

      CREATE INDEX idx_pending_flows_status ON pending_flows (status);
      CREATE INDEX idx_pending_flows_flow_type ON pending_flows (flow_type);

      -- Normalize blank/whitespace categories to NULL for recurring flows too
      UPDATE periodic_flows SET category = NULL WHERE TRIM(category) = '';
      """


class V0906PendingFlowStatus(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.9.0:6_pending_flow_status"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        for statement in self.parse_block(DDL):
            await cursor.execute(statement)
