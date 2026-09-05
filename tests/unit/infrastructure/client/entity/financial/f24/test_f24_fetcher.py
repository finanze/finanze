from unittest.mock import AsyncMock, MagicMock

import pytest

from domain.dezimal import Dezimal
from domain.global_position import AccountType, EquityType, ProductType
from domain.native_entities import F24
from infrastructure.client.entity.financial.f24.f24_fetcher import (
    F24Fetcher,
    _map_brokerage_cash,
    _map_stocks,
)


def _pos(
    ticker,
    name,
    isin,
    market_value,
    mkt_price,
    q=1,
    curr="USD",
    t=1,
):
    return {
        "t": t,
        "q": q,
        "i": ticker,
        "name": name,
        "name2": name,
        "issue_nb": isin,
        "market_value": market_value,
        "mkt_price": mkt_price,
        "curr": curr,
        "base_currency": curr,
        "base_contract_code": ticker,
    }


HAR_POS = [
    _pos("CPNG.US", "Coupang", "US22266T1097", 15.15, 15.32),
    _pos("PINS.US", "Pinterest Inc", "US72352L1061", 20.28, 20.44),
    _pos("RGTI.US", "RIGETTI COMPUTING INC", "US76655K1034", 15.07, 15.2),
]

HAR_MONEY_DETAILED = {
    "EUR": {
        "currency": "EUR",
        "avail_money": 5030.19,
        "Stotal": 5044.89,
        "Smoney": 5001,
    },
    "USD": {
        "currency": "USD",
        "avail_money": 5563.64,
        "Stotal": 5858.89,
        "Smoney": 0,
    },
}


def _fetcher():
    fetcher = F24Fetcher()
    fetcher._client = MagicMock()
    fetcher._users = {
        "brokerage": {"id": "7279469", "trader_systems_id": "1450325"},
    }
    return fetcher


def test_map_stocks_from_har_positions():
    stocks = _map_stocks(HAR_POS)
    assert [s.ticker for s in stocks] == ["CPNG.US", "PINS.US", "RGTI.US"]
    assert [s.isin for s in stocks] == [
        "US22266T1097",
        "US72352L1061",
        "US76655K1034",
    ]
    assert [s.market_value for s in stocks] == [
        Dezimal("15.15"),
        Dezimal("20.28"),
        Dezimal("15.07"),
    ]
    assert sum((s.market_value for s in stocks), Dezimal(0)) == Dezimal("50.5")
    for stock in stocks:
        assert stock.shares == Dezimal(1)
        assert stock.currency == "USD"
        assert stock.type == EquityType.STOCK
        assert stock.market == "US"
        assert stock.initial_investment == stock.market_value
        assert stock.average_buy_price == stock.market_value


def test_map_stocks_skips_zero_and_non_equity(caplog):
    stocks = _map_stocks(
        [
            _pos("CASH.US", "Cash", "US0000000000", 10, 10, t=6),
            _pos("ZERO.US", "Zero", "US0000000001", 10, 10, q=0),
            _pos("CPNG.US", "Coupang", "US22266T1097", 15.15, 15.32),
        ]
    )
    assert [s.ticker for s in stocks] == ["CPNG.US"]
    assert "unsupported type t=6" in caplog.text
    assert "non-positive shares q=0" in caplog.text


def test_map_stocks_skips_missing_currency(caplog):
    missing = _pos("CPNG.US", "Coupang", "US22266T1097", 15.15, 15.32)
    missing["curr"] = None
    missing["base_currency"] = None
    stocks = _map_stocks(
        [missing, _pos("PINS.US", "Pinterest Inc", "US72352L1061", 20.28, 20.44)]
    )
    assert [s.ticker for s in stocks] == ["PINS.US"]
    assert "missing ticker or currency" in caplog.text


def test_map_stocks_multiplies_when_market_value_is_per_share():
    stocks = _map_stocks(
        [_pos("CPNG.US", "Coupang", "US22266T1097", 15.15, 15.32, q=2)]
    )
    assert stocks[0].shares == Dezimal(2)
    assert stocks[0].market_value == Dezimal("30.3")
    assert stocks[0].average_buy_price == Dezimal("15.15")


def test_map_brokerage_cash_uses_smoney_not_buying_power():
    accounts = _map_brokerage_cash({"money_detailed": HAR_MONEY_DETAILED})
    assert len(accounts) == 1
    assert accounts[0].type == AccountType.BROKERAGE
    assert accounts[0].currency == "EUR"
    assert accounts[0].total == Dezimal("5001")


@pytest.mark.asyncio
async def test_global_position_maps_cash_and_stocks():
    fetcher = _fetcher()
    fetcher._client.get_positions = AsyncMock(
        return_value={
            "pos": HAR_POS,
            "money_detailed": HAR_MONEY_DETAILED,
            "offbalance": [],
        }
    )

    position = await fetcher.global_position()

    assert position.entity == F24
    accounts = position.products[ProductType.ACCOUNT].entries
    assert len(accounts) == 1
    assert accounts[0].total == Dezimal("5001")
    assert accounts[0].currency == "EUR"

    stocks = position.products[ProductType.STOCK_ETF].entries
    assert len(stocks) == 3
    assert {s.ticker for s in stocks} == {"CPNG.US", "PINS.US", "RGTI.US"}
    assert ProductType.DEPOSIT not in position.products
