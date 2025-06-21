from dataclasses import field
from typing import Optional

from pydantic.dataclasses import dataclass

DataField = str | list[str]
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
    data: DataField = field(default_factory=list)


@dataclass
class ContributionSheetConfig(BaseSheetConfig):
    data: DataField = field(default_factory=list)


@dataclass
class TransactionSheetConfig(BaseSheetConfig):
    data: DataField = field(default_factory=list)
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
class VirtualInvestmentSheetConfig(BaseSheetConfig):
    data: str = field(default_factory=str)


@dataclass
class VirtualTransactionSheetConfig(BaseSheetConfig):
    data: str = field(default_factory=str)


@dataclass
class VirtualFetchConfig:
    enabled: bool = False
    globals: GlobalsConfig | None = None
    investments: list[VirtualInvestmentSheetConfig] | None = None
    transactions: list[VirtualTransactionSheetConfig] | None = None


@dataclass
class FetchConfig:
    virtual: VirtualFetchConfig
    updateCooldown: int


@dataclass
class SheetsIntegrationConfig:
    credentials: GoogleCredentials


@dataclass
class IntegrationsConfig:
    sheets: Optional[SheetsIntegrationConfig] = None


@dataclass
class GeneralConfig:
    defaultCurrency: str = "EUR"


@dataclass
class Settings:
    general: GeneralConfig = field(default_factory=GeneralConfig)
    integrations: IntegrationsConfig = field(default_factory=IntegrationsConfig)
    export: ExportConfig = field(default_factory=ExportConfig)
    fetch: FetchConfig = field(default_factory=FetchConfig)


ProductSheetConfig = (
    PositionSheetConfig
    | ContributionSheetConfig
    | TransactionSheetConfig
    | HistoricSheetConfig
    | VirtualInvestmentSheetConfig
    | VirtualTransactionSheetConfig
)
