from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

DDL = """
      DROP TABLE IF EXISTS virtual_data_imports;

      CREATE TABLE virtual_data_imports
      (
          id                 CHAR(36) PRIMARY KEY,
          import_id          CHAR(36)     NOT NULL,
          global_position_id CHAR(36) REFERENCES global_positions (id) ON DELETE CASCADE ON UPDATE CASCADE,
          source             VARCHAR(255) NOT NULL,
          date               DATETIME     NOT NULL,
          feature            VARCHAR(255),
          entity_id          CHAR(36) REFERENCES entities (id) ON DELETE CASCADE ON UPDATE CASCADE
      );

      CREATE INDEX idx_vdimports_date_import_id ON virtual_data_imports (date DESC, import_id);

      CREATE INDEX idx_itxs_investment_is_real ON investment_transactions (is_real);
      """


class V0203(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.2.0:3_virtual_imports_feature"

    def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(DDL)
        for statement in statements:
            cursor.execute(statement)
