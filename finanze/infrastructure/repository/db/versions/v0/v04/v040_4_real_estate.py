from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

DDL = """
      -- REAL ESTATE
      CREATE TABLE real_estate
      (
          id                     CHAR(36) PRIMARY KEY,
          name                   VARCHAR(100) NOT NULL,
          currency               CHAR(3)      NOT NULL,
          photo_url              TEXT,
          is_residence           BOOLEAN      NOT NULL,
          is_rented              BOOLEAN      NOT NULL,
          bathrooms              INTEGER,
          bedrooms               INTEGER,
          address                TEXT,
          cadastral_reference    TEXT,
          purchase_date          DATE         NOT NULL,
          purchase_price         TEXT         NOT NULL,
          purchase_expenses      JSON         NOT NULL,
          estimated_market_value TEXT         NOT NULL,
          annual_appreciation    TEXT,
          valuations             JSON         NOT NULL,
          rental_data            JSON,
          created_at             TIMESTAMP    NOT NULL,
          updated_at             TIMESTAMP
      );

      CREATE TABLE real_estate_flows
      (
          real_estate_id   CHAR(36)    NOT NULL REFERENCES real_estate (id) ON DELETE CASCADE,
          periodic_flow_id CHAR(36)    NOT NULL REFERENCES periodic_flows (id) ON DELETE CASCADE,
          flow_subtype     VARCHAR(16) NOT NULL,
          description      TEXT        NOT NULL,
          payload          JSON        NOT NULL,

          PRIMARY KEY (real_estate_id, periodic_flow_id),
          UNIQUE (periodic_flow_id)
      );

      CREATE INDEX idx_real_estate_flows_real_estate_id ON real_estate_flows (real_estate_id);
      CREATE INDEX idx_real_estate_flows_periodic_flow_id ON real_estate_flows (periodic_flow_id);

      -- PERIODIC FLOWS
      ALTER TABLE periodic_flows
          ADD COLUMN max_amount TEXT;
      """


class V0404RealEstate(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.4.0:4_real_estate"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(DDL)
        for statement in statements:
            await cursor.execute(statement)
