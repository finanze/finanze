import json
from datetime import date, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
import pytest_asyncio
from dateutil.tz import tzlocal

from application.use_cases.position_snapshot_ids import regenerate_snapshot_ids
from domain.auto_contributions import (
    ContributionFrequency,
    ContributionTargetSubtype,
    ContributionTargetType,
    ManualPeriodicContribution,
    PeriodicContribution,
)
from domain.crypto import CryptoAsset, CryptoCurrencyType
from domain.dezimal import Dezimal
from domain.exception.exceptions import ManualHistoricEntryNotFinal
from domain.fetch_record import DataSource
from domain.fetch_result import FetchResult, FetchResultCode
from domain.entity_login import LoginConfirmationType
from domain.global_position import (
    Account,
    Accounts,
    AccountType,
    Card,
    Cards,
    CardType,
    CreditDetail,
    Credits,
    CryptoCurrencies,
    CryptoCurrencyPosition,
    CryptoCurrencyWallet,
    Deposit,
    Deposits,
    EquityType,
    FactoringDetail,
    FactoringInvestments,
    FundDetail,
    FundInvestments,
    FundPortfolio,
    FundPortfolios,
    FundType,
    Loan,
    Loans,
    LoanType,
    ManualEntryData,
    ProductType,
    RealEstateCFDetail,
    RealEstateCFInvestments,
    StockDetail,
    StockInvestments,
)
from domain.historic import (
    DeleteManualHistoricEntryRequest,
    HistoricTxDeletion,
    PartialAmortizeManualInvestmentRequest,
    SettleManualInvestmentRequest,
)
from domain.transactions import (
    TransactionQueryRequest,
    TransactionsResult,
    TransactionSortBy,
    TransactionSortOrder,
)

NOW = datetime(2025, 1, 15, 10, 30, tzinfo=tzlocal())
MANUAL = DataSource.MANUAL


class ToolCaller:
    def __init__(self, env, token: str):
        self._env = env
        self._token = token

    async def _call(self, tool: str, arguments: dict):
        async with self._env.connect(self._token) as mcp_client:
            return await mcp_client.call_tool(tool, arguments)

    async def ok(self, tool: str, **arguments):
        result = await self._call(tool, arguments)
        assert not result.is_error, result.content[0].text
        return json.loads(result.content[0].text)

    async def error(self, tool: str, **arguments) -> str:
        result = await self._call(tool, arguments)
        assert result.is_error
        return result.content[0].text


@pytest_asyncio.fixture
async def tools(mcp_env):
    token = (await mcp_env.configure(enabled=True, read_only=False))["token"]
    return ToolCaller(mcp_env, token)


