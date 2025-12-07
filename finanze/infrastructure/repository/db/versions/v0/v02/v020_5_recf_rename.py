from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

DDL = """
      DROP INDEX idx_rscfp_global_position_id;
          
      ALTER TABLE real_state_cf_positions RENAME TO real_estate_cf_positions;

      CREATE INDEX idx_recfp_global_position_id ON real_estate_cf_positions (global_position_id);
      """

DML = """
      UPDATE investment_transactions
      SET product_type = 'REAL_ESTATE_CF'
      WHERE product_type = 'REAL_STATE_CF';
      """


class V0205(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.2.0:5_recf_rename"

    def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(DDL)
        for statement in statements:
            cursor.execute(statement)

        cursor.execute(DML)
