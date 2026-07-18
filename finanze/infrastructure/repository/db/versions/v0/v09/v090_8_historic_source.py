from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

DDL = """
      ALTER TABLE investment_historic ADD COLUMN source VARCHAR(32) NOT NULL DEFAULT 'REAL';
      ALTER TABLE investment_historic ADD COLUMN manual_key CHAR(36);

      CREATE INDEX idx_ihist_manual_key ON investment_historic (manual_key);
      """


class V0908HistoricSource(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.9.0:8_historic_source"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        for statement in self.parse_block(DDL):
            await cursor.execute(statement)