def _manual_products():
    checking = Account(
        id=uuid4(),
        total=Dezimal("1000"),
        currency="EUR",
        type=AccountType.CHECKING,
        name="Main",
        iban="ES00",
        interest=Dezimal("0.01"),
        source=MANUAL,
    )
    cash = Account(
        id=uuid4(),
        total=Dezimal("0"),
        currency="EUR",
        type=AccountType.FUND_PORTFOLIO,
        name="Cash",
        source=MANUAL,
    )
    portfolio = FundPortfolio(
        id=uuid4(),
        name="Portfolio",
        currency="EUR",
        initial_investment=Dezimal("1000"),
        market_value=Dezimal("1100"),
        account_id=cash.id,
        account=Account(
            id=cash.id,
            total=Dezimal("0"),
            currency="EUR",
            type=AccountType.FUND_PORTFOLIO,
        ),
        source=MANUAL,
    )
    bitcoin = CryptoCurrencyPosition(
        id=uuid4(),
        symbol="BTC",
        amount=Dezimal("0.5"),
        type=CryptoCurrencyType.NATIVE,
        name="Bitcoin",
        crypto_asset=CryptoAsset(
            name="Bitcoin",
            symbol="BTC",
            icon_urls=None,
            external_ids={"COINGECKO": "bitcoin"},
        ),
        market_value=Dezimal("30000"),
        currency="EUR",
        source=MANUAL,
    )
    return {
        ProductType.ACCOUNT: Accounts([checking, cash]),
        ProductType.CARD: Cards(
            [
                Card(
                    id=uuid4(),
                    currency="EUR",
                    type=CardType.CREDIT,
                    used=Dezimal("50"),
                    limit=Dezimal("2000"),
                    name="Visa",
                    ending="1234",
                    related_account=checking.id,
                    source=MANUAL,
                )
            ]
        ),
        ProductType.FUND_PORTFOLIO: FundPortfolios([portfolio]),
        ProductType.FUND: FundInvestments(
            [
                FundDetail(
                    id=uuid4(),
                    name="Index Fund",
                    isin="IE00B03HCZ61",
                    market=None,
                    shares=Dezimal("10"),
                    market_value=Dezimal("500"),
                    currency="EUR",
                    type=FundType.MUTUAL_FUND,
                    initial_investment=Dezimal("400"),
                    portfolio=FundPortfolio(id=portfolio.id, name="Portfolio"),
                    source=MANUAL,
                )
            ]
        ),
        ProductType.STOCK_ETF: StockInvestments(
            [
                StockDetail(
                    id=uuid4(),
                    name="Apple",
                    ticker="AAPL",
                    isin="US0378331005",
                    shares=Dezimal("5"),
                    market_value=Dezimal("900"),
                    currency="USD",
                    type=EquityType.STOCK,
                    initial_investment=Dezimal("700"),
                    market="NASDAQ",
                    manual_data=ManualEntryData(tracker_key="US0378331005"),
                    source=MANUAL,
                )
            ]
        ),
        ProductType.DEPOSIT: Deposits(
            [
                Deposit(
                    id=uuid4(),
                    name="Deposit",
                    amount=Dezimal("5000"),
                    currency="EUR",
                    interest_rate=Dezimal("0.03"),
                    creation=NOW,
                    maturity=date(2026, 1, 15),
                    source=MANUAL,
                )
            ]
        ),
        ProductType.FACTORING: FactoringInvestments(
            [
                FactoringDetail(
                    id=uuid4(),
                    name="Invoice",
                    amount=Dezimal("1000"),
                    currency="EUR",
                    interest_rate=Dezimal("0.08"),
                    start=NOW,
                    maturity=date(2025, 6, 1),
                    type="INSURED",
                    state="FUNDED",
                    source=MANUAL,
                )
            ]
        ),
        ProductType.REAL_ESTATE_CF: RealEstateCFInvestments(
            [
                RealEstateCFDetail(
                    id=uuid4(),
                    name="Project",
                    amount=Dezimal("2000"),
                    pending_amount=Dezimal("2000"),
                    currency="EUR",
                    interest_rate=Dezimal("0.1"),
                    start=NOW,
                    maturity=date(2026, 1, 1),
                    type="LENDING",
                    state="FUNDED",
                    business_type="RESIDENTIAL",
                    source=MANUAL,
                )
            ]
        ),
        ProductType.LOAN: Loans(
            [
                Loan(
                    id=uuid4(),
                    type=LoanType.MORTGAGE,
                    currency="EUR",
                    current_installment=Dezimal("800"),
                    interest_rate=Dezimal("0.025"),
                    loan_amount=Dezimal("200000"),
                    creation=date(2020, 1, 1),
                    maturity=date(2050, 1, 1),
                    principal_outstanding=Dezimal("150000"),
                    name="Mortgage",
                    manual_data=ManualEntryData(track=True),
                    source=MANUAL,
                )
            ]
        ),
        ProductType.CREDIT: Credits(
            [
                CreditDetail(
                    id=uuid4(),
                    currency="EUR",
                    credit_limit=Dezimal("10000"),
                    drawn_amount=Dezimal("2000"),
                    interest_rate=Dezimal("0.05"),
                    name="Credit line",
                    source=MANUAL,
                )
            ]
        ),
        ProductType.CRYPTO: CryptoCurrencies([CryptoCurrencyWallet(assets=[bitcoin])]),
    }


def _entries(products, product_type):
    container = products[product_type]
    if product_type == ProductType.CRYPTO:
        return container.entries[0].assets
    return container.entries


@pytest.fixture
def manual(mcp_env):
    entity_id = uuid4()
    products = _manual_products()
    mcp_env.ucs.get_position.execute.return_value = SimpleNamespace(
        positions={
            str(entity_id): [
                SimpleNamespace(source=DataSource.REAL, products={}),
                SimpleNamespace(source=MANUAL, products=products),
            ]
        }
    )
    new_entity_id = uuid4()

    async def update(request):
        regenerate_snapshot_ids(SimpleNamespace(products=request.products))
        return request.entity_id or new_entity_id

    mcp_env.ucs.update_position.execute.side_effect = update
    return SimpleNamespace(
        entity_id=entity_id,
        new_entity_id=new_entity_id,
        products=products,
        request=lambda: mcp_env.ucs.update_position.execute.await_args.args[0],
    )


