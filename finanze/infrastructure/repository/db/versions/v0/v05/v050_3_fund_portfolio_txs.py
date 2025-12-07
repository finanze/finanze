from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

DDL = """
      ALTER TABLE investment_transactions
          ADD COLUMN iban VARCHAR(50);
      ALTER TABLE investment_transactions
          ADD COLUMN portfolio_name VARCHAR(255);
      """


class V0503FundPortfolioTxs(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.5.0:3_fund_portfolio_txs"

    def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(DDL)
        for statement in statements:
            cursor.execute(statement)
