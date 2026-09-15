import sqlite3
from datetime import date, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio

from application.use_cases.get_gains_timeline import GetGainsTimelineImpl
from application.use_cases.get_networth_timeline import GetNetworthTimelineImpl
from domain.commodity import CommodityType, WeightUnit
from domain.dezimal import Dezimal
from domain.exchange_rate import HistoricMetalRates
from domain.gains_timeline import GainsAssetFilter, GainsTimelineQuery
from domain.global_position import EquityType, ProductType
from domain.networth_timeline import NetworthTimelineQuery
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.gains_timeline.gains_timeline_repository import (
    GainsTimelineSQLRepository,
)
from infrastructure.repository.networth_timeline.networth_timeline_repository import (
    NetworthTimelineSQLRepository,
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
        entity_id CHAR(36),
        created_at TIMESTAMP,
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
    CREATE TABLE account_positions (
        id CHAR(36) PRIMARY KEY,
        global_position_id CHAR(36),
        currency CHAR(3),
        total TEXT
    );
    CREATE TABLE stock_positions (
        id CHAR(36) PRIMARY KEY,
        global_position_id CHAR(36),
        name TEXT,
        ticker TEXT,
        isin TEXT,
        currency CHAR(3),
        market_value TEXT,
        shares TEXT,
        initial_investment TEXT,
        type TEXT
    );
    CREATE TABLE fund_portfolios (
        id CHAR(36) PRIMARY KEY,
        global_position_id CHAR(36),
        name TEXT
    );
    CREATE TABLE fund_positions (
        id CHAR(36) PRIMARY KEY,
        global_position_id CHAR(36),
        name TEXT,
        isin TEXT,
        currency CHAR(3),
        market_value TEXT,
        shares TEXT,
        initial_investment TEXT,
        portfolio_id CHAR(36)
    );
    CREATE TABLE crypto_currency_positions (
        id CHAR(36) PRIMARY KEY,
        global_position_id CHAR(36),
        name TEXT,
        symbol TEXT,
        amount TEXT,
        type TEXT,
        market_value TEXT,
        currency CHAR(3),
        contract_address TEXT,
        wallet_id CHAR(36)
    );
    CREATE TABLE crypto_currency_initial_investments (
        id CHAR(36) PRIMARY KEY,
        crypto_currency_position CHAR(36),
        currency CHAR(3),
        initial_investment TEXT,
        average_buy_price TEXT
    );
    CREATE TABLE commodity_positions (
        id CHAR(36) PRIMARY KEY,
        global_position_id CHAR(36),
        name TEXT,
        type TEXT,
        currency CHAR(3),
        market_value TEXT,
        amount TEXT,
        unit TEXT,
        initial_investment TEXT
    );
    CREATE TABLE deposit_positions (
        id CHAR(36) PRIMARY KEY,
        global_position_id CHAR(36),
        name TEXT,
        currency CHAR(3),
        amount TEXT,
        interest_rate TEXT,
        creation DATETIME,
        maturity DATE
    );
    CREATE TABLE factoring_positions (
        id CHAR(36) PRIMARY KEY,
        global_position_id CHAR(36),
        name TEXT,
        currency CHAR(3),
        amount TEXT,
        interest_rate TEXT,
        start DATETIME,
        maturity DATE,
        late_interest_rate TEXT
    );
    CREATE TABLE real_estate_cf_positions (
        id CHAR(36) PRIMARY KEY,
        global_position_id CHAR(36),
        name TEXT,
        currency CHAR(3),
        amount TEXT,
        pending_amount TEXT,
        interest_rate TEXT,
        start DATETIME,
        maturity DATE,
        extended_maturity DATE,
        extended_interest_rate TEXT
    );
    CREATE TABLE crowdlending_positions (
        id CHAR(36) PRIMARY KEY,
        global_position_id CHAR(36),
        currency CHAR(3),
        total TEXT
    );
    CREATE TABLE derivative_positions (
        id CHAR(36) PRIMARY KEY,
        global_position_id CHAR(36),
        currency CHAR(3),
        market_value TEXT
    );
    CREATE TABLE market_forecast_positions (
        id CHAR(36) PRIMARY KEY,
        global_position_id CHAR(36),
        currency CHAR(3),
        market_value TEXT
    );
    CREATE TABLE card_positions (
        id CHAR(36) PRIMARY KEY,
        global_position_id CHAR(36),
        currency CHAR(3),
        used TEXT
    );
    CREATE TABLE loan_positions (
        id CHAR(36) PRIMARY KEY,
        global_position_id CHAR(36),
        currency CHAR(3),
        principal_outstanding TEXT,
        hash VARCHAR(64),
        creation DATE
    );
    CREATE TABLE credit_positions (
        id CHAR(36) PRIMARY KEY,
        global_position_id CHAR(36),
        currency CHAR(3),
        drawn_amount TEXT
    );
    CREATE TABLE investment_transactions (
        id CHAR(36) PRIMARY KEY,
        ref TEXT,
        entity_id CHAR(36),
        entity_account_id CHAR(36),
        source TEXT,
        product_type TEXT,
        type TEXT,
        date DATETIME,
        amount TEXT,
        currency CHAR(3),
        shares TEXT,
        net_amount TEXT,
        fees TEXT,
        retentions TEXT,
        isin TEXT,
        ticker TEXT,
        asset_contract_address TEXT,
        name TEXT,
        portfolio_name TEXT,
        product_subtype TEXT
    );
    CREATE TABLE investment_historic (
        id CHAR(36) PRIMARY KEY,
        entity_id CHAR(36),
        entity_account_id CHAR(36),
        source TEXT,
        product_type TEXT,
        name TEXT,
        effective_maturity DATETIME,
        last_tx_date DATETIME,
        currency CHAR(3),
        returned TEXT,
        repaid TEXT,
        interests TEXT,
        fees TEXT,
        retentions TEXT,
        state TEXT
    );
    CREATE TABLE investment_historic_txs (
        tx_id CHAR(36),
        historic_entry_id CHAR(36)
    );
    CREATE TABLE networth_timeline_points (
        date TEXT PRIMARY KEY,
        currency VARCHAR(10) NOT NULL,
        total TEXT NOT NULL,
        breakdown TEXT NOT NULL
    );
    CREATE TABLE networth_timeline_meta (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        inputs_signature TEXT,
        last_computed_date TEXT
    );
    CREATE TABLE sys_config (key TEXT PRIMARY KEY, value TEXT);
"""


@pytest_asyncio.fixture
async def setup():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(_SCHEMA)
    client = DBClient(connection)
    yield (
        connection,
        GainsTimelineSQLRepository(client),
        NetworthTimelineSQLRepository(client),
    )
    connection.close()


def _insert_position(connection, entity_id, day):
    position_id = str(uuid4())
    connection.execute(
        "INSERT INTO global_positions (id, entity_id, date, source, entity_account_id) "
        "VALUES (?, ?, ?, 'REAL', NULL)",
        (position_id, str(entity_id), f"{day.isoformat()}T12:00:00"),
    )
    return position_id


def _insert_account(connection, entity_id, account_id, deleted_at=None):
    connection.execute(
        "INSERT INTO entity_accounts (id, entity_id, created_at, deleted_at) "
        "VALUES (?, ?, '2025-01-01T00:00:00', ?)",
        (str(account_id), str(entity_id), deleted_at),
    )


def _insert_position_for_account(connection, entity_id, account_id, day):
    position_id = str(uuid4())
    connection.execute(
        "INSERT INTO global_positions (id, entity_id, date, source, entity_account_id) "
        "VALUES (?, ?, ?, 'REAL', ?)",
        (
            position_id,
            str(entity_id),
            f"{day.isoformat()}T12:00:00",
            str(account_id),
        ),
    )
    return position_id


def _insert_supported_position(connection, product_type, position_id, market_value):
    match product_type:
        case ProductType.STOCK_ETF:
            connection.execute(
                "INSERT INTO stock_positions "
                "(id, global_position_id, name, ticker, isin, currency, market_value, shares, initial_investment, type) "
                "VALUES (?, ?, 'Global ETF', 'ETF', 'IE00TEST0001', 'USD', ?, '1', ?, 'ETF')",
                (str(uuid4()), position_id, market_value, market_value),
            )
        case ProductType.FUND:
            connection.execute(
                "INSERT INTO fund_positions "
                "(id, global_position_id, name, isin, currency, market_value, shares, initial_investment) "
                "VALUES (?, ?, 'Global Fund', 'IE00TEST0001', 'USD', ?, '1', ?)",
                (str(uuid4()), position_id, market_value, market_value),
            )
        case ProductType.CRYPTO:
            connection.execute(
                "INSERT INTO crypto_currency_positions "
                "(id, global_position_id, name, symbol, amount, type, market_value, currency, contract_address) "
                "VALUES (?, ?, 'Bitcoin', 'BTC', '1', 'COIN', ?, 'USD', NULL)",
                (str(uuid4()), position_id, market_value),
            )
        case ProductType.COMMODITY:
            connection.execute(
                "INSERT INTO commodity_positions "
                "(id, global_position_id, name, type, currency, market_value, amount, unit, initial_investment) "
                "VALUES (?, ?, 'Gold', 'GOLD', 'USD', ?, '1', 'TROY_OUNCE', ?)",
                (str(uuid4()), position_id, market_value, market_value),
            )
        case ProductType.DEPOSIT:
            connection.execute(
                "INSERT INTO deposit_positions "
                "(id, global_position_id, name, currency, amount, interest_rate, creation, maturity) "
                "VALUES (?, ?, 'Deposit', 'USD', ?, '0', '2025-01-01', '2025-12-31')",
                (str(uuid4()), position_id, market_value),
            )
        case ProductType.FACTORING:
            connection.execute(
                "INSERT INTO factoring_positions "
                "(id, global_position_id, name, currency, amount, interest_rate, start, maturity, late_interest_rate) "
                "VALUES (?, ?, 'Factoring', 'USD', ?, '0', '2025-01-01', '2025-12-31', NULL)",
                (str(uuid4()), position_id, market_value),
            )
        case ProductType.REAL_ESTATE_CF:
            connection.execute(
                "INSERT INTO real_estate_cf_positions "
                "(id, global_position_id, name, currency, amount, pending_amount, interest_rate, start, maturity, extended_maturity, extended_interest_rate) "
                "VALUES (?, ?, 'Project', 'USD', ?, ?, '0', '2025-01-01', '2025-12-31', NULL, NULL)",
                (str(uuid4()), position_id, market_value, market_value),
            )
        case _:
            raise ValueError(f"Unsupported parity product type: {product_type.value}")


def _insert_import(connection, import_id, position_id, entity_id, day, source):
    connection.execute(
        "INSERT INTO virtual_data_imports "
        "(id, import_id, global_position_id, source, date, feature, entity_id) "
        "VALUES (?, ?, ?, ?, ?, 'POSITION', ?)",
        (
            str(uuid4()),
            str(import_id),
            position_id,
            source,
            f"{day.isoformat()}T12:00:00",
            str(entity_id),
        ),
    )


def _insert_empty_import(connection, import_id, day, source):
    connection.execute(
        "INSERT INTO virtual_data_imports "
        "(id, import_id, global_position_id, source, date, feature, entity_id) "
        "VALUES (?, ?, NULL, ?, ?, NULL, NULL)",
        (str(uuid4()), str(import_id), source, f"{day.isoformat()}T12:00:00"),
    )


def _use_cases(gains_repository, networth_repository, rates, metal_rates=None):
    entity_port = AsyncMock()
    entity_port.get_disabled_entities.return_value = []
    entity_port.get_all.return_value = []

    exchange_rate_storage = AsyncMock()
    exchange_rate_storage.get.return_value = rates

    metal_price_provider = AsyncMock()
    if metal_rates is None:
        metal_price_provider.get_partial_historic_rates.return_value = None
    else:
        metal_price_provider.get_partial_historic_rates.side_effect = (
            lambda commodity_type: metal_rates.get(commodity_type)
        )

    real_estate_port = AsyncMock()
    real_estate_port.get_all.return_value = []

    return (
        GetGainsTimelineImpl(
            gains_repository,
            exchange_rate_storage,
            entity_port,
            metal_price_provider,
        ),
        GetNetworthTimelineImpl(
            networth_repository,
            exchange_rate_storage,
            entity_port,
            real_estate_port,
            metal_price_provider,
        ),
    )


def _displayed(value: Dezimal) -> Dezimal:
    return Dezimal(str(round(value, 2)))


class TestGainsNetworthValueParity:
    @pytest.mark.parametrize(
        "product_type",
        [
            ProductType.STOCK_ETF,
            ProductType.FUND,
            ProductType.CRYPTO,
            ProductType.COMMODITY,
            ProductType.DEPOSIT,
            ProductType.FACTORING,
            ProductType.REAL_ESTATE_CF,
        ],
    )
    @pytest.mark.asyncio
    async def test_product_value_matches_networth_breakdown(self, setup, product_type):
        connection, gains_repository, networth_repository = setup
        entity_id = uuid4()
        first_day = date(2025, 1, 1)
        second_day = date(2025, 1, 2)
        first_position = _insert_position(connection, entity_id, first_day)
        second_position = _insert_position(connection, entity_id, second_day)
        _insert_supported_position(connection, product_type, first_position, "125")
        _insert_supported_position(connection, product_type, second_position, "250")
        connection.execute(
            "INSERT INTO sys_config (key, value) VALUES ('last_update', 'version-1')"
        )
        connection.commit()

        gains, networth = _use_cases(
            gains_repository,
            networth_repository,
            {"EUR": {"USD": Dezimal("1.25")}},
        )

        gains_timeline = await gains.execute(
            GainsTimelineQuery(
                assets=[GainsAssetFilter(product_type=product_type)],
                entities=[entity_id],
            )
        )
        networth_timeline = await networth.execute(NetworthTimelineQuery())

        gains_by_day = {point.date: point for point in gains_timeline.points}
        networth_by_day = {point.date: point for point in networth_timeline.points}
        assert set(gains_by_day) == {first_day, second_day}
        assert set(networth_by_day) == {first_day, second_day}
        for day in gains_by_day:
            assert (
                _displayed(gains_by_day[day].breakdown[product_type.value].value)
                == (networth_by_day[day].breakdown[product_type.value])
            )

    @pytest.mark.asyncio
    async def test_fund_value_matches_across_holder_carry_forward(self, setup):
        connection, gains_repository, networth_repository = setup
        first_entity_id = uuid4()
        second_entity_id = uuid4()
        first_day = date(2025, 1, 1)
        second_day = date(2025, 1, 2)
        _insert_supported_position(
            connection,
            ProductType.FUND,
            _insert_position(connection, first_entity_id, first_day),
            "125",
        )
        _insert_supported_position(
            connection,
            ProductType.FUND,
            _insert_position(connection, second_entity_id, second_day),
            "250",
        )
        connection.execute(
            "INSERT INTO sys_config (key, value) VALUES ('last_update', 'version-1')"
        )
        connection.commit()

        gains, networth = _use_cases(
            gains_repository,
            networth_repository,
            {"EUR": {"USD": Dezimal("1.25")}},
        )

        gains_timeline = await gains.execute(
            GainsTimelineQuery(
                assets=[GainsAssetFilter(product_type=ProductType.FUND)],
                entities=[first_entity_id, second_entity_id],
            )
        )
        networth_timeline = await networth.execute(NetworthTimelineQuery())

        gains_by_day = {point.date: point for point in gains_timeline.points}
        networth_by_day = {point.date: point for point in networth_timeline.points}
        assert gains_by_day[second_day].breakdown["FUND"].value == Dezimal(300)
        assert (
            _displayed(gains_by_day[second_day].breakdown["FUND"].value)
            == (networth_by_day[second_day].breakdown["FUND"])
        )

    @pytest.mark.asyncio
    async def test_fund_value_matches_after_manual_empty_redeclaration(self, setup):
        connection, gains_repository, networth_repository = setup
        entity_id = uuid4()
        first_day = date(2025, 1, 1)
        empty_day = date(2025, 1, 2)
        position_id = str(uuid4())
        connection.execute(
            "INSERT INTO global_positions (id, entity_id, date, source, entity_account_id) "
            "VALUES (?, ?, ?, 'MANUAL', NULL)",
            (position_id, str(entity_id), f"{first_day.isoformat()}T12:00:00"),
        )
        _insert_supported_position(connection, ProductType.FUND, position_id, "125")
        _insert_import(connection, uuid4(), position_id, entity_id, first_day, "MANUAL")
        _insert_empty_import(connection, uuid4(), empty_day, "MANUAL")
        connection.execute(
            "INSERT INTO sys_config (key, value) VALUES ('last_update', 'version-1')"
        )
        connection.commit()

        gains, networth = _use_cases(
            gains_repository,
            networth_repository,
            {"EUR": {"USD": Dezimal("1.25")}},
        )

        gains_timeline = await gains.execute(
            GainsTimelineQuery(
                assets=[GainsAssetFilter(product_type=ProductType.FUND)],
                entities=[entity_id],
            )
        )
        networth_timeline = await networth.execute(NetworthTimelineQuery())

        gains_by_day = {point.date: point for point in gains_timeline.points}
        networth_by_day = {point.date: point for point in networth_timeline.points}
        assert gains_by_day[empty_day].metrics.value == Dezimal(0)
        assert networth_by_day[empty_day].total == Dezimal(0)

    @pytest.mark.asyncio
    async def test_fund_value_matches_after_holder_deletion(self, setup):
        connection, gains_repository, networth_repository = setup
        deleted_entity_id = uuid4()
        active_entity_id = uuid4()
        deleted_account_id = uuid4()
        first_day = date(2025, 1, 1)
        deletion_day = date(2025, 1, 2)
        _insert_account(
            connection,
            deleted_entity_id,
            deleted_account_id,
            f"{deletion_day.isoformat()}T00:00:00",
        )
        _insert_supported_position(
            connection,
            ProductType.FUND,
            _insert_position_for_account(
                connection, deleted_entity_id, deleted_account_id, first_day
            ),
            "125",
        )
        _insert_supported_position(
            connection,
            ProductType.FUND,
            _insert_position(connection, active_entity_id, deletion_day),
            "250",
        )
        connection.execute(
            "INSERT INTO sys_config (key, value) VALUES ('last_update', 'version-1')"
        )
        connection.commit()

        gains, networth = _use_cases(
            gains_repository,
            networth_repository,
            {"EUR": {"USD": Dezimal("1.25")}},
        )

        gains_timeline = await gains.execute(
            GainsTimelineQuery(
                assets=[GainsAssetFilter(product_type=ProductType.FUND)],
                entities=[deleted_entity_id, active_entity_id],
            )
        )
        networth_timeline = await networth.execute(NetworthTimelineQuery())

        gains_by_day = {point.date: point for point in gains_timeline.points}
        networth_by_day = {point.date: point for point in networth_timeline.points}
        assert gains_by_day[deletion_day].breakdown["FUND"].value == Dezimal(200)
        assert (
            _displayed(gains_by_day[deletion_day].breakdown["FUND"].value)
            == (networth_by_day[deletion_day].breakdown["FUND"])
        )

    @pytest.mark.asyncio
    async def test_commodity_value_matches_historic_price_only_dates(self, setup):
        connection, gains_repository, networth_repository = setup
        entity_id = uuid4()
        first_day = date(2025, 6, 15)
        revaluation_day = date(2025, 6, 20)
        position_id = _insert_position(connection, entity_id, first_day)
        connection.execute(
            "INSERT INTO commodity_positions "
            "(id, global_position_id, name, type, currency, market_value, amount, unit, initial_investment) "
            "VALUES (?, ?, 'Gold', 'GOLD', 'USD', '1000', '31.1034768', 'GRAM', '1000')",
            (str(uuid4()), position_id),
        )
        connection.execute(
            "INSERT INTO sys_config (key, value) VALUES ('last_update', 'version-1')"
        )
        connection.commit()

        historic = HistoricMetalRates(
            unit=WeightUnit.TROY_OUNCE,
            days=(first_day, revaluation_day),
            prices={"USD": (Dezimal("2500"), Dezimal("2625"))},
        )
        gains, networth = _use_cases(
            gains_repository,
            networth_repository,
            {"EUR": {"USD": Dezimal("1.25")}},
            {CommodityType.GOLD: historic},
        )

        gains_timeline = await gains.execute(
            GainsTimelineQuery(
                assets=[GainsAssetFilter(product_type=ProductType.COMMODITY)],
                entities=[entity_id],
            )
        )
        networth_timeline = await networth.execute(NetworthTimelineQuery())

        gains_by_day = {point.date: point for point in gains_timeline.points}
        networth_by_day = {point.date: point for point in networth_timeline.points}
        assert set(gains_by_day) == {
            first_day + timedelta(days=offset)
            for offset in range((revaluation_day - first_day).days + 1)
        }
        assert set(networth_by_day) == {first_day, revaluation_day}
        assert gains_by_day[revaluation_day].breakdown["COMMODITY"].value == Dezimal(
            2100
        )
        assert (
            _displayed(gains_by_day[revaluation_day].breakdown["COMMODITY"].value)
            == networth_by_day[revaluation_day].breakdown["COMMODITY"]
        )

    @pytest.mark.asyncio
    async def test_fund_portfolios_and_equity_types_are_additive(self, setup):
        connection, gains_repository, networth_repository = setup
        entity_id = uuid4()
        snapshot_day = date(2025, 1, 1)
        position_id = _insert_position(connection, entity_id, snapshot_day)
        income_portfolio_id = str(uuid4())
        growth_portfolio_id = str(uuid4())
        connection.executemany(
            "INSERT INTO fund_portfolios (id, name) VALUES (?, ?)",
            [(income_portfolio_id, "Income"), (growth_portfolio_id, "Growth")],
        )
        connection.executemany(
            "INSERT INTO fund_positions "
            "(id, global_position_id, name, isin, currency, market_value, shares, initial_investment, portfolio_id) "
            "VALUES (?, ?, ?, ?, 'USD', ?, '1', ?, ?)",
            [
                (
                    str(uuid4()),
                    position_id,
                    "Income Fund",
                    "IE00TEST0001",
                    "125",
                    "125",
                    income_portfolio_id,
                ),
                (
                    str(uuid4()),
                    position_id,
                    "Growth Fund",
                    "IE00TEST0002",
                    "250",
                    "250",
                    growth_portfolio_id,
                ),
            ],
        )
        connection.executemany(
            "INSERT INTO stock_positions "
            "(id, global_position_id, name, ticker, isin, currency, market_value, shares, initial_investment, type) "
            "VALUES (?, ?, ?, ?, ?, 'USD', ?, '1', ?, ?)",
            [
                (
                    str(uuid4()),
                    position_id,
                    "Global Stock",
                    "STOCK",
                    "US00TEST0001",
                    "125",
                    "125",
                    EquityType.STOCK.value,
                ),
                (
                    str(uuid4()),
                    position_id,
                    "Global ETF",
                    "ETF",
                    "US00TEST0002",
                    "250",
                    "250",
                    EquityType.ETF.value,
                ),
            ],
        )
        connection.execute(
            "INSERT INTO sys_config (key, value) VALUES ('last_update', 'version-1')"
        )
        connection.commit()

        gains, _ = _use_cases(
            gains_repository,
            networth_repository,
            {"EUR": {"USD": Dezimal("1.25")}},
        )

        async def value_for(asset_filter):
            timeline = await gains.execute(
                GainsTimelineQuery(assets=[asset_filter], entities=[entity_id])
            )
            return timeline.points[-1].metrics.value

        broad_fund = await value_for(GainsAssetFilter(product_type=ProductType.FUND))
        income_fund = await value_for(
            GainsAssetFilter(
                product_type=ProductType.FUND,
                portfolio_names=["Income"],
            )
        )
        growth_fund = await value_for(
            GainsAssetFilter(
                product_type=ProductType.FUND,
                portfolio_names=["Growth"],
            )
        )
        broad_equity = await value_for(
            GainsAssetFilter(product_type=ProductType.STOCK_ETF)
        )
        stocks = await value_for(
            GainsAssetFilter(
                product_type=ProductType.STOCK_ETF,
                equity_types=[EquityType.STOCK],
            )
        )
        etfs = await value_for(
            GainsAssetFilter(
                product_type=ProductType.STOCK_ETF,
                equity_types=[EquityType.ETF],
            )
        )

        assert income_fund + growth_fund == broad_fund
        assert stocks + etfs == broad_equity
