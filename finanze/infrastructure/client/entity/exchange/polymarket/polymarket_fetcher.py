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

POLYMARKET_CURRENCY = "USDC"


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
            currency=POLYMARKET_CURRENCY,
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
            currency=POLYMARKET_CURRENCY,
            profile=client.profile,
            pnl_history=[
                MarketForecastPnlPoint(
                    timestamp=int(point["t"]),
                    value=Dezimal(point["p"]),
                    currency=POLYMARKET_CURRENCY,
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
                    name=position.get("title") or self._build_symbol(position),
                    size=size,
                    entry_price=avg_price,
                    currency=POLYMARKET_CURRENCY,
                    mark_price=(
                        Dezimal(position["curPrice"])
                        if position.get("curPrice") is not None
                        else None
                    ),
                    market_value=current_value,
                    unrealized_pnl=cash_pnl,
                    expiry=self._parse_date(position.get("endDate")),
                    initial_investment=initial_investment,
                    market_key=position.get("conditionId"),
                    event_key=position.get("eventSlug"),
                    outcome_key=position.get("asset"),
                    market_url=self._build_market_url(position),
                    icon_url=position.get("icon"),
                    outcome=position.get("outcome"),
                    source=DataSource.REAL,
                )
            )

        account_entries.append(
            Account(
                id=uuid4(),
                total=round(available_balance, 2),
                currency=available_balance_currency,
                type=AccountType.VIRTUAL_WALLET,
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
            currency=POLYMARKET_CURRENCY,
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
            currency=POLYMARKET_CURRENCY,
            name=position.get("title"),
            market_key=position.get("conditionId"),
            event_key=position.get("eventSlug"),
            outcome_key=position.get("asset"),
            market_url=PolymarketFetcher._build_market_url(position),
            icon_url=position.get("icon"),
            outcome=position.get("outcome"),
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

    @staticmethod
    def _build_market_url(entry: dict) -> str | None:
        market_slug = str(entry.get("slug") or "").strip()
        event_slug = str(entry.get("eventSlug") or "").strip()
        if event_slug and market_slug and event_slug != market_slug:
            return f"https://polymarket.com/event/{event_slug}/{market_slug}"

        final_slug = market_slug or event_slug
        return f"https://polymarket.com/event/{final_slug}" if final_slug else None
