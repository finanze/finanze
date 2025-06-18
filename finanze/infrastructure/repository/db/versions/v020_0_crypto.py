from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

DDL = """
      ALTER TABLE financial_entities RENAME TO entities;

      ALTER TABLE entities
          ADD COLUMN type VARCHAR(32) NOT NULL DEFAULT 'FINANCIAL_INSTITUTION';

      ALTER TABLE investment_position_kpis
          ADD COLUMN currency CHAR(3) DEFAULT NULL;

      -- CRYPTOCURRENCY WALLETS
      CREATE TABLE cryptocurrency_wallets
      (
          id                 CHAR(36) PRIMARY KEY,
          global_position_id CHAR(36)    NOT NULL REFERENCES global_positions (id) ON DELETE CASCADE ON UPDATE CASCADE,
          address            TEXT        NOT NULL,
          name               TEXT        NOT NULL,
          symbol             VARCHAR(10) NOT NULL,
          amount             TEXT        NOT NULL,
          initial_investment TEXT,
          average_buy_price  TEXT,
          market_value       TEXT        NOT NULL,
          currency           CHAR(3)     NOT NULL,
          crypto             VARCHAR(32) NOT NULL
      );

      CREATE INDEX idx_ccw_global_position_id ON cryptocurrency_wallets (global_position_id);

      -- CRYPTOCURRENCY TOKENS
      CREATE TABLE cryptocurrency_tokens
      (
          id                 CHAR(36) PRIMARY KEY,
          wallet_id          CHAR(36)     NOT NULL REFERENCES cryptocurrency_wallets (id) ON DELETE CASCADE ON UPDATE CASCADE,
          token_id           VARCHAR(255) NOT NULL,
          name               TEXT         NOT NULL,
          symbol             VARCHAR(10)  NOT NULL,
          amount             TEXT         NOT NULL,
          initial_investment TEXT,
          average_buy_price  TEXT,
          market_value       TEXT         NOT NULL,
          currency           CHAR(3)      NOT NULL,
          type               VARCHAR(32)
      );

      CREATE INDEX idx_cct_wallet_id ON cryptocurrency_tokens (wallet_id);

      CREATE TABLE crypto_wallet_connections
      (
          id        CHAR(36) PRIMARY KEY,
          entity_id CHAR(36) NOT NULL REFERENCES entities (id) ON DELETE CASCADE ON UPDATE CASCADE,
          address   TEXT     NOT NULL,
          name      TEXT     NOT NULL
      );
      """

UPDATE_KPI_ENTRIES = """
                     UPDATE investment_position_kpis SET currency = 'EUR' WHERE metric <> 'WEIGHTED_INTEREST_RATE';
                     """

ADD_CRYPTO_ENTITIES = """
                      INSERT INTO entities (id, name, type, is_real)
                      VALUES ('c0000000-0000-0000-0000-000000000001', 'Bitcoin', 'CRYPTO_WALLET', TRUE),
                             ('c0000000-0000-0000-0000-000000000002', 'Ethereum', 'CRYPTO_WALLET', TRUE),
                             ('c0000000-0000-0000-0000-000000000003', 'Litecoin', 'CRYPTO_WALLET', TRUE),
                             ('c0000000-0000-0000-0000-000000000004', 'Tron', 'CRYPTO_WALLET', TRUE)
                      """


class V0200Crypto(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.2.0:0_crypto"

    def upgrade(self, cursor: DBCursor):
        statements = self.parse_block(DDL)
        for statement in statements:
            cursor.execute(statement)

        cursor.execute(UPDATE_KPI_ENTRIES)
        cursor.execute(ADD_CRYPTO_ENTITIES)
