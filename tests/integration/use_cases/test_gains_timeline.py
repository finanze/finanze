import sqlite3
from datetime import date, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio

from application.use_cases.get_gains_timeline import GetGainsTimelineImpl
from domain.commodity import CommodityType, WeightUnit
from domain.dezimal import Dezimal
from domain.exchange_rate import HistoricMetalRates
from domain.gains_timeline import (
    GainsAssetFilter,
    GainsBasis,
    GainsCalculationMode,
    GainsMethod,
    GainsQuality,
    GainsTimelineQuery,
)
from domain.global_position import EquityType, ProductType
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.gains_timeline.gains_timeline_repository import (
    GainsTimelineSQLRepository,
)

_SCHEMA = """
    CREATE TABLE global_positions (
        id CHAR(36) PRIMARY KEY,
        entity_id CHAR(36) NOT NULL,
        date DATETIME NOT NULL,
        source VARCHAR(255) NOT NULL,
        entity_account_id CHAR(36)
    );
    CREATE TABLE entity_accounts (
        id CHAR(36) PRIMARY KEY,
        deleted_at TIMESTAMP
    );
    CREATE TABLE virtual_data_imports (
        id CHAR(36) PRIMARY KEY,
        import_id CHAR(36) NOT NULL,
        global_position_id CHAR(36),
        source VARCHAR(255) NOT NULL,
        date TIMESTAMP NOT NULL,
        feature VARCHAR(255),
        entity_id CHAR(36)
    );
    CREATE TABLE stock_positions (
        id CHAR(36) PRIMARY KEY, global_position_id CHAR(36), name TEXT,
        ticker TEXT, isin TEXT, currency CHAR(3), market_value TEXT,
        shares TEXT, initial_investment TEXT, type TEXT
    );
    CREATE TABLE fund_portfolios (
        id CHAR(36) PRIMARY KEY, global_position_id CHAR(36), name TEXT
    );
    CREATE TABLE fund_positions (
        id CHAR(36) PRIMARY KEY, global_position_id CHAR(36), name TEXT,
        isin TEXT, currency CHAR(3), market_value TEXT, shares TEXT,
        initial_investment TEXT, portfolio_id CHAR(36)
    );
    CREATE TABLE crypto_currency_positions (
        id CHAR(36) PRIMARY KEY, global_position_id CHAR(36), name TEXT,
        symbol TEXT, amount TEXT, type TEXT, market_value TEXT, currency CHAR(3),
        contract_address TEXT, wallet_id CHAR(36)
    );
    CREATE TABLE crypto_currency_initial_investments (
        id CHAR(36) PRIMARY KEY, crypto_currency_position CHAR(36), currency CHAR(3),
        initial_investment TEXT, average_buy_price TEXT
    );
    CREATE TABLE commodity_positions (
        id CHAR(36) PRIMARY KEY, global_position_id CHAR(36), name TEXT, type TEXT,
        currency CHAR(3), market_value TEXT, amount TEXT, unit TEXT,
        initial_investment TEXT
    );
    CREATE TABLE deposit_positions (
        id CHAR(36) PRIMARY KEY, global_position_id CHAR(36), name TEXT,
        currency CHAR(3), amount TEXT, interest_rate TEXT, creation DATETIME,
        maturity DATE
    );
    CREATE TABLE factoring_positions (
        id CHAR(36) PRIMARY KEY, global_position_id CHAR(36), name TEXT,
        currency CHAR(3), amount TEXT, interest_rate TEXT, start DATETIME,
        maturity DATE, late_interest_rate TEXT
    );
    CREATE TABLE real_estate_cf_positions (
        id CHAR(36) PRIMARY KEY, global_position_id CHAR(36), name TEXT,
        currency CHAR(3), pending_amount TEXT, interest_rate TEXT, start DATETIME,
        maturity DATE, extended_maturity DATE, extended_interest_rate TEXT
    );
    CREATE TABLE investment_transactions (
        id CHAR(36) PRIMARY KEY, ref TEXT, entity_id CHAR(36),
        entity_account_id CHAR(36), source TEXT, product_type TEXT, type TEXT,
        date DATETIME, amount TEXT, currency CHAR(3), shares TEXT,
        net_amount TEXT, fees TEXT, retentions TEXT, isin TEXT, ticker TEXT,
        asset_contract_address TEXT, name TEXT, portfolio_name TEXT,
        product_subtype TEXT
    );
    CREATE TABLE investment_historic (
        id CHAR(36) PRIMARY KEY, entity_id CHAR(36), entity_account_id CHAR(36),
        source TEXT, product_type TEXT, name TEXT, effective_maturity DATETIME,
        last_tx_date DATETIME, currency CHAR(3), returned TEXT, repaid TEXT,
        interests TEXT, fees TEXT, retentions TEXT, state TEXT
    );
    CREATE TABLE investment_historic_txs (
        tx_id CHAR(36), historic_entry_id CHAR(36)
    );
    CREATE TABLE sys_config (key TEXT PRIMARY KEY, value TEXT);
"""


