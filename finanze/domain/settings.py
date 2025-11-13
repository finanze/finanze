from dataclasses import field
from typing import Optional

from domain.commodity import WeightUnit
from pydantic.dataclasses import dataclass

CURRENT_VERSION = 4

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
class ExportPositionSheetConfig(BaseSheetConfig):
    data: list[str] = field(default_factory=list)


@dataclass
class ExportContributionSheetConfig(BaseSheetConfig):
    data: list[str] = field(default_factory=list)


@dataclass
class ExportTransactionsSheetConfig(BaseSheetConfig):
    data: list[str] = field(default_factory=list)
    filters: list[FilterConfig] | None = None


@dataclass
class ExportHistoricSheetConfig(BaseSheetConfig):
    filters: list[FilterConfig] | None = None


@dataclass
class SheetsExportConfig:
    globals: GlobalsConfig | None = None
    position: list[ExportPositionSheetConfig] = field(default_factory=list)
    contributions: list[ExportContributionSheetConfig] = field(default_factory=list)
    transactions: list[ExportTransactionsSheetConfig] = field(default_factory=list)
    historic: list[ExportHistoricSheetConfig] = field(default_factory=list)


@dataclass
class ExportConfig:
    sheets: Optional[SheetsExportConfig] = None


@dataclass
class ImportPositionSheetConfig(BaseSheetConfig):
    data: str = field(default_factory=str)


@dataclass
class ImportTransactionsSheetConfig(BaseSheetConfig):
    data: str = field(default_factory=str)


@dataclass
class SheetsImportConfig:
    globals: GlobalsConfig | None = None
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


@dataclass
class Settings:
    version: int = CURRENT_VERSION
    general: GeneralConfig = field(default_factory=GeneralConfig)
    export: ExportConfig = field(default_factory=ExportConfig)
    importing: ImportConfig = field(default_factory=ImportConfig)
    assets: AssetConfig = field(default_factory=AssetConfig)


ProductSheetConfig = (
    ExportPositionSheetConfig
    | ExportContributionSheetConfig
    | ExportTransactionsSheetConfig
    | ExportHistoricSheetConfig
    | ImportPositionSheetConfig
    | ImportTransactionsSheetConfig
)
