import json
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from domain.dezimal import Dezimal
from pydantic import BaseModel

_DROPPED_KEYS = {"icon_url", "photo_url"}


def _key(value: Any) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _is_empty(value: Any) -> bool:
    return value is None or (isinstance(value, (list, dict)) and not value)


def to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, Dezimal):
        return float(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, BaseModel):
        return to_jsonable(value.model_dump())
    if is_dataclass(value) and not isinstance(value, type):
        result = {}
        for f in fields(value):
            if f.name in _DROPPED_KEYS:
                continue
            item = to_jsonable(getattr(value, f.name))
            if not _is_empty(item):
                result[f.name] = item
        return result
    if isinstance(value, dict):
        result = {}
        for k, v in value.items():
            if k in _DROPPED_KEYS:
                continue
            item = to_jsonable(v)
            if not _is_empty(item):
                result[_key(k)] = item
        return result
    if isinstance(value, (list, tuple, set, frozenset)):
        return [to_jsonable(item) for item in value]
    return str(value)


def to_json(value: Any) -> str:
    return json.dumps(to_jsonable(value), ensure_ascii=False, separators=(",", ":"))
