from unittest.mock import AsyncMock

import httpx
import pytest

from domain.dezimal import Dezimal
from domain.fetch_result import FetchOptions
from domain.global_position import EquityType, ProductType
from domain.transactions import TxType
from infrastructure.client.entity.financial.mintos.mintos_fetcher import MintosFetcher


@pytest.fixture
def fetcher():
    instance = MintosFetcher()
    instance._client = AsyncMock()
    instance._client.get_asset_accounts.return_value = {
        "accounts": {
            "SINGLE_ETF": {"id": "etf-account"},
            "CRYPTO_ETP": {"id": "crypto"},
        }
    }
    instance._client.get_etf_details.return_value = {
        "fundProvider": {"code": "HSBC", "title": "HSBC ETF"}
    }
    instance._client.get_etf_instrument_details.return_value = {}
    return instance


def instrument():
    return {
        "isin": "IE00B5L01S80",
        "name": "HSBC ETF",
        "attributes": {"ticker": "H4ZL"},
    }


def transaction(ref, tx_type):
    return {
        "id": ref,
        "type": tx_type,
        "instrument": instrument(),
        "totalAmount": {"amount": "2.49", "currency": "EUR"},
        "netAmount": {"amount": "2.49", "currency": "EUR"},
        "feeAmount": {"amount": "0", "currency": "EUR"},
        "createdAt": "2026-07-27T17:47:30.764344Z",
        "details": {"orderId": "order"},
    }


@pytest.mark.asyncio
async def test_global_position_includes_etf_and_existing_products(fetcher):
    fetcher._client.get_user.return_value = {
        "aggregates": [{"currency": 978, "accountBalance": "10"}]
    }
    fetcher._client.get_overview.return_value = {"loans": {"value": "20"}}
    fetcher._client.get_net_annual_returns.return_value = {
        "netAnnualReturnPercentage": "5"
    }
    fetcher._client.get_portfolio.return_value = {"totalInvestmentDistribution": {}}
    fetcher._client.get_asset_positions.return_value = [
        {
            "productType": "SINGLE_ETF",
            "instrument": instrument(),
            "shares": {
                "available": "0.1",
                "locked": "0.0120107962",
                "total": "0.1120107962",
            },
            "invested": {"amount": "2.49", "currency": "EUR"},
        }
    ]
    fetcher._client.get_etf_quotes.return_value = {
        "quotes": [{"ts": 2, "l": "20.41"}, {"ts": 1, "l": "22"}]
    }
    fetcher._client.get_etf_details.return_value = {
        "fundProvider": {"code": "HSBC", "title": "HSBC ETF"},
        "tradingVenue": "Tradegate",
    }
    fetcher._client.get_etf_instrument_details.return_value = {
        "kid": {"language": "es", "url": "https://example.test/kid"}
    }

    result = await fetcher.global_position()

    holding = result.products[ProductType.STOCK_ETF].entries[0]
    assert holding.type == EquityType.ETF
    assert holding.shares == Dezimal("0.1120107962")
    assert holding.initial_investment == Dezimal("2.49")
    assert holding.market_value == Dezimal("2.29")
    assert holding.currency == "EUR"
    assert holding.ticker == "H4ZL"
    assert holding.type == EquityType.ETF
    assert holding.issuer == "HSBC"
    assert holding.market == "Tradegate"
    assert holding.info_sheet_url == "https://example.test/kid"
    assert ProductType.ACCOUNT in result.products
    assert ProductType.CROWDLENDING in result.products
    fetcher._client.get_asset_positions.assert_awaited_once_with("etf-account")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "raw_type, expected_type", [("BUY_ORDER", TxType.BUY), ("SELL_ORDER", TxType.SELL)]
)
async def test_trade_execution_and_dividend(fetcher, raw_type, expected_type):
    trade = transaction("trade", raw_type)
    dividend = transaction("dividend", "CA_CASH")
    dividend.update(
        totalAmount={"amount": "0.01", "currency": "EUR"},
        netAmount={"amount": "0.01", "currency": "EUR"},
        details={
            "corporateAction": {"upvestTransactionType": "CASH_DIVIDEND"},
            "taxAmount": {"amount": "0"},
        },
    )
    fetcher._client.get_asset_transactions.return_value = [dividend, trade, trade]
    fetcher._client.get_asset_orders.return_value = [
        {
            "id": "order",
            "executed": {
                "shares": "0.1120107962",
                "sharePrice": {"amount": "22.23", "currency": "EUR"},
                "executedAt": "2026-07-27T17:47:30.764344Z",
            },
        }
    ]

    result = await fetcher.transactions(set(), FetchOptions())

    assert len(result.investment) == 2
    income, execution = result.investment
    assert income.type == TxType.DIVIDEND
    assert income.amount == income.net_amount == Dezimal("0.01")
    assert income.currency == "EUR"
    assert income.shares == income.price == Dezimal(0)
    assert execution.type == expected_type
    assert execution.shares == Dezimal("0.1120107962")
    assert execution.price == Dezimal("22.23")
    assert execution.amount == Dezimal("2.49")
    assert execution.equity_type == income.equity_type == EquityType.ETF
    assert execution.date.tzinfo is not None
    assert execution.order_date == execution.date
    assert income.order_date is None


