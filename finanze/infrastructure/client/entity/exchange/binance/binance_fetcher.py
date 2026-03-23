import logging
import time
from datetime import datetime, timezone
from uuid import uuid4

from application.ports.financial_entity_fetcher import FinancialEntityFetcher
from domain.crypto import CryptoCurrencyType
from domain.dezimal import Dezimal
from domain.entity_login import EntityLoginParams, EntityLoginResult
from domain.fetch_record import DataSource
from domain.fetch_result import FetchOptions
from domain.global_position import (
    CryptoCurrencies,
    CryptoCurrencyPosition,
    CryptoCurrencyWallet,
    DerivativeContractType,
    DerivativeDetail,
    DerivativePositions,
    GlobalPosition,
    MarginType,
    PositionDirection,
    ProductType,
)
from domain.native_entities import BINANCE
from domain.transactions import CryptoCurrencyTx, Transactions, TxType
from infrastructure.client.entity.exchange.binance.binance_client import BinanceClient

FIAT_CURRENCIES = {
    "EUR",
    "USD",
    "GBP",
    "JPY",
    "AUD",
    "BRL",
    "CAD",
    "CHF",
    "CZK",
    "DKK",
    "HKD",
    "HUF",
    "IDR",
    "ILS",
    "INR",
    "KRW",
    "MXN",
    "MYR",
    "NOK",
    "NZD",
    "PHP",
    "PKR",
    "PLN",
    "RON",
    "RUB",
    "SEK",
    "SGD",
    "THB",
    "TRY",
    "TWD",
    "UAH",
    "ZAR",
    "ARS",
    "COP",
    "NGN",
    "BRL",
    "KES",
    "VND",
}

EXCLUDED_ASSETS = {
    "LDUSDT",
    "BFUSD",
    "RWUSD",
}

# Assets only relevant in the futures wallet context (not tradeable on spot)
FUTURES_ONLY_ASSETS = {"BNFCR"}

# Always query pairs involving these common quote currencies
ALWAYS_INCLUDE_ASSETS = {
    "EUR",
    "USD",
    "USDT",
    "USDC",
    "BUSD",
    "FDUSD",
    "BTC",
    "ETH",
    "BNB",
}

# Fiat currencies to use for market value, in order of preference
FIAT_QUOTES = ["EUR", "USD"]

# Stablecoin fallbacks: if no direct fiat pair exists, price via stablecoin then convert
STABLECOIN_QUOTES = ["USDT", "BUSD", "FDUSD", "USDC"]

# Max time range per deposit/withdrawal API call (90 days in ms)
_90_DAYS_MS = 90 * 24 * 60 * 60 * 1000


