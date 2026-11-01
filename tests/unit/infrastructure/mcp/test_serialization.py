import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID

from domain.dezimal import Dezimal
from pydantic import BaseModel

from infrastructure.mcp.serialization import to_json, to_jsonable


class Color(str, Enum):
    RED = "RED"


@dataclass
class Item:
    id: UUID
    amount: Dezimal
    color: Color
    day: date
    icon_url: Optional[str] = None
    note: Optional[str] = None
    tags: list[str] = field(default_factory=list)


class Model(BaseModel):
    when: datetime
    value: int


ITEM_ID = UUID("6f1c2a52-6ad4-4f2e-9e57-6e2f6f0c3b71")


class TestSerialization:
    def test_dataclass_is_compacted(self):
        item = Item(
            id=ITEM_ID,
            amount=Dezimal("10.25"),
            color=Color.RED,
            day=date(2025, 3, 1),
            icon_url="https://icons/x.png",
        )

        assert to_jsonable(item) == {
            "id": str(ITEM_ID),
            "amount": 10.25,
            "color": "RED",
            "day": "2025-03-01",
        }

    def test_dict_keys_and_nested_values(self):
        value = {
            Color.RED: [Dezimal("1.5"), None],
            "photo_url": "x",
            "empty": {},
            "zero": 0,
            "flag": False,
        }

        assert to_jsonable(value) == {
            "RED": [1.5, None],
            "zero": 0,
            "flag": False,
        }

    def test_pydantic_model(self):
        model = Model(when=datetime(2025, 1, 2, 3, 4, tzinfo=timezone.utc), value=3)

        assert to_jsonable(model) == {
            "when": "2025-01-02T03:04:00+00:00",
            "value": 3,
        }

    def test_to_json_is_compact_and_keeps_unicode(self):
        result = to_json({"name": "Café", "items": [1, 2]})

        assert result == '{"name":"Café","items":[1,2]}'
        assert json.loads(result)["name"] == "Café"
