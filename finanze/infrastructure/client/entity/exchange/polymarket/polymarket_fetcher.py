from collections import OrderedDict
from uuid import uuid4

from application.ports.financial_entity_fetcher import FinancialEntityFetcher
from application.ports.market_forecast_provider import MarketForecastProvider
from domain.dezimal import Dezimal
from domain.entity_login import EntityLoginParams, EntityLoginResult, LoginResultCode
from domain.fetch_record import DataSource
from domain.fetch_result import FetchOptions
from domain.global_position import (
    Account,
    AccountType,
    Accounts,
    GlobalPosition,
    MarketForecastDetail,
    MarketForecastPositions,
    PositionDirection,
    ProductType,
)
from domain.market_forecast import (
    MarketForecastClosedPosition,
    MarketForecastClosedPositionsAccountData,
    MarketForecastPnlAccountData,
    MarketForecastPnlPoint,
)
from domain.native_entities import POLYMARKET
from domain.transactions import MarketForecastTx, Transactions, TxType
from infrastructure.client.entity.exchange.polymarket.polymarket_client import (
    PolymarketClient,
)


class PolymarketFetcher(FinancialEntityFetcher, MarketForecastProvider):
    def __init__(self):
        self._client = PolymarketClient()

    async def login(self, login_params: EntityLoginParams) -> EntityLoginResult:
        return await self._client.setup(login_params)

    async def get_closed_positions(
        self, login_params: EntityLoginParams
    ) -> MarketForecastClosedPositionsAccountData | None:
        client = PolymarketClient()
        result = await client.setup(login_params)
        if result.code != LoginResultCode.CREATED:
            return None

        return MarketForecastClosedPositionsAccountData(
            wallet_address=client.wallet_address,
            profile=client.profile,
            closed_positions=[
                self._map_closed_position(position)
                for position in await client.get_closed_positions()
            ],
        )

    async def get_pnl_history(
        self, login_params: EntityLoginParams, interval: str = "all"
    ) -> MarketForecastPnlAccountData | None:
        client = PolymarketClient()
        result = await client.setup(login_params)
        if result.code != LoginResultCode.CREATED:
            return None

        return MarketForecastPnlAccountData(
            wallet_address=client.wallet_address,
            profile=client.profile,
            pnl_history=[
                MarketForecastPnlPoint(
                    timestamp=int(point["t"]),
                    value=Dezimal(point["p"]),
                )
                for point in await client.get_user_pnl(interval=interval)
            ],
        )

    async def global_position(self) -> GlobalPosition:
        positions = await self._client.get_positions()
        (
            available_balance,
            available_balance_currency,
        ) = await self._client.get_available_balance()
        market_forecast_entries: list[MarketForecastDetail] = []
        account_entries: list[Account] = []

        for position in positions:
            size = Dezimal(position.get("size", 0))
            if size == 0:
                continue

            avg_price = Dezimal(position.get("avgPrice", 0))
            current_value = Dezimal(position.get("currentValue", 0))
            initial_investment = Dezimal(position.get("initialValue", 0))
            cash_pnl = Dezimal(position.get("cashPnl", 0))
            market_forecast_entries.append(
                MarketForecastDetail(
                    id=uuid4(),
                    symbol=self._build_symbol(position),
                    name=position.get("title") or self._build_symbol(position),
                    market_type="BINARY",
                    direction=PositionDirection.LONG,
                    size=size,
                    entry_price=avg_price,
                    currency="USDC",
                    mark_price=(current_value / size) if size != 0 else None,
                    market_value=current_value,
                    unrealized_pnl=cash_pnl,
                    underlying_symbol=position.get("outcome") or position.get("slug"),
                    expiry=self._parse_date(position.get("endDate")),
                    initial_investment=initial_investment,
                    market_slug=position.get("slug"),
                    event_slug=position.get("eventSlug"),
                    outcome=position.get("outcome"),
                    condition_id=position.get("conditionId"),
                    token_id=position.get("asset"),
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
        if market_forecast_entries:
            products[ProductType.MARKET_FORECAST] = MarketForecastPositions(
                entries=market_forecast_entries
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

        txs_by_ref: OrderedDict[str, MarketForecastTx] = OrderedDict()

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

    def _map_trade(self, raw_trade: dict) -> MarketForecastTx:
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

        return MarketForecastTx(
            id=uuid4(),
            ref=ref,
            name=raw_trade.get("title") or self._build_symbol(raw_trade),
            amount=amount,
            currency="USDC",
            type=tx_type,
            date=timestamp,
            entity=POLYMARKET,
            product_type=ProductType.MARKET_FORECAST,
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
            market_type="BINARY",
            underlying_symbol=raw_trade.get("outcome") or raw_trade.get("slug"),
            market_slug=raw_trade.get("slug"),
            event_slug=raw_trade.get("eventSlug"),
            outcome=raw_trade.get("outcome"),
            condition_id=condition_id,
            token_id=raw_trade.get("asset"),
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
    def _map_closed_position(position: dict) -> MarketForecastClosedPosition:
        return MarketForecastClosedPosition(
            title=position.get("title"),
            slug=position.get("slug"),
            event_slug=position.get("eventSlug"),
            icon=position.get("icon"),
            outcome=position.get("outcome"),
            condition_id=position.get("conditionId"),
            asset=position.get("asset"),
            size=Dezimal(position["size"])
            if position.get("size") is not None
            else None,
            avg_price=(
                Dezimal(position["avgPrice"])
                if position.get("avgPrice") is not None
                else None
            ),
            price=Dezimal(position["price"])
            if position.get("price") is not None
            else None,
            initial_value=(
                Dezimal(position["initialValue"])
                if position.get("initialValue") is not None
                else None
            ),
            current_value=(
                Dezimal(position["currentValue"])
                if position.get("currentValue") is not None
                else None
            ),
            cash_pnl=(
                Dezimal(position["cashPnl"])
                if position.get("cashPnl") is not None
                else None
            ),
            percent_pnl=(
                Dezimal(position["percentPnl"])
                if position.get("percentPnl") is not None
                else None
            ),
            cur_price=(
                Dezimal(position["curPrice"])
                if position.get("curPrice") is not None
                else None
            ),
            redemption_value=(
                Dezimal(position["redemptionValue"])
                if position.get("redemptionValue") is not None
                else None
            ),
            end_date=position.get("endDate"),
            created_at=position.get("createdAt"),
            updated_at=position.get("updatedAt"),
            closed_at=position.get("closedAt"),
            realized_pnl=(
                Dezimal(position["realizedPnl"])
                if position.get("realizedPnl") is not None
                else None
            ),
            total_bought=(
                Dezimal(position["totalBought"])
                if position.get("totalBought") is not None
                else None
            ),
            total_sold=(
                Dezimal(position["totalSold"])
                if position.get("totalSold") is not None
                else None
            ),
        )

    @staticmethod
    def _parse_date(value: str | None):
        if not value:
            return None
        return PolymarketClient.parse_timestamp(value).date()