class TestMcpTools:
    @pytest.mark.asyncio
    async def test_context(self, tools):
        context = await tools.ok("get_context")

        assert context["default_currency"] == "EUR"
        assert context["read_only"] is False
        assert context["version"] == "0.0.0-test"

    @pytest.mark.asyncio
    async def test_label_and_periodic_flow_lifecycle(self, tools):
        label = await tools.ok("save_label", name="Salary", category="INCOME")

        created = await tools.ok(
            "save_periodic_flow",
            name="Salary",
            amount="3000.50",
            currency="eur",
            flow_type="EARNING",
            frequency="MONTHLY",
            since="2025-01-01",
            label_id=label["id"],
        )
        flow_id = created["created"]

        await tools.ok("save_periodic_flow", flow_id=flow_id, amount=3200)
        flows = await tools.ok("list_periodic_flows")

        assert len(flows) == 1
        assert flows[0]["id"] == flow_id
        assert flows[0]["name"] == "Salary"
        assert flows[0]["amount"] == 3200
        assert flows[0]["currency"] == "EUR"
        assert flows[0]["label_id"] == label["id"]

        await tools.ok("delete_periodic_flow", flow_id=flow_id)
        assert await tools.ok("list_periodic_flows") == []

    @pytest.mark.asyncio
    async def test_label_update_keeps_other_fields(self, tools):
        label = await tools.ok("save_label", name="Groceries", color="#22c55e")

        updated = await tools.ok("save_label", label_id=label["id"], name="Food")

        assert updated["name"] == "Food"
        assert updated["color"] == "#22c55e"
        assert updated["category"] == "EXPENSE"

    @pytest.mark.asyncio
    async def test_errors_are_reported_to_the_model(self, tools):
        missing = await tools.error("save_periodic_flow", name="Rent")
        assert "Missing required fields" in missing

        not_found = await tools.error(
            "save_periodic_flow", flow_id=str(uuid4()), amount=10
        )
        assert "Flow not found" in not_found

        invalid = await tools.error(
            "save_periodic_flow",
            name="Rent",
            amount=-5,
            currency="EUR",
            flow_type="EXPENSE",
            frequency="MONTHLY",
            since="2025-01-01",
        )
        assert "amount" in invalid

    @pytest.mark.asyncio
    async def test_real_estate_partial_update(self, tools):
        created = await tools.ok(
            "save_real_estate",
            basic_info={"name": "Flat", "is_residence": True},
            purchase_info={"date": "2020-05-01", "price": "200000"},
            valuation_info={
                "valuations": [
                    {"date": "2024-01-01", "amount": "250000", "market_value": True}
                ]
            },
            currency="EUR",
        )

        await tools.ok(
            "save_real_estate",
            real_estate_id=created["created"],
            basic_info={"name": "Beach flat", "is_residence": False},
        )
        [real_estate] = await tools.ok("list_real_estate")

        assert real_estate["id"] == created["created"]
        assert real_estate["basic_info"]["name"] == "Beach flat"
        assert real_estate["purchase_info"]["price"] == 200000
        assert real_estate["valuation_info"]["estimated_market_value"] == 250000

    @pytest.mark.asyncio
    async def test_real_estate_requires_market_valuation(self, tools):
        error = await tools.error(
            "save_real_estate",
            basic_info={"name": "Flat"},
            purchase_info={"date": "2020-05-01", "price": "200000"},
            valuation_info={"valuations": [{"date": "2024-01-01", "amount": "250000"}]},
            currency="EUR",
        )

        assert "Invalid input" in error

    @pytest.mark.asyncio
    async def test_loan_calculation(self, tools):
        result = await tools.ok(
            "calculate_loan",
            interest_rate="0.03",
            interest_type="FIXED",
            start="2024-01-01",
            end="2049-01-01",
            loan_amount="200000",
        )

        assert 900 < result["current_installment_payment"] < 1000

    @pytest.mark.asyncio
    async def test_fetch_requests_two_factor_without_leaking_details(
        self, tools, mcp_env
    ):
        mcp_env.ucs.fetch_financial_data.execute.return_value = FetchResult(
            FetchResultCode.CODE_REQUESTED,
            details={"message": "SMS sent", "processId": "p-1", "secret": "x"},
            confirmation_type=LoginConfirmationType.CHALLENGE,
        )

        result = await tools.ok("fetch_entity_data", account_id=str(uuid4()))

        assert result["code"] == "CODE_REQUESTED"
        assert result["process_id"] == "p-1"
        assert "secret" not in json.dumps(result)
        assert "code they received" in result["next_step"]

    @pytest.mark.asyncio
    async def test_net_worth_aggregates_positions_and_real_estate(self, tools, mcp_env):
        for name, is_residence, value in (
            ("Home", True, "300000"),
            ("Flat", False, "150000"),
        ):
            await tools.ok(
                "save_real_estate",
                basic_info={"name": name, "is_residence": is_residence},
                purchase_info={"date": "2020-01-15", "price": "100000"},
                valuation_info={
                    "valuations": [
                        {"date": "2024-01-15", "amount": value, "market_value": True}
                    ]
                },
                currency="EUR",
            )
        account = SimpleNamespace(total=Dezimal("2500.5"), currency="EUR")
        mcp_env.position_port.get_last_by_entity_broken_down.return_value = {
            uuid4(): [
                SimpleNamespace(
                    products={ProductType.ACCOUNT: SimpleNamespace(entries=[account])}
                )
            ]
        }

        result = await tools.ok("get_net_worth")

        assert result["currency"] == "EUR"
        assert result["total"] == 452500.5
        assert result["breakdown"] == {
            "ACCOUNT": 2500.5,
            "REAL_ESTATE": 150000,
            "REAL_ESTATE_RESIDENCE": 300000,
        }


