import asyncio
import threading
from datetime import date, datetime, timedelta
from uuid import uuid4

from dateutil.tz import tzlocal

from application.ports.financial_entity_fetcher import FinancialEntityFetcher
from domain.auto_contributions import (
    AutoContributions,
    ContributionFrequency,
    ContributionTargetType,
    PeriodicContribution,
)
from domain.crypto import CryptoCurrencyType
from domain.dezimal import Dezimal
from domain.entity_login import (
    EntityLoginParams,
    EntityLoginResult,
    EntitySession,
    LoginResultCode,
)
from domain.fetch_record import DataSource
from domain.fetch_result import FetchOptions
from domain.global_position import (
    Account,
    AccountType,
    Accounts,
    CryptoCurrencies,
    CryptoCurrencyPosition,
    CryptoCurrencyWallet,
    Deposit,
    Deposits,
    EquityType,
    FactoringDetail,
    FactoringInvestments,
    GlobalPosition,
    HistoricalPosition,
    ProductType,
    RealEstateCFDetail,
    RealEstateCFInvestments,
    StockDetail,
    StockInvestments,
)
from domain.transactions import (
    AccountTx,
    CryptoCurrencyTx,
    StockTx,
    Transactions,
    TxType,
)


class MockFinancialEntityFetcher(FinancialEntityFetcher):
    def __init__(self, entity):
        self._entity = entity

    async def login(self, login_params: EntityLoginParams) -> EntityLoginResult:
        session = EntitySession(
            creation=datetime.now(tzlocal()),
            expiration=None,
            payload={"mock": True},
        )
        return EntityLoginResult(
            code=LoginResultCode.CREATED,
            session=session,
        )

    def cancel_login(self) -> None:
        pass

    async def global_position(self) -> GlobalPosition:
        account = Account(
            id=uuid4(),
            total=Dezimal("12345.67"),
            currency="EUR",
            type=AccountType.CHECKING,
            name="Mock Checking Account",
        )
        deposit = Deposit(
            id=uuid4(),
            name="Mock Term Deposit",
            amount=Dezimal("5000"),
            currency="EUR",
            interest_rate=Dezimal("0.03"),
            creation=datetime.now(tzlocal()),
            maturity=date.today() + timedelta(days=365),
        )
        stock = StockDetail(
            id=uuid4(),
            name="Mock ETF",
            ticker="MKETF",
            isin="IE00B4L5Y983",
            shares=Dezimal("10"),
            market_value=Dezimal("500"),
            currency="EUR",
            type=EquityType.ETF,
            initial_investment=Dezimal("400"),
        )
        re_cf = RealEstateCFDetail(
            id=uuid4(),
            name="Mock RE Project",
            amount=Dezimal("1000"),
            pending_amount=Dezimal("1000"),
            currency="EUR",
            interest_rate=Dezimal("0.08"),
            start=datetime.now(tzlocal()),
            maturity=date.today() + timedelta(days=730),
            type="EQUITY",
            state="ACTIVE",
        )
        factoring = FactoringDetail(
            id=uuid4(),
            name="Mock Invoice",
            amount=Dezimal("2000"),
            currency="EUR",
            interest_rate=Dezimal("0.10"),
            start=datetime.now(tzlocal()),
            maturity=date.today() + timedelta(days=180),
            type="INVOICE",
            state="ACTIVE",
        )
        return GlobalPosition(
            id=uuid4(),
            entity=self._entity,
            products={
                ProductType.ACCOUNT: Accounts(entries=[account]),
                ProductType.DEPOSIT: Deposits(entries=[deposit]),
                ProductType.STOCK_ETF: StockInvestments(entries=[stock]),
                ProductType.REAL_ESTATE_CF: RealEstateCFInvestments(entries=[re_cf]),
                ProductType.FACTORING: FactoringInvestments(entries=[factoring]),
            },
        )

    async def auto_contributions(self) -> AutoContributions:
        now = date.today()
        contribution = PeriodicContribution(
            id=uuid4(),
            alias=None,
            target="MOCK_ETF",
            target_name="Mock ETF Plan",
            target_type=ContributionTargetType.STOCK_ETF,
            amount=Dezimal("100"),
            currency="EUR",
            since=now - timedelta(days=90),
            until=None,
            frequency=ContributionFrequency.MONTHLY,
            active=True,
            source=DataSource.REAL,
            entity=self._entity,
        )
        return AutoContributions(periodic=[contribution])

    async def transactions(
        self, registered_txs: set[str], options: FetchOptions
    ) -> Transactions:
        now = datetime.now(tzlocal())
        stock_a = StockTx(
            id=uuid4(),
            ref="mock-tx-stock-a",
            name="Mock Stock A",
            amount=Dezimal("500"),
            currency="EUR",
            type=TxType.BUY,
            date=now - timedelta(days=5),
            entity=self._entity,
            source=DataSource.REAL,
            product_type=ProductType.STOCK_ETF,
            shares=Dezimal("10"),
            price=Dezimal("50"),
            net_amount=Dezimal("498.50"),
            fees=Dezimal("1.50"),
        )
        stock_b = StockTx(
            id=uuid4(),
            ref="mock-tx-stock-b",
            name="Mock Stock B",
            amount=Dezimal("300"),
            currency="EUR",
            type=TxType.BUY,
            date=now - timedelta(days=3),
            entity=self._entity,
            source=DataSource.REAL,
            product_type=ProductType.STOCK_ETF,
            shares=Dezimal("5"),
            price=Dezimal("60"),
            net_amount=Dezimal("299.00"),
            fees=Dezimal("1.00"),
        )
        investment_txs = [stock_a, stock_b]

        if options.deep:
            stock_old = StockTx(
                id=uuid4(),
                ref="mock-tx-stock-old",
                name="Mock Stock Old",
                amount=Dezimal("200"),
                currency="EUR",
                type=TxType.BUY,
                date=now - timedelta(days=730),
                entity=self._entity,
                source=DataSource.REAL,
                product_type=ProductType.STOCK_ETF,
                shares=Dezimal("4"),
                price=Dezimal("50"),
                net_amount=Dezimal("199.50"),
                fees=Dezimal("0.50"),
            )
            investment_txs.append(stock_old)

        interest_tx = AccountTx(
            id=uuid4(),
            ref="mock-tx-interest",
            name="Mock Interest Payment",
            amount=Dezimal("25.50"),
            currency="EUR",
            type=TxType.INTEREST,
            date=now - timedelta(days=1),
            entity=self._entity,
            source=DataSource.REAL,
            product_type=ProductType.ACCOUNT,
            fees=Dezimal("0"),
            retentions=Dezimal("0"),
        )

        return Transactions(investment=investment_txs, account=[interest_tx])

    async def historical_position(self) -> HistoricalPosition:
        return HistoricalPosition(positions={})