class BinanceFetcher(FinancialEntityFetcher):
    def __init__(self):
        self._client = BinanceClient()
        self._log = logging.getLogger(__name__)

    async def login(self, login_params: EntityLoginParams) -> EntityLoginResult:
        api_key = login_params.credentials.get("apiKey")
        secret_key = login_params.credentials.get("secretKey")
        return await self._client.setup(api_key, secret_key)

    async def global_position(self) -> GlobalPosition:
        spot_account = await self._client.get_spot_account()
        spot_assets = self._get_spot_assets(spot_account)

        price_index = await self._build_price_index()

        # Futures wallet assets + derivative positions
        futures_wallet_assets: dict[str, Dezimal] = {}
        derivative_entries = []
        try:
            futures_account = await self._client.get_futures_account()
            futures_wallet_assets = self._get_futures_wallet_assets(futures_account)

            # Derivative positions from positionRisk
            position_risk = await self._client.get_position_risk()
            self._log.info(f"positionRisk returned {len(position_risk)} entries")
            derivative_entries = self._build_derivative_positions(position_risk)
        except Exception as e:
            self._log.warning(f"Could not fetch futures data: {e}")

        # Combine spot + futures wallet balances per asset
        combined = dict(spot_assets)
        for asset, amount in futures_wallet_assets.items():
            if asset in combined:
                combined[asset] = combined[asset] + amount
            else:
                combined[asset] = amount

        # Build crypto positions from combined balances
        crypto_positions = []
        for symbol, amount in combined.items():
            if amount == 0:
                continue
            if symbol == "BNFCR":
                # BNFCR is 1:1 USD
                market_value = amount
                currency = "USD"
            else:
                market_value, currency = self._price_in_fiat(
                    symbol, amount, price_index
                )

            crypto_positions.append(
                CryptoCurrencyPosition(
                    id=uuid4(),
                    name=symbol,
                    symbol=symbol,
                    amount=amount,
                    type=CryptoCurrencyType.NATIVE,
                    market_value=market_value,
                    currency=currency,
                )
            )

        products = {
            ProductType.CRYPTO: CryptoCurrencies(
                [CryptoCurrencyWallet(assets=crypto_positions)]
            ),
        }
        if derivative_entries:
            products[ProductType.DERIVATIVE] = DerivativePositions(derivative_entries)

        return GlobalPosition(
            id=uuid4(),
            entity=BINANCE,
            products=products,
        )

    async def _build_price_index(self) -> dict[str, Dezimal]:
        """Build a symbol -> price lookup from ticker prices."""
        try:
            tickers = await self._client.get_ticker_prices()
            return {t["symbol"]: Dezimal(t["price"]) for t in tickers}
        except Exception as e:
            self._log.warning(f"Could not fetch ticker prices: {e}")
            return {}

    @staticmethod
    def _price_in_fiat(
        asset: str,
        amount: Dezimal,
        price_index: dict[str, Dezimal],
    ) -> tuple[Dezimal | None, str | None]:
        """Price an asset in fiat (EUR/USD). Falls back via stablecoin conversion."""
        # 1. Direct fiat pair (e.g. BTCEUR, BTCUSD)
        for fiat in FIAT_QUOTES:
            price = price_index.get(f"{asset}{fiat}")
            if price is not None:
                return round(amount * price, 4), fiat

        # 2. Via stablecoin: asset->stablecoin then stablecoin->fiat
        for stable in STABLECOIN_QUOTES:
            asset_price = price_index.get(f"{asset}{stable}")
            if asset_price is None:
                continue
            for fiat in FIAT_QUOTES:
                conversion = price_index.get(f"{stable}{fiat}")
                if conversion is not None:
                    return round(amount * asset_price * conversion, 4), fiat

        return None, None

    async def transactions(
        self, registered_txs: set[str], options: FetchOptions
    ) -> Transactions:
        exchange_info = await self._client.get_exchange_info()
        symbol_map = self._build_symbol_map(exchange_info)

        discovered_assets = await self._discover_assets()
        pairs_to_query = self._resolve_pairs(discovered_assets, symbol_map)

        self._log.info(
            f"Discovered {len(discovered_assets)} assets, "
            f"querying {len(pairs_to_query)} trading pairs"
        )

        investment_txs = []
        for pair_symbol in pairs_to_query:
            try:
                raw_trades = await self._client.get_my_trades(pair_symbol)
            except Exception as e:
                self._log.warning(f"Could not fetch trades for {pair_symbol}: {e}")
                continue

            if not raw_trades:
                continue

            base_asset, quote_asset = symbol_map[pair_symbol]

            # Collect new assets found from actual trades for further discovery
            discovered_assets.add(base_asset)
            discovered_assets.add(quote_asset)

            for raw_trade in raw_trades:
                ref = str(raw_trade["id"])
                if ref in registered_txs:
                    continue

                tx = self._map_trade(raw_trade, base_asset, quote_asset, pair_symbol)
                if tx:
                    investment_txs.append(tx)

        # Second pass: check if trades revealed new assets with unexplored pairs
        new_pairs = self._resolve_pairs(discovered_assets, symbol_map) - pairs_to_query
        for pair_symbol in new_pairs:
            try:
                raw_trades = await self._client.get_my_trades(pair_symbol)
            except Exception as e:
                self._log.warning(f"Could not fetch trades for {pair_symbol}: {e}")
                continue

            if not raw_trades:
                continue

            base_asset, quote_asset = symbol_map[pair_symbol]
            for raw_trade in raw_trades:
                ref = str(raw_trade["id"])
                if ref in registered_txs:
                    continue

                tx = self._map_trade(raw_trade, base_asset, quote_asset, pair_symbol)
                if tx:
                    investment_txs.append(tx)

        return Transactions(investment=investment_txs)

    async def _discover_assets(self) -> set[str]:
        """Discover all assets the user has interacted with."""
        assets: set[str] = set(ALWAYS_INCLUDE_ASSETS)

        # 1. Current spot balances
        spot_account = await self._client.get_spot_account()
        for b in spot_account.get("balances", []):
            if b["asset"] in EXCLUDED_ASSETS:
                continue
            total = Dezimal(b.get("free", "0")) + Dezimal(b.get("locked", "0"))
            if total > 0:
                assets.add(b["asset"])

        # 2. Deposit history (paginated in 90-day windows)
        deposit_coins = await self._scan_history(self._client.get_deposit_history)
        assets.update(deposit_coins)

        # 3. Withdrawal history (paginated in 90-day windows)
        withdrawal_coins = await self._scan_history(self._client.get_withdrawal_history)
        assets.update(withdrawal_coins)

        return assets

    async def _scan_history(self, fetch_fn) -> set[str]:
        """Scan deposit or withdrawal history in 90-day windows to extract coin names."""
        coins: set[str] = set()
        now_ms = int(time.time() * 1000)
        # Go back ~2 years (enough to catch most activity)
        start_ms = now_ms - (730 * 24 * 60 * 60 * 1000)
        window_start = start_ms

        while window_start < now_ms:
            window_end = min(window_start + _90_DAYS_MS, now_ms)
            try:
                records = await fetch_fn(start_time=window_start, end_time=window_end)
                for record in records:
                    coin = record.get("coin")
                    if coin:
                        coins.add(coin)
            except Exception as e:
                self._log.warning(f"Could not fetch history window: {e}")
            window_start = window_end

        return coins

    @staticmethod
    def _resolve_pairs(
        assets: set[str],
        symbol_map: dict[str, tuple[str, str]],
    ) -> set[str]:
        """Find all valid trading pairs where both base and quote are in the asset set."""
        pairs = set()
        for pair_symbol, (base, quote) in symbol_map.items():
            if base in assets and quote in assets:
                pairs.add(pair_symbol)
        return pairs

    @staticmethod
    def _build_symbol_map(exchange_info: dict) -> dict[str, tuple[str, str]]:
        symbol_map: dict[str, tuple[str, str]] = {}
        for s in exchange_info.get("symbols", []):
            if s.get("status") != "TRADING":
                continue
            symbol_map[s["symbol"]] = (s["baseAsset"], s["quoteAsset"])
        return symbol_map

    def _map_trade(
        self,
        raw_trade: dict,
        base_asset: str,
        quote_asset: str,
        pair_symbol: str,
    ) -> CryptoCurrencyTx | None:
        is_buyer = raw_trade["isBuyer"]
        tx_type = TxType.BUY if is_buyer else TxType.SELL

        price = Dezimal(raw_trade["price"])
        qty = Dezimal(raw_trade["qty"])
        quote_qty = Dezimal(raw_trade["quoteQty"])
        commission = Dezimal(raw_trade["commission"])
        commission_asset = raw_trade["commissionAsset"]
        timestamp_ms = raw_trade["time"]
        date = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)

        # symbol = base asset (the crypto being bought/sold)
        # currency = quote asset (what it's priced in, e.g. EUR, USDT, BTC)
        symbol = base_asset
        currency = quote_asset

        # Fees: normalize to quote currency
        if commission_asset == quote_asset:
            fees = commission
        elif commission_asset == base_asset:
            fees = commission * price
        else:
            fees = Dezimal(0)

        amount = quote_qty
        net_amount = (amount - fees) if is_buyer else (amount + fees)

        return CryptoCurrencyTx(
            id=uuid4(),
            ref=str(raw_trade["id"]),
            name=pair_symbol,
            amount=amount,
            currency=currency,
            type=tx_type,
            date=date,
            entity=BINANCE,
            net_amount=net_amount,
            symbol=symbol,
            contract_address=None,
            currency_amount=qty,
            price=price,
            fees=fees,
            retentions=Dezimal(0),
            order_date=None,
            product_type=ProductType.CRYPTO,
            source=DataSource.REAL,
        )

    @staticmethod
    def _get_spot_assets(spot_account: dict) -> dict[str, Dezimal]:
        assets: dict[str, Dezimal] = {}
        for balance in spot_account.get("balances", []):
            asset = balance["asset"]
            if (
                asset in FIAT_CURRENCIES
                or asset in EXCLUDED_ASSETS
                or asset in FUTURES_ONLY_ASSETS
            ):
                continue
            free = Dezimal(balance.get("free", "0"))
            locked = Dezimal(balance.get("locked", "0"))
            total = free + locked
            if total > 0:
                assets[asset] = total
        return assets

    @staticmethod
    def _get_futures_wallet_assets(
        futures_account: dict,
    ) -> dict[str, Dezimal]:
        """Extract non-zero futures wallet balances as {asset: amount} dict.

        BNFCR (1:1 USD) represents the cash debt in multi-asset mode.
        Other assets (e.g. BTC) are collateral held in the futures wallet.
        These will be combined with spot balances to avoid duplication.
        """
        assets: dict[str, Dezimal] = {}
        for asset_data in futures_account.get("assets", []):
            asset = asset_data["asset"]
            if asset in EXCLUDED_ASSETS:
                continue
            wallet_balance = Dezimal(asset_data.get("walletBalance", "0"))
            if wallet_balance == 0:
                continue
            assets[asset] = wallet_balance
        return assets

    @staticmethod
    def _build_derivative_positions(
        position_risk: list[dict],
    ) -> list[DerivativeDetail]:
        """Map positionRisk entries to DerivativeDetail domain objects."""
        entries = []
        for position in position_risk:
            position_amt = Dezimal(position.get("positionAmt", "0"))
            if position_amt == 0:
                continue

            symbol = position["symbol"]
            direction = (
                PositionDirection.LONG if position_amt > 0 else PositionDirection.SHORT
            )
            size = abs(position_amt)

            # Perpetual vs dated futures: dated contracts have "_" in the symbol
            if "_" in symbol:
                contract_type = DerivativeContractType.FUTURES
            else:
                contract_type = DerivativeContractType.PERPETUAL

            entry_price = Dezimal(position.get("entryPrice", "0"))
            mark_price = Dezimal(position.get("markPrice", "0"))
            unrealized_pnl = Dezimal(position.get("unRealizedProfit", "0"))
            initial_margin = Dezimal(position.get("initialMargin", "0"))
            notional = abs(Dezimal(position.get("notional", "0")))
            liquidation_price = Dezimal(position.get("liquidationPrice", "0"))
            margin_asset = position.get("marginAsset", "USDT")

            # Leverage = notional / initialMargin
            leverage = None
            if initial_margin and initial_margin != 0:
                leverage = round(notional / initial_margin, 0)

            # Margin type from isolated wallet value
            isolated_wallet = position.get("isolatedWallet", "0")
            margin_type = (
                MarginType.ISOLATED if isolated_wallet != "0" else MarginType.CROSS
            )

            entries.append(
                DerivativeDetail(
                    id=uuid4(),
                    symbol=symbol,
                    underlying_asset=ProductType.CRYPTO,
                    underlying_symbol=symbol.replace("USDT", "").replace("BUSD", ""),
                    contract_type=contract_type,
                    direction=direction,
                    size=size,
                    entry_price=entry_price,
                    currency=margin_asset,
                    mark_price=mark_price,
                    market_value=unrealized_pnl,
                    unrealized_pnl=unrealized_pnl,
                    leverage=leverage,
                    margin=initial_margin,
                    margin_type=margin_type,
                    liquidation_price=liquidation_price
                    if liquidation_price != 0
                    else None,
                    name=symbol,
                    source=DataSource.REAL,
                )
            )
        return entries
