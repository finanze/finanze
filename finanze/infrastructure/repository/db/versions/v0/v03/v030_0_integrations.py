from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

DDL = """
      CREATE TABLE external_integrations
      (
          id     VARCHAR(36) NOT NULL PRIMARY KEY,
          name   VARCHAR(48) NOT NULL,
          type   VARCHAR(32) NOT NULL,
          status VARCHAR(32) NOT NULL
      );
      """

DML = """
      INSERT INTO external_integrations (id, name, type, status)
      VALUES ('GOOGLE_SHEETS', 'Google Sheets', 'DATA_SOURCE', 'OFF'),
             ('ETHERSCAN', 'Etherscan', 'CRYPTO_PROVIDER', 'OFF');
      """


class V0300Integrations(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.3.0:0_integrations"

    def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(DDL)
        for statement in statements:
            cursor.execute(statement)

        cursor.execute(DML)
