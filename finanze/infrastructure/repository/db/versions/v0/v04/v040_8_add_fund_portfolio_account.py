from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

SQL = """
      ALTER TABLE fund_portfolios
          ADD COLUMN account_id CHAR(36) DEFAULT NULL REFERENCES account_positions (id);
      """


class V0408FundPortfolioAccount(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.4.0:8_add_fund_portfolio_account"

    def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(SQL)
        for statement in statements:
            cursor.execute(statement)
