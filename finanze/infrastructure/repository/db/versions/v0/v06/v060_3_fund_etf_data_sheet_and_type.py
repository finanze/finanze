from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

SQL = """
      ALTER TABLE fund_positions
          ADD COLUMN info_sheet_url TEXT;
      ALTER TABLE fund_positions
          ADD COLUMN type           VARCHAR(50);

      UPDATE fund_positions
      SET type = 'MUTUAL_FUND';

      ALTER TABLE stock_positions
          ADD COLUMN info_sheet_url TEXT;
      """


class V0603FundETFFields(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.6.0:3_fund_etf_data_sheet_and_type"

    def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(SQL)
        for statement in statements:
            cursor.execute(statement)
