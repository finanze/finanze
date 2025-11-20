from dataclasses import field
from typing import Optional

from domain.commodity import WeightUnit
from pydantic.dataclasses import dataclass

CURRENT_VERSION = 5

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


@dataclass
class Settings:
    version: int = CURRENT_VERSION
    general: GeneralConfig = field(default_factory=GeneralConfig)
    export: ExportConfig = field(default_factory=ExportConfig)
    importing: ImportConfig = field(default_factory=ImportConfig)
    assets: AssetConfig = field(default_factory=AssetConfig)