MOCK_PIN_CODE = "123456"
MOCK_PROCESS_ID = "mock-process-123"


class MockPinEntityFetcher(MockFinancialEntityFetcher):
    async def login(self, login_params: EntityLoginParams) -> EntityLoginResult:
        two_factor = login_params.two_factor

        if not two_factor or not two_factor.code:
            return EntityLoginResult(
                code=LoginResultCode.CODE_REQUESTED,
                process_id=MOCK_PROCESS_ID,
            )

        if two_factor.code != MOCK_PIN_CODE:
            return EntityLoginResult(code=LoginResultCode.INVALID_CODE)

        session = EntitySession(
            creation=datetime.now(tzlocal()),
            expiration=None,
            payload={"mock": True},
        )
        return EntityLoginResult(
            code=LoginResultCode.CREATED,
            session=session,
        )

    async def global_position(self) -> GlobalPosition:
        await asyncio.sleep(2)
        return await super().global_position()


class MockManualLoginFetcher(MockFinancialEntityFetcher):
    async def login(self, login_params: EntityLoginParams) -> EntityLoginResult:
        if login_params.session and "awsWafToken" not in login_params.credentials:
            return EntityLoginResult(
                code=LoginResultCode.MANUAL_LOGIN,
                details={"phone": "+34612345678", "password": "1234"},
            )

        session = EntitySession(
            creation=datetime.now(tzlocal()),
            expiration=None,
            payload={"mock": True},
        )
        return EntityLoginResult(
            code=LoginResultCode.CREATED,
            session=session,
        )


class MockManualLoginFullCredsFetcher(MockFinancialEntityFetcher):
    """For entities where external browser provides ALL credentials (e.g. ING)."""

    async def login(self, login_params: EntityLoginParams) -> EntityLoginResult:
        if login_params.session and "genomaCookie" not in login_params.credentials:
            return EntityLoginResult(
                code=LoginResultCode.MANUAL_LOGIN,
                details={
                    "genomaCookie": "mock",
                    "genomaSessionId": "mock",
                    "apiCookie": "mock",
                    "apiAuth": "mock",
                    "apiExtendedSessionCtx": "mock",
                },
            )

        session = EntitySession(
            creation=datetime.now(tzlocal()),
            expiration=None,
            payload={"mock": True},
        )
        return EntityLoginResult(
            code=LoginResultCode.CREATED,
            session=session,
        )


