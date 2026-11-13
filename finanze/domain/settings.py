from dataclasses import field
from enum import Enum
from typing import Literal, Optional

from domain.commodity import WeightUnit
from domain.transactions import LabelOrigin, is_valid_iban_format, normalize_iban
from pydantic import Field, field_validator
from pydantic.dataclasses import dataclass

CURRENT_VERSION = 8
MAX_AI_PROVIDERS = 5

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
class AIProviderEntry:
    provider: str = Field(min_length=1, max_length=200)
    model: str = Field(min_length=1, max_length=200)
    upstreamProvider: Optional[str] = None

    @field_validator("provider", "model", "upstreamProvider", mode="before")
    @classmethod
    def trim_values(cls, value):
        return value.strip() if isinstance(value, str) else value


def _unique_entries(providers: list[AIProviderEntry]) -> list[AIProviderEntry]:
    identities = [
        (entry.provider, entry.model, entry.upstreamProvider or None)
        for entry in providers
    ]
    if len(identities) != len(set(identities)):
        raise ValueError("Duplicate AI providers")
    return providers


def effective_ai_providers(
    default: list[AIProviderEntry], override: list[AIProviderEntry]
) -> list[AIProviderEntry]:
    return list(override or default)


@dataclass
class AIConfig:
    providers: list[AIProviderEntry] = Field(
        default_factory=list, max_length=MAX_AI_PROVIDERS
    )

    @field_validator("providers")
    @classmethod
    def unique_providers(cls, providers):
        return _unique_entries(providers)


@dataclass
class AIImportConfig:
    providers: list[AIProviderEntry] = Field(
        default_factory=list, max_length=MAX_AI_PROVIDERS
    )
    instructions: Optional[str] = None

    @field_validator("providers")
    @classmethod
    def unique_providers(cls, providers):
        return _unique_entries(providers)


@dataclass
class ImportConfig:
    sheets: Optional[SheetsImportConfig] = None
    ai: AIImportConfig = field(default_factory=AIImportConfig)


@dataclass
class CryptoAssetConfig:
    stablecoins: list[str] = field(default_factory=list)
    hideUnknownTokens: bool = False


@dataclass
class AccountExclusion:
    type: Literal["IBAN"]
    value: str

    @field_validator("value", mode="before")
    @classmethod
    def validate_iban(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("Invalid IBAN")
        normalized = normalize_iban(value)
        if not normalized or not is_valid_iban_format(normalized):
            raise ValueError("Invalid IBAN")
        return normalized


@dataclass
class AccountAssetConfig:
    exclusions: list[AccountExclusion] = field(default_factory=list)

    @field_validator("exclusions")
    @classmethod
    def unique_exclusions(
        cls, exclusions: list[AccountExclusion]
    ) -> list[AccountExclusion]:
        values = [rule.value for rule in exclusions]
        if len(values) != len(set(values)):
            raise ValueError("Duplicate account exclusions")
        return exclusions


@dataclass
class AssetConfig:
    crypto: CryptoAssetConfig
    accounts: AccountAssetConfig = field(default_factory=AccountAssetConfig)


class EditMode(str, Enum):
    DRAFT = "DRAFT"
    QUICK = "QUICK"


@dataclass
class GeneralConfig:
    defaultCurrency: str = "EUR"
    defaultCommodityWeightUnit: str = WeightUnit.GRAM.value
    editMode: EditMode = EditMode.QUICK


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
class ExternalLabelingExamplesConfig:
    enabled: bool = False
    count: int = 20
    origins: list[LabelOrigin] = field(
        default_factory=lambda: [LabelOrigin.MANUAL, LabelOrigin.RULE]
    )


@dataclass
class ExternalLabelingConfig:
    enabled: bool = False
    providers: list[AIProviderEntry] = Field(
        default_factory=list, max_length=MAX_AI_PROVIDERS
    )
    autoRun: bool = True
    minConfidence: int = 70
    maxPerRun: int = 400
    examples: ExternalLabelingExamplesConfig = field(
        default_factory=ExternalLabelingExamplesConfig
    )
    instructions: Optional[str] = None

    @field_validator("providers")
    @classmethod
    def unique_providers(cls, providers):
        return _unique_entries(providers)


@dataclass
class LabelingConfig:
    external: ExternalLabelingConfig = field(default_factory=ExternalLabelingConfig)


class SettingsSection(str, Enum):
    GENERAL = "general"
    DATA = "data"
    EXPORT = "export"
    IMPORTING = "importing"
    ASSETS = "assets"
    LABELING = "labeling"
    AI = "ai"


@dataclass
class Settings:
    lastUpdate: str
    version: int = CURRENT_VERSION
    general: GeneralConfig = field(default_factory=GeneralConfig)
    data: DataConfig = field(default_factory=DataConfig)
    export: ExportConfig = field(default_factory=ExportConfig)
    importing: ImportConfig = field(default_factory=ImportConfig)
    assets: AssetConfig = field(default_factory=AssetConfig)
    labeling: LabelingConfig = field(default_factory=LabelingConfig)
    ai: AIConfig = field(default_factory=AIConfig)


@dataclass
class PartialSettings:
    lastUpdate: Optional[str] = None
    version: int = CURRENT_VERSION
    general: Optional[GeneralConfig] = None
    data: Optional[DataConfig] = None
    export: Optional[ExportConfig] = None
    importing: Optional[ImportConfig] = None
    assets: Optional[AssetConfig] = None
    labeling: Optional[LabelingConfig] = None
    ai: Optional[AIConfig] = None

    def included_sections(self) -> list[SettingsSection]:
        return [
            section
            for section in SettingsSection
            if getattr(self, section.value) is not None
        ]
