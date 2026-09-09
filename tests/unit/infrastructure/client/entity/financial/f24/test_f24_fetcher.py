from unittest.mock import AsyncMock, MagicMock

import pytest

from domain.dezimal import Dezimal
from domain.global_position import AccountType, EquityType, ProductType
from domain.native_entities import F24
from domain.transactions import TxType
from infrastructure.client.entity.financial.f24.f24_fetcher import (
    F24Fetcher,
    _currency_pair_tickers,
    _is_currency_pair,
    _map_brokerage_cash,
    _map_stocks,
    _trade_fee,
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
    k=1,
    price_a=0,
):
    return {
        "t": t,
        "k": k,
        "q": q,
        "i": ticker,
        "name": name,
        "name2": name,
        "issue_nb": isin,
        "market_value": market_value,
        "mkt_price": mkt_price,
        "price_a": price_a,
        "bal_price_a": price_a,
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

CURRENCY_PAIRS = {
    "tickers": {
        "USD/EUR": "USD/EUR",
        "EUR/USD": "EUR/USD",
        "RUR/USD": "RUR/USD.INT",
    }
}


def _fetcher():
    fetcher = F24Fetcher()
    fetcher._client = MagicMock()
    fetcher._client.get_allowed_currency_pairs = AsyncMock(return_value=CURRENCY_PAIRS)
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
        assert stock.initial_investment == Dezimal(0)
        assert stock.average_buy_price == Dezimal(0)


def test_map_stocks_kind_7_is_etf():
    stocks = _map_stocks(
        [
            _pos(
                "ERNE.EU",
                "iShares Ultrashort Bond UCITS ETF EUR",
                "IE00BCRY6557",
                10,
                10,
                curr="EUR",
                k=7,
            )
        ]
    )
    assert stocks[0].type == EquityType.ETF
    assert stocks[0].ticker == "ERNE.EU"


def test_map_stocks_skips_bond_kind(caplog):
    stocks = _map_stocks(
        [
            _pos(
                "BOND.EU",
                "Some Bond",
                "XS0000000000",
                100,
                100,
                curr="EUR",
                t=2,
                k=9,
            ),
            _pos(
                "BOND2.EU",
                "Bond Kind Only",
                "XS0000000001",
                100,
                100,
                curr="EUR",
                k=9,
            ),
            _pos("CPNG.US", "Coupang", "US22266T1097", 15.15, 15.32),
        ]
    )
    assert [s.ticker for s in stocks] == ["CPNG.US"]
    assert "unsupported type t=2" in caplog.text
    assert "unsupported kind k=9" in caplog.text


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
        [_pos("CPNG.US", "Coupang", "US22266T1097", 15.15, 15.32, q=2, price_a=15.15)]
    )
    assert stocks[0].shares == Dezimal(2)
    assert stocks[0].market_value == Dezimal("30.3")
    assert stocks[0].average_buy_price == Dezimal("15.15")
    assert stocks[0].initial_investment == Dezimal("30.3")


def test_map_stocks_uses_price_a_including_gifted_zero():
    stocks = _map_stocks(
        [
            _pos(
                "APLE.US",
                "Apple Hospitality REIT Inc",
                "US03784Y2000",
                15.61,
                15.62,
                price_a=15.626,
            ),
            _pos("CPNG.US", "Coupang", "US22266T1097", 15.15, 15.32, price_a=0),
            _pos(
                "TEF.EU",
                "Telefonica S.A.",
                "ES0178430E18",
                3.617,
                3.617,
                curr="EUR",
                price_a=3.618,
            ),
        ]
    )
    by_ticker = {s.ticker: s for s in stocks}
    assert by_ticker["APLE.US"].average_buy_price == Dezimal("15.626")
    assert by_ticker["APLE.US"].initial_investment == Dezimal("15.63")
    assert by_ticker["CPNG.US"].average_buy_price == Dezimal(0)
    assert by_ticker["CPNG.US"].initial_investment == Dezimal(0)
    assert by_ticker["TEF.EU"].average_buy_price == Dezimal("3.618")
    assert by_ticker["TEF.EU"].initial_investment == Dezimal("3.62")


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


def _trade(
    ticker,
    trade_id="1",
    operation="Buy",
    commission=0,
    commission_currency=None,
    commission_comment="",
    currency="USD",
    sum_amount=15.15,
    price=15.15,
):
    return {
        "trade_id": trade_id,
        "date": "2026-01-02 10:00:00",
        "operation": operation,
        "sum": sum_amount,
        "q": 1,
        "p": price,
        "commission": commission,
        "commission_currency": commission_currency,
        "commission_comment": commission_comment,
        "ticker": ticker,
        "currency": currency,
    }


