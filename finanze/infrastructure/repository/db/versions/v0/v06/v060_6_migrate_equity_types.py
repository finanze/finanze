from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.upgrader import DBVersionMigration

UPDATE_RV = """
            UPDATE stock_positions
            SET type = 'STOCK'
            WHERE type = 'RV';
            """

UPDATE_ETF = """
             UPDATE stock_positions
             SET type = 'ETF'
             WHERE type NOT IN ('STOCK', 'ETF');
             """


class V0606(DBVersionMigration):
    @property
    def name(self):
        return "v0.6.0:6_migrate_equity_types"

    def upgrade(self, cursor: DBCursor):
        cursor.execute(UPDATE_RV)
        cursor.execute(UPDATE_ETF)
