import json
from datetime import date, datetime
from typing import Optional
from uuid import UUID, uuid4

from application.ports.labeling_rule_port import LabelingRulePort
from dateutil.tz import tzlocal
from domain.dezimal import Dezimal
from domain.labeling import (
    LabelingRule,
    LabelingRuleConditions,
    LabelingRuleKind,
    TextCondition,
    TextMatchField,
    TextMatchOperator,
)
from domain.transactions import TxType
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.labeling.queries import LabelingRuleQueries


def serialize_conditions(conditions: LabelingRuleConditions) -> str:
    data = {}
    if conditions.types:
        data["types"] = [t.value for t in conditions.types]
    if conditions.min_amount is not None:
        data["min_amount"] = str(conditions.min_amount)
    if conditions.max_amount is not None:
        data["max_amount"] = str(conditions.max_amount)
    if conditions.currency:
        data["currency"] = conditions.currency
    if conditions.from_date:
        data["from_date"] = conditions.from_date.isoformat()
    if conditions.to_date:
        data["to_date"] = conditions.to_date.isoformat()
    if conditions.day_from is not None:
        data["day_from"] = conditions.day_from
    if conditions.day_to is not None:
        data["day_to"] = conditions.day_to
    if conditions.entities:
        data["entities"] = [str(e) for e in conditions.entities]
    if conditions.text is not None:
        data["text"] = {
            "value": conditions.text.value,
            "operator": conditions.text.operator.value,
            "field": conditions.text.field.value,
        }
    if conditions.max_days is not None:
        data["max_days"] = conditions.max_days
    if conditions.ibans:
        data["ibans"] = list(conditions.ibans)
    return json.dumps(data)


def deserialize_conditions(raw: str) -> LabelingRuleConditions:
    data = json.loads(raw) if raw else {}
    text = data.get("text")
    return LabelingRuleConditions(
        types=[TxType(t) for t in data["types"]] if data.get("types") else None,
        min_amount=Dezimal(data["min_amount"])
        if data.get("min_amount") is not None
        else None,
        max_amount=Dezimal(data["max_amount"])
        if data.get("max_amount") is not None
        else None,
        currency=data.get("currency"),
        from_date=date.fromisoformat(data["from_date"])
        if data.get("from_date")
        else None,
        to_date=date.fromisoformat(data["to_date"]) if data.get("to_date") else None,
        day_from=data.get("day_from"),
        day_to=data.get("day_to"),
        entities=[UUID(e) for e in data["entities"]] if data.get("entities") else None,
        text=TextCondition(
            value=text["value"],
            operator=TextMatchOperator(text.get("operator", "CONTAINS")),
            field=TextMatchField(text.get("field", "ANY")),
        )
        if text
        else None,
        max_days=data.get("max_days"),
        ibans=data.get("ibans") or None,
    )


def _group_rows(rows) -> list[LabelingRule]:
    rules: dict[str, LabelingRule] = {}
    for row in rows:
        rule_id = row["id"]
        rule = rules.get(rule_id)
        if rule is None:
            rule = LabelingRule(
                id=UUID(rule_id),
                name=row["name"],
                enabled=bool(row["enabled"]),
                kind=LabelingRuleKind(row["kind"]),
                conditions=deserialize_conditions(row["conditions"]),
                label_ids=[],
            )
            rules[rule_id] = rule
        if row["label_id"]:
            rule.label_ids.append(UUID(row["label_id"]))
    return list(rules.values())


class LabelingRuleRepository(LabelingRulePort):
    def __init__(self, client: DBClient):
        self._db_client = client

    async def get_all(self, enabled_only: bool = False) -> list[LabelingRule]:
        query = (
            LabelingRuleQueries.GET_ENABLED
            if enabled_only
            else LabelingRuleQueries.GET_ALL
        )
        async with self._db_client.read() as cursor:
            await cursor.execute(query)
            return _group_rows(await cursor.fetchall())

    async def get_by_id(self, rule_id: UUID) -> Optional[LabelingRule]:
        async with self._db_client.read() as cursor:
            await cursor.execute(LabelingRuleQueries.GET_BY_ID, (str(rule_id),))
            rules = _group_rows(await cursor.fetchall())
            return rules[0] if rules else None

    async def save(self, rule: LabelingRule) -> LabelingRule:
        if rule.id is None:
            rule.id = uuid4()
        now = datetime.now(tzlocal()).isoformat()
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                LabelingRuleQueries.INSERT,
                (
                    str(rule.id),
                    rule.name,
                    rule.enabled,
                    rule.kind.value,
                    serialize_conditions(rule.conditions),
                    now,
                    now,
                ),
            )
            for label_id in dict.fromkeys(rule.label_ids):
                await cursor.execute(
                    LabelingRuleQueries.INSERT_LABEL, (str(rule.id), str(label_id))
                )
        return rule

    async def update(self, rule: LabelingRule):
        now = datetime.now(tzlocal()).isoformat()
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                LabelingRuleQueries.UPDATE,
                (
                    rule.name,
                    rule.enabled,
                    serialize_conditions(rule.conditions),
                    now,
                    str(rule.id),
                ),
            )
            await cursor.execute(LabelingRuleQueries.DELETE_LABELS, (str(rule.id),))
            for label_id in dict.fromkeys(rule.label_ids):
                await cursor.execute(
                    LabelingRuleQueries.INSERT_LABEL, (str(rule.id), str(label_id))
                )

    async def delete(self, rule_id: UUID):
        async with self._db_client.tx() as cursor:
            await cursor.execute(LabelingRuleQueries.DELETE, (str(rule_id),))
