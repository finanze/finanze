from datetime import datetime

from domain.commodity import WeightUnit
from domain.settings import (
    CURRENT_VERSION,
    AssetConfig,
    AutoRefresh,
    CryptoAssetConfig,
    DataConfig,
    GeneralConfig,
    Settings,
)

DEFAULT_STABLECOINS = [
    "USDT",
    "USDC",
    "USDe",
    "DAI",
    "USD1",
    "BUSD",
    "PYUSD",
    "FDUSD",
    "TUSD",
    "USDD",
    "GUSD",
    "USDP",
    "LUSD",
    "cUSD",
    "OUSD",
    "FRAX",
    "sUSD",
    "USDX",
    "USDY",
    "USYC",
    "EURC",
    "EURS",
    "EURT",
    "PAXG",
    "XAUT",
    "JPYC",
]

BASE_CONFIG = Settings(
    lastUpdate=datetime.now().astimezone().isoformat(),
    version=CURRENT_VERSION,
    general=GeneralConfig(
        defaultCurrency="EUR", defaultCommodityWeightUnit=WeightUnit.GRAM.value
    ),
    data=DataConfig(autoRefresh=AutoRefresh()),
    assets=AssetConfig(crypto=CryptoAssetConfig(stablecoins=DEFAULT_STABLECOINS)),
)
