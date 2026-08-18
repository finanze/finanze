from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

TARGET_ISIN = "XF000BTC0017"

SQL = f"""
      INSERT INTO crypto_currency_positions (id, global_position_id, wallet_id, name, symbol,
                                             amount, type, market_value, currency,
                                             contract_address, crypto_asset_id)
      SELECT s.id,
             s.global_position_id,
             NULL,
             s.name,
             s.ticker,
             s.shares,
             'NATIVE',
             s.market_value,
             s.currency,
             NULL,
             (SELECT a.id FROM crypto_assets a WHERE a.symbol = s.ticker LIMIT 1)
      FROM stock_positions s
      WHERE s.isin = '{TARGET_ISIN}'
        AND s.subtype = 'CRYPTO'
        AND NOT EXISTS (SELECT 1
                        FROM crypto_currency_positions c
                        WHERE c.global_position_id = s.global_position_id
                          AND c.symbol = s.ticker);

      INSERT INTO crypto_currency_initial_investments (id, crypto_currency_position, currency,
                                                       initial_investment, average_buy_price)
      SELECT lower(hex(randomblob(4)) || '-' || hex(randomblob(2)) || '-4' || substr(hex(randomblob(2)),2) || '-' || substr('89ab', abs(random()) % 4 + 1, 1) || substr(hex(randomblob(2)),2) || '-' || hex(randomblob(6))),
             s.id,
             s.currency,
             s.initial_investment,
             s.average_buy_price
      FROM stock_positions s
      WHERE s.isin = '{TARGET_ISIN}'
        AND s.subtype = 'CRYPTO'
        AND EXISTS (SELECT 1 FROM crypto_currency_positions c WHERE c.id = s.id);

      DELETE FROM stock_positions
      WHERE isin = '{TARGET_ISIN}'
        AND subtype = 'CRYPTO'
        AND id IN (SELECT id FROM crypto_currency_positions);
      """


class V01004CryptoEtpToCryptoPositions(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.10.0:4_crypto_etp_to_crypto_positions"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(SQL)
        for statement in statements:
            await cursor.execute(statement)
