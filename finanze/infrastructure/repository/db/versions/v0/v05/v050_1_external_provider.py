from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

DDL = """
      -- We do a little trick in order to achieve the foreign_keys disable in a TX
      COMMIT TRANSACTION;
      PRAGMA foreign_keys = OFF;
      BEGIN TRANSACTION;

      CREATE TABLE entities_new
      (
          id         CHAR(36)    NOT NULL PRIMARY KEY,
          name       VARCHAR(50) NOT NULL,
          natural_id VARCHAR(50),
          type       VARCHAR(32) NOT NULL,
          origin     VARCHAR(32) NOT NULL
      );

      INSERT INTO entities_new (id, name, natural_id, type, origin)
      SELECT id,
             name,
             NULL as natural_id,
             type,
             CASE
                 WHEN id = 'ccccdddd-0000-0000-0000-000000000000' THEN 'INTERNAL'
                 WHEN is_real THEN 'NATIVE'
                 ELSE 'MANUAL'
             END as origin
      FROM entities;

      DROP TABLE entities;
      ALTER TABLE entities_new RENAME TO entities;

      PRAGMA foreign_key_check;
      COMMIT TRANSACTION;
      PRAGMA foreign_keys = ON;
      BEGIN TRANSACTION;
      -- End of trick, let the normal TX continue

      -- External entities table
      CREATE TABLE external_entities
      (
          id                   CHAR(36)    NOT NULL PRIMARY KEY,
          entity_id            CHAR(36)    NOT NULL REFERENCES entities (id) ON DELETE CASCADE ON UPDATE CASCADE,
          status               VARCHAR(32) NOT NULL,
          provider             VARCHAR(36) NOT NULL REFERENCES external_integrations (id) ON DELETE CASCADE ON UPDATE CASCADE,
          date                 TIMESTAMP   NOT NULL,
          provider_instance_id TEXT,
          payload              JSON
      );

      CREATE INDEX idx_ee_entity_id ON external_entities (entity_id);
      """

DML = """
      INSERT INTO external_integrations (id, name, type, status)
      VALUES ('GOCARDLESS', 'GoCardless', 'ENTITY_PROVIDER', 'OFF');

      -- Set BICs (natural_id) for native financial entities
      UPDATE entities SET natural_id = 'BACAESMM'
      WHERE id = 'e0000000-0000-0000-0000-000000000001'; -- MyInvestor

      UPDATE entities SET natural_id = 'UCJAES2M'
      WHERE id = 'e0000000-0000-0000-0000-000000000002'; -- Unicaja

      UPDATE entities SET natural_id = 'TRBKDEBB'
      WHERE id = 'e0000000-0000-0000-0000-000000000003'; -- Trade Republic

      UPDATE entities SET natural_id = 'INGDESMM'
      WHERE id = 'e0000000-0000-0000-0000-000000000010'; -- ING
      """


class V0501ExternalEntityProvider(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.5.0:1_external_entity_provider"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(DDL)
        for statement in statements:
            await cursor.execute(statement)

        statements = self.parse_block(DML)
        for statement in statements:
            await cursor.execute(statement)
