import hashlib
import logging
from datetime import datetime
from uuid import uuid4

from application.ports.financial_entity_fetcher import FinancialEntityFetcher
from dateutil.tz import tzlocal
from domain.dezimal import Dezimal
from domain.entity_login import EntityLoginParams, EntityLoginResult
from domain.fetch_record import DataSource
from domain.fetch_result import FetchOptions
from domain.global_position import (
    FundDetail,
    FundInvestments,
    FundType,
    GlobalPosition,
    ProductType,
)
from domain.native_entities import CRESCENTA
from domain.transactions import FundTx, Transactions, TxType
from infrastructure.client.entity.financial.crescenta.crescenta_client import (
    CrescentaClient,
)


class CrescentaFetcher(FinancialEntityFetcher):
    def __init__(self):
        self._client = CrescentaClient()
        self._log = logging.getLogger(__name__)

    async def login(self, login_params: EntityLoginParams) -> EntityLoginResult:
        credentials = login_params.credentials
        return await self._client.login(credentials["user"], credentials["password"])

    async def global_position(self) -> GlobalPosition:
        account = await self._client.get_current_account()
        account_id = account.get("id")
        if not account_id:
            return GlobalPosition(id=uuid4(), entity=CRESCENTA, products={})

        flow_data = await self._client.get_flow_data(account_id)
        portfolio_ids: list[str] = []
        product_id_to_participations: dict[str, Dezimal] = {}
        product_name_to_id: dict[str, str] = {}

        for portfolio in flow_data.get("portfolios", []):
            portfolio_id = portfolio.get("id")
            if portfolio_id and portfolio_id not in portfolio_ids:
                portfolio_ids.append(portfolio_id)
            for contract in portfolio.get("contracts", []):
                product_name = contract.get("product")
                product_id = contract.get("productId")
                if product_name and product_id:
                    product_name_to_id[product_name] = product_id
                participations = contract.get("participations")
                if product_id and participations is not None:
                    product_id_to_participations[product_id] = Dezimal(participations)

        fund_details: list[FundDetail] = []
        for portfolio_id in portfolio_ids:
            portfolio_data = await self._client.get_portfolio_data(portfolio_id)
            for position in portfolio_data.get("accountPositions", []):
                product_name = position.get("productName")
                if not product_name or product_name.upper() == "TOTAL":
                    continue
                product_id = position.get("productId") or product_name_to_id.get(
                    product_name
                )
                if not product_id:
                    continue
                details = await self._client.get_product_details(account_id, product_id)
                isin = self._resolve_isin(details, product_id)
                currency = details.get("currency") or "EUR"
                shares = product_id_to_participations.get(product_id) or Dezimal(
                    position.get("disbursed", 0)
                )
                disbursed = Dezimal(position.get("disbursed", 0))
                nav = position.get("nav")
                market_value = Dezimal(
                    nav if nav is not None else position.get("totalValue", 0)
                )
                fund_details.append(
                    FundDetail(
                        id=uuid4(),
                        name=product_name,
                        isin=isin,
                        market=None,
                        shares=shares,
                        initial_investment=disbursed,
                        market_value=market_value,
                        currency=currency,
                        type=FundType.PRIVATE_EQUITY,
                        source=DataSource.REAL,
                    )
                )

        products = {
            ProductType.FUND: FundInvestments(fund_details),
        }
        return GlobalPosition(id=uuid4(), entity=CRESCENTA, products=products)

    @staticmethod
    def _resolve_isin(details: dict, product_id: str) -> str:
        isin = details.get("isin")
        if isin:
            return isin
        product_class = details.get("productClass") or {}
        isin = product_class.get("isin")
        if isin:
            return isin
        return product_id

    @staticmethod
    def _parse_date(date_str: str | None) -> datetime:
        if not date_str:
            return datetime.now(tzlocal())
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt.astimezone(tzlocal())
        except Exception:
            return datetime.now(tzlocal())

    @staticmethod
    def _calc_ref(
        date_str: str, concept: str, product_name: str, amount: Dezimal
    ) -> str:
        raw = f"{date_str}|{concept}|{product_name}|{amount}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    async def transactions(
        self, registered_txs: set[str], options: FetchOptions
    ) -> Transactions:
        account = await self._client.get_current_account()
        account_id = account.get("id")
        if not account_id:
            return Transactions(investment=[], account=[])

        flow_data = await self._client.get_flow_data(account_id)
        product_name_to_id: dict[str, str] = {}
        for portfolio in flow_data.get("portfolios", []):
            for contract in portfolio.get("contracts", []):
                product_name = contract.get("product")
                product_id = contract.get("productId")
                if product_name and product_id:
                    product_name_to_id[product_name] = product_id

        movements_data = await self._client.get_movements(account_id)
        investment_txs: list[FundTx] = []
        for movement in movements_data.get("items", []):
            if movement.get("status") != "SUCCESS":
                continue
            if movement.get("type") != "CAPITAL_CALL":
                continue
            product_name = movement.get("productName")
            if not product_name:
                continue
            amount = Dezimal(movement.get("amount", 0))
            if amount == 0:
                continue
            date_str = movement.get("date") or ""
            concept = movement.get("concept") or ""
            ref = self._calc_ref(date_str, concept, product_name, amount)
            if ref in registered_txs:
                continue
            product_id = product_name_to_id.get(product_name)
            details = {}
            if product_id:
                details = await self._client.get_product_details(account_id, product_id)
            isin = self._resolve_isin(details, product_id or product_name)
            currency = details.get("currency") or "EUR"
            investment_txs.append(
                FundTx(
                    id=uuid4(),
                    ref=ref,
                    name=concept or product_name,
                    amount=amount,
                    currency=currency,
                    type=TxType.BUY,
                    date=self._parse_date(date_str),
                    entity=CRESCENTA,
                    source=DataSource.REAL,
                    product_type=ProductType.FUND,
                    shares=amount,
                    price=Dezimal(1),
                    fees=Dezimal(0),
                    net_amount=amount,
                    isin=isin,
                    fund_type=FundType.PRIVATE_EQUITY,
                )
            )

        return Transactions(investment=investment_txs, account=[])
