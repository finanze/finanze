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
    GlobalPosition,
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
    "BNFCR",
    "RWUSD",
}

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

        futures_assets: dict[str, Dezimal] = {}
        try:
            futures_account = await self._client.get_futures_account()
            futures_assets = self._get_futures_assets(futures_account, spot_assets)
        except Exception as e:
            self._log.warning(f"Could not fetch futures account: {e}")

        combined = self._combine_assets(spot_assets, futures_assets)

        positions = []
        for symbol, amount in combined.items():
            if amount == 0:
                continue

            positions.append(
                CryptoCurrencyPosition(
                    id=uuid4(),
                    name=symbol,
                    symbol=symbol,
                    amount=amount,
                    type=CryptoCurrencyType.NATIVE,
                )
            )

        products = {
            ProductType.CRYPTO: CryptoCurrencies(
                [CryptoCurrencyWallet(assets=positions)]
            ),
        }

        return GlobalPosition(
            id=uuid4(),
            entity=BINANCE,
            products=products,
        )

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
            if asset in FIAT_CURRENCIES or asset in EXCLUDED_ASSETS:
                continue
            free = Dezimal(balance.get("free", "0"))
            locked = Dezimal(balance.get("locked", "0"))
            total = free + locked
            if total > 0:
                assets[asset] = total
        return assets

    @staticmethod
    def _get_futures_assets(
        futures_account: dict, spot_assets: dict[str, Dezimal]
    ) -> dict[str, Dezimal]:
        assets: dict[str, Dezimal] = {}
        for asset_data in futures_account.get("assets", []):
            asset = asset_data["asset"]
            if asset in FIAT_CURRENCIES or asset in EXCLUDED_ASSETS:
                continue
            wallet_balance = Dezimal(asset_data.get("walletBalance", "0"))
            if wallet_balance > 0 and asset in spot_assets:
                assets[asset] = wallet_balance
        return assets

    @staticmethod
    def _combine_assets(
        spot: dict[str, Dezimal], futures: dict[str, Dezimal]
    ) -> dict[str, Dezimal]:
        combined: dict[str, Dezimal] = dict(spot)
        for asset, amount in futures.items():
            if asset in combined:
                combined[asset] = combined[asset] + amount
            else:
                combined[asset] = amount
        return combined
