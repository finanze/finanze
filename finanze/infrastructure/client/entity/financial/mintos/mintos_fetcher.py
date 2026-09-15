import logging
from datetime import datetime
from uuid import uuid4

from application.ports.financial_entity_fetcher import FinancialEntityFetcher
from domain.dezimal import Dezimal
from domain.fetch_record import DataSource
from domain.fetch_result import FetchOptions
from domain.native_entity import EntitySetupLoginType
from domain.entity_login import EntityLoginParams, EntityLoginResult, LoginResultCode
from domain.global_position import (
    Account,
    Accounts,
    AccountType,
    Crowdlending,
    EquityType,
    GlobalPosition,
    ProductType,
    StockDetail,
    StockInvestments,
)
from domain.instrument_issuer import resolve_issuer
from domain.native_entities import MINTOS
from domain.transactions import StockTx, Transactions, TxType
from infrastructure.client.entity.financial.mintos.mintos_client import MintosAPIClient

CURRENCY_ID_MAPPING = {
    203: "CZK",
    978: "EUR",
    208: "DKK",
    826: "GBP",
    981: "GEL",
    398: "KZT",
    484: "MXN",
    985: "PLN",
    946: "RON",
    643: "RUB",
    752: "SEK",
    840: "USD",
}

ORDER_TX_TYPE_MAPPING = {
    "BUY_ORDER": TxType.BUY,
    "SELL_ORDER": TxType.SELL,
}

CORPORATE_ACTION_TX_TYPE_MAPPING = {
    "CASH_DIVIDEND": TxType.DIVIDEND,
}


def map_loan_distribution(input_json: dict) -> dict:
    mapping = {
        "active": {"count_key": "activeCount", "sum_key": "activeSum"},
        "gracePeriod": {
            "count_key": "delayedWithinGracePeriodCount",
            "sum_key": "delayedWithinGracePeriodSum",
        },
        "late1_15": {"count_key": "late115Count", "sum_key": "late115Sum"},
        "late16_30": {"count_key": "late1630Count", "sum_key": "late1630Sum"},
        "late31_60": {"count_key": "late3160Count", "sum_key": "late3160Sum"},
        "default": {"count_key": "defaultCount", "sum_key": "defaultSum"},
        "badDebt": {"count_key": "badDebtCount", "sum_key": "badDebtSum"},
        "recovery": {"count_key": "recoveryCount", "sum_key": "recoverySum"},
        "total": {"count_key": "totalCount", "sum_key": "totalSum"},
    }

    output_json = {}
    for key, value in mapping.items():
        count = input_json.get(value["count_key"], 0)
        sum_value = input_json.get(value["sum_key"], 0)

        output_json[key] = {"total": round(Dezimal(sum_value), 2), "count": count}

    return output_json


