import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

import strictyaml

from domain.settings import (
    AutoRefresh,
    AutoRefreshEntityEntry,
    AutoRefreshMaxOutdatedTime,
    AutoRefreshMode,
    EditMode,
    ExportConfig,
    ExportPositionSheetConfig,
    ExportTransactionsSheetConfig,
    ExternalLabelingConfig,
    ExternalLabelingExamplesConfig,
    FilterConfig,
    ImportConfig,
    ImportPositionSheetConfig,
    ImportTransactionsSheetConfig,
    LabelingConfig,
    Settings,
    SheetsExportConfig,
    SheetsGlobalConfig,
    SheetsImportConfig,
    TemplateConfig,
)
from domain.transactions import LabelOrigin
from infrastructure.config.base_config import BASE_CONFIG
from infrastructure.config.config_migrator import ConfigMigrator

SAMPLES_DIR = Path(__file__).parent / "resources" / "legacy_config"

SECTION_KEYS = ("general", "data", "export", "importing", "assets", "labeling")
V8_SECTIONS = frozenset({"general", "data", "assets", "labeling"})
ALL_SECTIONS = frozenset(SECTION_KEYS)

V8_LAST_UPDATE = datetime.fromisoformat("2026-03-01T10:00:00+01:00")


def read_sample(name: str) -> str:
    return (SAMPLES_DIR / name).read_text()


def parse_sample(name: str) -> Any:
    content = read_sample(name)
    if name.endswith(".json"):
        return json.loads(content)
    return strictyaml.load(content).data


def mobile_backup_payload(name: str) -> bytes:
    return strictyaml.as_document(json.loads(read_sample(name))).as_yaml().encode()


def _base() -> Settings:
    return deepcopy(BASE_CONFIG)


def default_settings() -> Settings:
    return _base()


def custom_settings() -> Settings:
    settings = _base()
    settings.general.defaultCurrency = "USD"
    settings.general.defaultCommodityWeightUnit = "TROY_OUNCE"
    settings.general.editMode = EditMode.DRAFT
    settings.data.autoRefresh = AutoRefresh(
        mode=AutoRefreshMode.OFF,
        max_outdated=AutoRefreshMaxOutdatedTime.WEEK,
        entities=[
            AutoRefreshEntityEntry(id="e0000000-0000-0000-0000-000000000001"),
            AutoRefreshEntityEntry(id="e0000000-0000-0000-0000-000000000002"),
        ],
    )
    settings.export = ExportConfig(
        sheets=SheetsExportConfig(
            globals=SheetsGlobalConfig(
                spreadsheetId="sheet-global", dateFormat="%d/%m/%Y"
            ),
            position=[
                ExportPositionSheetConfig(
                    range="Positions!A1",
                    data=["STOCK_ETF", "FUND"],
                    filters=[FilterConfig(field="entity", values=["MyBank"])],
                    lastUpdate=True,
                )
            ],
            transactions=[
                ExportTransactionsSheetConfig(
                    range="Txs!A1",
                    spreadsheetId="sheet-txs",
                    data=["ACCOUNT"],
                    template=TemplateConfig(id="tpl-1", params={"sep": ";"}),
                )
            ],
        )
    )
    settings.importing = ImportConfig(
        sheets=SheetsImportConfig(
            globals=SheetsGlobalConfig(spreadsheetId="sheet-import"),
            position=[
                ImportPositionSheetConfig(
                    range="Import!A1",
                    data="DEPOSIT",
                    template=TemplateConfig(id="tpl-2"),
                )
            ],
        )
    )
    settings.assets.crypto.stablecoins = ["USDC", "EURC", "PUSD"]
    settings.assets.crypto.hideUnknownTokens = True
    return settings


def labeling_settings() -> Settings:
    settings = _base()
    settings.general.editMode = EditMode.DRAFT
    settings.labeling = LabelingConfig(
        external=ExternalLabelingConfig(
            enabled=True,
            provider="OPENROUTER",
            model="openai/gpt-5-mini",
            upstreamProvider="openai",
            autoRun=False,
            minConfidence=85,
            maxPerRun=150,
            examples=ExternalLabelingExamplesConfig(
                enabled=True, count=35, origins=[LabelOrigin.MANUAL]
            ),
            instructions="Groceries are always needs.\nRent goes to housing.",
        )
    )
    return settings


def emptied_settings() -> Settings:
    settings = _base()
    settings.assets.crypto.stablecoins = []
    return settings


def unknown_keys_settings() -> Settings:
    settings = _base()
    settings.general.defaultCurrency = "JPY"
    settings.assets.crypto.stablecoins = ["JPYC"]
    return settings


