import logging
from datetime import datetime
from uuid import uuid4

from application.ports.financial_entity_fetcher import FinancialEntityFetcher
from dateutil.tz import tzlocal
from domain.dezimal import Dezimal
from domain.entity_login import EntityLoginParams, EntityLoginResult
from domain.fetch_result import FetchOptions
from domain.global_position import (
    Account,
    Accounts,
    AccountType,
    FundDetail,
    FundInvestments,
    FundPortfolio,
    FundPortfolios,
    GlobalPosition,
    ProductType,
)
from domain.native_entities import INDEXA_CAPITAL
from domain.transactions import FundPortfolioTx, FundTx, Transactions, TxType
from infrastructure.client.entity.financial.indexa_capital.indexa_capital_client import (
    IndexaCapitalClient,
)


class IndexaCapitalFetcher(FinancialEntityFetcher):
    def __init__(self):
        self._client = IndexaCapitalClient()
        self._log = logging.getLogger(__name__)

    async def login(self, login_params: EntityLoginParams) -> EntityLoginResult:
        token = login_params.credentials.get("token")
        return self._client.setup(token)

    async def global_position(self) -> GlobalPosition:
        user_info = self._client.get_user_info()
        accounts_list = []
        fund_details = []
        fund_portfolios = []

        for account_data in user_info["accounts"]:
            if account_data.get("role") == "guest":
                continue

            account_number = account_data.get("account_number")
            account_name = account_number
            iban = account_data.get("account_cash")
            account_currency = account_data.get("currency")

            portfolio_data = self._client.get_portfolio(account_number)
            # New API structure has keys at top level (portfolio, cash_accounts, instrument_accounts)
            portfolio_info = portfolio_data.get("portfolio", {})
            # instrument_accounts may be at top level or nested (backwards compatibility)
            instrument_accounts = portfolio_data.get(
                "instrument_accounts"
            ) or portfolio_info.get("instrument_accounts", [])
            cash_accounts = portfolio_data.get("cash_accounts", [])

            # Cash amount can be directly provided or we derive it from cash_accounts list
            cash_amount = portfolio_info.get("cash_amount")
            if cash_amount is None and cash_accounts:
                try:
                    cash_amount = sum(
                        [Dezimal(ca.get("amount", 0)) for ca in cash_accounts]
                    )
                except Exception:
                    cash_amount = 0
            cash_amount = cash_amount or 0
            total_cash = Dezimal(cash_amount)

            # Portfolio aggregated investment values (instruments) if provided
            instruments_cost = Dezimal(portfolio_info.get("instruments_cost", 0))
            instruments_amount = Dezimal(portfolio_info.get("instruments_amount", 0))

            fund_portfolio_id = uuid4()

            # Cash retained per account (if API returns cash position entries)
            retained_cash = Dezimal(0)

            for account_item in instrument_accounts:
                positions = account_item.get("positions", [])
                for pos in positions:
                    market_value = Dezimal(pos.get("amount", 0))
                    instrument = pos.get("instrument", {})
                    asset_type = instrument.get("asset_class")

                    # Treat explicit cash instrument differently (current API seems to provide only investable assets)
                    if asset_type == "cash_euro":
                        retained_cash += market_value
                        continue

                    titles = Dezimal(pos.get("titles", 0))
                    initial_investment = Dezimal(pos.get("cost_amount", 0))

                    if market_value == 0 or initial_investment == 0 or titles == 0:
                        continue

                    price = Dezimal(pos.get("price", 0))

                    try:
                        isin = instrument.get("identifier") or instrument.get(
                            "isin_code"
                        )
                        if not isin:
                            # Skip instruments without an ISIN identifier
                            continue
                    except Exception:
                        continue

                    fund_details.append(
                        FundDetail(
                            id=uuid4(),
                            name=instrument.get("name"),
                            isin=isin,
                            market=instrument.get("market_code"),
                            shares=titles,
                            initial_investment=initial_investment,
                            average_buy_price=price,
                            market_value=market_value,
                            currency=account_currency,
                            portfolio=FundPortfolio(id=fund_portfolio_id),
                        )
                    )

            account = Account(
                id=uuid4(),
                name=account_name,
                iban=iban,
                total=total_cash,
                currency=account_currency,
                retained=retained_cash,
                type=AccountType.FUND_PORTFOLIO,
            )
            accounts_list.append(account)

            fund_portfolios.append(
                FundPortfolio(
                    id=fund_portfolio_id,
                    name=account_name,
                    currency=account_currency,
                    initial_investment=instruments_cost
                    if instruments_cost > 0
                    else total_cash,
                    market_value=instruments_amount
                    if instruments_amount > 0
                    else total_cash,
                    account_id=account.id,
                )
            )

        products = {
            ProductType.ACCOUNT: Accounts(accounts_list),
            ProductType.FUND: FundInvestments(
                fund_details,
            ),
            ProductType.FUND_PORTFOLIO: FundPortfolios(fund_portfolios),
        }

        return GlobalPosition(id=uuid4(), entity=INDEXA_CAPITAL, products=products)

    @staticmethod
    def _parse_date(date_str: str | None, fallback: str | None = None) -> datetime:
        if not date_str:
            date_str = fallback
        if not date_str:
            return datetime.now(tzlocal())
        fmt = "%Y-%m-%d %H:%M:%S" if " " in date_str else "%Y-%m-%d"
        try:
            return datetime.strptime(date_str, fmt).replace(tzinfo=tzlocal())
        except Exception:
            return datetime.now(tzlocal())

    @staticmethod
    def _map_type(op_code: int | None, op_type: str) -> TxType | None:
        normalized = (op_type or "").upper()
        if op_code == 20 or "SUSCRIPCIÓN FONDOS" in normalized:
            return TxType.BUY
        elif op_code in {1371}:
            return TxType.SWITCH_TO
        elif op_code in {1372}:
            return TxType.SWITCH_FROM
        elif op_code in {67}:
            return TxType.TRANSFER_IN
        elif op_code in {72}:
            return TxType.TRANSFER_OUT
        elif "REEMBOLSO FONDOS" in normalized:
            return TxType.SELL
        return None

    async def transactions(
        self, registered_txs: set[str], options: FetchOptions
    ) -> Transactions:
        user_info = self._client.get_user_info()
        investment_txs = self._fetch_investment_txs(registered_txs, user_info)
        portfolio_txs = self._fetch_portfolio_txs(registered_txs, user_info)

        return Transactions(investment=investment_txs + portfolio_txs, account=[])

    def _fetch_investment_txs(
        self, registered_txs: set[str], user_info: dict
    ) -> list[FundTx]:
        investment_txs: list[FundTx] = []

        for account_data in user_info.get("accounts", []):
            if account_data.get("role") == "guest":
                continue

            account_number = account_data.get("account_number")
            if not account_number:
                continue

            raw_txs = self._client.get_instrument_transactions(account_number)
            for tx in raw_txs:
                if tx.get("status") != "closed":
                    continue
                order = tx.get("order") or {}
                if order.get("status") != "completed":
                    continue

                ref = tx.get("reference")
                if not ref or ref in registered_txs:
                    continue

                op_code = tx.get("operation_code")
                op_type = tx.get("operation_type", "")
                tx_type = self._map_type(op_code, op_type)
                if not tx_type:
                    self._log.warning(
                        f"Unmapped transaction type {op_type} (code {op_code})"
                    )
                    continue

                instrument = tx.get("instrument", {})
                isin = instrument.get("identifier") or instrument.get("isin_code")
                if not isin:
                    continue

                name = instrument.get("name") or tx.get("operation_type") or "Fund"
                market = instrument.get("market_code") or ""
                currency = tx.get("currency")
                gross_amount = Dezimal(tx.get("amount", 0))
                shares = Dezimal(tx.get("titles", 0))
                price = Dezimal(tx.get("price", 0))
                if shares == 0 or gross_amount == 0:
                    continue  # Skip zero transactions

                # Dates
                executed_at = tx.get("executed_at") or tx.get("date")
                order_date_str = (
                    order.get("date") or order.get("date_start") or tx.get("date")
                )
                date_dt = self._parse_date(executed_at)
                order_dt = self._parse_date(order_date_str)

                fallback_price = gross_amount / shares if shares > 0 else Dezimal(0)

                investment_txs.append(
                    FundTx(
                        id=uuid4(),
                        ref=ref,
                        name=name,
                        amount=gross_amount,
                        net_amount=gross_amount,
                        currency=currency,
                        type=tx_type,
                        order_date=order_dt,
                        date=date_dt,
                        entity=INDEXA_CAPITAL,
                        isin=isin,
                        shares=shares,
                        price=price if price > 0 else fallback_price,
                        market=market,
                        fees=Dezimal(0),
                        retentions=Dezimal(0),
                        product_type=ProductType.FUND,
                        is_real=True,
                    )
                )
        return investment_txs

    def _fetch_portfolio_txs(
        self, registered_txs: set[str], user_info: dict
    ) -> list[FundPortfolioTx]:
        # We only take fee transactions for the portfolio level (custody / management)
        portfolio_txs: list[FundPortfolioTx] = []

        for account_data in user_info.get("accounts", []):
            if account_data.get("role") == "guest":
                continue

            account_number = account_data.get("account_number")
            if not account_number:
                continue
            iban = account_data.get("account_cash")
            portfolio_name = account_number

            try:
                cash_txs = self._client.get_cash_transactions(account_number)
            except Exception as e:
                self._log.error(
                    f"Failed fetching cash transactions for {account_number}: {e}"
                )
                continue

            for tx in cash_txs:
                if tx.get("status") != "closed":
                    continue

                op_code = tx.get("operation_code")
                op_type = (tx.get("operation_type") or "").strip()
                op_type_upper = op_type.upper()
                if op_code not in {4547, 5185} and "COMISI" not in op_type_upper:
                    continue
                ref = tx.get("reference")
                if not ref or ref in registered_txs:
                    continue
                raw_amount = Dezimal(tx.get("amount", 0))
                if raw_amount == 0:
                    continue

                amount = abs(raw_amount)
                comments = (tx.get("comments") or "").strip()
                name = op_type
                if comments:
                    name = f"{op_type} {comments}".strip()
                date_dt = self._parse_date(tx.get("date"))
                currency = tx.get("currency")

                portfolio_txs.append(
                    FundPortfolioTx(
                        id=uuid4(),
                        ref=ref,
                        name=name,
                        amount=amount,
                        currency=currency,
                        type=TxType.FEE,
                        date=date_dt,
                        entity=INDEXA_CAPITAL,
                        is_real=True,
                        product_type=ProductType.FUND_PORTFOLIO,
                        fees=amount,
                        portfolio_name=portfolio_name,
                        iban=iban,
                    )
                )
        return portfolio_txs