class TestManualPositionTools:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "product_type, changes, expected",
        [
            (
                "ACCOUNT",
                {"total": "1500"},
                {"total": Dezimal("1500"), "iban": "ES00", "interest": Dezimal("0.01")},
            ),
            (
                "CARD",
                {"used": "75"},
                {"used": Dezimal("75"), "limit": Dezimal("2000"), "ending": "1234"},
            ),
            (
                "FUND_PORTFOLIO",
                {"market_value": "1200"},
                {
                    "market_value": Dezimal("1200"),
                    "initial_investment": Dezimal("1000"),
                },
            ),
            (
                "FUND",
                {"shares": "12"},
                {
                    "shares": Dezimal("12"),
                    "isin": "IE00B03HCZ61",
                    "average_buy_price": Dezimal("40"),
                    "initial_investment": Dezimal("480"),
                },
            ),
            (
                "STOCK_ETF",
                {"shares": "6"},
                {"shares": Dezimal("6"), "ticker": "AAPL", "market": "NASDAQ"},
            ),
            (
                "DEPOSIT",
                {"amount": "6000"},
                {
                    "amount": Dezimal("6000"),
                    "creation": NOW,
                    "maturity": date(2026, 1, 15),
                },
            ),
            (
                "FACTORING",
                {"state": "MANAGING_COLLECTION"},
                {
                    "state": "MANAGING_COLLECTION",
                    "start": NOW,
                    "amount": Dezimal("1000"),
                },
            ),
            (
                "REAL_ESTATE_CF",
                {"pending_amount": "1500"},
                {
                    "pending_amount": Dezimal("1500"),
                    "business_type": "RESIDENTIAL",
                    "start": NOW,
                },
            ),
            (
                "LOAN",
                {"principal_outstanding": "149000"},
                {
                    "principal_outstanding": Dezimal("149000"),
                    "creation": date(2020, 1, 1),
                    "name": "Mortgage",
                },
            ),
            (
                "CREDIT",
                {"drawn_amount": "2500"},
                {"drawn_amount": Dezimal("2500"), "credit_limit": Dezimal("10000")},
            ),
            (
                "CRYPTO",
                {"amount": "0.75"},
                {
                    "amount": Dezimal("0.75"),
                    "symbol": "BTC",
                    "market_value": Dezimal("30000"),
                },
            ),
        ],
    )
    async def test_update_keeps_other_fields(
        self, tools, manual, product_type, changes, expected
    ):
        ptype = ProductType(product_type)
        original = _entries(manual.products, ptype)[0]

        result = await tools.ok(
            "save_manual_position",
            entity_id=str(manual.entity_id),
            entry_id=str(original.id),
            position={"product_type": product_type, **changes},
        )

        request = manual.request()
        saved = _entries(request.products, ptype)
        assert len(saved) == len(_entries(manual.products, ptype))
        for attr, value in expected.items():
            assert getattr(saved[0], attr) == value, attr
        assert list(request.products) == [ptype]
        assert request.entity_id == manual.entity_id
        assert request.create_investment_txs is False
        assert result == {
            "updated": str(saved[0].id),
            "entity_id": str(manual.entity_id),
        }
        assert saved[0].id != original.id

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "changes, shares, initial_investment, average_buy_price",
        [
            ({"initial_investment": "800"}, "5", "800", "160"),
            ({"average_buy_price": "150"}, "5", "750", "150"),
            ({"shares": "10"}, "10", "1400", "140"),
            ({"shares": "10", "initial_investment": "1000"}, "10", "1000", "100"),
            ({"shares": "10", "average_buy_price": "120"}, "10", "1200", "120"),
        ],
    )
    async def test_update_keeps_cost_basis_consistent(
        self, tools, manual, changes, shares, initial_investment, average_buy_price
    ):
        stock = _entries(manual.products, ProductType.STOCK_ETF)[0]

        await tools.ok(
            "save_manual_position",
            entity_id=str(manual.entity_id),
            entry_id=str(stock.id),
            position={"product_type": "STOCK_ETF", **changes},
        )

        [saved] = manual.request().products[ProductType.STOCK_ETF].entries
        assert saved.shares == Dezimal(shares)
        assert saved.initial_investment == Dezimal(initial_investment)
        assert saved.average_buy_price == Dezimal(average_buy_price)

    @pytest.mark.asyncio
    async def test_update_keeps_links_and_tracking(self, tools, manual):
        products = manual.products
        cash, portfolio, fund = (
            products[ProductType.ACCOUNT].entries[1],
            products[ProductType.FUND_PORTFOLIO].entries[0],
            products[ProductType.FUND].entries[0],
        )

        await tools.ok(
            "save_manual_position",
            entity_id=str(manual.entity_id),
            entry_id=str(portfolio.id),
            position={"product_type": "FUND_PORTFOLIO", "name": "Renamed"},
        )
        [saved_portfolio] = (
            manual.request().products[ProductType.FUND_PORTFOLIO].entries
        )
        assert saved_portfolio.account_id == cash.id

        await tools.ok(
            "save_manual_position",
            entity_id=str(manual.entity_id),
            entry_id=str(fund.id),
            position={"product_type": "FUND", "tracker_key": "IE00B03HCZ61"},
        )
        [saved_fund] = manual.request().products[ProductType.FUND].entries
        assert saved_fund.portfolio.id == portfolio.id
        assert saved_fund.manual_data.tracker_key == "IE00B03HCZ61"

    @pytest.mark.asyncio
    async def test_create_investment_appends_with_local_start(self, tools, manual):
        result = await tools.ok(
            "save_manual_position",
            entity_id=str(manual.entity_id),
            position={
                "product_type": "FACTORING",
                "name": "New invoice",
                "amount": "500",
                "currency": "eur",
                "interest_rate": "0.07",
                "start": "2025-02-01",
                "maturity": "2025-08-01",
                "type": "INSURED",
                "state": "FUNDED",
            },
        )

        request = manual.request()
        existing, created = request.products[ProductType.FACTORING].entries
        assert existing.name == "Invoice"
        assert created.currency == "EUR"
        assert created.amount == Dezimal("500")
        assert created.start == datetime(2025, 2, 1, tzinfo=tzlocal())
        assert created.start.tzinfo is not None
        assert request.create_investment_txs is True
        assert result["created"] == str(created.id)

    @pytest.mark.asyncio
    async def test_create_in_new_entity(self, tools, manual, mcp_env):
        result = await tools.ok(
            "save_manual_position",
            new_entity_name="Broker",
            create_investment_tx=True,
            position={
                "product_type": "STOCK_ETF",
                "name": "Microsoft",
                "ticker": "msft",
                "isin": "us5949181045",
                "type": "STOCK",
                "shares": "2",
                "currency": "usd",
                "average_buy_price": "300",
                "tracker_key": "US5949181045",
            },
        )

        request = manual.request()
        [stock] = request.products[ProductType.STOCK_ETF].entries
        mcp_env.ucs.get_position.execute.assert_not_awaited()
        assert request.entity_id is None
        assert request.new_entity_name == "Broker"
        assert request.create_investment_txs is False
        assert stock.initial_investment == Dezimal("600")
        assert stock.ticker == "MSFT"
        assert stock.isin == "US5949181045"
        assert stock.manual_data.tracker_key == "US5949181045"
        assert result == {
            "created": str(stock.id),
            "entity_id": str(manual.new_entity_id),
        }

    @pytest.mark.asyncio
    async def test_create_crypto_with_provider(self, tools, manual):
        await tools.ok(
            "save_manual_position",
            entity_id=str(manual.entity_id),
            position={
                "product_type": "CRYPTO",
                "symbol": "eth",
                "name": "Ethereum",
                "type": "NATIVE",
                "amount": "2",
                "provider": "COINGECKO",
                "provider_id": "ethereum",
                "initial_investment": "3000",
                "investment_currency": "usd",
            },
        )

        [wallet] = manual.request().products[ProductType.CRYPTO].entries
        bitcoin, ether = wallet.assets
        assert bitcoin.crypto_asset.external_ids == {"COINGECKO": "bitcoin"}
        assert ether.symbol == "ETH"
        assert ether.investment_currency == "USD"
        assert ether.crypto_asset.name == "Ethereum"
        assert ether.crypto_asset.external_ids == {"COINGECKO": "ethereum"}

    @pytest.mark.asyncio
    async def test_delete_account_unlinks_cards(self, tools, manual):
        checking, cash = manual.products[ProductType.ACCOUNT].entries

        result = await tools.ok(
            "delete_manual_position",
            entity_id=str(manual.entity_id),
            product_type="ACCOUNT",
            entry_id=str(checking.id),
        )

        request = manual.request()
        [remaining] = request.products[ProductType.ACCOUNT].entries
        [card] = request.products[ProductType.CARD].entries
        assert remaining.name == cash.name
        assert card.related_account is None
        assert card.name == "Visa"
        assert ProductType.FUND_PORTFOLIO not in request.products
        assert request.create_investment_txs is False
        assert result == {"deleted": str(checking.id)}

    @pytest.mark.asyncio
    async def test_delete_portfolio_unlinks_funds(self, tools, manual):
        portfolio = manual.products[ProductType.FUND_PORTFOLIO].entries[0]

        await tools.ok(
            "delete_manual_position",
            entity_id=str(manual.entity_id),
            product_type="FUND_PORTFOLIO",
            entry_id=str(portfolio.id),
        )

        request = manual.request()
        [fund] = request.products[ProductType.FUND].entries
        assert request.products[ProductType.FUND_PORTFOLIO].entries == []
        assert fund.portfolio is None
        assert fund.isin == "IE00B03HCZ61"

    @pytest.mark.asyncio
    async def test_errors(self, tools, manual):
        entity_id = str(manual.entity_id)
        account = {"product_type": "ACCOUNT", "total": "10"}

        both = await tools.error(
            "save_manual_position",
            entity_id=entity_id,
            new_entity_name="Bank",
            position=account,
        )
        assert "Provide either entity_id or new_entity_name" in both

        missing = await tools.error(
            "save_manual_position", entity_id=entity_id, position=account
        )
        assert "Missing required fields: type, currency" in missing

        not_found = await tools.error(
            "save_manual_position",
            entity_id=entity_id,
            entry_id=str(uuid4()),
            position=account,
        )
        assert "Manual position entry not found" in not_found

        no_investment = await tools.error(
            "save_manual_position",
            entity_id=entity_id,
            position={
                "product_type": "FUND",
                "name": "Fund",
                "isin": "LU0000000000",
                "type": "MUTUAL_FUND",
                "shares": "1",
                "currency": "EUR",
            },
        )
        assert "Invalid input" in no_investment

        bitcoin = _entries(manual.products, ProductType.CRYPTO)[0]
        unpaired = await tools.error(
            "save_manual_position",
            entity_id=entity_id,
            entry_id=str(bitcoin.id),
            position={"product_type": "CRYPTO", "provider": "COINGECKO"},
        )
        assert "provider and provider_id must be provided together" in unpaired


