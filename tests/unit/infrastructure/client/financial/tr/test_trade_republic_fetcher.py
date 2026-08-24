from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from domain.dezimal import Dezimal
from domain.entity_login import (
    EntityLoginParams,
    EntityLoginResult,
    LoginResultCode,
    TwoFactor,
)
from domain.fetch_result import FetchOptions
from domain.global_position import (
    FundType,
    ProductType,
    StockDetail,
)
from domain.public_keychain import PublicKeychain
from domain.transactions import StockTx
from infrastructure.client.entity.financial.tr.trade_republic_fetcher import (
    TradeRepublicFetcher,
)


def _make_fetcher():
    fetcher = TradeRepublicFetcher()
    fetcher._client = MagicMock()
    return fetcher


def _make_keychain():
    return MagicMock(spec=PublicKeychain)


class TestFetcherLogin:
    @pytest.mark.asyncio
    async def test_login_delegates_to_client(self):
        fetcher = _make_fetcher()
        expected = EntityLoginResult(LoginResultCode.MANUAL_LOGIN)
        fetcher._client.login = AsyncMock(return_value=expected)

        params = EntityLoginParams(
            credentials={"phone": "+49123", "password": "1234"},
            keychain=_make_keychain(),
        )
        result = await fetcher.login(params)

        assert result.code == LoginResultCode.MANUAL_LOGIN
        fetcher._client.login.assert_called_once()

    @pytest.mark.asyncio
    async def test_login_with_process_id_and_no_code_calls_complete_login(self):
        fetcher = _make_fetcher()
        expected = EntityLoginResult(LoginResultCode.CREATED)
        fetcher._client.complete_login = AsyncMock(return_value=expected)

        params = EntityLoginParams(
            credentials={"phone": "+49123", "password": "1234", "awsWafToken": "waf"},
            keychain=_make_keychain(),
            two_factor=TwoFactor(process_id="proc-123"),
        )
        result = await fetcher.login(params)

        assert result.code == LoginResultCode.CREATED
        fetcher._client.complete_login.assert_called_once_with("proc-123", "waf")
        fetcher._client.login.assert_not_called()

    @pytest.mark.asyncio
    async def test_login_with_process_id_and_code_delegates_to_login(self):
        fetcher = _make_fetcher()
        expected = EntityLoginResult(LoginResultCode.CREATED)
        fetcher._client.login = AsyncMock(return_value=expected)

        params = EntityLoginParams(
            credentials={"phone": "+49123", "password": "1234", "awsWafToken": "waf"},
            keychain=_make_keychain(),
            two_factor=TwoFactor(process_id="proc-123", code="654321"),
        )
        result = await fetcher.login(params)

        assert result.code == LoginResultCode.CREATED
        fetcher._client.login.assert_called_once()


class TestFetcherCancelLogin:
    def test_cancel_login_delegates_to_client(self):
        fetcher = _make_fetcher()
        fetcher._client.cancel_login = MagicMock()

        fetcher.cancel_login()

        fetcher._client.cancel_login.assert_called_once()


def _stock_position(isin="US0378331005", instrument_type="STOCK"):
    return {
        "instrumentId": isin,
        "instrumentType": instrument_type,
        "averageBuyIn": "100",
        "netSize": "2",
        "netValue": "250.50",
    }


def _stock_details(
    isin="US0378331005",
    name="Apple Inc.",
    ticker="AAPL",
    stock_details=None,
    fund_details=None,
    etf_details=None,
):
    return SimpleNamespace(
        instrument={
            "name": name,
            "homeSymbol": ticker,
            "exchangeIds": ["LSX"],
            "isin": isin,
        },
        stock_details=stock_details
        if stock_details is not None
        else {"company": {"name": name, "tickerSymbol": ticker}},
        fund_details=fund_details,
        etf_details=etf_details,
    )


def _portfolio(positions, cash=None):
    return SimpleNamespace(
        cash=cash if cash is not None else [{"currencyId": "EUR", "amount": "1000"}],
        portfolio=positions,
    )


def _setup_position_client(fetcher, positions, details_by_isin, user_info=None):
    fetcher._client.get_user_info = AsyncMock(
        return_value=user_info if user_info is not None else {}
    )
    fetcher._client.get_portfolio = AsyncMock(return_value=_portfolio(positions))
    fetcher._client.get_active_interest_rate = AsyncMock(
        side_effect=Exception("unavailable")
    )
    fetcher._client.get_portfolio_by_type = AsyncMock(return_value={"categories": []})
    fetcher._client.get_private_markets_portfolio_status = AsyncMock(
        return_value={"hasInvested": False, "status": "INACTIVE"}
    )
    fetcher._client.close = AsyncMock()

    async def get_details(isin, types=None):
        details = details_by_isin.get(isin)
        if isinstance(details, Exception):
            raise details
        return details

    fetcher._client.get_details = AsyncMock(side_effect=get_details)


