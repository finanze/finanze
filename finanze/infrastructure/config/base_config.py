from domain.commodity import WeightUnit
from domain.settings import (
    CURRENT_VERSION,
    AssetConfig,
    CryptoAssetConfig,
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
    version=CURRENT_VERSION,
    general=GeneralConfig(
        defaultCurrency="EUR", defaultCommodityWeightUnit=WeightUnit.GRAM.value
    ),
    assets=AssetConfig(crypto=CryptoAssetConfig(stablecoins=DEFAULT_STABLECOINS)),
)