class TestContributionTools:
    @pytest.fixture
    def contributions(self, mcp_env):
        entity_id = uuid4()
        base = {
            "target": "IE00B03HCZ61",
            "target_name": "Index Fund",
            "target_type": ContributionTargetType.FUND,
            "target_subtype": ContributionTargetSubtype.MUTUAL_FUND,
            "amount": Dezimal("100"),
            "currency": "EUR",
            "since": date(2024, 1, 1),
            "until": None,
            "frequency": ContributionFrequency.MONTHLY,
            "active": True,
        }
        manual = PeriodicContribution(
            id=uuid4(), alias="Monthly fund", source=MANUAL, **base
        )
        real = PeriodicContribution(
            id=uuid4(), alias=None, source=DataSource.REAL, **base
        )
        mcp_env.ucs.get_contributions.execute.return_value = SimpleNamespace(
            contributions={str(entity_id): SimpleNamespace(periodic=[manual, real])}
        )
        return SimpleNamespace(
            entity_id=entity_id,
            manual=manual,
            real=real,
            saved=lambda: mcp_env.ucs.update_contributions.execute.await_args.args[0],
        )

    @pytest.mark.asyncio
    async def test_create_update_and_delete(self, tools, contributions):
        existing = ManualPeriodicContribution(
            entity_id=contributions.entity_id,
            name="Monthly fund",
            target="IE00B03HCZ61",
            target_name="Index Fund",
            target_type=ContributionTargetType.FUND,
            target_subtype=ContributionTargetSubtype.MUTUAL_FUND,
            amount=Dezimal("100"),
            currency="EUR",
            since=date(2024, 1, 1),
            until=None,
            frequency=ContributionFrequency.MONTHLY,
        )

        created = await tools.ok(
            "save_contribution",
            entity_id=str(contributions.entity_id),
            name="ETF plan",
            target_type="STOCK_ETF",
            target=" ie00b4l5 y983 ",
            target_subtype="ETF",
            amount="50",
            currency="eur",
            frequency="MONTHLY",
            since="2025-02-01",
        )
        first, new = contributions.saved()
        assert created == {"created": "ETF plan"}
        assert first == existing
        assert new.target == "IE00B4L5Y983"
        assert new.target_name == "ETF plan"
        assert new.currency == "EUR"
        assert new.amount == Dezimal("50")

        updated = await tools.ok(
            "save_contribution",
            contribution_id=str(contributions.manual.id),
            amount="200",
            target_type="CRYPTO",
        )
        [changed] = contributions.saved()
        assert updated == {"updated": "Monthly fund"}
        assert changed.amount == Dezimal("200")
        assert changed.target_type == ContributionTargetType.CRYPTO
        assert changed.target_subtype is None
        assert changed.since == existing.since

        deleted = await tools.ok(
            "delete_contribution", contribution_id=str(contributions.manual.id)
        )
        assert deleted == {"deleted": str(contributions.manual.id)}
        assert contributions.saved() == []

    @pytest.mark.asyncio
    async def test_errors(self, tools, contributions):
        real = await tools.error(
            "delete_contribution", contribution_id=str(contributions.real.id)
        )
        assert "Manual contribution not found" in real

        missing = await tools.error(
            "save_contribution", entity_id=str(contributions.entity_id), name="X"
        )
        assert (
            "Missing required fields: target_type, target, amount, currency, "
            "frequency, since" in missing
        )


