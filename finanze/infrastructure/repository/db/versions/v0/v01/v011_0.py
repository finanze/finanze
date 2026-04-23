from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

DDL = """
     CREATE TABLE virtual_data_imports
     (
         import_id          CHAR(36)     NOT NULL,
         global_position_id CHAR(36)     NOT NULL REFERENCES global_positions (id) ON DELETE CASCADE ON UPDATE CASCADE,
         source             VARCHAR(255) NOT NULL,
         date               DATETIME     NOT NULL,

         PRIMARY KEY (import_id, global_position_id)
     );

     CREATE INDEX idx_vdimports_date_import_id ON virtual_data_imports (date DESC, import_id);
     """


class V0110(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.1.1:0"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(DDL)
        for statement in statements:
            await cursor.execute(statement)