APLE_COMMENT = (
    " Market: usa, security type: stocks, commission currency: EUR, service plan: "
    "All inclusive in EUR, trade currency: USD.  The minimum commission per cent of "
    "the trade amount is set to: 0.5.  Currency exchange of trade (USD) to a currency "
    "exchange of the service plan (EUR) is 0.8604.  Additional commissions for a trade "
    "have been added:  Minimum per order in the currency of the tariff: 1.2 EUR.  The "
    "minimum fee per security in the transaction in the fee plan currency is set: EUR "
    "0.012.  Total additional commissions: 1.21 EUR "
)


def test_trade_fee_converts_commission_to_trade_currency():
    fee = _trade_fee(
        _trade(
            "APLE.US",
            commission=1.28,
            commission_currency="EUR",
            commission_comment=APLE_COMMENT,
        )
    )
    assert fee == Dezimal("1.49")


def test_trade_fee_same_currency_stays():
    fee = _trade_fee(
        _trade(
            "TEF.EU",
            commission=1.23,
            commission_currency="EUR",
            currency="EUR",
            sum_amount=3.62,
            price=3.618,
        )
    )
    assert fee == Dezimal("1.23")


def test_trade_fee_warns_when_fx_missing(caplog):
    fee = _trade_fee(
        _trade(
            "APLE.US",
            commission=1.28,
            commission_currency="EUR",
        )
    )
    assert fee == Dezimal("1.28")
    assert "no FX rate in comment" in caplog.text


@pytest.mark.asyncio
async def test_map_investment_txs_sets_equity_type():
    fetcher = _fetcher()
    fetcher._client.find_by_ticker = AsyncMock(
        side_effect=lambda ticker: {
            "CPNG.US": {
                "isin": "US22266T1097",
                "mkt": "US",
                "nm": "Coupang",
                "type": 1,
                "kind": 1,
            },
            "ERNE.EU": [
                {
                    "isin": "IE00BCRY6557",
                    "mkt": "EU",
                    "nm": "iShares Ultrashort Bond UCITS ETF EUR",
                    "type": 1,
                    "kind": 7,
                }
            ],
        }[ticker]
    )

    txs = await fetcher._map_investment_txs(
        [_trade("CPNG.US"), _trade("ERNE.EU", trade_id="2")],
        set(),
    )

    assert [tx.ticker for tx in txs] == ["CPNG.US", "ERNE.EU"]
    assert [tx.equity_type for tx in txs] == [EquityType.STOCK, EquityType.ETF]
    assert txs[0].type == TxType.BUY
    assert txs[0].product_type == ProductType.STOCK_ETF
    assert txs[0].fees == Dezimal(0)
    assert txs[0].amount == Dezimal("15.15")


@pytest.mark.asyncio
async def test_map_investment_txs_skips_currency_pairs():
    fetcher = _fetcher()
    fetcher._client.find_by_ticker = AsyncMock(
        return_value={
            "isin": "US22266T1097",
            "mkt": "US",
            "nm": "Coupang",
            "type": 1,
            "kind": 1,
        }
    )


def test_currency_pair_tickers_reads_nested_and_values():
    pairs = _currency_pair_tickers(
        {
            "result": {
                "tickers": {"GBP/EUR": "GBP/EUR", "RUR/USD": "RUR/USD.INT"},
                "fiat": ["EUR", "USD"],
            }
        }
    )
    assert "GBP/EUR" in pairs
    assert "RUR/USD.INT" in pairs


def test_is_currency_pair_even_without_api_list():
    assert _is_currency_pair("GBP/EUR", set())
    assert _is_currency_pair("RUR/USD.INT", set())
    assert not _is_currency_pair("CPNG.US", set())


@pytest.mark.asyncio
async def test_map_investment_txs_skips_fx_ticker_when_pairs_empty():
    fetcher = _fetcher()
    fetcher._client.get_allowed_currency_pairs = AsyncMock(return_value={})
    fetcher._client.find_by_ticker = AsyncMock(
        return_value={
            "isin": "US22266T1097",
            "mkt": "US",
            "nm": "Coupang",
            "type": 1,
            "kind": 1,
        }
    )

    txs = await fetcher._map_investment_txs(
        [
            _trade("GBP/EUR", trade_id="1", operation="Sell"),
            _trade("CPNG.US", trade_id="2"),
        ],
        set(),
    )

    assert [tx.ticker for tx in txs] == ["CPNG.US"]
    fetcher._client.find_by_ticker.assert_awaited_once_with("CPNG.US")
    assert [tx.ticker for tx in txs] == ["CPNG.US"]
    fetcher._client.find_by_ticker.assert_awaited_once_with("CPNG.US")


@pytest.mark.asyncio
async def test_map_investment_txs_skips_bond(caplog):
    fetcher = _fetcher()
    fetcher._client.find_by_ticker = AsyncMock(
        return_value={
            "isin": "XS0000000000",
            "mkt": "EU",
            "nm": "Some Bond",
            "type": 2,
            "kind": 9,
        }
    )

    txs = await fetcher._map_investment_txs([_trade("BOND.EU")], set())

    assert txs == []
    assert "unsupported type t=2 kind k=9" in caplog.text