class TestTransactionSearch:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("arguments", "sort_by", "sort_order"),
        [
            ({}, TransactionSortBy.DATE, TransactionSortOrder.DESC),
            ({"sort_order": "asc"}, TransactionSortBy.DATE, TransactionSortOrder.ASC),
            (
                {"sort_by": "amount"},
                TransactionSortBy.AMOUNT,
                TransactionSortOrder.DESC,
            ),
            (
                {"sort_by": "date", "sort_order": "desc"},
                TransactionSortBy.DATE,
                TransactionSortOrder.DESC,
            ),
            (
                {"sort_by": "amount", "sort_order": "asc", "page": 2, "limit": 3},
                TransactionSortBy.AMOUNT,
                TransactionSortOrder.ASC,
            ),
        ],
    )
    async def test_sorting_arguments(
        self, tools, mcp_env, arguments, sort_by, sort_order
    ):
        mcp_env.ucs.get_transactions.execute.return_value = TransactionsResult(
            transactions=[]
        )

        result = await tools.ok("search_transactions", **arguments)

        page = arguments.get("page", 1)
        limit = arguments.get("limit", 50)
        mcp_env.ucs.get_transactions.execute.assert_awaited_once_with(
            TransactionQueryRequest(
                page=page, limit=limit, sort_by=sort_by, sort_order=sort_order
            )
        )
        assert result == {"page": page, "limit": limit}

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "arguments",
        [
            {"sort_by": "name"},
            {"sort_by": "amount; DROP TABLE account_transactions"},
            {"sort_order": "ascending"},
            {"sort_order": "desc; DROP TABLE account_transactions"},
        ],
    )
    async def test_invalid_sorting_is_rejected(self, tools, mcp_env, arguments):
        error = await tools.error("search_transactions", **arguments)

        assert next(iter(arguments)) in error
        mcp_env.ucs.get_transactions.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_schema_advertises_sorting(self, mcp_env):
        token = (await mcp_env.configure(enabled=True, read_only=True))["token"]
        async with mcp_env.connect(token) as client:
            result = await client.list_tools()

        tool = next(tool for tool in result.tools if tool.name == "search_transactions")
        schema = tool.model_dump(by_alias=True)["inputSchema"]
        for name, default, choices in [
            ("sort_by", "date", ["date", "amount"]),
            ("sort_order", "desc", ["asc", "desc"]),
        ]:
            field = schema["properties"][name]
            assert field["default"] == default
            assert name not in schema.get("required", [])
            definition = schema["$defs"][field["$ref"].removeprefix("#/$defs/")]
            assert definition["enum"] == choices