class TestFetcherGlobalPositionHardening:
    @pytest.mark.asyncio
    async def test_unsupported_and_unknown_positions_skipped_siblings_kept(self):
        fetcher = _make_fetcher()
        positions = [
            _stock_position("BOND1", "BOND"),
            _stock_position("DERIV1", "DERIVATIVE"),
            _stock_position("UNK1", "WARRANT"),
            _stock_position("US0378331005", "STOCK"),
        ]
        _setup_position_client(
            fetcher,
            positions,
            {"US0378331005": _stock_details()},
        )

        position = await fetcher.global_position()
        stocks = position.products[ProductType.STOCK_ETF].entries
        assert len(stocks) == 1
        assert stocks[0].isin == "US0378331005"
        assert stocks[0].market_value == Dezimal("250.5")
        assert position.products[ProductType.FUND].entries == []

    @pytest.mark.asyncio
    async def test_private_fund_position_mapped_as_private_equity(self):
        fetcher = _make_fetcher()
        positions = [
            {
                "instrumentId": "PE1",
                "instrumentType": "PRIVATEFUND",
                "averageBuyIn": "100",
                "netSize": "2",
                "pendingAmounts": [{"amount": "50"}],
            },
            _stock_position(),
        ]
        _setup_position_client(
            fetcher,
            positions,
            {"US0378331005": _stock_details()},
        )
        fetcher._client.get_instrument_details = AsyncMock(
            return_value={"name": "Private Markets Fund", "kidLink": "https://kid"}
        )

        position = await fetcher.global_position()
        funds = position.products[ProductType.FUND].entries
        assert len(funds) == 1
        assert funds[0].isin == "PE1"
        assert funds[0].type == FundType.PRIVATE_EQUITY
        assert funds[0].market_value == Dezimal("250")
        assert len(position.products[ProductType.STOCK_ETF].entries) == 1

    @pytest.mark.asyncio
    async def test_net_value_present_sets_market_value(self):
        fetcher = _make_fetcher()
        _setup_position_client(
            fetcher,
            [_stock_position()],
            {"US0378331005": _stock_details()},
        )

        position = await fetcher.global_position()
        stock = position.products[ProductType.STOCK_ETF].entries[0]
        assert isinstance(stock, StockDetail)
        assert stock.market_value == Dezimal("250.5")
        assert stock.shares == Dezimal("2")

    @pytest.mark.asyncio
    async def test_missing_stock_details_falls_back_to_instrument_identity(self):
        fetcher = _make_fetcher()
        _setup_position_client(
            fetcher,
            [_stock_position()],
            {
                "US0378331005": _stock_details(stock_details={}),
            },
        )

        position = await fetcher.global_position()
        stock = position.products[ProductType.STOCK_ETF].entries[0]
        assert stock.name == "Apple Inc."
        assert stock.ticker == "AAPL"

    @pytest.mark.asyncio
    async def test_missing_fund_type_and_crypto_symbol_skipped_siblings_kept(self):
        fetcher = _make_fetcher()
        positions = [
            {
                "instrumentId": "FUND1",
                "instrumentType": "MUTUALFUND",
                "averageBuyIn": "10",
                "netSize": "5",
                "netValue": "60",
            },
            {
                "instrumentId": "CRYPTO1",
                "instrumentType": "CRYPTO",
                "averageBuyIn": "10",
                "netSize": "1",
                "netValue": "20",
            },
            _stock_position(),
        ]
        _setup_position_client(
            fetcher,
            positions,
            {
                "FUND1": _stock_details(
                    isin="FUND1",
                    name="Broken Fund",
                    ticker=None,
                    stock_details={},
                    fund_details={"name": "Broken Fund"},
                ),
                "CRYPTO1": _stock_details(
                    isin="CRYPTO1",
                    name="Bitcoin",
                    ticker=None,
                    stock_details={},
                ),
                "US0378331005": _stock_details(),
            },
        )

        position = await fetcher.global_position()
        assert len(position.products[ProductType.STOCK_ETF].entries) == 1
        assert position.products[ProductType.FUND].entries == []
        assert position.products[ProductType.CRYPTO].entries[0].assets == []

    @pytest.mark.asyncio
    async def test_mapper_exception_does_not_abort_global_position(self):
        fetcher = _make_fetcher()
        positions = [
            _stock_position("BADISIN"),
            _stock_position("US0378331005"),
        ]
        _setup_position_client(
            fetcher,
            positions,
            {
                "BADISIN": RuntimeError("details failed"),
                "US0378331005": _stock_details(),
            },
        )

        position = await fetcher.global_position()
        stocks = position.products[ProductType.STOCK_ETF].entries
        assert [stock.isin for stock in stocks] == ["US0378331005"]

    @pytest.mark.asyncio
    async def test_private_markets_error_still_returns_position(self):
        fetcher = _make_fetcher()
        _setup_position_client(
            fetcher,
            [_stock_position()],
            {"US0378331005": _stock_details()},
            user_info={"securitiesAccountNumber": "sec-1"},
        )
        fetcher._client.get_private_markets_portfolio_status = AsyncMock(
            side_effect=Exception("private markets down")
        )

        position = await fetcher.global_position()
        assert len(position.products[ProductType.STOCK_ETF].entries) == 1


