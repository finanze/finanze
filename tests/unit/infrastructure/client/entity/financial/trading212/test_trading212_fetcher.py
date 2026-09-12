from unittest.mock import AsyncMock, MagicMock

import pytest

from domain.dezimal import Dezimal
from domain.entity_login import EntityLoginParams, EntityLoginResult, LoginResultCode
from domain.fetch_result import FetchOptions
from domain.global_position import (
    AccountType,
    EquityType,
    ProductType,
)
from domain.public_keychain import PublicKeychain
from domain.transactions import TxType
from infrastructure.client.entity.financial.trading212.trading212_fetcher import (
    Trading212Fetcher,
    _get_ref,
)


def _instruments():
    return [
        {
            "ticker": "AAPL_US_EQ",
            "type": "STOCK",
            "isin": "US0378331005",
            "name": "Apple",
            "shortName": "AAPL",
        },
        {
            "ticker": "VWCE_EQ",
            "type": "ETF",
            "isin": "IE00BK5BQT80",
            "name": "Vanguard FTSE",
            "shortName": "VWCE",
        },
        {
            "ticker": "SOME_WARRANT",
            "type": "WARRANT",
            "isin": "XX0000000001",
            "name": "Warrant",
            "shortName": "SOME",
        },
    ]


def _fetcher():
    fetcher = Trading212Fetcher()
    fetcher._client = MagicMock()
    fetcher._client.get_instruments = AsyncMock(return_value=_instruments())
    fetcher._client.iter_history_orders = MagicMock(return_value=_agen([]))
    fetcher._client.iter_history_dividends = MagicMock(return_value=_agen([]))
    fetcher._client.iter_history_transactions = MagicMock(return_value=_agen([]))
    return fetcher


async def _agen(pages):
    for page in pages:
        yield page


def _login_params(api_key="key", secret_key="secret"):
    return EntityLoginParams(
        credentials={"apiKey": api_key, "secretKey": secret_key},
        keychain=MagicMock(spec=PublicKeychain),
    )


def _summary():
    return {
        "id": 42,
        "currency": "EUR",
        "cash": {
            "availableToTrade": "10",
            "inPies": "2",
            "reservedForOrders": "3",
        },
    }


def _stock_position():
    return {
        "ticker": "AAPL_US_EQ",
        "quantity": "2",
        "averagePricePaid": "150",
        "instrument": {
            "name": "Apple",
            "isin": "US0378331005",
            "ticker": "AAPL_US_EQ",
        },
        "walletImpact": {
            "currentValue": "400",
            "totalCost": "300",
            "currency": "EUR",
        },
    }


def _trade_order(
    fill_id, side="BUY", quantity="2", fill_type="TRADE", net_value="-300"
):
    return {
        "order": {
            "id": fill_id,
            "side": side,
            "status": "FILLED",
            "ticker": "AAPL_US_EQ",
            "createdAt": "2024-01-01T00:00:00Z",
            "instrument": {
                "name": "Apple",
                "isin": "US0378331005",
                "ticker": "AAPL_US_EQ",
            },
        },
        "fill": {
            "id": fill_id,
            "type": fill_type,
            "quantity": quantity,
            "price": "150",
            "filledAt": "2024-01-02T00:00:00Z",
            "walletImpact": {
                "netValue": net_value,
                "currency": "EUR",
                "taxes": [{"quantity": "1"}],
            },
        },
    }


@pytest.mark.asyncio
async def test_login_delegates_to_setup():
    fetcher = _fetcher()
    fetcher._client.setup = AsyncMock(
        return_value=EntityLoginResult(LoginResultCode.CREATED)
    )
    result = await fetcher.login(_login_params())
    assert result.code == LoginResultCode.CREATED
    fetcher._client.setup.assert_awaited_once_with("key", "secret")


@pytest.mark.asyncio
async def test_global_position_maps_cash_stock_and_etf():
    fetcher = _fetcher()
    fetcher._client.get_account_summary = AsyncMock(return_value=_summary())
    fetcher._client.get_positions = AsyncMock(
        return_value=[
            _stock_position(),
            {
                "ticker": "VWCE_EQ",
                "quantity": "1",
                "averagePricePaid": "100",
                "instrument": {
                    "name": "Vanguard FTSE",
                    "isin": "IE00BK5BQT80",
                    "ticker": "VWCE_EQ",
                },
                "walletImpact": {
                    "currentValue": "120",
                    "totalCost": "100",
                    "currency": "EUR",
                },
            },
            {
                "ticker": "BTC_USD_CR",
                "quantity": "0.5",
                "averagePricePaid": "20000",
                "instrument": {"name": "Bitcoin", "ticker": "BTC_USD_CR"},
                "walletImpact": {
                    "currentValue": "15000",
                    "totalCost": "10000",
                    "currency": "EUR",
                },
            },
            {
                "ticker": "SOME_WARRANT",
                "quantity": "1",
                "averagePricePaid": "1",
                "instrument": {"name": "Warrant", "isin": "XX0000000001"},
                "walletImpact": {
                    "currentValue": "1",
                    "totalCost": "1",
                    "currency": "EUR",
                },
            },
        ]
    )

    position = await fetcher.global_position()
    accounts = position.products[ProductType.ACCOUNT].entries
    stocks = position.products[ProductType.STOCK_ETF].entries

    assert accounts[0].total == Dezimal("15")
    assert accounts[0].retained == Dezimal("5")
    assert accounts[0].type == AccountType.BROKERAGE
    assert accounts[0].name == "42"

    assert len(stocks) == 2
    apple = next(s for s in stocks if s.isin == "US0378331005")
    etf = next(s for s in stocks if s.isin == "IE00BK5BQT80")
    assert apple.type == EquityType.STOCK
    assert apple.ticker == "AAPL"
    assert apple.market == "US"
    assert apple.shares == Dezimal("2")
    assert etf.type == EquityType.ETF
    assert etf.ticker == "VWCE"
    assert ProductType.CRYPTO not in position.products


