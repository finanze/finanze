from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

DDL = """
      PRAGMA foreign_keys=OFF;
      
      DROP INDEX idx_fpo_global_position_id;
      ALTER TABLE fund_portfolios RENAME TO fund_portfolios_old;
      
      CREATE TABLE fund_portfolios
      (
          id                 CHAR(36) PRIMARY KEY,
          global_position_id CHAR(36) NOT NULL REFERENCES global_positions (id) ON DELETE CASCADE ON UPDATE CASCADE,
          name               TEXT        NOT NULL,
          currency           CHAR(3),
          initial_investment TEXT,
          market_value       TEXT
      );
      
      INSERT INTO fund_portfolios SELECT * FROM fund_portfolios_old;
          
      DROP TABLE fund_portfolios_old;
      
      ALTER TABLE fund_portfolios RENAME TO fund_portfolios_old;
      ALTER TABLE fund_portfolios_old RENAME TO fund_portfolios;
      
      CREATE INDEX idx_fpo_global_position_id ON fund_portfolios (global_position_id);
      
      PRAGMA foreign_keys=ON;
      """


class V0202(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.2.0:2_null_portfolio_kpis"

    def upgrade(self, cursor: DBCursor):
        statements = self.parse_block(DDL)
        for statement in statements:
            cursor.execute(statement)
