from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

DDL = """
      -- FINANCIAL ENTITY

      CREATE TABLE financial_entities
      (
          id      CHAR(36) PRIMARY KEY,
          name    VARCHAR(50) NOT NULL,
          is_real BOOLEAN     NOT NULL
      );

      -- POSITION

      CREATE TABLE global_positions
      (
          id        CHAR(36) PRIMARY KEY,
          date      DATETIME NOT NULL,
          entity_id CHAR(36) NOT NULL REFERENCES financial_entities (id) ON DELETE CASCADE ON UPDATE CASCADE,
          is_real   BOOLEAN  NOT NULL
      );

      CREATE INDEX idx_gp_entity_id ON global_positions (entity_id);
      CREATE INDEX idx_global_positions_date ON global_positions (date DESC);

      CREATE TABLE account_positions
      (
          id                 CHAR(36) PRIMARY KEY,
          global_position_id CHAR(36) NOT NULL REFERENCES global_positions (id) ON DELETE CASCADE ON UPDATE CASCADE,
          type               VARCHAR(32) NOT NULL,
          name               TEXT,
          iban               VARCHAR(32),
          total              TEXT        NOT NULL,
          currency           CHAR(3)     NOT NULL,
          interest           TEXT,
          retained           TEXT,
          pending_transfers  TEXT
      );

      CREATE INDEX idx_ap_global_position_id ON account_positions (global_position_id);

      CREATE TABLE card_positions
      (
          id                 CHAR(36) PRIMARY KEY,
          global_position_id CHAR(36) NOT NULL REFERENCES global_positions (id) ON DELETE CASCADE ON UPDATE CASCADE,
          type               VARCHAR(32) NOT NULL,
          name               TEXT,
          currency           CHAR(3)     NOT NULL,
          ending             TEXT,
          card_limit         TEXT,
          used               TEXT,
          active             BOOLEAN     NOT NULL,
          related_account    CHAR(36) REFERENCES account_positions (id) ON DELETE CASCADE ON UPDATE CASCADE
      );

      CREATE INDEX idx_cp_global_position_id ON card_positions (global_position_id);

      CREATE TABLE loan_positions
      (
          id                    CHAR(36) PRIMARY KEY,
          global_position_id    CHAR(36) NOT NULL REFERENCES global_positions (id) ON DELETE CASCADE ON UPDATE CASCADE,
          type                  VARCHAR(32) NOT NULL,
          currency              CHAR(3)     NOT NULL,
          name                  TEXT,
          current_installment   TEXT        NOT NULL,
          interest_rate         TEXT        NOT NULL,
          loan_amount           TEXT,
          next_payment_date     DATE        NOT NULL,
          principal_outstanding TEXT        NOT NULL,
          principal_paid        TEXT        NOT NULL
      );

      CREATE INDEX idx_lp_global_position_id ON loan_positions (global_position_id);

      -- Latest investment position KPIs

      CREATE TABLE investment_position_kpis
      (
          global_position_id CHAR(36)    NOT NULL REFERENCES global_positions (id) ON DELETE CASCADE ON UPDATE CASCADE,
          entity_id          CHAR(36)    NOT NULL REFERENCES financial_entities (id) ON DELETE CASCADE ON UPDATE CASCADE,
          investment_type    VARCHAR(32) NOT NULL,
          metric             VARCHAR(64) NOT NULL,
          value              TEXT        NOT NULL,
          date               TIMESTAMP   NOT NULL,
          PRIMARY KEY (global_position_id, investment_type, metric)
      );

      CREATE INDEX idx_ikpis_global_position_id ON investment_position_kpis (global_position_id);
      CREATE INDEX idx_ikpis_entity_type_metric ON investment_position_kpis (global_position_id, investment_type, metric);

      CREATE TABLE stock_positions
      (
          id                 CHAR(36) PRIMARY KEY,
          global_position_id CHAR(36) REFERENCES global_positions (id) ON DELETE CASCADE ON UPDATE CASCADE,
          name               TEXT        NOT NULL,
          ticker             VARCHAR(16) NOT NULL,
          isin               VARCHAR(12) NOT NULL,
          market             VARCHAR(50) NOT NULL,
          shares             TEXT        NOT NULL,
          initial_investment TEXT        NOT NULL,
          average_buy_price  TEXT        NOT NULL,
          market_value       TEXT        NOT NULL,
          currency           CHAR(3)     NOT NULL,
          type               VARCHAR(32) NOT NULL,
          subtype            VARCHAR(32)
      );

      CREATE INDEX idx_sp_global_position_id ON stock_positions (global_position_id);

      CREATE TABLE fund_portfolios
      (
          id                 CHAR(36) PRIMARY KEY,
          global_position_id CHAR(36) NOT NULL REFERENCES global_positions (id) ON DELETE CASCADE ON UPDATE CASCADE,
          name               TEXT        NOT NULL,
          currency           CHAR(3)     NOT NULL,
          initial_investment TEXT        NOT NULL,
          market_value       TEXT        NOT NULL
      );
      
      CREATE INDEX idx_fpo_global_position_id ON fund_portfolios (global_position_id);

      CREATE TABLE fund_positions
      (
          id                 CHAR(36) PRIMARY KEY,
          global_position_id CHAR(36) NOT NULL REFERENCES global_positions (id) ON DELETE CASCADE ON UPDATE CASCADE,
          name               TEXT        NOT NULL,
          isin               VARCHAR(12) NOT NULL,
          market             VARCHAR(50) NOT NULL,
          shares             TEXT        NOT NULL,
          initial_investment TEXT        NOT NULL,
          average_buy_price  TEXT        NOT NULL,
          market_value       TEXT        NOT NULL,
          currency           CHAR(3)     NOT NULL,
          portfolio_id       CHAR(36) REFERENCES fund_portfolios (id) ON DELETE CASCADE ON UPDATE CASCADE
      );

      CREATE INDEX idx_fp_global_position_id ON fund_positions (global_position_id);
      CREATE INDEX idx_fp_portfolio_id ON fund_positions (portfolio_id);

      CREATE TABLE factoring_positions
      (
          id                  CHAR(36) PRIMARY KEY,
          global_position_id  CHAR(36) NOT NULL REFERENCES global_positions (id) ON DELETE CASCADE ON UPDATE CASCADE,
          name                TEXT        NOT NULL,
          amount              TEXT        NOT NULL,
          currency            CHAR(3)     NOT NULL,
          interest_rate       TEXT        NOT NULL,
          gross_interest_rate TEXT        NOT NULL,
          last_invest_date    DATETIME    NOT NULL,
          maturity            DATE        NOT NULL,
          type                VARCHAR(32) NOT NULL,
          state               VARCHAR(32) NOT NULL
      );

      CREATE INDEX idx_facp_global_position_id ON factoring_positions (global_position_id);

      CREATE TABLE real_state_cf_positions
      (
          id                 CHAR(36) PRIMARY KEY,
          global_position_id CHAR(36) NOT NULL REFERENCES global_positions (id) ON DELETE CASCADE ON UPDATE CASCADE,
          name               TEXT        NOT NULL,
          amount             TEXT        NOT NULL,
          pending_amount     TEXT        NOT NULL,
          currency           CHAR(3)     NOT NULL,
          interest_rate      TEXT        NOT NULL,
          last_invest_date   DATETIME,
          maturity           DATE        NOT NULL,
          type               VARCHAR(32) NOT NULL,
          business_type      VARCHAR(32) NOT NULL,
          state              VARCHAR(32) NOT NULL,
          extended_maturity  DATE
      );

      CREATE INDEX idx_rscfp_global_position_id ON real_state_cf_positions (global_position_id);

      CREATE TABLE deposit_positions
      (
          id                 CHAR(36) PRIMARY KEY,
          global_position_id CHAR(36) NOT NULL REFERENCES global_positions (id) ON DELETE CASCADE ON UPDATE CASCADE,
          name               TEXT     NOT NULL,
          amount             TEXT     NOT NULL,
          currency           CHAR(3)  NOT NULL,
          expected_interests TEXT     NOT NULL,
          interest_rate      TEXT     NOT NULL,
          creation           DATETIME NOT NULL,
          maturity           DATE     NOT NULL
      );

      CREATE INDEX idx_dp_global_position_id ON deposit_positions (global_position_id);

      CREATE TABLE crowdlending_positions
      (
          id                 CHAR(36) PRIMARY KEY,
          global_position_id CHAR(36) NOT NULL REFERENCES global_positions (id) ON DELETE CASCADE ON UPDATE CASCADE,
          currency           CHAR(3) NOT NULL,
          distribution       JSON    NOT NULL
      );

      CREATE INDEX idx_clp_global_position_id ON crowdlending_positions (global_position_id);

      -- CONTRIBUTIONS

      CREATE TABLE periodic_contributions
      (
          id          CHAR(36)    NOT NULL PRIMARY KEY,
          entity_id   CHAR(36)    NOT NULL REFERENCES financial_entities (id) ON DELETE CASCADE ON UPDATE CASCADE,
          target      TEXT        NOT NULL,
          target_type VARCHAR(32) NOT NULL,
          alias       VARCHAR(100),
          amount      TEXT        NOT NULL,
          currency    CHAR(3)     NOT NULL,
          since       DATE        NOT NULL,
          until       DATE,
          frequency   VARCHAR(32) NOT NULL,
          active      BOOLEAN     NOT NULL,
          is_real     BOOLEAN     NOT NULL,
          created_at  TIMESTAMP   NOT NULL
      );

      CREATE INDEX idx_pcont_entity_target ON periodic_contributions (entity_id, target);

      -- TRANSACTIONS

      CREATE TABLE investment_transactions
      (
          id           CHAR(36)    NOT NULL PRIMARY KEY,
          ref          TEXT        NOT NULL,
          name         TEXT        NOT NULL,
          amount       TEXT        NOT NULL,
          currency     CHAR(3)     NOT NULL,
          type         VARCHAR(32) NOT NULL,
          date         DATETIME    NOT NULL,
          entity_id    CHAR(36)    NOT NULL REFERENCES financial_entities (id) ON DELETE CASCADE ON UPDATE CASCADE,
          is_real      BOOLEAN     NOT NULL,
          created_at   DATETIME    NOT NULL,
          product_type VARCHAR(32),

          isin         VARCHAR(12) DEFAULT NULL,
          market       VARCHAR(32) DEFAULT NULL,
          order_date   DATETIME    DEFAULT NULL,
          linked_tx    CHAR(36)    DEFAULT NULL,

          net_amount   TEXT        DEFAULT NULL,
          shares       TEXT        DEFAULT NULL,
          price        TEXT        DEFAULT NULL,
          fees         TEXT        DEFAULT NULL,
          retentions   TEXT        DEFAULT NULL,
          ticker       VARCHAR(16) DEFAULT NULL,

          interests    TEXT        DEFAULT NULL
      );

      CREATE INDEX idx_itxs_investment_entity_id ON investment_transactions (entity_id);
      CREATE INDEX idx_itxs_investment_date ON investment_transactions (date DESC);
      CREATE INDEX idx_itxs_investment_isin ON investment_transactions (isin);
      CREATE INDEX idx_itxs_investment_product_type ON investment_transactions (product_type);


      CREATE TABLE account_transactions
      (
          id            CHAR(36)    NOT NULL PRIMARY KEY,
          ref           TEXT        NOT NULL,
          name          TEXT        NOT NULL,
          amount        TEXT        NOT NULL,
          currency      CHAR(3)     NOT NULL,
          type          VARCHAR(32) NOT NULL,
          date          DATETIME    NOT NULL,
          entity_id     CHAR(36)    NOT NULL REFERENCES financial_entities (id) ON DELETE CASCADE ON UPDATE CASCADE,
          is_real       BOOLEAN     NOT NULL,
          created_at    DATETIME    NOT NULL,

          interest_rate TEXT DEFAULT NULL,
          avg_balance   TEXT DEFAULT NULL,
          fees          TEXT DEFAULT NULL,
          retentions    TEXT DEFAULT NULL
      );

      CREATE INDEX idx_account_entity_id ON account_transactions (entity_id);
      CREATE INDEX idx_account_date ON account_transactions (date DESC);
      CREATE INDEX idx_account_type ON account_transactions (type);


      CREATE TABLE investment_historic
      (
          id                  CHAR(36)    NOT NULL PRIMARY KEY,
          name                TEXT        NOT NULL,
          invested            TEXT        NOT NULL,
          repaid              TEXT,
          returned            TEXT,
          currency            CHAR(3)     NOT NULL,
          last_invest_date    DATETIME    NOT NULL,
          last_tx_date        DATETIME    NOT NULL,
          effective_maturity  DATE,
          net_return          TEXT,
          fees                TEXT,
          retentions          TEXT,
          interests           TEXT,
          state               VARCHAR(32),
          entity_id           CHAR(36)    NOT NULL REFERENCES financial_entities (id) ON DELETE CASCADE ON UPDATE CASCADE,
          product_type        VARCHAR(32) NOT NULL,
          created_at          DATETIME    NOT NULL,

          gross_interest_rate TEXT,
          interest_rate       TEXT,
          maturity            DATE,
          extended_maturity   DATE,
          type                VARCHAR(32),
          business_type       VARCHAR(32)
      );

      CREATE INDEX idx_ihist_entity_id ON investment_historic (entity_id);
      CREATE INDEX idx_ihist_product_type ON investment_historic (product_type);

      CREATE TABLE investment_historic_txs
      (
          tx_id             CHAR(36) NOT NULL PRIMARY KEY,
          historic_entry_id CHAR(36) NOT NULL,

          FOREIGN KEY (historic_entry_id) REFERENCES investment_historic (id) ON DELETE CASCADE ON UPDATE CASCADE,
          FOREIGN KEY (tx_id) REFERENCES investment_transactions (id) ON DELETE CASCADE ON UPDATE CASCADE
      );

      CREATE INDEX idx_ihist_txs_historic_entry_id ON investment_historic_txs (historic_entry_id);

      CREATE TABLE entity_credentials
      (
          entity_id    CHAR(36)  NOT NULL PRIMARY KEY REFERENCES financial_entities (id) ON DELETE CASCADE ON UPDATE CASCADE,
          credentials  JSON      NOT NULL,
          created_at   TIMESTAMP NOT NULL,
          last_used_at TIMESTAMP DEFAULT NULL,
          expiration   TIMESTAMP DEFAULT NULL
      );

      CREATE TABLE entity_sessions
      (
          entity_id  CHAR(36)  NOT NULL PRIMARY KEY REFERENCES financial_entities (id) ON DELETE CASCADE ON UPDATE CASCADE,
          created_at TIMESTAMP NOT NULL,
          expiration TIMESTAMP,
          payload    JSON      NOT NULL
      );
      """

INSERT_FINANCIAL_ENTITIES = """
                            INSERT INTO financial_entities (id, name, is_real)
                            VALUES ('e0000000-0000-0000-0000-000000000001', 'MyInvestor', TRUE),
                                   ('e0000000-0000-0000-0000-000000000002', 'Unicaja', TRUE),
                                   ('e0000000-0000-0000-0000-000000000003', 'Trade Republic', TRUE),
                                   ('e0000000-0000-0000-0000-000000000004', 'Urbanitae', TRUE),
                                   ('e0000000-0000-0000-0000-000000000005', 'Wecity', TRUE),
                                   ('e0000000-0000-0000-0000-000000000006', 'SEGO', TRUE),
                                   ('e0000000-0000-0000-0000-000000000007', 'Mintos', TRUE),
                                   ('e0000000-0000-0000-0000-000000000008', 'Freedom24', TRUE),
                                   ('e0000000-0000-0000-0000-000000000009', 'Indexa Capital', TRUE);
                            """


class V0Genesis(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0 Genesis"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(DDL)
        for statement in statements:
            await cursor.execute(statement)

        await cursor.execute(INSERT_FINANCIAL_ENTITIES)
