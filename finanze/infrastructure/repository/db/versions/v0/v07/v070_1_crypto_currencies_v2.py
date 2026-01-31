from uuid import uuid4

from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.query_mixin import QueryMixin
from infrastructure.repository.db.upgrader import DBVersionMigration

SQL_CREATE = """
             CREATE TABLE crypto_assets
             (
                 id           CHAR(36)     NOT NULL PRIMARY KEY,
                 name         VARCHAR(150) NOT NULL,
                 symbol       VARCHAR(30)  NOT NULL,
                 icon_urls    JSON,
                 external_ids JSON         NOT NULL
             );

             CREATE TABLE crypto_currency_positions
             (
                 id                 CHAR(36)     NOT NULL PRIMARY KEY,
                 global_position_id CHAR(36)     NOT NULL REFERENCES global_positions ON UPDATE CASCADE ON DELETE CASCADE,
                 wallet_id          CHAR(36)     REFERENCES crypto_wallet_connections ON UPDATE CASCADE ON DELETE SET NULL,
                 name               VARCHAR(150) NOT NULL,
                 symbol             VARCHAR(30)  NOT NULL,
                 amount             TEXT         NOT NULL,
                 type               VARCHAR(20)  NOT NULL,
                 market_value       TEXT,
                 currency           CHAR(3),
                 contract_address   TEXT,
                 crypto_asset_id    CHAR(36) REFERENCES crypto_assets ON DELETE SET NULL ON UPDATE CASCADE
             );

             CREATE INDEX idx_ccp_wallet_id ON crypto_currency_positions (wallet_id);
             CREATE INDEX idx_ccp_global_position_id ON crypto_currency_positions (global_position_id); \
             """

SQL_INSERT_CRYPTO_ASSETS = """
                           INSERT INTO crypto_assets (id, name, symbol, icon_urls, external_ids)
                           VALUES (?, 'Bitcoin', 'BTC',
                                   json_array('https://www.cryptocompare.com/media/37746251/btc.png',
                                              'https://coin-images.coingecko.com/coins/images/1/large/bitcoin.png'),
                                   json_object('COINGECKO', 'bitcoin')),
                                  (?, 'Ethereum', 'ETH',
                                   json_array('https://www.cryptocompare.com/media/37746238/eth.png',
                                              'https://coin-images.coingecko.com/coins/images/279/large/ethereum.png'),
                                   json_object('COINGECKO', 'ethereum')),
                                  (?, 'Litecoin', 'LTC',
                                   json_array('https://www.cryptocompare.com/media/37746243/ltc.png',
                                              'https://coin-images.coingecko.com/coins/images/2/large/litecoin.png'),
                                   json_object('COINGECKO', 'litecoin')),
                                  (?, 'TRON', 'TRX',
                                   json_array('https://www.cryptocompare.com/media/37746879/trx.png',
                                              'https://coin-images.coingecko.com/coins/images/1094/large/tron-logo.png'),
                                   json_object('COINGECKO', 'tron')),
                                  (?, 'Binance Coin', 'BNB',
                                   json_array('https://www.cryptocompare.com/media/40485170/bnb.png',
                                              'https://coin-images.coingecko.com/coins/images/825/large/bnb-icon2_2x.png'),
                                   json_object('COINGECKO', 'binancecoin')),
                                  (?, 'Tether', 'USDT',
                                   json_array('https://www.cryptocompare.com/media/37746338/usdt.png',
                                              'https://coin-images.coingecko.com/coins/images/325/large/Tether.png'),
                                   json_object('COINGECKO', 'tether')),
                                  (?, 'USD Coin', 'USDC',
                                   json_array('https://www.cryptocompare.com/media/34835941/usdc.png',
                                              'https://coin-images.coingecko.com/coins/images/6319/large/usdc.png'),
                                   json_object('COINGECKO', 'usd-coin')); \
                           """

SQL_REMAINING = """

                INSERT INTO crypto_currency_positions (id, global_position_id, wallet_id, name, symbol, amount,
                                                       type, market_value,
                                                       currency, crypto_asset_id)
                SELECT ccwp.id,
                       ccwp.global_position_id,
                       ccwp.wallet_connection_id,
                       ccwp.crypto,
                       ccwp.symbol,
                       ccwp.amount,
                       'NATIVE',
                       ccwp.market_value,
                       ccwp.currency,
                       NULL
                from crypto_currency_wallet_positions ccwp;

                INSERT INTO crypto_currency_positions (id, global_position_id, wallet_id, name, symbol, amount,
                                                       type, market_value,
                                                       currency, crypto_asset_id, contract_address)
                SELECT cctp.id,
                       ccwp.global_position_id,
                       ccwp.wallet_connection_id,
                       cctp.token,
                       cctp.symbol,
                       cctp.amount,
                       'TOKEN',
                       cctp.market_value,
                       cctp.currency,
                       NULL,
                       cctp.token_id
                from crypto_currency_token_positions cctp
                         join crypto_currency_wallet_positions ccwp on cctp.wallet_id = ccwp.id;

                UPDATE crypto_currency_positions
                SET crypto_asset_id = (SELECT id
                                       FROM crypto_assets
                                       WHERE symbol = crypto_currency_positions.symbol);

                UPDATE crypto_currency_positions
                SET name = (SELECT name
                            FROM crypto_assets
                            WHERE symbol = crypto_currency_positions.symbol);

                DROP INDEX idx_ccwp_global_position_id;
                DROP INDEX idx_cctp_wallet_id;
                DROP INDEX idx_cii_wallet_conn;
                DROP INDEX idx_cii_wallet_conn_type_symbol;
                DROP TABLE crypto_initial_investments;
                DROP TABLE crypto_currency_token_positions;
                DROP TABLE crypto_currency_wallet_positions; \
                """


class V0701CryptoCurrenciesV2(DBVersionMigration, QueryMixin):
    @property
    def name(self):
        return "v0.7.0:1_crypto_currencies_v2"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        statements = self.parse_block(SQL_CREATE)
        for statement in statements:
            await cursor.execute(statement)

        uuids = [str(uuid4()) for _ in range(7)]
        await cursor.execute(SQL_INSERT_CRYPTO_ASSETS, uuids)

        statements = self.parse_block(SQL_REMAINING)
        for statement in statements:
            await cursor.execute(statement)