class MintosFetcher(FinancialEntityFetcher):
    def __init__(self):
        self._log = logging.getLogger(__name__)
        self._client = MintosAPIClient()
        if self._client.automated_login:
            MINTOS.setup_login_type = EntitySetupLoginType.AUTOMATED

    async def login(self, login_params: EntityLoginParams) -> EntityLoginResult:
        credentials = login_params.credentials
        username, password = credentials["user"], credentials["password"]
        if self._client.automated_login:
            return await self._client.login(username, password)

        elif "cookie" not in credentials and not self._client.has_completed_login():
            if login_params.options.avoid_new_login:
                return EntityLoginResult(code=LoginResultCode.NOT_LOGGED)

            return EntityLoginResult(
                code=LoginResultCode.MANUAL_LOGIN, details=credentials
            )

        cookie_header = credentials.get("cookie")
        return await self._client.complete_login(cookie_header)

    async def global_position(self) -> GlobalPosition:
        user_json = await self._client.get_user()
        wallet = user_json["aggregates"][0]
        wallet_currency_id = wallet["currency"]
        currency_iso = CURRENCY_ID_MAPPING[wallet_currency_id]
        balance = wallet["accountBalance"]

        overview_json = await self._client.get_overview(wallet_currency_id)
        loans = overview_json["loans"]["value"]

        overview_net_annual_returns_json = await self._client.get_net_annual_returns(
            wallet_currency_id
        )
        net_annual_returns = overview_net_annual_returns_json[
            "netAnnualReturnPercentage"
        ]

        portfolio_data_json = await self._client.get_portfolio(wallet_currency_id)
        total_investment_distribution = portfolio_data_json[
            "totalInvestmentDistribution"
        ]

        account_data = Account(
            id=uuid4(),
            total=round(Dezimal(balance), 2),
            currency=currency_iso,
            type=AccountType.VIRTUAL_WALLET,
        )

        accounts = [account_data]

        smart_cash_account = await self._build_smart_cash_account(
            overview_json, currency_iso
        )
        if smart_cash_account is not None:
            accounts.append(smart_cash_account)

        loan_distribution = map_loan_distribution(total_investment_distribution)
        crowdlending = Crowdlending(
            id=uuid4(),
            total=round(Dezimal(loans), 2),
            weighted_interest_rate=round(Dezimal(net_annual_returns) / 100, 4),
            currency=currency_iso,
            distribution=loan_distribution,
            entries=[],
        )

        products = {
            ProductType.ACCOUNT: Accounts(accounts),
            ProductType.CROWDLENDING: crowdlending,
        }

        etfs = await self._build_etf_positions()
        if etfs:
            products[ProductType.STOCK_ETF] = StockInvestments(etfs)

        return GlobalPosition(
            id=uuid4(),
            entity=MINTOS,
            products=products,
        )

    async def _get_etf_account_id(self) -> str | None:
        response = await self._client.get_asset_accounts()
        account = response["accounts"].get("SINGLE_ETF")
        return account["id"] if account else None

    async def _build_etf_positions(self) -> list[StockDetail]:
        account_id = await self._get_etf_account_id()
        if account_id is None:
            return []

        entries = []
        for position in await self._client.get_asset_positions(account_id):
            try:
                if position["productType"] != "SINGLE_ETF":
                    continue
                shares = Dezimal(position["shares"]["total"])
                if shares <= 0:
                    continue
                instrument = position["instrument"]
                isin = instrument["isin"]
                quotes = await self._client.get_etf_quotes(isin)
                latest_quote = max(quotes["quotes"], key=lambda quote: quote["ts"])
                details = await self._client.get_etf_details(isin) or {}
                instrument_details = (
                    await self._client.get_etf_instrument_details(isin) or {}
                )
                fund_provider = details.get("fundProvider") or {}
                issuer = resolve_issuer(
                    fund_provider.get("title") or fund_provider.get("code"),
                    instrument["name"],
                )
                entries.append(
                    StockDetail(
                        id=uuid4(),
                        name=instrument["name"],
                        isin=instrument["isin"],
                        ticker=instrument.get("attributes", {}).get("ticker", ""),
                        shares=shares,
                        initial_investment=Dezimal(position["invested"]["amount"]),
                        market_value=round(shares * Dezimal(latest_quote["l"]), 2),
                        currency=position["invested"]["currency"],
                        type=EquityType.ETF,
                        market=details.get("tradingVenue") or "",
                        issuer=issuer,
                        info_sheet_url=(instrument_details.get("kid") or {}).get("url"),
                    )
                )
            except (KeyError, TypeError, ValueError, AttributeError) as error:
                self._log.warning(
                    "Skipping Mintos ETF asset due to invalid or missing fields: %s",
                    error,
                )
        return entries

    async def transactions(
        self, registered_txs: set[str], options: FetchOptions
    ) -> Transactions:
        account_id = await self._get_etf_account_id()
        if account_id is None:
            return Transactions(investment=[])

        raw_txs = await self._client.get_asset_transactions(account_id)
        orders = None
        entries = []
        seen_refs = set(registered_txs)
        for raw_tx in raw_txs:
            try:
                if raw_tx["id"] in seen_refs:
                    continue
                tx_type = self._get_etf_tx_type(raw_tx)
                if tx_type is None:
                    continue

                execution = None
                if tx_type in (TxType.BUY, TxType.SELL):
                    if orders is None:
                        orders = await self._get_etf_orders(account_id)
                    order_id = raw_tx.get("orderId") or raw_tx["details"]["orderId"]
                    execution = orders[order_id]["executed"]

                entries.append(self._map_etf_transaction(raw_tx, tx_type, execution))
                seen_refs.add(raw_tx["id"])
            except (KeyError, TypeError, ValueError, AttributeError) as error:
                self._log.warning(
                    "Skipping Mintos ETF transaction due to invalid or missing fields: %s",
                    error,
                )
        return Transactions(investment=entries)

    async def _get_etf_orders(self, account_id: str) -> dict[str, dict]:
        orders = {}
        for order in await self._client.get_asset_orders(account_id):
            try:
                orders[order["id"]] = order
            except (KeyError, TypeError) as error:
                self._log.warning(
                    "Skipping Mintos ETF order due to invalid or missing fields: %s",
                    error,
                )
        return orders

    @staticmethod
    def _get_etf_tx_type(raw_tx: dict) -> TxType | None:
        if raw_tx["type"] == "CA_CASH":
            corporate_action = raw_tx["details"].get("corporateAction", {})
            return CORPORATE_ACTION_TX_TYPE_MAPPING.get(
                corporate_action.get("upvestTransactionType")
            )
        return ORDER_TX_TYPE_MAPPING.get(raw_tx["type"])

    @staticmethod
    def _map_etf_transaction(
        raw_tx: dict, tx_type: TxType, execution: dict | None
    ) -> StockTx:
        instrument = raw_tx["instrument"]
        details = raw_tx["details"]
        if tx_type in (TxType.BUY, TxType.SELL):
            if not execution:
                raise ValueError("Missing trade execution")
            shares = Dezimal(execution["shares"])
            price = Dezimal(execution["sharePrice"]["amount"])
            date = execution["executedAt"]
            order_date = raw_tx["createdAt"]
        else:
            shares = Dezimal(0)
            price = Dezimal(0)
            date = raw_tx["createdAt"]
            order_date = None

        return StockTx(
            id=uuid4(),
            ref=raw_tx["id"],
            name=instrument["name"],
            isin=instrument["isin"],
            ticker=instrument.get("attributes", {}).get("ticker"),
            amount=Dezimal(raw_tx["totalAmount"]["amount"]),
            net_amount=Dezimal(raw_tx["netAmount"]["amount"]),
            currency=raw_tx["totalAmount"]["currency"],
            fees=Dezimal(raw_tx["feeAmount"]["amount"]),
            retentions=Dezimal(details.get("taxAmount", {}).get("amount", 0)),
            shares=shares,
            price=price,
            date=datetime.fromisoformat(date).astimezone(),
            order_date=(
                datetime.fromisoformat(order_date).astimezone() if order_date else None
            ),
            type=tx_type,
            entity=MINTOS,
            source=DataSource.REAL,
            product_type=ProductType.STOCK_ETF,
            equity_type=EquityType.ETF,
        )

    async def _build_smart_cash_account(
        self, overview_json: dict, currency_iso: str
    ) -> Account | None:
        smart_cash = overview_json.get("smartCash") or {}
        raw_value = smart_cash.get("value")
        if raw_value is None:
            return None

        try:
            smart_cash_total = round(Dezimal(raw_value), 2)
        except (ValueError, TypeError):
            return None

        if not smart_cash_total > 0:
            return None

        interest = None
        fund_json = await self._client.get_smart_cash_fund()
        raw_interest = fund_json.get("interestRatePercentage")
        if raw_interest is not None:
            try:
                interest = round(Dezimal(raw_interest) / 100, 6)
            except (ValueError, TypeError):
                interest = None

        return Account(
            id=uuid4(),
            total=smart_cash_total,
            currency=currency_iso,
            type=AccountType.SAVINGS,
            interest=interest,
        )