def _insert_position(conn, entity_id, day):
    position_id = str(uuid4())
    conn.execute(
        "INSERT INTO global_positions (id, entity_id, date, source, entity_account_id) "
        "VALUES (?, ?, ?, 'REAL', NULL)",
        (position_id, str(entity_id), f"{day}T12:00:00"),
    )
    return position_id


@pytest_asyncio.fixture
async def setup():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    repository = GainsTimelineSQLRepository(DBClient(conn))
    yield repository, conn
    conn.close()


def _use_case(repository, metal=None):
    exchange = AsyncMock()
    exchange.get.return_value = {}
    entity = AsyncMock()
    entity.get_disabled_entities.return_value = []
    entity.get_all.return_value = []
    if metal is None:
        metal = AsyncMock()
        metal.get_partial_historic_rates.return_value = None
    return GetGainsTimelineImpl(repository, exchange, entity, metal)


class TestGainsTimelineRepositoryIntegration:
    @pytest.mark.asyncio
    async def test_calculates_crypto_gain_from_repository_snapshots_and_flow(
        self, setup
    ):
        repository, conn = setup
        entity_id = uuid4()
        first_position = _insert_position(conn, entity_id, "2025-01-01")
        second_position = _insert_position(conn, entity_id, "2025-01-02")
        conn.execute(
            "INSERT INTO crypto_currency_positions "
            "(id, global_position_id, name, symbol, amount, type, market_value, currency, contract_address) "
            "VALUES (?, ?, 'Bitcoin', 'BTC', '1', 'COIN', '100', 'EUR', NULL)",
            (str(uuid4()), first_position),
        )
        conn.execute(
            "INSERT INTO crypto_currency_positions "
            "(id, global_position_id, name, symbol, amount, type, market_value, currency, contract_address) "
            "VALUES (?, ?, 'Bitcoin', 'BTC', '2', 'COIN', '250', 'EUR', NULL)",
            (str(uuid4()), second_position),
        )
        conn.execute(
            "INSERT INTO investment_transactions "
            "(id, ref, entity_id, entity_account_id, source, product_type, type, date, amount, currency, shares, net_amount, fees, retentions, isin, ticker, asset_contract_address, name) "
            "VALUES (?, 'buy-btc', ?, NULL, 'REAL', 'CRYPTO', 'BUY', ?, '125', 'EUR', '1', '120', '5', '0', NULL, 'BTC', NULL, 'Bitcoin')",
            (str(uuid4()), str(entity_id), "2025-01-02T12:00:00"),
        )
        conn.execute(
            "INSERT INTO sys_config (key, value) VALUES ('last_update', 'version-1')"
        )
        conn.commit()

        result = await _use_case(repository).execute(
            GainsTimelineQuery(
                assets=[GainsAssetFilter(product_type=ProductType.CRYPTO)],
                entities=[entity_id],
            )
        )

        metrics = result.points[-1].metrics
        assert metrics.value == Dezimal(250)
        assert metrics.net_contributions == Dezimal(230)
        assert metrics.gain == Dezimal(20)
        assert metrics.period_return == Dezimal("0.086956521739130434782608696")
        assert metrics.index == Dezimal("108.6956521739130434782608696")
        assert await repository.get_data_version() == "version-1"

    @pytest.mark.asyncio
    async def test_snapshots_mode_uses_stored_cost_basis_without_flows(self, setup):
        repository, conn = setup
        entity_id = uuid4()
        first_position = _insert_position(conn, entity_id, "2025-01-01")
        second_position = _insert_position(conn, entity_id, "2025-01-02")
        first_crypto_id = str(uuid4())
        second_crypto_id = str(uuid4())
        conn.execute(
            "INSERT INTO crypto_currency_positions "
            "(id, global_position_id, name, symbol, amount, type, market_value, currency, contract_address) "
            "VALUES (?, ?, 'Bitcoin', 'BTC', '1', 'COIN', '100', 'EUR', NULL)",
            (first_crypto_id, first_position),
        )
        conn.execute(
            "INSERT INTO crypto_currency_positions "
            "(id, global_position_id, name, symbol, amount, type, market_value, currency, contract_address) "
            "VALUES (?, ?, 'Bitcoin', 'BTC', '1', 'COIN', '130', 'EUR', NULL)",
            (second_crypto_id, second_position),
        )
        for crypto_id in (first_crypto_id, second_crypto_id):
            conn.execute(
                "INSERT INTO crypto_currency_initial_investments "
                "(id, crypto_currency_position, currency, initial_investment, average_buy_price) "
                "VALUES (?, ?, 'EUR', '100', '100')",
                (str(uuid4()), crypto_id),
            )
        conn.execute(
            "INSERT INTO investment_transactions "
            "(id, ref, entity_id, entity_account_id, source, product_type, type, date, amount, currency, shares, net_amount, fees, retentions, isin, ticker, asset_contract_address, name) "
            "VALUES (?, 'buy-btc', ?, NULL, 'REAL', 'CRYPTO', 'BUY', ?, '100', 'EUR', '1', '100', '0', '0', NULL, 'BTC', NULL, 'Bitcoin')",
            (str(uuid4()), str(entity_id), "2025-01-01T12:00:00"),
        )
        conn.execute(
            "INSERT INTO sys_config (key, value) VALUES ('last_update', 'version-1')"
        )
        conn.commit()

        result = await _use_case(repository).execute(
            GainsTimelineQuery(
                assets=[GainsAssetFilter(product_type=ProductType.CRYPTO)],
                entities=[entity_id],
                calculation_mode=GainsCalculationMode.SNAPSHOTS,
            )
        )

        assert result.method == GainsMethod.SNAPSHOT_BOOK_BASIS
        assert result.basis == GainsBasis.BOOK_BASIS
        assert result.quality == GainsQuality.COMPLETE
        assert [point.date for point in result.points] == [
            date(2025, 1, 1),
            date(2025, 1, 2),
        ]
        metrics = result.points[-1].metrics
        assert metrics.value == Dezimal(130)
        assert metrics.cost_basis == Dezimal(100)
        assert metrics.net_contributions == Dezimal(100)
        assert metrics.gain == Dezimal(30)
        assert metrics.period_return is None
        assert metrics.index is None

    @pytest.mark.asyncio
    async def test_replays_transactions_without_any_position_snapshots(self, setup):
        repository, conn = setup
        entity_id = uuid4()
        conn.execute(
            "INSERT INTO investment_transactions "
            "(id, ref, entity_id, entity_account_id, source, product_type, type, date, amount, currency, shares, net_amount, fees, retentions, isin, ticker, asset_contract_address, name) "
            "VALUES (?, 'buy-btc', ?, NULL, 'REAL', 'CRYPTO', 'BUY', ?, '100', 'EUR', '1', '100', '0', '0', NULL, 'BTC', NULL, 'Bitcoin')",
            (str(uuid4()), str(entity_id), "2024-01-01T12:00:00"),
        )
        conn.execute(
            "INSERT INTO investment_transactions "
            "(id, ref, entity_id, entity_account_id, source, product_type, type, date, amount, currency, shares, net_amount, fees, retentions, isin, ticker, asset_contract_address, name) "
            "VALUES (?, 'sell-btc', ?, NULL, 'REAL', 'CRYPTO', 'SELL', ?, '120', 'EUR', '1', '120', '0', '0', NULL, 'BTC', NULL, 'Bitcoin')",
            (str(uuid4()), str(entity_id), "2024-06-01T12:00:00"),
        )
        conn.execute(
            "INSERT INTO sys_config (key, value) VALUES ('last_update', 'version-1')"
        )
        conn.commit()

        result = await _use_case(repository).execute(
            GainsTimelineQuery(
                assets=[GainsAssetFilter(product_type=ProductType.CRYPTO)],
                entities=[entity_id],
            )
        )

        assert result.points[0].date == date(2024, 1, 1)
        assert result.points[-1].date == date.today() - timedelta(days=1)
        by_day = {point.date: point.metrics for point in result.points}
        assert by_day[date(2024, 1, 1)].value == Dezimal(100)
        assert by_day[date(2024, 1, 1)].gain == Dezimal(0)
        assert by_day[date(2024, 6, 1)].value == Dezimal(0)
        assert by_day[date(2024, 6, 1)].net_contributions == Dezimal(-20)
        assert by_day[date(2024, 6, 1)].gain == Dezimal(20)
        assert by_day[date(2024, 6, 2)].value == Dezimal(0)
        assert by_day[date(2024, 6, 2)].gain == Dezimal(20)
        assert result.quality == GainsQuality.ESTIMATED

    @pytest.mark.asyncio
    async def test_bounded_range_loads_latest_pre_range_snapshot(self, setup):
        repository, conn = setup
        entity_id = uuid4()
        old_position = _insert_position(conn, entity_id, "2024-01-01")
        in_range_position = _insert_position(conn, entity_id, "2025-06-01")
        conn.execute(
            "INSERT INTO crypto_currency_positions "
            "(id, global_position_id, name, symbol, amount, type, market_value, currency, contract_address) "
            "VALUES (?, ?, 'Bitcoin', 'BTC', '1', 'COIN', '100', 'EUR', NULL)",
            (str(uuid4()), old_position),
        )
        conn.execute(
            "INSERT INTO crypto_currency_positions "
            "(id, global_position_id, name, symbol, amount, type, market_value, currency, contract_address) "
            "VALUES (?, ?, 'Bitcoin', 'BTC', '1', 'COIN', '130', 'EUR', NULL)",
            (str(uuid4()), in_range_position),
        )
        conn.execute(
            "INSERT INTO sys_config (key, value) VALUES ('last_update', 'version-1')"
        )
        conn.commit()

        result = await _use_case(repository).execute(
            GainsTimelineQuery(
                assets=[GainsAssetFilter(product_type=ProductType.CRYPTO)],
                entities=[entity_id],
                from_date=date(2025, 1, 1),
            )
        )

        assert result.points[0].date == date(2025, 1, 1)
        assert result.points[-1].date == date(2025, 6, 1)
        by_day = {point.date: point.metrics for point in result.points}
        assert by_day[date(2025, 1, 1)].value == Dezimal(100)
        assert by_day[date(2025, 1, 1)].gain == Dezimal(0)
        assert by_day[date(2025, 6, 1)].value == Dezimal(130)
        assert by_day[date(2025, 6, 1)].gain == Dezimal(30)
        assert result.opening_value == Dezimal(100)

    @pytest.mark.asyncio
    async def test_scopes_crypto_snapshots_to_wallet_and_excludes_unassigned_flows(
        self, setup
    ):
        repository, conn = setup
        entity_id = uuid4()
        selected_wallet_id = uuid4()
        other_wallet_id = uuid4()
        position_id = _insert_position(conn, entity_id, "2025-01-01")
        for wallet_id, symbol, amount, market_value in (
            (selected_wallet_id, "BTC", "1", "100"),
            (other_wallet_id, "ETH", "2", "200"),
        ):
            conn.execute(
                "INSERT INTO crypto_currency_positions "
                "(id, global_position_id, name, symbol, amount, type, market_value, currency, contract_address, wallet_id) "
                "VALUES (?, ?, ?, ?, ?, 'COIN', ?, 'EUR', NULL, ?)",
                (
                    str(uuid4()),
                    position_id,
                    symbol,
                    symbol,
                    amount,
                    market_value,
                    str(wallet_id),
                ),
            )
        conn.execute(
            "INSERT INTO investment_transactions "
            "(id, ref, entity_id, entity_account_id, source, product_type, type, date, amount, currency, shares, net_amount, fees, retentions, isin, ticker, asset_contract_address, name) "
            "VALUES (?, 'buy-btc', ?, NULL, 'REAL', 'CRYPTO', 'BUY', ?, '50', 'EUR', '0.5', '50', '0', '0', NULL, 'BTC', NULL, 'Bitcoin')",
            (str(uuid4()), str(entity_id), "2025-01-01T12:00:00"),
        )
        conn.execute(
            "INSERT INTO sys_config (key, value) VALUES ('last_update', 'version-1')"
        )
        conn.commit()

        scoped_assets = [
            GainsAssetFilter(
                product_type=ProductType.CRYPTO,
                wallet_ids=[selected_wallet_id],
            )
        ]
        scoped_snapshots = await repository.get_asset_snapshots(
            scoped_assets, [str(entity_id)]
        )
        scoped_flows = await repository.get_flows(scoped_assets, [str(entity_id)])

        assert [
            (value.asset_key, value.wallet_id, value.market_value)
            for value in scoped_snapshots[0].valuations
        ] == [("BTC", selected_wallet_id, Dezimal(100))]
        assert scoped_flows == []

        scoped = await _use_case(repository).execute(
            GainsTimelineQuery(assets=scoped_assets, entities=[entity_id])
        )
        broad = await _use_case(repository).execute(
            GainsTimelineQuery(
                assets=[GainsAssetFilter(product_type=ProductType.CRYPTO)],
                entities=[entity_id],
            )
        )

        assert scoped.points[0].metrics.value == Dezimal(100)
        assert broad.points[0].metrics.value == Dezimal(300)
        assert (
            len(
                await repository.get_flows(
                    [GainsAssetFilter(product_type=ProductType.CRYPTO)],
                    [str(entity_id)],
                )
            )
            == 1
        )

    @pytest.mark.asyncio
    async def test_aggregates_duplicate_market_assets_within_one_snapshot(self, setup):
        repository, conn = setup
        entity_id = uuid4()
        position_id = _insert_position(conn, entity_id, "2025-01-01")
        for amount, market_value in (("1", "100"), ("2", "250")):
            conn.execute(
                "INSERT INTO crypto_currency_positions "
                "(id, global_position_id, name, symbol, amount, type, market_value, currency, contract_address) "
                "VALUES (?, ?, 'Ethereum', 'ETH', ?, 'COIN', ?, 'EUR', NULL)",
                (str(uuid4()), position_id, amount, market_value),
            )
        for shares, market_value, cost_basis in (
            ("1", "100", "90"),
            ("2", "200", "180"),
        ):
            conn.execute(
                "INSERT INTO fund_positions "
                "(id, global_position_id, name, isin, currency, market_value, shares, initial_investment) "
                "VALUES (?, ?, 'Global Fund', 'IE00TEST0001', 'EUR', ?, ?, ?)",
                (str(uuid4()), position_id, market_value, shares, cost_basis),
            )
        conn.execute(
            "INSERT INTO sys_config (key, value) VALUES ('last_update', 'version-1')"
        )
        conn.commit()
        assets = [
            GainsAssetFilter(product_type=ProductType.CRYPTO),
            GainsAssetFilter(product_type=ProductType.FUND),
        ]

        snapshots = await repository.get_asset_snapshots(assets, [str(entity_id)])
        result = await _use_case(repository).execute(
            GainsTimelineQuery(assets=assets, entities=[entity_id])
        )

        valuations = {
            valuation.product_type: valuation for valuation in snapshots[0].valuations
        }
        assert valuations[ProductType.CRYPTO].quantity == Dezimal(3)
        assert valuations[ProductType.CRYPTO].market_value == Dezimal(350)
        assert valuations[ProductType.FUND].quantity == Dezimal(3)
        assert valuations[ProductType.FUND].market_value == Dezimal(300)
        assert valuations[ProductType.FUND].cost_basis == Dezimal(270)
        assert result.points[0].metrics.value == Dezimal(650)

    @pytest.mark.asyncio
    async def test_aggregates_duplicate_market_assets_within_one_batched_import(
        self, setup
    ):
        repository, conn = setup
        entity_id = uuid4()
        import_id = str(uuid4())
        position_ids = [str(uuid4()), str(uuid4())]
        for position_id, market_value, shares, cost_basis in (
            (position_ids[0], "100", "1", "90"),
            (position_ids[1], "200", "2", "180"),
        ):
            conn.execute(
                "INSERT INTO global_positions (id, entity_id, date, source, entity_account_id) "
                "VALUES (?, ?, '2025-01-01T12:00:00', 'MANUAL', NULL)",
                (position_id, str(entity_id)),
            )
            conn.execute(
                "INSERT INTO virtual_data_imports "
                "(id, import_id, global_position_id, source, date, feature, entity_id) "
                "VALUES (?, ?, ?, 'MANUAL', '2025-01-01T12:00:00', 'POSITION', ?)",
                (str(uuid4()), import_id, position_id, str(entity_id)),
            )
            conn.execute(
                "INSERT INTO fund_positions "
                "(id, global_position_id, name, isin, currency, market_value, shares, initial_investment) "
                "VALUES (?, ?, 'Global Fund', 'IE00TEST0001', 'EUR', ?, ?, ?)",
                (str(uuid4()), position_id, market_value, shares, cost_basis),
            )
        conn.commit()

        snapshots = await repository.get_asset_snapshots(
            [GainsAssetFilter(product_type=ProductType.FUND)], [str(entity_id)]
        )

        assert len(snapshots) == 1
        assert len(snapshots[0].valuations) == 1
        valuation = snapshots[0].valuations[0]
        assert valuation.market_value == Dezimal(300)
        assert valuation.quantity == Dezimal(3)
        assert valuation.cost_basis == Dezimal(270)

    @pytest.mark.asyncio
    async def test_projects_fund_portfolio_and_stock_equity_type_metadata(self, setup):
        repository, conn = setup
        entity_id = uuid4()
        position_id = _insert_position(conn, entity_id, "2025-01-02")
        portfolio_id = str(uuid4())
        conn.execute(
            "INSERT INTO fund_portfolios (id, global_position_id, name) VALUES (?, ?, 'Retirement')",
            (portfolio_id, position_id),
        )
        conn.execute(
            "INSERT INTO fund_positions "
            "(id, global_position_id, name, isin, currency, market_value, shares, initial_investment, portfolio_id) "
            "VALUES (?, ?, 'Retirement Fund', 'IE00FUND0001', 'EUR', '100', '1', '100', ?)",
            (str(uuid4()), position_id, portfolio_id),
        )
        conn.execute(
            "INSERT INTO stock_positions "
            "(id, global_position_id, name, ticker, isin, currency, market_value, shares, initial_investment, type) "
            "VALUES (?, ?, 'ETF', 'ETF', 'IE00ETF0001', 'EUR', '200', '1', '200', 'ETF')",
            (str(uuid4()), position_id),
        )
        later_position_id = _insert_position(conn, entity_id, "2025-01-03")
        later_portfolio_id = str(uuid4())
        conn.execute(
            "INSERT INTO fund_portfolios (id, global_position_id, name) VALUES (?, ?, 'Brokerage')",
            (later_portfolio_id, later_position_id),
        )
        conn.execute(
            "INSERT INTO fund_positions "
            "(id, global_position_id, name, isin, currency, market_value, shares, initial_investment, portfolio_id) "
            "VALUES (?, ?, 'Retirement Fund', 'IE00FUND0001', 'EUR', '100', '1', '100', ?)",
            (str(uuid4()), later_position_id, later_portfolio_id),
        )
        conn.execute(
            "INSERT INTO stock_positions "
            "(id, global_position_id, name, ticker, isin, currency, market_value, shares, initial_investment, type) "
            "VALUES (?, ?, 'ETF', 'ETF', 'IE00ETF0001', 'EUR', '200', '1', '200', 'STOCK')",
            (str(uuid4()), later_position_id),
        )
        for product_type, isin, ticker in (
            ("FUND", "IE00FUND0001", None),
            ("STOCK_ETF", "IE00ETF0001", "ETF"),
        ):
            conn.execute(
                "INSERT INTO investment_transactions "
                "(id, ref, entity_id, entity_account_id, source, product_type, type, date, amount, currency, shares, net_amount, fees, retentions, isin, ticker, asset_contract_address, name) "
                "VALUES (?, ?, ?, NULL, 'REAL', ?, 'BUY', '2025-01-01T12:00:00', '100', 'EUR', '1', '100', '0', '0', ?, ?, NULL, 'Investment')",
                (
                    str(uuid4()),
                    str(uuid4()),
                    str(entity_id),
                    product_type,
                    isin,
                    ticker,
                ),
            )
        conn.commit()

        assets = [
            GainsAssetFilter(product_type=ProductType.FUND),
            GainsAssetFilter(product_type=ProductType.STOCK_ETF),
        ]
        snapshots = await repository.get_asset_snapshots(assets, [str(entity_id)])
        flows = await repository.get_flows(assets, [str(entity_id)])

        valuations = {
            valuation.product_type: valuation for valuation in snapshots[0].valuations
        }
        flows_by_type = {flow.product_type: flow for flow in flows}
        assert valuations[ProductType.FUND].portfolio_name == "Retirement"
        assert valuations[ProductType.STOCK_ETF].equity_type == EquityType.ETF
        assert flows_by_type[ProductType.FUND].portfolio_name == "Retirement"
        assert flows_by_type[ProductType.STOCK_ETF].equity_type == EquityType.ETF

    @pytest.mark.asyncio
    async def test_inferring_commodity_flows_normalizes_units_and_keeps_same_type_holdings(
        self, setup
    ):
        repository, conn = setup
        entity_id = uuid4()
        first_position = _insert_position(conn, entity_id, "2025-01-01")
        second_position = _insert_position(conn, entity_id, "2025-01-02")
        for position_id, gold_amount, gold_unit, gold_value in (
            (first_position, "1", "TROY_OUNCE", "100"),
            (second_position, "62.2069536", "GRAM", "200"),
        ):
            conn.execute(
                "INSERT INTO commodity_positions "
                "(id, global_position_id, name, type, currency, market_value, amount, unit, initial_investment) "
                "VALUES (?, ?, 'Gold Coins', 'GOLD', 'EUR', ?, ?, ?, '100')",
                (str(uuid4()), position_id, gold_value, gold_amount, gold_unit),
            )
            for name, value in (("Platinum Coin", "30"), ("Platinum Bar", "70")):
                conn.execute(
                    "INSERT INTO commodity_positions "
                    "(id, global_position_id, name, type, currency, market_value, amount, unit, initial_investment) "
                    "VALUES (?, ?, ?, 'PLATINUM', 'EUR', ?, '1', 'TROY_OUNCE', ?)",
                    (str(uuid4()), position_id, name, value, value),
                )
        conn.execute(
            "INSERT INTO sys_config (key, value) VALUES ('last_update', 'version-1')"
        )
        conn.commit()

        result = await _use_case(repository).execute(
            GainsTimelineQuery(
                assets=[GainsAssetFilter(product_type=ProductType.COMMODITY)],
                entities=[entity_id],
            )
        )
        platinum_result = await _use_case(repository).execute(
            GainsTimelineQuery(
                assets=[
                    GainsAssetFilter(
                        product_type=ProductType.COMMODITY,
                        asset_keys=["PLATINUM"],
                    )
                ],
                entities=[entity_id],
            )
        )

        first_day, second_day = result.points
        assert first_day.metrics.value == Dezimal(200)
        assert first_day.metrics.net_contributions == Dezimal(200)
        assert second_day.metrics.value == Dezimal(300)
        assert second_day.metrics.net_contributions == Dezimal(300)
        assert second_day.metrics.gain == Dezimal(0)
        assert platinum_result.points[-1].metrics.value == Dezimal(100)
        assert platinum_result.points[-1].metrics.net_contributions == Dezimal(100)

    @pytest.mark.asyncio
    async def test_revalues_repository_commodity_snapshots_from_historic_rates(
        self, setup
    ):
        repository, conn = setup
        entity_id = uuid4()
        position_id = _insert_position(conn, entity_id, "2025-01-01")
        conn.execute(
            "INSERT INTO commodity_positions "
            "(id, global_position_id, name, type, currency, market_value, amount, unit, initial_investment) "
            "VALUES (?, ?, 'Gold Coins', 'GOLD', 'EUR', '100', '31.1034768', 'GRAM', '100')",
            (str(uuid4()), position_id),
        )
        conn.execute(
            "INSERT INTO sys_config (key, value) VALUES ('last_update', 'version-1')"
        )
        conn.commit()
        metal = AsyncMock()
        metal.get_partial_historic_rates.return_value = HistoricMetalRates(
            unit=WeightUnit.TROY_OUNCE,
            days=(date(2025, 1, 1), date(2025, 1, 2)),
            prices={"EUR": (Dezimal(100), Dezimal(120))},
        )

        result = await _use_case(repository, metal).execute(
            GainsTimelineQuery(
                assets=[GainsAssetFilter(product_type=ProductType.COMMODITY)],
                entities=[entity_id],
            )
        )

        by_day = {point.date: point.metrics for point in result.points}
        assert by_day[date(2025, 1, 1)].value == Dezimal(100)
        assert by_day[date(2025, 1, 2)].value == Dezimal(120)
        assert by_day[date(2025, 1, 2)].gain == Dezimal(20)
        metal.get_partial_historic_rates.assert_awaited_once_with(CommodityType.GOLD)

    @pytest.mark.asyncio
    async def test_projects_unlinked_fixed_income_settlement(self, setup):
        repository, conn = setup
        entity_id = uuid4()
        conn.execute(
            "INSERT INTO investment_historic "
            "(id, entity_id, entity_account_id, source, product_type, name, effective_maturity, last_tx_date, currency, returned, repaid, interests, fees, retentions, state) "
            "VALUES (?, ?, NULL, 'REAL', 'FACTORING', 'Project', ?, ?, 'EUR', '115', '100', '15', '2', '3', 'COMPLETED')",
            (
                str(uuid4()),
                str(entity_id),
                "2025-01-03T12:00:00",
                "2025-01-03T12:00:00",
            ),
        )
        conn.commit()

        settlements = await repository.get_settlements(
            [GainsAssetFilter(product_type=ProductType.FACTORING)], [str(entity_id)]
        )

        assert len(settlements) == 1
        assert settlements[0].asset_key == "Project"
        assert settlements[0].net_proceeds == Dezimal(110)

    @pytest.mark.asyncio
    async def test_normalizes_mixed_timezone_transaction_timestamps(self, setup):
        repository, conn = setup
        entity_id = uuid4()
        for transaction_date in (
            "2025-01-01T12:00:00",
            "2025-01-02T12:00:00+02:00",
        ):
            conn.execute(
                "INSERT INTO investment_transactions "
                "(id, ref, entity_id, entity_account_id, source, product_type, type, date, amount, currency, shares, net_amount, fees, retentions, isin, ticker, asset_contract_address, name) "
                "VALUES (?, ?, ?, NULL, 'REAL', 'CRYPTO', 'BUY', ?, '100', 'EUR', '1', '100', '0', '0', NULL, 'BTC', NULL, 'Bitcoin')",
                (str(uuid4()), str(uuid4()), str(entity_id), transaction_date),
            )
        conn.commit()

        flows = await repository.get_flows(
            [GainsAssetFilter(product_type=ProductType.CRYPTO)], [str(entity_id)]
        )

        assert all(flow.moment.tzinfo is not None for flow in flows)
        assert sorted(flow.moment for flow in flows)

    @pytest.mark.asyncio
    async def test_maps_aggregated_deposit_transactions_to_one_lifecycle(self, setup):
        repository, conn = setup
        entity_id = uuid4()
        position_id = _insert_position(conn, entity_id, "2025-01-01")
        conn.execute(
            "INSERT INTO deposit_positions "
            "(id, global_position_id, name, currency, amount, interest_rate, creation, maturity) "
            "VALUES (?, ?, 'Deposit', 'EUR', '5000', '0.02', '2025-01-01T00:00:00', '2025-02-01')",
            (str(uuid4()), position_id),
        )
        for transaction_type, transaction_date in (
            ("INVESTMENT", "2025-01-01T12:00:00"),
            ("REPAYMENT", "2025-02-01T12:00:00"),
            ("INTEREST", "2025-02-01T12:00:00"),
        ):
            conn.execute(
                "INSERT INTO investment_transactions "
                "(id, ref, entity_id, entity_account_id, source, product_type, type, date, amount, currency, shares, net_amount, fees, retentions, isin, ticker, asset_contract_address, name) "
                "VALUES (?, ?, ?, NULL, 'REAL', 'DEPOSIT', ?, ?, '1000', 'EUR', NULL, '1000', '0', '0', NULL, NULL, NULL, 'Provider operation')",
                (
                    str(uuid4()),
                    str(uuid4()),
                    str(entity_id),
                    transaction_type,
                    transaction_date,
                ),
            )
        conn.commit()

        flows = await repository.get_flows(
            [GainsAssetFilter(product_type=ProductType.DEPOSIT)], [str(entity_id)]
        )

        assert {flow.asset_key for flow in flows} == {
            "DEPOSIT:2025-01-01:2025-02-01:5000:EUR"
        }

    @pytest.mark.asyncio
    async def test_deduplicates_identical_real_factoring_flows(self, setup):
        repository, conn = setup
        entity_id = uuid4()
        for reference in ("provider-ref-1", "provider-ref-2"):
            conn.execute(
                "INSERT INTO investment_transactions "
                "(id, ref, entity_id, entity_account_id, source, product_type, type, date, amount, currency, shares, net_amount, fees, retentions, isin, ticker, asset_contract_address, name) "
                "VALUES (?, ?, ?, NULL, 'REAL', 'FACTORING', 'REPAYMENT', '2025-01-02T00:00:00', '100', 'EUR', NULL, '100', '0', '0', NULL, NULL, NULL, 'Project')",
                (str(uuid4()), reference, str(entity_id)),
            )
        conn.commit()

        flows = await repository.get_flows(
            [GainsAssetFilter(product_type=ProductType.FACTORING)], [str(entity_id)]
        )

        assert len(flows) == 1
        assert flows[0].amount == Dezimal(100)
