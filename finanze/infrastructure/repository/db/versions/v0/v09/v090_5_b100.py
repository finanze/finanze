from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

SQL = """
      INSERT OR IGNORE INTO entities (id, name, natural_id, type, origin)
      VALUES ('e0000000-0000-0000-0000-000000000014', 'B100', 'CAGLESMM100', 'FINANCIAL_INSTITUTION', 'NATIVE');

      INSERT INTO public_keychain (key, value, algo, version, updated_at)
      VALUES ('b2cc24f3d85a4ae5', '79ms2anYrdnZwqvY3d_C26rY2sLW1t6pwtrY397YrN7Z19jbre8ae9hJc0g', 1, 1, strftime('%Y-%m-%dT%H:%M:%S+00:00', 'now'));
      """


class V0905B100(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.9.0:5_b100"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        for statement in self.parse_block(SQL):
            await cursor.execute(statement)
