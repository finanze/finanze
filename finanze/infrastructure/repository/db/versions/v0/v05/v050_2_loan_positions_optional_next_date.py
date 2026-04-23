from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

DDL = """
      DROP INDEX IF EXISTS idx_lp_global_position_id;

      CREATE TABLE loan_positions_new
      (
          id                    CHAR(36) PRIMARY KEY,
          global_position_id    CHAR(36)    NOT NULL REFERENCES global_positions (id) ON DELETE CASCADE ON UPDATE CASCADE,
          type                  VARCHAR(32) NOT NULL,
          currency              CHAR(3)     NOT NULL,
          name                  TEXT,
          current_installment   TEXT        NOT NULL,
          interest_rate         TEXT        NOT NULL,
          loan_amount           TEXT,
          next_payment_date     DATE,
          principal_outstanding TEXT        NOT NULL,
          principal_paid        TEXT,
          creation              DATE        NOT NULL,
          maturity              DATE        NOT NULL,
          unpaid                TEXT,
          interest_type         VARCHAR(16),
          euribor_rate          TEXT,
          fixed_years           INTEGER
      );

      INSERT INTO loan_positions_new
      SELECT id,
             global_position_id,
             type,
             currency,
             name,
             current_installment,
             interest_rate,
             loan_amount,
             next_payment_date,
             principal_outstanding,
             principal_paid,
             creation,
             maturity,
             unpaid,
             interest_type,
             euribor_rate,
             fixed_years
      FROM loan_positions lp
      WHERE lp.creation IS NOT NULL
        AND lp.maturity IS NOT NULL;

      DROP TABLE loan_positions;
      ALTER TABLE loan_positions_new RENAME TO loan_positions;

      CREATE INDEX idx_lp_global_position_id ON loan_positions (global_position_id);
      """


class V0502(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.5.0:2_loan_positions_optional_next_date"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(DDL)
        for statement in statements:
            await cursor.execute(statement)
