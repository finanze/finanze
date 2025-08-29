from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

DDL = """
      ALTER TABLE loan_positions ADD COLUMN interest_type VARCHAR(16);
      ALTER TABLE loan_positions ADD COLUMN euribor_rate TEXT;
      ALTER TABLE loan_positions ADD COLUMN fixed_years INTEGER;
      """


class V0402(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.4.0:2_var_mixed_loans"

    def upgrade(self, cursor: DBCursor):
        statements = self.parse_block(DDL)
        for statement in statements:
            cursor.execute(statement)
