import httpx
import pytest

from domain.dezimal import Dezimal
from domain.fetch_result import FetchOptions
from domain.global_position import EquityType, ProductType
from domain.transactions import TxType
from infrastructure.client.entity.financial.mintos.mintos_fetcher import MintosFetcher
from infrastructure.client.http.http_session import HttpSession


@pytest.mark.asyncio
async def test_mintos_etf_http_flow():
    instrument = {
        "isin": "IE00B5L01S80",
        "name": "HSBC FTSE EPRA NAREIT Developed UCITS ETF USD",
        "attributes": {"ticker": "H4ZL"},
    }
    execution_date = "2026-07-27T17:47:30.764344Z"
    responses = {
        "/en/webapp-api/user": {
            "aggregates": [{"currency": 978, "accountBalance": "10"}]
        },
        "/marketplace-api/v1/user/overview/currency/978": {"loans": {"value": "0"}},
        "/marketplace-api/v1/accounts/978/net-annual-return": {
            "netAnnualReturnPercentage": "0"
        },
        "/marketplace-api/v1/user/overview/currency/978/portfolio-data": {
            "totalInvestmentDistribution": {}
        },
        "/assetx-api/v1/accounts": {
            "accounts": {"SINGLE_ETF": {"id": "account", "status": "ACTIVE"}}
        },
        "/assetx-api/v1/accounts/account/positions": {
            "content": [
                {
                    "instrument": instrument,
                    "productType": "SINGLE_ETF",
                    "shares": {"total": "0.1120107962"},
                    "invested": {"amount": "2.49", "currency": "EUR"},
                }
            ],
            "metadata": {"hasNext": False},
        },
        "/assetx-price-api/v1/history/quotes/IE00B5L01S80": {
            "quotes": [{"l": "20.41", "ts": 1788800601}]
        },
        "/assetx-price-api/v1/instruments/etf/IE00B5L01S80": {
            "fundProvider": {"code": "HSBC", "title": "HSBC ETF"},
            "tradingVenue": "Tradegate",
        },
        "/assetx-api/v1/instruments/IE00B5L01S80": {
            "instrument": instrument,
            "kid": {
                "language": "es",
                "url": "https://solutions.vwdservices.com/products/documents/kid",
            },
        },
        "/assetx-api/v1/accounts/account/transactions": {
            "content": [
                {
                    "id": "buy",
                    "instrument": instrument,
                    "type": "BUY_ORDER",
                    "totalAmount": {"amount": "2.49", "currency": "EUR"},
                    "netAmount": {"amount": "2.49", "currency": "EUR"},
                    "feeAmount": {"amount": "0", "currency": "EUR"},
                    "createdAt": execution_date,
                    "details": {"orderId": "order"},
                },
                {
                    "id": "dividend",
                    "instrument": instrument,
                    "type": "CA_CASH",
                    "totalAmount": {"amount": "0.01", "currency": "EUR"},
                    "netAmount": {"amount": "0.01", "currency": "EUR"},
                    "feeAmount": {"amount": "0", "currency": "EUR"},
                    "createdAt": "2026-08-21T13:07:23.158200Z",
                    "details": {
                        "corporateAction": {"upvestTransactionType": "CASH_DIVIDEND"},
                        "taxAmount": {"amount": "0", "currency": "EUR"},
                    },
                },
            ],
            "metadata": {"hasNext": False},
        },
        "/assetx-api/v1/accounts/account/orders": {
            "content": [
                {
                    "id": "order",
                    "status": "EXECUTED",
                    "executed": {
                        "shares": "0.1120107962",
                        "sharePrice": {"amount": "22.23", "currency": "EUR"},
                        "executedAt": execution_date,
                    },
                }
            ],
            "metadata": {"hasNext": False},
        },
    }

    def handle_request(request):
        path = request.url.path.removeprefix("/webapp/api")
        if path.endswith(("/positions", "/orders", "/transactions")):
            assert dict(request.url.params) == {"page": "0", "size": "30"}
        if "/history/quotes/" in path:
            assert request.url.params["range"] == "ONE_DAY"
        if path == "/assetx-api/v1/instruments/IE00B5L01S80":
            assert request.url.params["productType"] == "SINGLE_ETF"
        return httpx.Response(200, json=responses[path])

    fetcher = MintosFetcher()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handle_request)
    ) as client:
        fetcher._client._session = HttpSession(client)
        position = await fetcher.global_position()
        transactions = await fetcher.transactions(set(), FetchOptions())
        repeated = await fetcher.transactions({"buy", "dividend"}, FetchOptions())

    holding = position.products[ProductType.STOCK_ETF].entries[0]
    assert holding.type == EquityType.ETF
    assert holding.market_value == Dezimal("2.29")
    assert holding.initial_investment == Dezimal("2.49")
    assert holding.issuer == "HSBC"
    assert holding.market == "Tradegate"
    assert (
        holding.info_sheet_url
        == "https://solutions.vwdservices.com/products/documents/kid"
    )
    buy, dividend = transactions.investment
    assert buy.type == TxType.BUY
    assert buy.shares == holding.shares
    assert buy.price == Dezimal("22.23")
    assert buy.order_date == buy.date
    assert dividend.type == TxType.DIVIDEND
    assert dividend.net_amount == Dezimal("0.01")
    assert dividend.order_date is None
    assert repeated.investment == []
