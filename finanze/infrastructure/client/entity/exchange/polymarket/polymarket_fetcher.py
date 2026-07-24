from collections import OrderedDict
from uuid import uuid4

from application.ports.financial_entity_fetcher import FinancialEntityFetcher
from domain.dezimal import Dezimal
from domain.entity_login import EntityLoginParams, EntityLoginResult
from domain.fetch_record import DataSource
from domain.fetch_result import FetchOptions
from domain.global_position import (
    Account,
    Accounts,
    AccountType,
    DerivativeContractType,
    DerivativeDetail,
    DerivativePositions,
    GlobalPosition,
    PositionDirection,
    ProductType,
)
from domain.native_entities import POLYMARKET
from domain.transactions import DerivativeTx, Transactions, TxType
from infrastructure.client.entity.exchange.polymarket.polymarket_client import (
    PolymarketClient,
)


class PolymarketFetcher(FinancialEntityFetcher):
    def __init__(self):
        self._client = PolymarketClient()

    async def login(self, login_params: EntityLoginParams) -> EntityLoginResult:
        return await self._client.setup(login_params)

    async def global_position(self) -> GlobalPosition:
        positions = await self._client.get_positions()
        (
            available_balance,
            available_balance_currency,
        ) = await self._client.get_available_balance()
        derivative_entries: list[DerivativeDetail] = []
        account_entries: list[Account] = []

        for position in positions:
            size = Dezimal(position.get("size", 0))
            if size == 0:
                continue

            avg_price = Dezimal(position.get("avgPrice", 0))
            current_value = Dezimal(position.get("currentValue", 0))
            initial_investment = Dezimal(position.get("initialValue", 0))
            cash_pnl = Dezimal(position.get("cashPnl", 0))
            derivative_entries.append(
                DerivativeDetail(
                    id=uuid4(),
                    symbol=self._build_symbol(position),
                    name=position.get("title") or self._build_symbol(position),
                    underlying_asset=ProductType.CRYPTO,
                    underlying_symbol=position.get("outcome") or position.get("slug"),
                    contract_type=DerivativeContractType.OTHER,
                    direction=PositionDirection.LONG,
                    size=size,
                    entry_price=avg_price,
                    currency="USDC",
                    mark_price=(current_value / size) if size != 0 else None,
                    market_value=current_value,
                    unrealized_pnl=cash_pnl,
                    expiry=self._parse_date(position.get("endDate")),
                    initial_investment=initial_investment,
                    source=DataSource.REAL,
                )
            )

        account_entries.append(
            Account(
                id=uuid4(),
                total=round(available_balance, 2),
                currency=available_balance_currency,
                type=AccountType.VIRTUAL_WALLET,
                name="Polymarket available balance",
                source=DataSource.REAL,
            )
        )

        products = {}
        if account_entries:
            products[ProductType.ACCOUNT] = Accounts(account_entries)
        if derivative_entries:
            products[ProductType.DERIVATIVE] = DerivativePositions(
                entries=derivative_entries
            )

        return GlobalPosition(
            id=uuid4(),
            entity=POLYMARKET,
            products=products,
        )

    async def transactions(
        self, registered_txs: set[str], options: FetchOptions
    ) -> Transactions:
        trades = await self._client.get_trades()
        activity = await self._client.get_activity()

        txs_by_ref: OrderedDict[str, DerivativeTx] = OrderedDict()

        for raw_trade in trades:
            tx = self._map_trade(raw_trade)
            if tx.ref in registered_txs:
                continue
            txs_by_ref.setdefault(tx.ref, tx)

        for raw_activity in activity:
            tx = self._map_trade(raw_activity)
            if tx.ref in registered_txs:
                continue
            txs_by_ref.setdefault(tx.ref, tx)

        return Transactions(investment=list(txs_by_ref.values()))

    def _map_trade(self, raw_trade: dict) -> DerivativeTx:
        tx_type = (
            TxType.BUY
            if str(raw_trade.get("side", "BUY")).upper() == "BUY"
            else TxType.SELL
        )
        size = Dezimal(raw_trade.get("size", 0))
        price = Dezimal(raw_trade.get("price", 0))
        amount = Dezimal(raw_trade.get("usdcSize") or (size * price))
        timestamp = self._client.parse_timestamp(raw_trade.get("timestamp"))
        contract_address = raw_trade.get("asset")
        condition_id = raw_trade.get("conditionId")
        ref = str(
            raw_trade.get("transactionHash")
            or raw_trade.get("id")
            or (
                f"{condition_id}-{timestamp.isoformat()}-"
                f"{raw_trade.get('side', '')}-{size}"
            )
        )

        return DerivativeTx(
            id=uuid4(),
            ref=ref,
            name=raw_trade.get("title") or self._build_symbol(raw_trade),
            amount=amount,
            currency="USDC",
            type=tx_type,
            date=timestamp,
            entity=POLYMARKET,
            product_type=ProductType.DERIVATIVE,
            source=DataSource.REAL,
            symbol=self._build_symbol(raw_trade),
            size=size,
            price=price,
            fees=Dezimal(0),
            net_amount=amount,
            order_date=timestamp,
            contract_address=contract_address,
            linked_tx=condition_id,
            direction=PositionDirection.LONG,
            contract_type=DerivativeContractType.OTHER,
            underlying_asset=ProductType.CRYPTO,
            underlying_symbol=raw_trade.get("outcome") or raw_trade.get("slug"),
        )

    @staticmethod
    def _build_symbol(entry: dict) -> str:
        title = str(entry.get("title") or "").strip()
        outcome = str(entry.get("outcome") or "").strip()
        if title and outcome:
            return f"{title} [{outcome}]"
        return (
            title
            or outcome
            or str(entry.get("conditionId") or entry.get("asset") or "Polymarket")
        )

    @staticmethod
    def _parse_date(value: str | None):
        if not value:
            return None
        return PolymarketClient.parse_timestamp(value).date()
