from domain.data_init import DatasourceInitContext
from infrastructure.repository.db.client import DBCursor
from infrastructure.repository.db.upgrader import DBVersionMigration


class V01109SplitCacheCoverage(DBVersionMigration):
    @property
    def name(self):
        return "v0.11.0:9_split_cache_coverage"

    async def upgrade(self, cursor: DBCursor, context: DatasourceInitContext):
        await cursor.execute(
            "ALTER TABLE instrument_split_checked ADD COLUMN checked_from DATE"
        )
        await cursor.execute(
            "ALTER TABLE instrument_split_checked ADD COLUMN checked_to DATE"
        )
        await cursor.execute(
            "CREATE TEMP TABLE gains_cache_products "
            "(asset_key TEXT NOT NULL, product_type TEXT NOT NULL, "
            "PRIMARY KEY (asset_key, product_type))"
        )
        await cursor.execute(
            "INSERT OR IGNORE INTO gains_cache_products (asset_key, product_type) "
            "SELECT COALESCE(NULLIF(isin, ''), NULLIF(ticker, ''), NULLIF(name, '')), "
            "'STOCK_ETF' FROM stock_positions "
            "WHERE COALESCE(NULLIF(isin, ''), NULLIF(ticker, ''), NULLIF(name, '')) IS NOT NULL"
        )
        await cursor.execute(
            "INSERT OR IGNORE INTO gains_cache_products (asset_key, product_type) "
            "SELECT COALESCE(NULLIF(isin, ''), NULLIF(name, '')), 'FUND' "
            "FROM fund_positions WHERE COALESCE(NULLIF(isin, ''), NULLIF(name, '')) IS NOT NULL"
        )
        await cursor.execute(
            "INSERT OR IGNORE INTO gains_cache_products (asset_key, product_type) "
            "SELECT CASE WHEN product_type = 'STOCK_ETF' "
            "THEN COALESCE(NULLIF(isin, ''), NULLIF(ticker, ''), NULLIF(name, '')) "
            "ELSE COALESCE(NULLIF(isin, ''), NULLIF(name, '')) END, product_type "
            "FROM investment_transactions WHERE product_type IN ('STOCK_ETF', 'FUND') "
            "AND COALESCE(NULLIF(isin, ''), NULLIF(ticker, ''), NULLIF(name, '')) IS NOT NULL"
        )
        for table_name in (
            "instrument_price_history",
            "instrument_symbol_map",
            "instrument_price_gap",
            "instrument_no_result",
        ):
            await cursor.execute(
                f"UPDATE OR IGNORE {table_name} SET instrument_key = "
                f"(SELECT product_type || ':' || {table_name}.instrument_key "
                "FROM gains_cache_products WHERE asset_key = "
                f"{table_name}.instrument_key LIMIT 1) "
                "WHERE instrument_key IN (SELECT asset_key FROM gains_cache_products "
                "GROUP BY asset_key HAVING COUNT(*) = 1)"
            )
        await cursor.execute("DROP TABLE gains_cache_products")
