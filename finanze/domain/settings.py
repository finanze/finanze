from dataclasses import field
from enum import Enum
from typing import Optional

from domain.commodity import WeightUnit
from pydantic.dataclasses import dataclass

CURRENT_VERSION = 6

FilterValues = str | list[str]


@dataclass
class SheetsGlobalConfig:
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
    lastUpdate: bool | None = None


@dataclass
class TemplateConfig:
    id: str
    params: dict | None = None


@dataclass
class ExportSheetConfig(BaseSheetConfig):
    data: list[str] = field(default_factory=list)
    filters: list[FilterConfig] | None = None
    template: TemplateConfig | None = None


@dataclass
class ExportPositionSheetConfig(ExportSheetConfig):
    pass


@dataclass
class ExportContributionSheetConfig(ExportSheetConfig):
    pass


@dataclass
class ExportTransactionsSheetConfig(ExportSheetConfig):
    pass


@dataclass
class ExportHistoricSheetConfig(ExportSheetConfig):
    pass


@dataclass
class SheetsExportConfig:
    globals: SheetsGlobalConfig | None = None
    position: list[ExportPositionSheetConfig] = field(default_factory=list)
    contributions: list[ExportContributionSheetConfig] = field(default_factory=list)
    transactions: list[ExportTransactionsSheetConfig] = field(default_factory=list)
    historic: list[ExportHistoricSheetConfig] = field(default_factory=list)


@dataclass
class ExportConfig:
    sheets: Optional[SheetsExportConfig] = None


@dataclass
class ImportSheetConfig(BaseSheetConfig):
    template: TemplateConfig | None = None
    data: str = field(default_factory=str)


@dataclass
class ImportPositionSheetConfig(ImportSheetConfig):
    pass


@dataclass
class ImportTransactionsSheetConfig(ImportSheetConfig):
    pass


@dataclass
class SheetsImportConfig:
    globals: SheetsGlobalConfig | None = None
    position: list[ImportPositionSheetConfig] | None = None
    transactions: list[ImportTransactionsSheetConfig] | None = None


@dataclass
class ImportConfig:
    sheets: Optional[SheetsImportConfig] = None


@dataclass
class CryptoAssetConfig:
    stablecoins: list[str] = field(default_factory=list)
    hideUnknownTokens: bool = False


@dataclass
class AssetConfig:
    crypto: CryptoAssetConfig


@dataclass
class GeneralConfig:
    defaultCurrency: str = "EUR"
    defaultCommodityWeightUnit: str = WeightUnit.GRAM.value


class AutoRefreshMode(str, Enum):
    OFF = "OFF"
    NO_2FA = "NO_2FA"


class AutoRefreshMaxOutdatedTime(str, Enum):
    THREE_HOURS = "THREE_HOURS"
    SIX_HOURS = "SIX_HOURS"
    TWELVE_HOURS = "TWELVE_HOURS"
    DAY = "DAY"
    TWO_DAYS = "TWO_DAYS"
    WEEK = "WEEK"


@dataclass
class AutoRefreshEntityEntry:
    id: str


@dataclass
class AutoRefresh:
    mode: AutoRefreshMode = AutoRefreshMode.NO_2FA
    max_outdated: AutoRefreshMaxOutdatedTime = AutoRefreshMaxOutdatedTime.TWELVE_HOURS
    entities: list[AutoRefreshEntityEntry] = field(default_factory=list)


@dataclass
class DataConfig:
    autoRefresh: AutoRefresh = field(default_factory=AutoRefresh)


@dataclass
class Settings:
    lastUpdate: str
    version: int = CURRENT_VERSION
    general: GeneralConfig = field(default_factory=GeneralConfig)
    data: DataConfig = field(default_factory=DataConfig)
    export: ExportConfig = field(default_factory=ExportConfig)
    importing: ImportConfig = field(default_factory=ImportConfig)
    assets: AssetConfig = field(default_factory=AssetConfig)
