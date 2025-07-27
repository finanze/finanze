from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

DDL = """
      ALTER TABLE loan_positions ADD COLUMN creation DATE;
      ALTER TABLE loan_positions ADD COLUMN maturity DATE;
      ALTER TABLE loan_positions ADD COLUMN unpaid TEXT;
      """


class V0401(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.4.0:1_more_loan_details"

    def upgrade(self, cursor: DBCursor):
        statements = self.parse_block(DDL)
        for statement in statements:
            cursor.execute(statement)