@pytest.mark.asyncio
async def test_global_position_skips_zero_cash():
    fetcher = _fetcher()
    fetcher._client.get_account_summary = AsyncMock(
        return_value={"currency": "EUR", "cash": {}}
    )
    fetcher._client.get_positions = AsyncMock(return_value=[])
    position = await fetcher.global_position()
    assert ProductType.ACCOUNT not in position.products
    assert ProductType.STOCK_ETF not in position.products


@pytest.mark.asyncio
async def test_transactions_map_buy_sell_dividend_and_cash():
    fetcher = _fetcher()
    fetcher._client.iter_history_orders = MagicMock(
        return_value=_agen(
            [
                [
                    _trade_order(1, side="BUY", quantity="2", net_value="-300"),
                    _trade_order(2, side="SELL", quantity="-1", net_value="160"),
                ]
            ]
        )
    )
    fetcher._client.iter_history_dividends = MagicMock(
        return_value=_agen(
            [
                [
                    {
                        "reference": "div-1",
                        "ticker": "AAPL_US_EQ",
                        "amount": "1.5",
                        "currency": "EUR",
                        "quantity": "2",
                        "paidOn": "2024-03-01T00:00:00Z",
                        "instrument": {
                            "name": "Apple",
                            "isin": "US0378331005",
                            "ticker": "AAPL_US_EQ",
                        },
                    }
                ]
            ]
        )
    )
    fetcher._client.iter_history_transactions = MagicMock(
        return_value=_agen(
            [
                [
                    {
                        "reference": "cash-1",
                        "type": "FEE",
                        "amount": "-1.5",
                        "currency": "EUR",
                        "dateTime": "2024-01-01T00:00:00Z",
                    },
                    {
                        "reference": "cash-2",
                        "type": "INTEREST_ON_FREE_CASH",
                        "amount": "0.4",
                        "currency": "EUR",
                        "dateTime": "2024-01-02T00:00:00Z",
                    },
                    {
                        "reference": "cash-3",
                        "type": "DEPOSIT",
                        "amount": "100",
                        "currency": "EUR",
                        "dateTime": "2024-01-03T00:00:00Z",
                    },
                    {
                        "reference": "cash-4",
                        "type": "WITHDRAW",
                        "amount": "-20",
                        "currency": "EUR",
                        "dateTime": "2024-01-04T00:00:00Z",
                    },
                    {
                        "reference": "cash-5",
                        "type": "TRANSFER",
                        "amount": "50",
                        "currency": "EUR",
                        "dateTime": "2024-01-05T00:00:00Z",
                    },
                ]
            ]
        )
    )

    txs = await fetcher.transactions(set(), FetchOptions())
    buys = [tx for tx in txs.investment if tx.type == TxType.BUY]
    sells = [tx for tx in txs.investment if tx.type == TxType.SELL]
    dividends = [tx for tx in txs.investment if tx.type == TxType.DIVIDEND]
    assert len(buys) == 1
    assert buys[0].shares == Dezimal("2")
    assert buys[0].amount == Dezimal("300")
    assert sells[0].type == TxType.SELL
    assert sells[0].shares == Dezimal("1")
    assert dividends[0].amount == Dezimal("1.5")
    assert {tx.type for tx in txs.account} == {TxType.FEE, TxType.INTEREST}
    assert all(
        tx.type not in {TxType.TRANSFER_IN, TxType.TRANSFER_OUT} for tx in txs.account
    )