class MockManualLoginReloginFetcher(MockFinancialEntityFetcher):
    """For entities where external browser provides a cookie and user re-enters credentials (e.g. Unicaja)."""

    async def login(self, login_params: EntityLoginParams) -> EntityLoginResult:
        if login_params.session and "abck" not in login_params.credentials:
            credentials = login_params.credentials
            return EntityLoginResult(
                code=LoginResultCode.MANUAL_LOGIN,
                details={
                    "user": credentials.get("user"),
                    "password": credentials.get("password"),
                },
            )

        session = EntitySession(
            creation=datetime.now(tzlocal()),
            expiration=None,
            payload={"mock": True},
        )
        return EntityLoginResult(
            code=LoginResultCode.CREATED,
            session=session,
        )


class MockCryptoExchangeFetcher(FinancialEntityFetcher):
    _call_counter = 0
    _lock = threading.Lock()

    def __init__(self, entity):
        self._entity = entity

    @classmethod
    def _next_counter(cls):
        with cls._lock:
            cls._call_counter += 1
            return cls._call_counter

    async def login(self, login_params: EntityLoginParams) -> EntityLoginResult:
        session = EntitySession(
            creation=datetime.now(tzlocal()),
            expiration=None,
            payload={"mock": True},
        )
        return EntityLoginResult(
            code=LoginResultCode.CREATED,
            session=session,
        )

    def cancel_login(self) -> None:
        pass

    async def global_position(self) -> GlobalPosition:
        counter = self._next_counter()
        btc = CryptoCurrencyPosition(
            id=uuid4(),
            symbol="BTC",
            amount=Dezimal("0.5"),
            type=CryptoCurrencyType.NATIVE,
            name="Bitcoin",
            market_value=Dezimal("25000"),
            currency="USD",
            source=DataSource.REAL,
        )
        eth = CryptoCurrencyPosition(
            id=uuid4(),
            symbol="ETH",
            amount=Dezimal("5.0"),
            type=CryptoCurrencyType.NATIVE,
            name="Ethereum",
            market_value=Dezimal("10000"),
            currency="USD",
            source=DataSource.REAL,
        )
        wallet = CryptoCurrencyWallet(
            name=f"Mock Crypto Wallet {counter}",
            assets=[btc, eth],
        )
        return GlobalPosition(
            id=uuid4(),
            entity=self._entity,
            products={ProductType.CRYPTO: CryptoCurrencies(entries=[wallet])},
        )

    async def auto_contributions(self) -> AutoContributions:
        return AutoContributions(periodic=[])

    async def transactions(
        self, registered_txs: set[str], options: FetchOptions
    ) -> Transactions:
        now = datetime.now(tzlocal())
        counter = self._next_counter()
        btc_buy = CryptoCurrencyTx(
            id=uuid4(),
            ref=f"mock-crypto-tx-btc-{counter}",
            name=f"Crypto BTC Buy {counter}",
            amount=Dezimal("1000"),
            currency="USD",
            type=TxType.BUY,
            date=now - timedelta(days=2),
            entity=self._entity,
            source=DataSource.REAL,
            product_type=ProductType.CRYPTO,
            currency_amount=Dezimal("0.04"),
            symbol="BTC",
            price=Dezimal("25000"),
            net_amount=Dezimal("995.00"),
            fees=Dezimal("5.00"),
        )
        eth_sell = CryptoCurrencyTx(
            id=uuid4(),
            ref=f"mock-crypto-tx-eth-{counter}",
            name=f"Crypto ETH Sell {counter}",
            amount=Dezimal("500"),
            currency="USD",
            type=TxType.SELL,
            date=now - timedelta(days=1),
            entity=self._entity,
            source=DataSource.REAL,
            product_type=ProductType.CRYPTO,
            currency_amount=Dezimal("0.25"),
            symbol="ETH",
            price=Dezimal("2000"),
            net_amount=Dezimal("497.50"),
            fees=Dezimal("2.50"),
        )
        return Transactions(investment=[btc_buy, eth_sell], account=[])

    async def historical_position(self) -> HistoricalPosition:
        return HistoricalPosition(positions={})
