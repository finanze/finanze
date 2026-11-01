from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

DDL = """
      ALTER TABLE periodic_flows
          ADD COLUMN label_id CHAR(36) REFERENCES labels(id) ON DELETE SET NULL;
      CREATE INDEX idx_periodic_flows_label_id ON periodic_flows(label_id);

      ALTER TABLE labels ADD COLUMN subcategory VARCHAR(16) NOT NULL DEFAULT 'NONE';

      UPDATE labels
      SET subcategory = CASE
          WHEN category = 'EXPENSE' AND key IN (
              'restaurants', 'shopping', 'subscriptions', 'leisure', 'travel',
              'personal_care', 'gifts_donations', 'bank_fees', 'other_expense'
          ) THEN 'WANTS'
          WHEN category = 'EXPENSE' THEN 'NEED'
          WHEN category = 'EXCLUDED' AND key = 'savings_investment' THEN 'SAVINGS'
          ELSE 'NONE'
      END;

      UPDATE labels SET category = 'EXCLUDED', subcategory = 'NONE'
      WHERE key = 'internal_transfer';
      """


class V01103PeriodicFlowBudgetLabel(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.11.0:3_periodic_flow_budget_label"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        for statement in self.parse_block(DDL):
            await cursor.execute(statement)
