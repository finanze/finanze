import json
from datetime import datetime
from typing import Optional
from uuid import UUID

from application.ports.template_port import TemplatePort
from dateutil.tz import tzlocal
from domain.entity import Feature
from domain.global_position import ProductType
from domain.template import Template, TemplatedField
from domain.template_type import TemplateType
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.templates.queries import TemplateQueries


def _serialize_fields(fields: list[TemplatedField]) -> str:
    payload = [
        {
            "field": f.field,
            **({"name": f.name} if f.name else {}),
            **({"default": f.default_value} if f.default_value else {}),
        }
        for f in fields
    ]
    return json.dumps(payload)


def _deserialize_fields(raw: str) -> list[TemplatedField]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:
        return []
    templated: list[TemplatedField] = []
    for entry in data:
        field = entry.get("field")
        if field is None:
            continue
        templated.append(
            TemplatedField(
                field=field, name=entry.get("name"), default_value=entry.get("default")
            )
        )
    return templated


def _serialize_products(products: Optional[list[ProductType]]) -> Optional[str]:
    if not products:
        return None
    return json.dumps([p.value for p in products])


def _deserialize_products(raw: Optional[str]) -> Optional[list[ProductType]]:
    if not raw:
        return None
    try:
        arr = json.loads(raw)
    except Exception:
        return None
    if not isinstance(arr, list):
        return None
    result: list[ProductType] = []
    for v in arr:
        try:
            result.append(ProductType(v))
        except Exception:
            continue
    return result or None


def _map_row(row) -> Template:
    return Template(
        id=UUID(row["id"]),
        name=row["name"],
        feature=Feature(row["feature"]),
        type=TemplateType(row["type"]),
        fields=_deserialize_fields(row["fields"]),
        products=_deserialize_products(row["products"]),
    )


class TemplateRepository(TemplatePort):
    def __init__(self, client: DBClient):
        self._db_client = client

    async def save(self, template: Template):
        now = datetime.now(tzlocal())
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                TemplateQueries.INSERT,
                (
                    str(template.id),
                    template.name,
                    template.feature.value,
                    template.type.value,
                    _serialize_fields(template.fields),
                    _serialize_products(template.products),
                    now.isoformat(),
                    now.isoformat(),
                ),
            )

    async def update(self, template: Template):
        now = datetime.now(tzlocal())
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                TemplateQueries.UPDATE,
                (
                    template.name,
                    template.feature.value,
                    template.type.value,
                    _serialize_fields(template.fields),
                    _serialize_products(template.products),
                    now.isoformat(),
                    str(template.id),
                ),
            )

    async def delete(self, template_id: UUID):
        async with self._db_client.tx() as cursor:
            await cursor.execute(TemplateQueries.DELETE_BY_ID, (str(template_id),))

    async def get_by_id(self, template_id: UUID) -> Template | None:
        async with self._db_client.read() as cursor:
            await cursor.execute(TemplateQueries.GET_BY_ID, (str(template_id),))
            row = await cursor.fetchone()
            if row is None:
                return None
            return _map_row(row)

    async def get_by_type(self, template_type: TemplateType) -> list[Template]:
        async with self._db_client.read() as cursor:
            await cursor.execute(TemplateQueries.GET_BY_TYPE, (template_type.value,))
            rows = await cursor.fetchall()
            return [_map_row(r) for r in rows] if rows else []

    async def get_by_name_and_type(
        self, name: str, template_type: TemplateType
    ) -> Template | None:
        async with self._db_client.read() as cursor:
            await cursor.execute(
                TemplateQueries.GET_BY_NAME_AND_TYPE,
                (name, template_type.value),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return _map_row(row)