def partial_invalid_settings() -> Settings:
    settings = _base()
    settings.assets.crypto.stablecoins = ["USDC"]
    settings.assets.crypto.hideUnknownTokens = True
    return settings


def v7_settings() -> Settings:
    settings = _base()
    settings.general.defaultCurrency = "USD"
    settings.data.autoRefresh.max_outdated = AutoRefreshMaxOutdatedTime.DAY
    settings.assets.crypto.stablecoins = ["USDT", "USDC", "PUSD"]
    settings.assets.crypto.hideUnknownTokens = True
    return settings


def v6_settings() -> Settings:
    settings = _base()
    settings.general.defaultCommodityWeightUnit = "TROY_OUNCE"
    settings.assets.crypto.stablecoins = ["USDT", "DAI", "PUSD"]
    return settings


def v5_settings() -> Settings:
    settings = _base()
    settings.general.defaultCurrency = "GBP"
    settings.export = ExportConfig(
        sheets=SheetsExportConfig(
            globals=SheetsGlobalConfig(spreadsheetId="export-sheet"),
            transactions=[ExportTransactionsSheetConfig(range="Txs", data=["ACCOUNT"])],
        )
    )
    settings.assets.crypto.stablecoins = ["USDT", "PUSD"]
    return settings


def v4_settings() -> Settings:
    settings = _base()
    settings.export = ExportConfig(
        sheets=SheetsExportConfig(
            globals=SheetsGlobalConfig(spreadsheetId="export-sheet"),
            transactions=[
                ExportTransactionsSheetConfig(range="Account Txs", data=["ACCOUNT"]),
                ExportTransactionsSheetConfig(
                    range="Investment Txs",
                    data=[
                        "STOCK_ETF",
                        "FUND",
                        "FUND_PORTFOLIO",
                        "FACTORING",
                        "REAL_ESTATE_CF",
                        "DEPOSIT",
                    ],
                ),
            ],
        )
    )
    settings.importing = ImportConfig(
        sheets=SheetsImportConfig(
            globals=SheetsGlobalConfig(spreadsheetId="import-sheet"),
            transactions=[
                ImportTransactionsSheetConfig(
                    range="Imported",
                    data="ACCOUNT",
                    template=TemplateConfig(id="tpl-import"),
                ),
                ImportTransactionsSheetConfig(range="Invest", data=""),
            ],
        )
    )
    settings.assets.crypto.stablecoins = ["USDC", "PUSD"]
    return settings


def v3_settings() -> Settings:
    settings = _base()
    settings.importing = ImportConfig(
        sheets=SheetsImportConfig(
            globals=SheetsGlobalConfig(spreadsheetId="virtual-sheet"),
            position=[ImportPositionSheetConfig(range="Virtual!A1", data="FUND")],
        )
    )
    settings.assets.crypto.stablecoins = ["USDT", "PUSD"]
    return settings


def v2_settings() -> Settings:
    settings = _base()
    settings.assets.crypto.hideUnknownTokens = True
    return settings


def v1_settings() -> Settings:
    settings = _base()
    settings.general.defaultCurrency = "CHF"
    settings.export = ExportConfig(
        sheets=SheetsExportConfig(
            globals=SheetsGlobalConfig(spreadsheetId="legacy-export"),
            position=[
                ExportPositionSheetConfig(range="Investments!A1", data=["STOCK_ETF"])
            ],
        )
    )
    settings.importing = ImportConfig(
        sheets=SheetsImportConfig(
            globals=SheetsGlobalConfig(spreadsheetId="legacy-virtual"),
            transactions=[
                ImportTransactionsSheetConfig(range="Legacy Txs", data="ACCOUNT")
            ],
        )
    )
    return settings


def pre07_integrations_settings() -> Settings:
    settings = _base()
    settings.assets.crypto.stablecoins = ["USDT", "PUSD"]
    return settings


def mobile_v7_settings() -> Settings:
    settings = _base()
    settings.data.autoRefresh.mode = AutoRefreshMode.OFF
    settings.data.autoRefresh.max_outdated = AutoRefreshMaxOutdatedTime.SIX_HOURS
    settings.assets.crypto.stablecoins = ["USDT", "PUSD"]
    settings.assets.crypto.hideUnknownTokens = True
    return settings


def real_0110_settings() -> Settings:
    return old_app_settings(parse_sample("desktop_real_0110.yml"))


@dataclass(frozen=True)
class LegacySample:
    name: str
    expected: Callable[[], Settings]
    sections: frozenset[str]
    last_update: Optional[datetime]
    old_app_loadable: bool = True

    @property
    def is_mobile(self) -> bool:
        return self.name.startswith("mobile_")

    def __str__(self) -> str:
        return self.name


