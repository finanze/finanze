from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

SQL = """
      ALTER TABLE factoring_positions
          ADD COLUMN start DATETIME NOT NULL DEFAULT '';

      ALTER TABLE factoring_positions
          ADD COLUMN late_interest_rate TEXT;

      ALTER TABLE factoring_positions
          ADD COLUMN gross_late_interest_rate TEXT;

      ALTER TABLE real_estate_cf_positions
          ADD COLUMN start DATETIME NOT NULL DEFAULT '';

      ALTER TABLE real_estate_cf_positions
          ADD COLUMN extended_interest_rate TEXT;
      """

UPDATE = """
         UPDATE factoring_positions
         SET start = last_invest_date;

         UPDATE real_estate_cf_positions
         SET start = last_invest_date;
         """


class V0706RECFAndFactoringFields(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.7.0:6_add_recf_factoring_start_extended"

    def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(SQL)
        for statement in statements:
            cursor.execute(statement)

        update_statements = self.parse_block(UPDATE)
        for statement in update_statements:
            cursor.execute(statement)
