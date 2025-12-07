from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

REMOVE_KPIS = """
              ALTER TABLE crowdlending_positions
                  ADD COLUMN total TEXT NOT NULL DEFAULT '0';
              ALTER TABLE crowdlending_positions
                  ADD COLUMN weighted_interest_rate TEXT NOT NULL DEFAULT '0';

              DROP TABLE IF EXISTS investment_position_kpis;
              """

DDL = """
      ALTER TABLE financial_entities RENAME TO entities;

      ALTER TABLE entities
          ADD COLUMN type VARCHAR(32) NOT NULL DEFAULT 'FINANCIAL_INSTITUTION';

      -- CRYPTOCURRENCY WALLET POSITIONS
      CREATE TABLE crypto_currency_wallet_positions
      (
          id                   CHAR(36) PRIMARY KEY,
          global_position_id   CHAR(36)    NOT NULL REFERENCES global_positions (id) ON DELETE CASCADE ON UPDATE CASCADE,
          wallet_connection_id CHAR(36)    NOT NULL REFERENCES crypto_wallet_connections (id) ON DELETE CASCADE ON UPDATE CASCADE,
          symbol               VARCHAR(10) NOT NULL,
          amount               TEXT        NOT NULL,
          initial_investment   TEXT,
          average_buy_price    TEXT,
          market_value         TEXT        NOT NULL,
          currency             CHAR(3)     NOT NULL,
          crypto               VARCHAR(32) NOT NULL
      );

      CREATE INDEX idx_ccwp_global_position_id ON crypto_currency_wallet_positions (global_position_id);

      -- CRYPTOCURRENCY TOKEN POSITIONS
      CREATE TABLE crypto_currency_token_positions
      (
          id                 CHAR(36) PRIMARY KEY,
          wallet_id          CHAR(36)     NOT NULL REFERENCES crypto_currency_wallet_positions (id) ON DELETE CASCADE ON UPDATE CASCADE,
          token_id           VARCHAR(255) NOT NULL,
          name               TEXT         NOT NULL,
          symbol             VARCHAR(10)  NOT NULL,
          token              TEXT         NOT NULL,
          amount             TEXT         NOT NULL,
          initial_investment TEXT,
          average_buy_price  TEXT,
          market_value       TEXT         NOT NULL,
          currency           CHAR(3)      NOT NULL,
          type               VARCHAR(32)
      );

      CREATE INDEX idx_cctp_wallet_id ON crypto_currency_token_positions (wallet_id);

      CREATE TABLE crypto_wallet_connections
      (
          id         CHAR(36) PRIMARY KEY,
          entity_id  CHAR(36)  NOT NULL REFERENCES entities (id) ON DELETE CASCADE ON UPDATE CASCADE,
          address    TEXT      NOT NULL,
          name       TEXT      NOT NULL,
          created_at TIMESTAMP NOT NULL
      );

      CREATE INDEX idx_cwc_entity_id ON crypto_wallet_connections (entity_id);
      CREATE INDEX idx_cwc_address ON crypto_wallet_connections (address);
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

    def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(REMOVE_KPIS)
        for statement in statements:
            cursor.execute(statement)

        statements = self.parse_block(DDL)
        for statement in statements:
            cursor.execute(statement)

        cursor.execute(ADD_CRYPTO_ENTITIES)
