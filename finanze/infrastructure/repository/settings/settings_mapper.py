import json
import logging
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from domain.settings import (
    CURRENT_VERSION,
    AssetConfig,
    DataConfig,
    ExportConfig,
    GeneralConfig,
    ImportConfig,
    LabelingConfig,
    PartialSettings,
    Settings,
)
from infrastructure.config.base_config import BASE_CONFIG
from infrastructure.config.config_migrator import ConfigMigrator

SECTION_TYPES = {
    "general": GeneralConfig,
    "data": DataConfig,
    "export": ExportConfig,
    "importing": ImportConfig,
    "assets": AssetConfig,
    "labeling": LabelingConfig,
}

_log = logging.getLogger(__name__)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def parse_timestamp(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.strip())
        except ValueError:
            return None
    else:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return parsed


def parse_section(key: str, value: Any):
    if not isinstance(value, dict):
        raise ValueError(f"Settings section '{key}' must be an object")
    return SECTION_TYPES[key](**value)


def serialize_section(section: dict) -> str:
    return json.dumps(section)


def deserialize_section(value: str) -> Any:
    return json.loads(value)


def settings_to_sections(settings: Settings | PartialSettings) -> dict[str, dict]:
    return {
        key: _json_safe(asdict(value))
        for key in SECTION_TYPES
        if (value := getattr(settings, key)) is not None
    }


def _resolve_sections(sections: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    defaults = deepcopy(BASE_CONFIG)
    values = {}
    for key in keys:
        raw = sections.get(key)
        if raw is not None:
            try:
                values[key] = parse_section(key, raw)
                continue
            except Exception as e:
                _log.warning(
                    "Invalid stored settings section '%s', using defaults: %s", key, e
                )
        values[key] = getattr(defaults, key)
    return values


def sections_to_settings(sections: dict[str, Any], last_update: str) -> Settings:
    values = _resolve_sections(sections, list(SECTION_TYPES))
    return Settings(lastUpdate=last_update, version=CURRENT_VERSION, **values)


def sections_to_partial_settings(
    sections: dict[str, Any], keys: list[str], last_update: str
) -> PartialSettings:
    values = _resolve_sections(sections, keys)
    return PartialSettings(lastUpdate=last_update, version=CURRENT_VERSION, **values)


def legacy_to_sections(raw: Any) -> tuple[dict[str, dict], Optional[datetime]]:
    if not isinstance(raw, dict):
        return {}, None

    try:
        migrated, _ = ConfigMigrator().migrate(raw)
    except Exception as e:
        _log.warning("Could not migrate legacy config, using it as is: %s", e)
        migrated = raw

    sections = {}
    for key in SECTION_TYPES:
        value = migrated.get(key)
        if value is None:
            continue
        try:
            sections[key] = _json_safe(asdict(parse_section(key, value)))
        except Exception as e:
            _log.warning(
                "Invalid legacy config section '%s', using defaults: %s", key, e
            )

    return sections, parse_timestamp(migrated.get("lastUpdate"))