class TestFetcherTransactionsHardening:
    def _buy_tx(self, tx_id="tx-stock", isin="US0378331005"):
        return {
            "id": tx_id,
            "title": "Apple",
            "subtitle": "Buy",
            "status": "EXECUTED",
            "eventType": "ORDER_EXECUTED",
            "timestamp": "2024-01-15T10:00:00+00:00",
            "amount": {"currency": "EUR", "value": "-200.00"},
            "icon": f"logos/{isin}/v2",
            "details": {
                "sections": [
                    {
                        "title": "Transaction",
                        "data": [
                            {"title": "Shares", "detail": {"text": "2"}},
                            {"title": "Fee", "detail": {"text": "1.00"}},
                            {"title": "Tax", "detail": {"text": "0"}},
                        ],
                    }
                ]
            },
        }

    @pytest.mark.asyncio
    async def test_missing_overview_or_transaction_section_skips_tx(self):
        fetcher = _make_fetcher()
        raw_tx = self._buy_tx()
        raw_tx["details"] = {"sections": [{"title": "Übersicht", "data": []}]}
        fetcher._client.get_instrument_details = AsyncMock(
            return_value={"typeId": "STOCK"}
        )
        fetcher._client.get_transactions = AsyncMock(return_value=[raw_tx])
        fetcher._client.close = AsyncMock()

        txs = await fetcher.transactions(set(), FetchOptions())
        assert txs.investment == []
        assert txs.account == []

    @pytest.mark.asyncio
    async def test_bond_and_derivative_txs_skipped_not_stock_tx(self):
        fetcher = _make_fetcher()
        bond_tx = self._buy_tx("tx-bond", "DE0001102309")
        deriv_tx = self._buy_tx("tx-deriv", "DE000ABC1234")
        stock_tx = self._buy_tx()

        async def instrument_details(isin):
            mapping = {
                "DE0001102309": {"typeId": "BOND"},
                "DE000ABC1234": {"typeId": "DERIVATIVE"},
                "US0378331005": {"typeId": "STOCK"},
            }
            return mapping[isin]

        fetcher._client.get_instrument_details = AsyncMock(
            side_effect=instrument_details
        )
        fetcher._client.get_transactions = AsyncMock(
            return_value=[bond_tx, deriv_tx, stock_tx]
        )
        fetcher._client.close = AsyncMock()

        txs = await fetcher.transactions(set(), FetchOptions())
        assert len(txs.investment) == 1
        assert isinstance(txs.investment[0], StockTx)
        assert txs.investment[0].ref == "tx-stock"
        assert txs.investment[0].isin == "US0378331005"


class TestFetcherAutoContributionsHardening:
    @pytest.mark.asyncio
    async def test_savings_plans_none_returns_empty(self):
        fetcher = _make_fetcher()
        fetcher._client.get_portfolio = AsyncMock(
            return_value=SimpleNamespace(cash=[], portfolio=[])
        )
        fetcher._client.get_saving_plans = AsyncMock(return_value=None)
        fetcher._client.close = AsyncMock()

        contributions = await fetcher.auto_contributions()
        assert contributions.periodic == []

    @pytest.mark.asyncio
    async def test_savings_plans_null_list_returns_empty(self):
        fetcher = _make_fetcher()
        fetcher._client.get_portfolio = AsyncMock(
            return_value=SimpleNamespace(cash=None, portfolio=[])
        )
        fetcher._client.get_saving_plans = AsyncMock(
            return_value={"savingsPlans": None}
        )
        fetcher._client.close = AsyncMock()

        contributions = await fetcher.auto_contributions()
        assert contributions.periodic == []


class TestFetcherCloseLifecycle:
    @pytest.mark.asyncio
    async def test_close_delegates_to_client(self):
        fetcher = _make_fetcher()
        fetcher._client.close = AsyncMock()

        await fetcher.close()

        fetcher._client.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_feature_methods_leave_client_open(self):
        fetcher = _make_fetcher()
        _setup_position_client(
            fetcher,
            [_stock_position()],
            {"US0378331005": _stock_details()},
        )
        fetcher._client.get_transactions = AsyncMock(return_value=[])
        fetcher._client.get_saving_plans = AsyncMock(return_value={"savingsPlans": []})

        await fetcher.global_position()
        await fetcher.transactions(set(), FetchOptions())
        await fetcher.auto_contributions()

        fetcher._client.close.assert_not_awaited()
