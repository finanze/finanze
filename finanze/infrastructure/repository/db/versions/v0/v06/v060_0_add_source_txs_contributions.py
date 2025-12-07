from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

SQL = """
      ALTER TABLE periodic_contributions
          ADD COLUMN source VARCHAR(255);

      ALTER TABLE investment_transactions
          ADD COLUMN source VARCHAR(255);

      ALTER TABLE account_transactions
          ADD COLUMN source VARCHAR(255);

      UPDATE periodic_contributions
      SET source = 'REAL'
      WHERE is_real = 1;
      UPDATE periodic_contributions
      SET source = 'SHEETS'
      WHERE is_real = 0;

      UPDATE investment_transactions
      SET source = 'REAL'
      WHERE is_real = 1;
      UPDATE investment_transactions
      SET source = 'SHEETS'
      WHERE is_real = 0;

      UPDATE account_transactions
      SET source = 'REAL'
      WHERE is_real = 1;
      UPDATE account_transactions
      SET source = 'SHEETS'
      WHERE is_real = 0;
      """


class V0600Source(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.6.0:0_add_source_txs_contributions"

    def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(SQL)
        for statement in statements:
            cursor.execute(statement)
