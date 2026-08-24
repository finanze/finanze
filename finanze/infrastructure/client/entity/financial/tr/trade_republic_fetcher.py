import logging
import re
from datetime import datetime
from typing import Optional
from uuid import uuid4

from application.ports.financial_entity_fetcher import FinancialEntityFetcher
from domain.auto_contributions import (
    AutoContributions,
    ContributionFrequency,
    ContributionTargetSubtype,
    ContributionTargetType,
    PeriodicContribution,
)
from domain.crypto import CryptoCurrencyType
from domain.dezimal import Dezimal
from domain.entity_login import EntityLoginParams, EntityLoginResult
from domain.fetch_record import DataSource
from domain.fetch_result import FetchOptions
from domain.global_position import (
    Account,
    Accounts,
    AccountType,
    AssetType,
    CryptoCurrencies,
    CryptoCurrencyPosition,
    CryptoCurrencyWallet,
    EquityType,
    FundDetail,
    FundInvestments,
    FundType,
    GlobalPosition,
    ProductType,
    StockDetail,
    StockInvestments,
)
from domain.instrument_issuer import resolve_issuer
from domain.native_entities import TRADE_REPUBLIC
from domain.transactions import (
    AccountTx,
    CryptoCurrencyTx,
    FundTx,
    StockTx,
    Transactions,
    TxType,
)
from infrastructure.client.entity.financial.tr.trade_republic_client import (
    TradeRepublicClient,
)
from domain.status import FFStatus

FALLBACK_LOCALE = "en"


def parse_sub_section_float(section: dict, fallback_locale: str) -> Optional[Dezimal]:
    if not section:
        return None

    value = section.get("detail", {}).get("text")
    if value is None:
        return None
    if "free" in value.strip().lower():
        return Dezimal(0)
    return parse_float(value, fallback_locale)


def infer_locale_from_section(section: dict) -> str | None:
    if not section:
        return None

    value = section.get("detail", {}).get("text")
    if value is None:
        return None
    return infer_locale(value)


def infer_locale(value: str, fallback: str = FALLBACK_LOCALE) -> str:
    value = value.replace("\xa0", "").replace(" ", "").strip()
    currency_symbol_pattern = r"^[^\d\-]+|[^\d\-]+$"
    symbols = re.findall(currency_symbol_pattern, value)
    # If currency symbols
    if symbols:
        if value.startswith(symbols[0]):
            return "en"
        else:
            return "de"

    # If no symbols, check number format
    trailing_decimals = re.findall(r"[.,](\d*)$", value)
    trailing_decimals = len(trailing_decimals[0]) if trailing_decimals else 0
    commas_dots = re.findall(r"[.,]", value)
    if len(commas_dots) == 1:
        if commas_dots[0] == ".":
            if 1 <= trailing_decimals <= 2 or trailing_decimals > 3:
                return "en"
            elif trailing_decimals == 3:
                return (
                    fallback if fallback else "de"
                )  # 900.557 could be either 900.557 or 900,557.00, we assume "de"
        else:
            if 1 <= trailing_decimals <= 2 or trailing_decimals > 3:
                return "de"
            elif trailing_decimals == 3:
                return (
                    fallback if fallback else "de"
                )  # 900,557 could be either 900.557 or 900,557.00, we assume "de"
    elif len(commas_dots) > 1:
        if 1 <= trailing_decimals <= 2:
            if commas_dots[-1] == ".":
                return "en"
            else:
                return "de"
        else:
            return "de" if commas_dots[0] == "." else "en"

    # If no decimals
    return "en"  # We assume "en" as it's the one we use in the client


def parse_float(value: str, fallback_locale: str) -> Dezimal:
    value = re.sub(r"[^\d,.\-]", "", value)
    locale = infer_locale(value, fallback_locale)
    if locale == "en":
        value = value.replace(",", "")
    else:
        value = value.replace(".", "").replace(",", ".")

    return Dezimal(value)


def get_section(d, title):
    if not d:
        return None
    for section in d:
        if title.lower() in section.get("title", "").lower():
            return section
    return None


def _as_dezimal(value) -> Optional[Dezimal]:
    if value is None or value == "":
        return None
    if isinstance(value, dict):
        value = value.get("value")
        if value is None or value == "":
            return None
    return Dezimal(value)


DATE_FORMAT = "%Y-%m-%d"