class TestHistoricTools:
    @pytest.mark.asyncio
    async def test_settle_maps_request(self, tools, mcp_env):
        entity_id, entry_id = uuid4(), uuid4()

        result = await tools.ok(
            "settle_manual_investment",
            entity_id=str(entity_id),
            entry_id=str(entry_id),
            product_type="FACTORING",
            maturity="2025-06-01",
            interests="12.5",
            pending_capital="100",
        )

        mcp_env.ucs.settle_manual_investment.execute.assert_awaited_once_with(
            SettleManualInvestmentRequest(
                entity_id=entity_id,
                entry_id=entry_id,
                product_type=ProductType.FACTORING,
                maturity=datetime(2025, 6, 1, tzinfo=tzlocal()),
                interests=Dezimal("12.5"),
                pending_capital=Dezimal("100"),
            )
        )
        assert result == {"settled": str(entry_id)}

    @pytest.mark.asyncio
    async def test_amortize_maps_request(self, tools, mcp_env):
        entity_id, entry_id = uuid4(), uuid4()

        await tools.ok(
            "amortize_manual_investment",
            entity_id=str(entity_id),
            entry_id=str(entry_id),
            product_type="REAL_ESTATE_CF",
            amount="250",
            interests="5",
            create_investment_tx=True,
        )

        mcp_env.ucs.partial_amortize_manual_investment.execute.assert_awaited_once_with(
            PartialAmortizeManualInvestmentRequest(
                entity_id=entity_id,
                entry_id=entry_id,
                product_type=ProductType.REAL_ESTATE_CF,
                amount=Dezimal("250"),
                interests=Dezimal("5"),
                create_investment_tx=True,
            )
        )

    @pytest.mark.asyncio
    async def test_delete_and_errors(self, tools, mcp_env):
        historic_id = uuid4()

        await tools.ok(
            "delete_manual_historic_entry",
            historic_entry_id=str(historic_id),
            tx_deletion="ALL",
        )
        mcp_env.ucs.delete_manual_historic_entry.execute.assert_awaited_once_with(
            DeleteManualHistoricEntryRequest(
                entry_id=historic_id, tx_deletion=HistoricTxDeletion.ALL
            )
        )

        mcp_env.ucs.unsettle_manual_investment.execute.side_effect = (
            ManualHistoricEntryNotFinal(historic_id)
        )
        not_final = await tools.error(
            "unsettle_manual_investment", historic_entry_id=str(historic_id)
        )
        assert "Only completed or defaulted" in not_final

        wrong_type = await tools.error(
            "settle_manual_investment",
            entity_id=str(uuid4()),
            entry_id=str(uuid4()),
            product_type="STOCK_ETF",
        )
        assert "product_type" in wrong_type
