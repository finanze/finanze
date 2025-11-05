from dataclasses import field
from typing import Optional

from domain.commodity import WeightUnit
from pydantic.dataclasses import dataclass

FilterValues = str | list[str]


@dataclass
class GlobalsConfig:
    spreadsheetId: str
    datetimeFormat: str | None = None
    dateFormat: str | None = None


@dataclass
class FilterConfig:
    field: str
    values: FilterValues


@dataclass
class BaseSheetConfig:
    range: str
    spreadsheetId: str | None = None
    datetimeFormat: str | None = None
    dateFormat: str | None = None


@dataclass
class PositionSheetConfig(BaseSheetConfig):
    data: list[str] = field(default_factory=list)


@dataclass
class ContributionSheetConfig(BaseSheetConfig):
    data: list[str] = field(default_factory=list)


@dataclass
class TransactionSheetConfig(BaseSheetConfig):
    data: list[str] = field(default_factory=list)
    filters: list[FilterConfig] | None = None


@dataclass
class HistoricSheetConfig(BaseSheetConfig):
    filters: list[FilterConfig] | None = None


@dataclass
class GoogleCredentials:
    client_id: str
    client_secret: str


@dataclass
class SheetsConfig:
    enabled: bool
    globals: GlobalsConfig | None = None
    position: list[PositionSheetConfig] = field(default_factory=list)
    contributions: list[ContributionSheetConfig] = field(default_factory=list)
    transactions: list[TransactionSheetConfig] = field(default_factory=list)
    historic: list[HistoricSheetConfig] = field(default_factory=list)


@dataclass
class ExportConfig:
    sheets: Optional[SheetsConfig] = None


@dataclass
class VirtualPositionSheetConfig(BaseSheetConfig):
    data: str = field(default_factory=str)


@dataclass
class VirtualTransactionSheetConfig(BaseSheetConfig):
    data: str = field(default_factory=str)


@dataclass
class VirtualFetchConfig:
    enabled: bool = False
    globals: GlobalsConfig | None = None
    position: list[VirtualPositionSheetConfig] | None = None
    transactions: list[VirtualTransactionSheetConfig] | None = None


@dataclass
class FetchConfig:
    virtual: VirtualFetchConfig


@dataclass
class SheetsIntegrationConfig:
    credentials: GoogleCredentials


@dataclass
class EtherscanIntegrationConfig:
    api_key: str


@dataclass
class GoCardlessIntegrationConfig:
    secret_id: str
    secret_key: str


@dataclass
class IntegrationsConfig:
    sheets: Optional[SheetsIntegrationConfig] = None
    etherscan: Optional[EtherscanIntegrationConfig] = None
    gocardless: Optional[GoCardlessIntegrationConfig] = None


@dataclass
class CryptoAssetConfig:
    stablecoins: list[str] = field(default_factory=list)


@dataclass
class AssetConfig:
    crypto: CryptoAssetConfig


@dataclass
class GeneralConfig:
    defaultCurrency: str = "EUR"
    defaultCommodityWeightUnit: str = WeightUnit.GRAM.value


@dataclass
class Settings:
    general: GeneralConfig = field(default_factory=GeneralConfig)
    integrations: IntegrationsConfig = field(default_factory=IntegrationsConfig)
    export: ExportConfig = field(default_factory=ExportConfig)
    fetch: FetchConfig = field(default_factory=FetchConfig)
    assets: AssetConfig = field(default_factory=AssetConfig)


ProductSheetConfig = (
    PositionSheetConfig
    | ContributionSheetConfig
    | TransactionSheetConfig
    | HistoricSheetConfig
    | VirtualPositionSheetConfig
    | VirtualTransactionSheetConfig
)