DESKTOP_SAMPLES = [
    LegacySample(
        "desktop_v8_default.yml", default_settings, V8_SECTIONS, V8_LAST_UPDATE
    ),
    LegacySample(
        "desktop_v8_custom.yml", custom_settings, ALL_SECTIONS, V8_LAST_UPDATE
    ),
    LegacySample(
        "desktop_v8_labeling.yml", labeling_settings, V8_SECTIONS, V8_LAST_UPDATE
    ),
    LegacySample(
        "desktop_v8_emptied.yml", emptied_settings, V8_SECTIONS, V8_LAST_UPDATE
    ),
    LegacySample(
        "desktop_v8_unknown_keys.yml",
        unknown_keys_settings,
        frozenset({"general", "assets"}),
        datetime.fromisoformat("2026-02-01T18:45:00+01:00"),
    ),
    LegacySample(
        "desktop_v8_partial_invalid.yml",
        partial_invalid_settings,
        frozenset({"assets"}),
        datetime.fromisoformat("2026-02-15T07:00:00+01:00"),
        old_app_loadable=False,
    ),
    LegacySample(
        "desktop_v7.yml",
        v7_settings,
        frozenset({"general", "data", "assets"}),
        datetime.fromisoformat("2025-11-20T09:30:00+01:00"),
    ),
    LegacySample(
        "desktop_v6.yml",
        v6_settings,
        frozenset({"general", "assets"}),
        datetime.fromisoformat("2025-09-10T12:00:00+02:00"),
    ),
    LegacySample(
        "desktop_v5.yml", v5_settings, frozenset({"general", "export", "assets"}), None
    ),
    LegacySample(
        "desktop_v4.yml",
        v4_settings,
        frozenset({"general", "export", "importing", "assets"}),
        None,
    ),
    LegacySample(
        "desktop_v3.yml",
        v3_settings,
        frozenset({"general", "importing", "assets"}),
        None,
    ),
    LegacySample("desktop_v2.yml", v2_settings, frozenset({"general", "assets"}), None),
    LegacySample(
        "desktop_v1.yml",
        v1_settings,
        frozenset({"general", "export", "importing", "assets"}),
        None,
    ),
    LegacySample(
        "desktop_pre07_integrations.yml",
        pre07_integrations_settings,
        frozenset({"general", "assets"}),
        datetime.fromisoformat("2025-05-01T08:00:00+02:00"),
    ),
    LegacySample(
        "desktop_real_0110.yml",
        real_0110_settings,
        ALL_SECTIONS,
        datetime.fromisoformat("2026-10-12T16:59:35.166498+02:00"),
    ),
]

MOBILE_SAMPLES = [
    LegacySample(
        "mobile_v8_default.json", default_settings, V8_SECTIONS, V8_LAST_UPDATE
    ),
    LegacySample(
        "mobile_v8_custom.json", custom_settings, ALL_SECTIONS, V8_LAST_UPDATE
    ),
    LegacySample(
        "mobile_v8_labeling.json", labeling_settings, V8_SECTIONS, V8_LAST_UPDATE
    ),
    LegacySample(
        "mobile_v8_emptied.json", emptied_settings, V8_SECTIONS, V8_LAST_UPDATE
    ),
    LegacySample(
        "mobile_v7.json",
        mobile_v7_settings,
        frozenset({"general", "data", "assets"}),
        datetime.fromisoformat("2025-12-05T21:10:00+01:00"),
    ),
    LegacySample(
        "mobile_empty_object.json",
        default_settings,
        frozenset({"general", "assets"}),
        None,
    ),
]

LEGACY_SAMPLES = DESKTOP_SAMPLES + MOBILE_SAMPLES

BROKEN_DESKTOP_SAMPLES = [
    "desktop_empty.yml",
    "desktop_list.yml",
    "desktop_scalar.yml",
    "desktop_invalid_yaml.yml",
]
BROKEN_MOBILE_SAMPLES = ["mobile_invalid.json", "mobile_list.json"]


def old_app_settings(raw: dict) -> Settings:
    migrated, _ = ConfigMigrator().migrate(deepcopy(raw))
    return Settings(**migrated)


def assert_same_settings(actual: Settings, expected: Settings):
    for key in SECTION_KEYS:
        assert getattr(actual, key) == getattr(expected, key), key


def assert_last_update(
    actual: Optional[datetime],
    expected: Optional[datetime],
    before: datetime,
    after: datetime,
):
    assert actual is not None
    assert actual.tzinfo is not None
    if expected is None:
        assert before <= actual <= after
    else:
        assert actual == expected
