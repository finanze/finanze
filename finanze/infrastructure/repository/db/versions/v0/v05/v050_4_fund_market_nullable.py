from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

DDL = """
      DROP INDEX IF EXISTS idx_fp_global_position_id;
      DROP INDEX IF EXISTS idx_fp_portfolio_id;

      CREATE TABLE fund_positions_new
      (
          id                 CHAR(36) PRIMARY KEY,
          name               TEXT                                                                       NOT NULL,
          isin               VARCHAR(12)                                                                NOT NULL,
          market             VARCHAR(50),
          shares             TEXT                                                                       NOT NULL,
          initial_investment TEXT                                                                       NOT NULL,
          average_buy_price  TEXT                                                                       NOT NULL,
          market_value       TEXT                                                                       NOT NULL,
          currency           CHAR(3)                                                                    NOT NULL,
          global_position_id CHAR(36) REFERENCES global_positions ON DELETE CASCADE ON UPDATE CASCADE NOT NULL,
          portfolio_id       CHAR(36)
              REFERENCES fund_portfolios
                  ON DELETE CASCADE ON UPDATE CASCADE
      );

      INSERT INTO fund_positions_new (
          id, name, isin, market, shares,
          initial_investment, average_buy_price, market_value,
          currency, global_position_id, portfolio_id
      )
      SELECT
          id, name, isin, market, shares,
          initial_investment, average_buy_price, market_value,
          currency, global_position_id, portfolio_id
      FROM fund_positions;

      DROP TABLE fund_positions;
      ALTER TABLE fund_positions_new RENAME TO fund_positions;

      CREATE INDEX idx_fp_global_position_id ON fund_positions (global_position_id);
      CREATE INDEX idx_fp_portfolio_id ON fund_positions (portfolio_id);
      """


class V0504(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.5.0:4_fund_market_nullable"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(DDL)
        for statement in statements:
            await cursor.execute(statement)
