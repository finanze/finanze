import json
from datetime import datetime, timezone

import pytest

from domain.settings import (
    CURRENT_VERSION,
    AutoRefreshMaxOutdatedTime,
    AutoRefreshMode,
    EditMode,
    PartialSettings,
    SettingsSection,
)
from domain.transactions import LabelOrigin
from infrastructure.config.base_config import BASE_CONFIG
from infrastructure.config.config_migrator import ConfigMigrator
from infrastructure.repository.settings.settings_mapper import (
    SECTION_TYPES,
    deserialize_section,
    legacy_to_sections,
    parse_timestamp,
    sections_to_partial_settings,
    sections_to_settings,
    serialize_section,
    settings_to_sections,
)
from tests.legacy_config_samples import (
    LEGACY_SAMPLES,
    SECTION_KEYS,
    assert_last_update,
    assert_same_settings,
    custom_settings,
    default_settings,
    labeling_settings,
    old_app_settings,
    parse_sample,
)

PARSEABLE_BROKEN_SAMPLES = [
    "desktop_empty.yml",
    "desktop_list.yml",
    "desktop_scalar.yml",
    "mobile_list.json",
]


class TestLegacyToSections:
    @pytest.mark.parametrize("sample", LEGACY_SAMPLES, ids=str)
    def test_maps_sample_to_expected_settings(self, sample):
        raw = parse_sample(sample.name)

        before = datetime.now().astimezone()
        sections, last_update = legacy_to_sections(raw)
        after = datetime.now().astimezone()

        assert set(sections) == sample.sections
        assert_same_settings(sections_to_settings(sections, "x"), sample.expected())
        assert_last_update(last_update, sample.last_update, before, after)

    @pytest.mark.parametrize(
        "sample", [s for s in LEGACY_SAMPLES if s.old_app_loadable], ids=str
    )
    def test_matches_legacy_loader_result(self, sample):
        raw = parse_sample(sample.name)

        sections, _ = legacy_to_sections(raw)

        assert_same_settings(sections_to_settings(sections, "x"), old_app_settings(raw))

    @pytest.mark.parametrize("sample", LEGACY_SAMPLES, ids=str)
    def test_sections_are_json_serializable(self, sample):
        sections, _ = legacy_to_sections(parse_sample(sample.name))

        for key, section in sections.items():
            assert deserialize_section(serialize_section(section)) == section, key

    def test_partial_invalid_keeps_valid_sections_only(self):
        raw = parse_sample("desktop_v8_partial_invalid.yml")

        with pytest.raises(Exception):
            old_app_settings(raw)

        sections, _ = legacy_to_sections(raw)
        assert set(sections) == {"assets"}

    def test_ignores_integrations_section(self):
        raw = parse_sample("desktop_pre07_integrations.yml")

        sections, _ = legacy_to_sections(raw)

        assert "integrations" not in sections
        assert "integrations" not in json.dumps(sections)

    @pytest.mark.parametrize("name", PARSEABLE_BROKEN_SAMPLES)
    def test_broken_samples_produce_nothing(self, name):
        assert legacy_to_sections(parse_sample(name)) == ({}, None)

    @pytest.mark.parametrize("raw", [None, "", "text", 1, [], ["general"]])
    def test_non_dict_produces_nothing(self, raw):
        assert legacy_to_sections(raw) == ({}, None)

    def test_falls_back_to_raw_when_migrator_fails(self, monkeypatch):
        def _fail(self, data):
            raise RuntimeError("boom")

        monkeypatch.setattr(ConfigMigrator, "migrate", _fail)
        raw = parse_sample("desktop_v8_labeling.yml")

        sections, last_update = legacy_to_sections(raw)

        assert_same_settings(sections_to_settings(sections, "x"), labeling_settings())
        assert last_update == datetime.fromisoformat("2026-03-01T10:00:00+01:00")

    def test_non_dict_section_is_skipped(self):
        raw = {
            "version": CURRENT_VERSION,
            "lastUpdate": "2026-01-01T00:00:00+00:00",
            "general": ["EUR"],
            "assets": {"crypto": {"stablecoins": ["USDT"]}},
        }

        sections, _ = legacy_to_sections(raw)

        assert set(sections) == {"assets"}

    def test_invalid_last_update_is_ignored(self):
        raw = {
            "version": CURRENT_VERSION,
            "lastUpdate": "not a date",
            "general": {"defaultCurrency": "USD"},
        }

        sections, last_update = legacy_to_sections(raw)

        assert sections["general"]["defaultCurrency"] == "USD"
        assert last_update is None

    def test_real_0110_desktop_config_keeps_user_values(self):
        sections, _ = legacy_to_sections(parse_sample("desktop_real_0110.yml"))

        settings = sections_to_settings(sections, "x")

        assert settings.general.editMode == EditMode.DRAFT
        assert settings.data.autoRefresh.mode == AutoRefreshMode.OFF
        assert settings.data.autoRefresh.max_outdated == AutoRefreshMaxOutdatedTime.WEEK
        assert [e.id for e in settings.data.autoRefresh.entities] == [
            "00000000-0000-4000-8000-000000000001"
        ]
        export = settings.export.sheets
        assert export.globals.spreadsheetId == "anonymized-export-spreadsheet-id"
        assert export.globals.datetimeFormat == "%d/%m/%Y %H:%M:%S"
        assert len(export.position) == 10
        assert [p.lastUpdate for p in export.position].count(True) == 1
        assert export.position[0].template.id == "00000000-0000-4000-8000-000000000002"
        assert [c.range for c in export.contributions] == ["Auto Contribuciones"]
        assert [(f.field, f.values) for f in export.transactions[3].filters] == [
            ("source", ["SHEETS"]),
            ("entity", ["ING"]),
        ]
        assert export.historic[0].data == ["REAL_ESTATE_CF", "FACTORING"]
        importing = settings.importing.sheets
        assert importing.globals.spreadsheetId == "anonymized-import-spreadsheet-id"
        assert len(importing.position) == 7
        assert importing.position[1].template.params == {"entity": "Goibank"}
        assert importing.position[4].dateFormat == "%d-%m-%Y"
        assert [t.data for t in importing.transactions] == ["STOCK_ETF", "STOCK_ETF"]
        assert len(settings.assets.crypto.stablecoins) == 28
        assert settings.assets.crypto.hideUnknownTokens is False
        external = settings.labeling.external
        assert external.enabled is True
        assert external.provider == "OPENROUTER"
        assert external.model == "~typesafe/jev-latest"
        assert (external.minConfidence, external.maxPerRun) == (70, 500)
        assert external.examples.origins == [LabelOrigin.MANUAL]
        assert external.instructions.startswith("I am based in Spain.")
        assert external.instructions.endswith("each month in a tx.")


