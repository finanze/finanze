import hashlib

from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

DDL = """
      ALTER TABLE manual_position_data ADD COLUMN track_loan BOOLEAN NOT NULL DEFAULT 0;

      UPDATE manual_position_data SET track_loan = 1
      WHERE product_type = 'LOAN' AND track_ticker = 1;

      DROP INDEX IF EXISTS idx_lp_global_position_id;

      CREATE TABLE loan_positions_new
      (
          id                    CHAR(36) PRIMARY KEY,
          global_position_id    CHAR(36)    NOT NULL
              REFERENCES global_positions (id)
                  ON DELETE CASCADE ON UPDATE CASCADE,
          type                  VARCHAR(32) NOT NULL,
          currency              CHAR(3)     NOT NULL,
          name                  TEXT,
          current_installment   TEXT        NOT NULL,
          installment_frequency VARCHAR(32) NOT NULL,
          interest_type         VARCHAR(16) NOT NULL,
          interest_rate         TEXT        NOT NULL,
          installment_interests TEXT,
          loan_amount           TEXT        NOT NULL,
          principal_outstanding TEXT        NOT NULL,
          creation              DATE        NOT NULL,
          maturity              DATE        NOT NULL,
          unpaid                TEXT,
          euribor_rate          TEXT,
          fixed_years           INTEGER,
          fixed_interest_rate   TEXT,
          next_payment_date     DATE,
          hash                  VARCHAR(64) NOT NULL
      );

      INSERT INTO loan_positions_new
        (id, global_position_id, type, currency, name, current_installment,
         installment_frequency, interest_type, interest_rate, loan_amount,
         principal_outstanding, creation, maturity, unpaid, euribor_rate,
         fixed_years, next_payment_date, hash)
      SELECT
        id, global_position_id, type, currency, name, current_installment,
        'MONTHLY',
        COALESCE(interest_type, 'FIXED'),
        interest_rate, loan_amount,
        principal_outstanding, creation, maturity, unpaid, euribor_rate,
        fixed_years, next_payment_date, ''
      FROM loan_positions
      WHERE loan_amount IS NOT NULL;

      DROP TABLE loan_positions;
      ALTER TABLE loan_positions_new RENAME TO loan_positions;

      CREATE INDEX idx_lp_global_position_id ON loan_positions (global_position_id);

      ALTER TABLE real_estate_flows ADD COLUMN extra_reference VARCHAR(255);

      ALTER TABLE manual_position_data ADD COLUMN tracking_ref_outstanding TEXT;
      ALTER TABLE manual_position_data ADD COLUMN tracking_ref_date DATE;
      """


class V0813ImprovedLoans(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.8.0:13_improved_loans"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(DDL)
        for statement in statements:
            await cursor.execute(statement)

        await self._compute_hashes(cursor)

    async def _compute_hashes(self, cursor: DBCursor):
        await cursor.execute(
            "SELECT lp.id, gp.entity_id, lp.loan_amount, lp.creation "
            "FROM loan_positions lp "
            "JOIN global_positions gp ON lp.global_position_id = gp.id"
        )
        rows = list(cursor)
        for row in rows:
            entity_id = row["entity_id"]
            loan_amount = row["loan_amount"]
            creation = row["creation"]
            raw = f"{entity_id}|{loan_amount}|{creation}"
            h = hashlib.shake_128(raw.encode()).hexdigest(16)
            await cursor.execute(
                "UPDATE loan_positions SET hash = ? WHERE id = ?",
                (h, row["id"]),
            )
