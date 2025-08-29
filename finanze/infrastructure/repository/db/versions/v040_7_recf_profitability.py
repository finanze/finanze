from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

SQL = """
      -- Add profitability to real estate CF positions
      ALTER TABLE real_estate_cf_positions
          ADD COLUMN profitability TEXT NOT NULL DEFAULT '0';

      ALTER TABLE factoring_positions
          ADD COLUMN profitability TEXT NOT NULL DEFAULT '0';

      UPDATE real_estate_cf_positions
      SET profitability = interest_rate
      WHERE profitability IS NULL;

      UPDATE factoring_positions
      SET profitability = interest_rate
      WHERE profitability IS NULL;
      """


class V0407RECFProfitability(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.4.0:7_recf_factoring_profitability"

    def upgrade(self, cursor: DBCursor):
        statements = self.parse_block(SQL)
        for statement in statements:
            cursor.execute(statement)