class TestSectionsToSettings:
    def test_empty_sections_returns_defaults(self):
        settings = sections_to_settings({}, "2026-01-01T00:00:00+00:00")

        assert settings.lastUpdate == "2026-01-01T00:00:00+00:00"
        assert settings.version == CURRENT_VERSION
        assert_same_settings(settings, default_settings())

    def test_defaults_are_not_shared_with_base_config(self):
        settings = sections_to_settings({}, "x")
        settings.assets.crypto.stablecoins.append("NEW")

        assert "NEW" not in BASE_CONFIG.assets.crypto.stablecoins

    def test_invalid_section_falls_back_to_default(self):
        sections = settings_to_sections(custom_settings())
        sections["general"] = {"editMode": "BOGUS"}
        sections["data"] = "not an object"

        settings = sections_to_settings(sections, "x")

        expected = custom_settings()
        assert settings.general == default_settings().general
        assert settings.data == default_settings().data
        assert settings.assets == expected.assets
        assert settings.export == expected.export

    def test_unknown_sections_are_ignored(self):
        sections = {"future": {"anything": 1}}

        settings = sections_to_settings(sections, "x")

        assert_same_settings(settings, default_settings())


class TestSectionsToPartialSettings:
    def test_only_requested_keys_are_included(self):
        sections = settings_to_sections(custom_settings())

        partial = sections_to_partial_settings(sections, ["general", "export"], "ts")

        assert partial.included_sections() == [
            SettingsSection.GENERAL,
            SettingsSection.EXPORT,
        ]
        assert partial.general == custom_settings().general
        assert partial.export == custom_settings().export
        assert partial.lastUpdate == "ts"
        assert partial.version == CURRENT_VERSION

    def test_missing_or_invalid_sections_fall_back_to_defaults(self):
        partial = sections_to_partial_settings(
            {"general": {"editMode": "BOGUS"}}, ["general", "assets"], "x"
        )

        assert partial.general == default_settings().general
        assert partial.assets == default_settings().assets
        assert partial.data is None


class TestSettingsToSections:
    def test_partial_settings_only_serializes_present_sections(self):
        partial = PartialSettings(labeling=labeling_settings().labeling)

        sections = settings_to_sections(partial)

        assert set(sections) == {"labeling"}
        assert sections["labeling"]["external"]["provider"] == "OPENROUTER"

    @pytest.mark.parametrize(
        "factory", [default_settings, custom_settings, labeling_settings]
    )
    def test_round_trip(self, factory):
        sections = settings_to_sections(factory())

        assert set(sections) == set(SECTION_KEYS)
        stored = {
            k: deserialize_section(serialize_section(v)) for k, v in sections.items()
        }
        assert_same_settings(sections_to_settings(stored, "x"), factory())

    def test_enums_are_serialized_as_values(self):
        settings = default_settings()
        settings.general.editMode = EditMode.DRAFT

        sections = settings_to_sections(settings)

        assert sections["general"]["editMode"] == "DRAFT"
        assert sections["data"]["autoRefresh"]["mode"] == "NO_2FA"

    def test_section_keys_match_section_types(self):
        assert set(SECTION_TYPES) == set(SECTION_KEYS)


class TestParseTimestamp:
    def test_parses_aware_iso_string(self):
        assert parse_timestamp("2026-03-01T10:00:00+01:00") == datetime.fromisoformat(
            "2026-03-01T10:00:00+01:00"
        )

    def test_naive_string_gets_local_timezone(self):
        parsed = parse_timestamp("2026-03-01T10:00:00")

        assert parsed.tzinfo is not None
        assert parsed.replace(tzinfo=None) == datetime(2026, 3, 1, 10, 0, 0)

    def test_aware_datetime_is_kept(self):
        value = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)

        assert parse_timestamp(value) == value

    def test_naive_datetime_gets_local_timezone(self):
        parsed = parse_timestamp(datetime(2026, 3, 1, 10, 0))

        assert parsed.tzinfo is not None

    @pytest.mark.parametrize("value", [None, "", "garbage", 123, ["2026-01-01"]])
    def test_invalid_values_return_none(self, value):
        assert parse_timestamp(value) is None