@pytest.mark.asyncio
async def test_acquisition_maps_to_share_swap_only():
    fetcher = _fetcher()
    fetcher._client.iter_history_orders = MagicMock(
        return_value=_agen(
            [
                [
                    _trade_order(
                        11,
                        quantity="-10",
                        fill_type="STOCK_ACQUISITION",
                        net_value="0",
                    ),
                    _trade_order(
                        12,
                        quantity="5",
                        fill_type="CASH_AND_STOCK_ACQUISITION",
                        net_value="25",
                    ),
                ]
            ]
        )
    )
    txs = await fetcher.transactions(set(), FetchOptions())
    swaps = [
        tx for tx in txs.investment if tx.type in {TxType.SWAP_FROM, TxType.SWAP_TO}
    ]
    assert len(swaps) == 2
    assert any(
        tx.type == TxType.SWAP_FROM and tx.shares == Dezimal("10") for tx in swaps
    )
    assert any(tx.type == TxType.SWAP_TO and tx.shares == Dezimal("5") for tx in swaps)
    assert all(tx.amount == Dezimal(0) for tx in swaps)
    assert txs.account == []


@pytest.mark.asyncio
async def test_split_maps_to_swap():
    fetcher = _fetcher()
    fetcher._client.iter_history_orders = MagicMock(
        return_value=_agen(
            [[_trade_order(21, quantity="10", fill_type="STOCK_SPLIT", net_value="0")]]
        )
    )
    txs = await fetcher.transactions(set(), FetchOptions())
    assert len(txs.investment) == 1
    assert txs.investment[0].type == TxType.SWAP_TO
    assert txs.investment[0].ticker == "AAPL"
    assert txs.investment[0].amount == Dezimal(0)


@pytest.mark.asyncio
async def test_spin_off_is_skipped():
    fetcher = _fetcher()
    fetcher._client.iter_history_orders = MagicMock(
        return_value=_agen(
            [[_trade_order(31, quantity="1", fill_type="SPIN_OFF", net_value="0")]]
        )
    )
    txs = await fetcher.transactions(set(), FetchOptions())
    assert txs.investment == []
    assert txs.account == []


@pytest.mark.asyncio
async def test_registered_refs_are_deduped():
    fetcher = _fetcher()
    fetcher._client.iter_history_orders = MagicMock(
        return_value=_agen([[_trade_order(41)]])
    )
    known = {_get_ref("order", 41)}
    txs = await fetcher.transactions(known, FetchOptions())
    assert txs.investment == []


@pytest.mark.asyncio
async def test_pagination_stops_unless_deep():
    page1 = [_trade_order(51)]
    page2 = [_trade_order(52)]
    fetcher = _fetcher()
    fetcher._client.iter_history_orders = MagicMock(return_value=_agen([page1, page2]))
    known = {_get_ref("order", 51)}
    shallow = await fetcher.transactions(known, FetchOptions(deep=False))
    assert shallow.investment == []

    fetcher._client.iter_history_orders = MagicMock(return_value=_agen([page1, page2]))
    deep = await fetcher.transactions(known, FetchOptions(deep=True))
    assert len(deep.investment) == 1
    assert deep.investment[0].ref == _get_ref("order", 52)


@pytest.mark.asyncio
async def test_unexecuted_orders_are_skipped():
    fetcher = _fetcher()
    pending = {
        "order": {
            "id": 99,
            "side": "BUY",
            "status": "NEW",
            "ticker": "AAPL_US_EQ",
            "quantity": "2",
            "createdAt": "2024-01-01T00:00:00Z",
            "instrument": {
                "name": "Apple",
                "isin": "US0378331005",
                "ticker": "AAPL_US_EQ",
            },
        }
    }
    unfilled = {
        "order": {
            "id": 100,
            "side": "BUY",
            "ticker": "AAPL_US_EQ",
            "quantity": "2",
            "createdAt": "2024-01-01T00:00:00Z",
            "instrument": {
                "name": "Apple",
                "isin": "US0378331005",
                "ticker": "AAPL_US_EQ",
            },
        },
        "fill": {},
    }
    fetcher._client.iter_history_orders = MagicMock(
        return_value=_agen([[pending, unfilled, _trade_order(101)]])
    )
    txs = await fetcher.transactions(set(), FetchOptions())
    assert len(txs.investment) == 1
    assert txs.investment[0].ref == _get_ref("order", 101)


@pytest.mark.asyncio
async def test_crypto_positions_and_trades_are_skipped():
    fetcher = _fetcher()
    fetcher._client.get_account_summary = AsyncMock(return_value=_summary())
    fetcher._client.get_positions = AsyncMock(
        return_value=[
            {
                "ticker": "BTC_USD_CR",
                "quantity": "0.25",
                "averagePricePaid": "40000",
                "instrument": {"name": "Bitcoin", "ticker": "BTC_USD_CR"},
                "walletImpact": {
                    "currentValue": "12000",
                    "totalCost": "10000",
                    "currency": "EUR",
                },
            }
        ]
    )
    position = await fetcher.global_position()
    assert ProductType.CRYPTO not in position.products
    assert ProductType.STOCK_ETF not in position.products

    order = _trade_order(61)
    order["order"]["ticker"] = "BTC_USD_CR"
    order["order"]["instrument"] = {"name": "Bitcoin", "ticker": "BTC_USD_CR"}
    fetcher._client.iter_history_orders = MagicMock(return_value=_agen([[order]]))
    txs = await fetcher.transactions(set(), FetchOptions())
    assert txs.investment == []