CONTRIBUTION_FREQUENCY = {
    "weekly": ContributionFrequency.WEEKLY,
    "twoPerMonth": ContributionFrequency.BIWEEKLY,
    "monthly": ContributionFrequency.MONTHLY,
    "quarterly": ContributionFrequency.QUARTERLY,
}


class TradeRepublicFetcher(FinancialEntityFetcher):
    DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%f%z"
    SUPPORTED_INSTRUMENT_TYPES = {
        "FUND",
        "STOCK",
        "CRYPTO",
        "MUTUALFUND",
        "PRIVATEFUND",
    }
    UNSUPPORTED_INSTRUMENT_TYPES = {"BOND", "DERIVATIVE"}

    def __init__(self):
        self._client = TradeRepublicClient()
        self._log = logging.getLogger(__name__)

    async def _safe_await(self, awaitable, context: str, identifier: str | None = None):
        try:
            return await awaitable
        except Exception:
            self._log.warning(
                "Skipping Trade Republic %s %s due to mapping error",
                context,
                identifier or "",
                exc_info=True,
            )
            return None

    def cancel_login(self) -> None:
        self._client.cancel_login()

    async def close(self) -> None:
        await self._client.close()

    async def login(self, login_params: EntityLoginParams) -> EntityLoginResult:
        credentials = login_params.credentials
        two_factor = login_params.two_factor

        phone, pin = credentials["phone"], credentials["password"]
        waf_token = credentials.get("awsWafToken")
        process_id, code = None, None
        if two_factor:
            process_id, code = two_factor.process_id, two_factor.code

        use_v2 = (login_params.feature_flags or {}).get("TR_V2_AUTH_API") == FFStatus.ON

        if process_id and not code:
            return await self._client.complete_login(process_id, waf_token)

        return await self._client.login(
            phone,
            pin,
            login_options=login_params.options,
            process_id=process_id,
            code=code,
            waf_token=waf_token,
            session=login_params.session,
            use_v2=use_v2,
        )

    async def _map_private_equity(
        self, position: dict, currency: str
    ) -> Optional[FundDetail]:
        isin = position.get("instrumentId")
        if not isin:
            self._log.warning("No ISIN found for private equity instrument")
            return None

        self._log.info(position)
        details = await self._client.get_instrument_details(isin) or {}

        average_buy = round(_as_dezimal(position.get("averageBuyIn")) or Dezimal(0), 4)
        shares = _as_dezimal(position.get("netSize")) or Dezimal(0)
        initial_investment = round(average_buy * shares, 4)
        raw_pending_amounts = position.get("pendingAmounts") or []
        total_pending_amount = Dezimal(0)
        for pending in raw_pending_amounts:
            amount_value = _as_dezimal((pending or {}).get("amount")) or Dezimal(0)
            total_pending_amount += amount_value

        initial_investment += total_pending_amount
        market_value = initial_investment

        name = details.get("name") or position.get("instrumentName")
        if not name:
            self._log.warning("No name found for private equity instrument %s", isin)
            return None
        kid_url = details.get("kidLink")

        raw_issuer = details.get("issuer")
        issuer = resolve_issuer(raw_issuer, name)

        return FundDetail(
            id=uuid4(),
            name=name,
            isin=isin,
            market=None,
            shares=shares,
            initial_investment=initial_investment,
            average_buy_price=average_buy,
            market_value=market_value,
            info_sheet_url=kid_url,
            type=FundType.PRIVATE_EQUITY,
            asset_type=AssetType.OTHER,
            currency=currency,
            issuer=issuer,
        )

    async def _instrument_mapper(
        self, instrument: dict, currency: str
    ) -> Optional[StockDetail | FundDetail | CryptoCurrencyPosition]:
        isin = instrument.get("instrumentId") or instrument.get("isin")
        instrument_type = (instrument.get("instrumentType") or "").upper()
        if instrument_type in self.UNSUPPORTED_INSTRUMENT_TYPES:
            self._log.warning(
                "Skipping unsupported instrument type: %s for ISIN %s",
                instrument_type,
                isin,
            )
            return None
        if instrument_type not in self.SUPPORTED_INSTRUMENT_TYPES:
            self._log.warning(
                "Unknown instrument type: %s for ISIN %s",
                instrument_type,
                isin,
            )
            return None

        if instrument_type == "PRIVATEFUND":
            return await self._map_private_equity(instrument, currency)

        average_buy = _as_dezimal(instrument.get("averageBuyIn"))
        shares = _as_dezimal(instrument.get("netSize"))
        if average_buy is None or shares is None:
            self._log.warning(
                "Incomplete position data for ISIN %s type %s", isin, instrument_type
            )
            return None
        average_buy = round(average_buy, 4)
        net_value = _as_dezimal(instrument.get("netValue"))
        initial_investment = round(average_buy * shares, 4)

        detail_topics = ["instrument"]
        if instrument_type == "MUTUALFUND":
            detail_topics.append("mutualFundDetails")
        elif instrument_type == "FUND":
            detail_topics.append("etfDetails")
        elif instrument_type == "STOCK":
            detail_topics.append("stockDetails")

        details = await self._client.get_details(isin, detail_topics)
        instrument_details = (details.instrument or {}) if details else {}
        if not instrument_details:
            self._log.warning("No instrument details for ISIN %s", isin)
            return None

        if net_value is None:
            exchange_ids = instrument_details.get("exchangeIds") or []
            if exchange_ids:
                ticker_data = await self._client.ticker(isin, exchange=exchange_ids[0])
                last_price = _as_dezimal(
                    ((ticker_data or {}).get("last") or {}).get("price")
                )
                net_value = (
                    last_price * shares
                    if last_price is not None
                    else initial_investment
                )
            else:
                net_value = initial_investment

        market_value = (
            round(net_value, 4) if net_value is not None else initial_investment
        )

        name = instrument_details.get("name")
        ticker = instrument_details.get("homeSymbol")
        subtype = ""
        type_id = instrument_type
        issuer = None
        exchange_ids = instrument_details.get("exchangeIds") or []
        market = ", ".join(exchange_ids)

        if instrument_type == "FUND":
            type_id = "ETF"
            if details.etf_details:
                raw_issuer = details.etf_details.get("issuer")
                issuer = resolve_issuer(raw_issuer, name)

        elif instrument_type == "CRYPTO":
            if not ticker:
                self._log.warning("Crypto symbol not found for ISIN %s", isin)
                return None
            return CryptoCurrencyPosition(
                id=uuid4(),
                name=name,
                amount=shares,
                symbol=ticker,
                type=CryptoCurrencyType.NATIVE,
                initial_investment=initial_investment,
                average_buy_price=average_buy,
                market_value=market_value,
                currency=currency,
                investment_currency=currency,
            )

        elif instrument_type == "STOCK":
            company = (details.stock_details or {}).get("company") or {}
            name = company.get("name") or name
            ticker = company.get("tickerSymbol") or ticker

        elif instrument_type == "MUTUALFUND":
            fund_details = details.fund_details
            if not fund_details or not fund_details.get("fundType"):
                self._log.warning("Incomplete mutual fund details for ISIN %s", isin)
                return None
            name = fund_details.get("name") or name
            if not name:
                self._log.warning("No name for mutual fund ISIN %s", isin)
                return None
            fund_type = fund_details["fundType"].lower()
            kid_url = instrument_details.get("kidLink")
            asset_type = AssetType.OTHER
            if "equity" in fund_type:
                asset_type = AssetType.EQUITY
            elif "bond" in fund_type:
                asset_type = AssetType.FIXED_INCOME
            elif "money" in fund_type:
                asset_type = AssetType.MONEY_MARKET

            raw_issuer = fund_details.get("issuer")
            issuer = resolve_issuer(raw_issuer, name)

            return FundDetail(
                id=uuid4(),
                name=name,
                isin=isin,
                market=market or None,
                shares=shares,
                initial_investment=initial_investment,
                average_buy_price=average_buy,
                market_value=market_value,
                info_sheet_url=kid_url,
                type=FundType.MUTUAL_FUND,
                asset_type=asset_type,
                currency=currency,
                issuer=issuer,
            )

        if not name or not ticker:
            self._log.warning(
                "Incomplete instrument identity for ISIN %s type %s",
                isin,
                instrument_type,
            )
            return None

        if not subtype:
            subtype = instrument_type

        equity_type = EquityType.STOCK if type_id == "STOCK" else EquityType.ETF

        return StockDetail(
            id=uuid4(),
            name=name,
            ticker=ticker,
            isin=isin,
            market=market,
            shares=shares,
            initial_investment=initial_investment,
            average_buy_price=average_buy,
            market_value=market_value,
            currency=currency,
            type=equity_type,
            subtype=subtype,
            issuer=issuer,
        )

    async def global_position(self) -> GlobalPosition:
        user_info = await self._client.get_user_info()
        cash_account = user_info.get("cashAccount")
        iban = None
        if cash_account:
            iban = cash_account.get("iban")

        raw_portfolio = await self._client.get_portfolio()

        try:
            # This works sometimes, throws 401 :(, wrong param?, or is this only available in mobile app?
            cash_acc_num = raw_portfolio.cash[0].get("accountNumber")
            active_interest = round(
                Dezimal(
                    (await self._client.get_active_interest_rate(cash_acc_num)).get(
                        "activeInterestRate"
                    )
                )
                / 100,
                4,
            )
        except Exception as e:
            self._log.error(f"Could not fetch active interest rate: {e}")
            active_interest = None

        accounts = []
        currency = None
        for account in raw_portfolio.cash or []:
            currency = account.get("currencyId")
            if not currency:
                self._log.warning("Skipping cash account without currency")
                continue
            cash_total = Dezimal(account.get("amount") or 0)
            accounts.append(
                Account(
                    id=uuid4(),
                    total=cash_total,
                    interest=active_interest,
                    currency=currency,
                    iban=iban,
                    type=AccountType.CHECKING,
                )
            )

        investments = []
        for position in raw_portfolio.portfolio or []:
            identifier = position.get("instrumentId") or position.get("isin")
            investment = await self._safe_await(
                self._instrument_mapper(position, currency),
                "position",
                identifier,
            )
            if investment:
                investments.append(investment)

        securities_account_number = user_info.get("securitiesAccountNumber")
        if securities_account_number:
            try:
                securities_portfolio = await self._client.get_portfolio_by_type(
                    securities_account_number
                )
            except Exception:
                self._log.warning(
                    "Could not fetch Trade Republic securities portfolio",
                    exc_info=True,
                )
                securities_portfolio = None

            for category in (securities_portfolio or {}).get("categories", []):
                for position in category.get("positions", []):
                    identifier = position.get("instrumentId") or position.get("isin")
                    investment = await self._safe_await(
                        self._instrument_mapper(position, currency),
                        "position",
                        identifier,
                    )
                    if investment:
                        investments.append(investment)

            try:
                pm_status = await self._client.get_private_markets_portfolio_status()
            except Exception:
                self._log.warning(
                    "Could not fetch Trade Republic private markets status",
                    exc_info=True,
                )
                pm_status = None
            if (
                pm_status
                and pm_status.get("hasInvested")
                and pm_status.get("status") == "ACTIVE"
            ):
                try:
                    private_markets_portfolio = (
                        await self._client.get_private_markets_portfolio(
                            securities_account_number
                        )
                    )
                except Exception:
                    self._log.warning(
                        "Could not fetch Trade Republic private markets portfolio",
                        exc_info=True,
                    )
                    private_markets_portfolio = None
                pm_positions = (private_markets_portfolio or {}).get("positions", [])
                for position in pm_positions:
                    identifier = position.get("instrumentId")
                    investment = await self._safe_await(
                        self._map_private_equity(position, currency),
                        "private equity position",
                        identifier,
                    )
                    if investment:
                        investments.append(investment)

        stocks = [i for i in investments if isinstance(i, StockDetail)]
        funds = [i for i in investments if isinstance(i, FundDetail)]
        crypto = [i for i in investments if isinstance(i, CryptoCurrencyPosition)]

        products = {
            ProductType.ACCOUNT: Accounts(accounts),
            ProductType.STOCK_ETF: StockInvestments(stocks),
            ProductType.FUND: FundInvestments(funds),
            ProductType.CRYPTO: CryptoCurrencies([CryptoCurrencyWallet(assets=crypto)]),
        }

        return GlobalPosition(
            id=uuid4(),
            entity=TRADE_REPUBLIC,
            products=products,
        )

    TRADE_TX_TYPES = [
        "TRADE_INVOICE",
        "ORDER_EXECUTED",
        "TRADING_TRADE_EXECUTED",
        "MUTUAL_FUND_TRADE_EXECUTED",
        "SAVINGS_PLAN_EXECUTED",
        "TRADING_SAVGINSPLAN_EXECUTED",
        "PRIVATE_MARKETS_ORDER_CREATED",
        "TRADE_CORRECTED",
    ]

    ACCOUNT_INTEREST_TX_TYPES = [
        "INTEREST_PAYOUT",
        "INTEREST_PAYOUT_CREATED",
    ]

    DIVIDEND_TX_TYPES = [
        "SSP_CORPORATE_ACTION_INVOICE_CASH",
        "CREDIT",
        "SSP_CORPORATE_ACTION_CASH",
    ]

    OTHER_TX_TYPES = [
        "TIMELINE_LEGACY_MIGRATED_EVENTS",
    ]

    HANDLED_TX_TYPES = (
        ACCOUNT_INTEREST_TX_TYPES + TRADE_TX_TYPES + DIVIDEND_TX_TYPES + OTHER_TX_TYPES
    )

    async def transactions(
        self, registered_txs: set[str], options: FetchOptions
    ) -> Transactions:
        raw_txs = await self._client.get_transactions(
            already_registered_ids=registered_txs
        )

        investment_txs = []
        account_txs = []
        for raw_tx in raw_txs or []:
            tx_id = raw_tx.get("id")
            if tx_id in registered_txs:
                continue

            status = raw_tx.get("status", None)
            event_type = raw_tx.get("eventType", None)
            if not (
                status == "EXECUTED"
                and (not event_type or event_type.upper() in self.HANDLED_TX_TYPES)
            ):
                continue

            title = raw_tx.get("title", None)
            date = self._parse_tx_date(raw_tx)
            if date is None:
                continue

            try:
                if event_type in self.ACCOUNT_INTEREST_TX_TYPES or title in [
                    "Interest"
                ]:
                    mapped_tx = self.map_account_tx(raw_tx, date)
                    if mapped_tx:
                        account_txs.append(mapped_tx)
                else:
                    mapped_tx = await self.map_investment_tx(raw_tx, date)
                    if mapped_tx:
                        investment_txs.append(mapped_tx)
            except Exception:
                self._log.warning(
                    "Skipping Trade Republic transaction %s due to mapping error",
                    tx_id,
                    exc_info=True,
                )

        return Transactions(investment=investment_txs, account=account_txs)

    def _parse_tx_date(self, raw_tx: dict) -> Optional[datetime]:
        timestamp = raw_tx.get("timestamp")
        if not timestamp:
            self._log.warning(
                "No timestamp for Trade Republic transaction %s", raw_tx.get("id")
            )
            return None
        try:
            return datetime.strptime(timestamp, self.DATETIME_FORMAT)
        except ValueError:
            try:
                return datetime.fromisoformat(timestamp)
            except ValueError:
                self._log.warning(
                    "Could not parse Trade Republic transaction timestamp %s for %s",
                    timestamp,
                    raw_tx.get("id"),
                )
                return None

    async def _map_saving_plan(
        self, saving_plan: dict, currency: str
    ) -> Optional[PeriodicContribution]:
        raw_amount = saving_plan.get("amount")
        isin = saving_plan.get("instrumentId")
        raw_saving_interval = saving_plan.get("interval")
        if not isin or not raw_amount or not raw_saving_interval:
            self._log.warning("Incomplete saving plan data")
            return None

        amount = round(Dezimal(raw_amount), 2)
        currency = saving_plan.get("currency") or currency

        frequency = CONTRIBUTION_FREQUENCY.get(raw_saving_interval)
        if not frequency:
            self._log.warning(f"Unknown contribution frequency: {frequency}")
            return None

        target_subtype = None
        raw_target_type = saving_plan.get("instrumentType")
        if raw_target_type == "stock":
            target_type = ContributionTargetType.STOCK_ETF
            target_subtype = ContributionTargetSubtype.STOCK
        elif raw_target_type == "crypto":
            target_type = ContributionTargetType.CRYPTO
        elif raw_target_type == "fund":
            target_type = ContributionTargetType.STOCK_ETF
            target_subtype = ContributionTargetSubtype.ETF
        elif raw_target_type in ("mutualFund", "privateFund"):
            target_type = ContributionTargetType.FUND
            if raw_target_type == "mutualFund":
                target_subtype = ContributionTargetSubtype.MUTUAL_FUND
            else:
                target_subtype = ContributionTargetSubtype.PRIVATE_EQUITY
        else:
            self._log.warning(f"Unknown contribution target type: {raw_target_type}")
            return None

        active = not saving_plan.get("paused")
        raw_start_date = saving_plan.get("startDate")
        if not raw_start_date:
            self._log.warning("No start date in saving plan")
            return None

        start_date_type = raw_start_date.get("type")
        if start_date_type == "dayOfMonth":
            since_str = raw_start_date.get("nextExecutionDate")
            since = datetime.strptime(since_str, DATE_FORMAT).date()
            if not since:
                self._log.warning("No start date in saving plan")
                return None
        else:
            self._log.warning(f"Unknown start date type: {start_date_type}")
            return None

        isin_details = await self._client.get_instrument_details(isin) or {}
        instrument_name = (
            isin_details.get("name")
            if raw_target_type == "privateFund"
            else isin_details.get("shortName")
        )
        if not instrument_name:
            self._log.warning("No name for saving plan instrument %s", isin)
            return None

        return PeriodicContribution(
            id=uuid4(),
            alias=instrument_name,
            target=isin,
            target_name=instrument_name,
            target_type=target_type,
            target_subtype=target_subtype,
            amount=amount,
            currency=currency,
            since=since,
            until=None,
            frequency=frequency,
            active=active,
            source=DataSource.REAL,
        )

    async def auto_contributions(self) -> AutoContributions:
        portfolio_details = await self._client.get_portfolio()
        saving_plans_response = await self._client.get_saving_plans()

        cash = getattr(portfolio_details, "cash", None) or []
        user_currency = cash[0].get("currencyId") if cash else None

        saving_plans = (saving_plans_response or {}).get("savingsPlans") or []

        contributions = []
        for saving_plan in saving_plans:
            if not saving_plan:
                continue
            identifier = saving_plan.get("instrumentId")
            contribution = await self._safe_await(
                self._map_saving_plan(saving_plan, user_currency),
                "saving plan",
                identifier,
            )
            if contribution:
                contributions.append(contribution)

        return AutoContributions(periodic=contributions)

    async def map_investment_tx(
        self, raw_tx: dict, date: datetime
    ) -> Optional[StockTx | FundTx | CryptoCurrencyTx]:
        name = (raw_tx.get("title") or "").strip()
        subtitle = (raw_tx.get("subtitle") or "").strip().lower()
        amount_obj = raw_tx.get("amount") or {}
        currency = amount_obj.get("currency")
        raw_amount_value = amount_obj.get("value")
        event_type = (raw_tx.get("eventType") or "").strip().upper()
        if not amount_obj or not currency or not raw_amount_value:
            self._log.warning("Incomplete transaction data: %s", raw_tx.get("id"))
            return None

        net_amount_val = round(Dezimal(raw_amount_value), 2)
        net_amount = abs(net_amount_val)

        if net_amount_val > 0 and "sell" in subtitle:
            tx_type = TxType.SELL
        elif (
            net_amount_val < 0 and "buy" in subtitle
        ) or "saving executed" in subtitle:
            tx_type = TxType.BUY
        elif event_type in self.DIVIDEND_TX_TYPES:
            tx_type = TxType.DIVIDEND
        else:
            self._log.warning(f"Unknown transaction type: {subtitle}")
            return None

        detail_sections = (raw_tx.get("details") or {}).get("sections") or []

        isin = self._get_tx_isin(raw_tx, detail_sections)
        if not isin:
            self._log.warning(f"No ISIN found for transaction: {raw_tx['id']}")
            self._log.debug(detail_sections)
            return None

        instrument_details = await self._client.get_instrument_details(isin) or {}
        raw_type = (instrument_details.get("typeId") or "").upper()
        product_subtype: FundType | EquityType | None = None
        product_type: ProductType

        if raw_type == "STOCK":
            product_type = ProductType.STOCK_ETF
            product_subtype = EquityType.STOCK

        elif raw_type == "CRYPTO":
            product_type = ProductType.CRYPTO

        elif raw_type == "FUND":
            product_type = ProductType.STOCK_ETF
            product_subtype = EquityType.ETF

        elif raw_type == "MUTUALFUND":
            product_type = ProductType.FUND
            product_subtype = FundType.MUTUAL_FUND

        elif raw_type == "PRIVATEFUND":
            product_type = ProductType.FUND
            product_subtype = FundType.PRIVATE_EQUITY
            extra_name = instrument_details.get("name", "")
            if extra_name:
                name += " - " + extra_name

        elif raw_type in self.UNSUPPORTED_INSTRUMENT_TYPES:
            self._log.warning(
                "Skipping unsupported product type: %s for ISIN %s",
                raw_type,
                isin,
            )
            return None

        else:
            self._log.warning(f"Unknown product type: {raw_type} for ISIN {isin}")
            return None

        parent_tx_section = get_section(detail_sections, "Transaction")
        if not parent_tx_section:
            parent_tx_section = get_section(detail_sections, "Overview")
        if not parent_tx_section or "data" not in parent_tx_section:
            self._log.warning(
                "No transaction/overview section for transaction %s", raw_tx.get("id")
            )
            return None
        tx_section = parent_tx_section["data"]
        inferred_locale = infer_locale_from_section(
            get_section(tx_section, "Total")
        ) or infer_locale_from_section(get_section(tx_section, "Fee"))
        shares = parse_sub_section_float(
            get_section(tx_section, "Shares"), inferred_locale
        )
        taxes = parse_sub_section_float(get_section(tx_section, "Tax"), inferred_locale)
        taxes = abs(taxes) if taxes else None
        fees = parse_sub_section_float(get_section(tx_section, "Fee"), inferred_locale)
        fees = abs(fees) if fees else None

        sub_tx_section = get_section(tx_section, "Transaction")
        if sub_tx_section:
            tx_sections = (
                sub_tx_section.get("detail", {})
                .get("action", {})
                .get("payload", {})
                .get("sections", [])
            )
            for section in tx_sections:
                if "data" not in section:
                    continue
                section_data = section["data"]
                inferred_locale = infer_locale_from_section(
                    get_section(tx_section, "Total")
                ) or infer_locale_from_section(get_section(tx_section, "Share price"))
                if not shares or shares == 0:
                    shares = parse_sub_section_float(
                        get_section(section_data, "Shares"), inferred_locale
                    )
                if not taxes or taxes == 0:
                    taxes = parse_sub_section_float(
                        get_section(section_data, "Tax"), inferred_locale
                    )
                    taxes = abs(taxes) if taxes else None

        fees = fees or 0
        taxes = taxes or 0
        amount = abs(net_amount_val + fees + taxes)

        if shares is None:
            self._log.warning(
                f"Could not get shares for ISIN {isin} transaction {raw_tx['id']}, skipping"
            )
            return None

        # Provided price sometimes doesn't match with the executed price, or it has another currency
        # In Private Equity we don't have shares
        if shares != 0:
            price = round(amount / shares, 4)
        else:
            price = amount

        if product_type == ProductType.FUND:
            return FundTx(
                id=uuid4(),
                ref=raw_tx["id"],
                name=name,
                amount=Dezimal(amount),
                currency=currency,
                type=tx_type,
                date=date,
                entity=TRADE_REPUBLIC,
                net_amount=Dezimal(net_amount),
                isin=isin,
                shares=Dezimal(shares),
                price=Dezimal(price),
                market=None,
                fees=Dezimal(fees),
                retentions=Dezimal(taxes),
                order_date=None,
                product_type=product_type,
                fund_type=product_subtype,
                source=DataSource.REAL,
            )
        elif product_type == ProductType.CRYPTO:
            symbol = instrument_details.get("homeSymbol")
            if not symbol:
                self._log.warning(f"Crypto symbol not found for name {name}")
                return None

            return CryptoCurrencyTx(
                id=uuid4(),
                ref=raw_tx["id"],
                name=name,
                amount=Dezimal(amount),
                currency=currency,
                type=tx_type,
                date=date,
                entity=TRADE_REPUBLIC,
                net_amount=Dezimal(net_amount),
                symbol=symbol,
                contract_address=None,
                currency_amount=Dezimal(shares),
                price=Dezimal(price),
                fees=Dezimal(fees),
                retentions=Dezimal(taxes),
                order_date=None,
                product_type=product_type,
                source=DataSource.REAL,
            )

        else:
            return StockTx(
                id=uuid4(),
                ref=raw_tx["id"],
                name=name,
                amount=Dezimal(amount),
                currency=currency,
                type=tx_type,
                date=date,
                entity=TRADE_REPUBLIC,
                net_amount=Dezimal(net_amount),
                isin=isin,
                ticker=None,
                shares=Dezimal(shares),
                price=Dezimal(price),
                market=None,
                fees=Dezimal(fees),
                retentions=Dezimal(taxes),
                order_date=None,
                product_type=product_type,
                equity_type=product_subtype,
                linked_tx=None,
                source=DataSource.REAL,
            )

    @staticmethod
    def _extract_isin_from_asset(asset: str | dict) -> Optional[str]:
        if isinstance(asset, dict):
            asset = asset.get("asset")
        if not asset:
            return None
        isin = asset[asset.find("/") + 1 :]
        isin = isin[: isin.find("/")]
        return isin or None

    @classmethod
    def _get_tx_isin(cls, raw_tx, sections: list[dict]) -> Optional[str]:
        isin = cls._extract_isin_from_asset(raw_tx.get("icon", ""))
        isin2 = None
        for section in sections:
            action = section.get("action", None)
            if action and action.get("type", {}) == "instrumentDetail":
                isin2 = section.get("action", {}).get("payload")
                break
            if section.get("type", {}) == "header":
                isin2 = cls._extract_isin_from_asset(
                    section.get("data", {}).get("icon")
                )
                break

        return isin2 if isin2 else isin

    def map_account_tx(self, raw_tx: dict, date: datetime) -> Optional[AccountTx]:
        title = (raw_tx.get("title") or "").strip()
        subtitle = (raw_tx.get("subtitle") or "").strip().replace("\xa0", "")
        amount_obj = raw_tx.get("amount") or {}
        currency = amount_obj.get("currency")
        if not currency:
            self._log.warning(
                "Incomplete account transaction data: %s", raw_tx.get("id")
            )
            return None

        detail_sections = (raw_tx.get("details") or {}).get("sections") or []

        overview = get_section(detail_sections, "Overview")
        if not overview or "data" not in overview:
            self._log.warning(
                "No overview section for account transaction %s", raw_tx.get("id")
            )
            return None
        ov_section = overview["data"]
        inferred_locale = infer_locale_from_section(
            get_section(ov_section, "Average balance")
        )
        avg_balance = parse_sub_section_float(
            get_section(ov_section, "Average balance"), inferred_locale
        )
        annual_rate = parse_sub_section_float(
            get_section(ov_section, "Annual rate"), inferred_locale
        )
        taxes = parse_sub_section_float(
            get_section(ov_section, "Taxes"), inferred_locale
        )
        accrued = parse_sub_section_float(
            get_section(ov_section, "Accrued"), inferred_locale
        )

        if not annual_rate:
            if subtitle:
                annual_rate = parse_float(subtitle.split(" ")[0], inferred_locale)
            else:
                self._log.warning(f"No interest rate found in tx: {raw_tx['id']}")

        event_type = (raw_tx.get("eventType") or "").strip().upper()
        if title in ["Interest"] or event_type == "INTEREST_PAYOUT":
            tx_section_parent = get_section(detail_sections, "Transaction")
            if tx_section_parent and "data" in tx_section_parent:
                tx_section = tx_section_parent["data"]
                inferred_locale = infer_locale_from_section(
                    get_section(ov_section, "Total")
                ) or infer_locale_from_section(get_section(ov_section, "Accrued"))
                if not accrued or accrued == 0:
                    accrued = parse_sub_section_float(
                        get_section(tx_section, "Accrued"), inferred_locale
                    )
                if not taxes or taxes == 0:
                    taxes = parse_sub_section_float(
                        get_section(tx_section, "Tax"), inferred_locale
                    )
            else:
                if not taxes or taxes == 0:
                    taxes = 0
                if not accrued or accrued == 0:
                    accrued = amount_obj.get("value")
        else:
            if not taxes or taxes == 0:
                taxes = 0
            if not accrued or accrued == 0:
                accrued = amount_obj.get("value")

        if accrued is None:
            self._log.warning(
                "Could not determine accrued amount for account transaction %s",
                raw_tx.get("id"),
            )
            return None
        accrued = Dezimal(round(accrued, 2))
        if avg_balance is None and annual_rate is not None and annual_rate != 0:
            avg_balance = accrued / annual_rate * 12 * 100

        if avg_balance:
            avg_balance = Dezimal(round(avg_balance, 2))

        if not annual_rate and avg_balance is not None and avg_balance != 0:
            annual_rate = accrued / avg_balance * 12 * 100

        if annual_rate:
            annual_rate = Dezimal(round(annual_rate / 100, 4))

        fallback_subtitle = (
            f"{str(annual_rate * 100).rstrip('0').rstrip('.')}%" if annual_rate else ""
        )
        name = f"{title} - {(subtitle or fallback_subtitle)}"

        taxes = Dezimal(round(taxes or 0, 2))
        net_amount = accrued - taxes
        return AccountTx(
            id=uuid4(),
            ref=raw_tx["id"],
            name=name,
            amount=accrued,
            currency=currency,
            fees=Dezimal(0),
            retentions=taxes,
            interest_rate=annual_rate,
            avg_balance=avg_balance,
            net_amount=net_amount,
            type=TxType.INTEREST,
            product_type=ProductType.ACCOUNT,
            date=date,
            entity=TRADE_REPUBLIC,
            source=DataSource.REAL,
        )