@pytest.mark.asyncio
async def test_registered_and_unsupported_transactions_do_not_fetch_orders(fetcher):
    fetcher._client.get_asset_transactions.return_value = [
        transaction("known", "BUY_ORDER"),
        transaction("other", "CA_CASH"),
    ]
    result = await fetcher.transactions({"known"}, FetchOptions())
    assert result.investment == []
    fetcher._client.get_asset_orders.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_etf_account(fetcher):
    fetcher._client.get_asset_accounts.return_value = {
        "accounts": {"CRYPTO_ETP": {"id": "crypto"}}
    }
    assert await fetcher._build_etf_positions() == []
    assert (await fetcher.transactions(set(), FetchOptions())).investment == []
    fetcher._client.get_asset_positions.assert_not_awaited()
    fetcher._client.get_asset_transactions.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["productType", "instrument", "shares", "invested"])
@pytest.mark.parametrize("missing", [True, False])
async def test_malformed_asset_is_skipped(fetcher, caplog, field, missing):
    valid = {
        "productType": "SINGLE_ETF",
        "instrument": instrument(),
        "shares": {"total": "1"},
        "invested": {"amount": "22.23", "currency": "EUR"},
    }
    malformed = dict(valid)
    if missing:
        del malformed[field]
    else:
        malformed[field] = None
    fetcher._client.get_asset_positions.return_value = [malformed, valid]
    fetcher._client.get_etf_quotes.return_value = {"quotes": [{"ts": 1, "l": "20.41"}]}

    result = await fetcher._build_etf_positions()

    assert len(result) == 1
    if field != "productType" or missing:
        assert "Skipping Mintos ETF asset" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("quotes", [{}, {"quotes": []}, {"quotes": [{"ts": 1}]}])
async def test_missing_quote_fields_skip_only_affected_asset(fetcher, caplog, quotes):
    position = {
        "productType": "SINGLE_ETF",
        "instrument": instrument(),
        "shares": {"total": "1"},
        "invested": {"amount": "22.23", "currency": "EUR"},
    }
    fetcher._client.get_asset_positions.return_value = [position, position]
    fetcher._client.get_etf_quotes.side_effect = [
        quotes,
        {"quotes": [{"ts": 1, "l": "20"}]},
    ]

    assert len(await fetcher._build_etf_positions()) == 1
    assert "Skipping Mintos ETF asset" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field",
    [
        "id",
        "type",
        "instrument",
        "details",
        "totalAmount",
        "netAmount",
        "feeAmount",
        "createdAt",
    ],
)
async def test_missing_transaction_field_is_skipped(fetcher, caplog, field):
    valid = transaction("valid", "CA_CASH")
    valid["details"] = {"corporateAction": {"upvestTransactionType": "CASH_DIVIDEND"}}
    malformed = dict(valid, id="malformed")
    del malformed[field]
    fetcher._client.get_asset_transactions.return_value = [malformed, valid]

    result = await fetcher.transactions(set(), FetchOptions())

    assert [entry.ref for entry in result.investment] == ["valid"]
    assert "Skipping Mintos ETF transaction" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "execution", [None, {}, {"shares": "1"}, {"shares": "1", "sharePrice": None}]
)
async def test_missing_trade_execution_fields_are_skipped(fetcher, caplog, execution):
    malformed = transaction("retry", "BUY_ORDER")
    malformed["details"] = {"orderId": "broken"}
    valid = transaction("retry", "BUY_ORDER")
    fetcher._client.get_asset_transactions.return_value = [malformed, valid]
    fetcher._client.get_asset_orders.return_value = [
        {},
        {"id": "broken", "executed": execution},
        {
            "id": "order",
            "executed": {
                "shares": "1",
                "sharePrice": {"amount": "22.23"},
                "executedAt": "2026-07-27T17:47:30.764344Z",
            },
        },
    ]

    result = await fetcher.transactions(set(), FetchOptions())

    assert [entry.ref for entry in result.investment] == ["retry"]
    assert result.investment[0].shares == Dezimal(1)
    assert "Skipping Mintos ETF transaction" in caplog.text
    assert "Skipping Mintos ETF order" in caplog.text
    fetcher._client.get_asset_orders.assert_awaited_once()


@pytest.mark.asyncio
async def test_http_failure_is_not_silently_skipped(fetcher):
    fetcher._client.get_asset_transactions.return_value = [
        transaction("trade", "BUY_ORDER")
    ]
    fetcher._client.get_asset_orders.side_effect = httpx.ReadTimeout("Timed out")

    with pytest.raises(httpx.ReadTimeout):
        await fetcher.transactions(set(), FetchOptions())
