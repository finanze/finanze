from datetime import date
from typing import Optional
from uuid import UUID

from domain.dezimal import Dezimal
from domain.labeling import (
    Label,
    LabelCategory,
    LabelingRule,
    LabelingRuleConditions,
    LabelingRuleKind,
    RelabelRequest,
    TextCondition,
    TextMatchField,
    TextMatchOperator,
)
from domain.transactions import LabelOrigin, TxType, normalize_iban


def _optional_str(value) -> Optional[str]:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _optional_date(value) -> Optional[date]:
    if not value:
        return None
    return date.fromisoformat(str(value)[:10])


def _optional_dezimal(value) -> Optional[Dezimal]:
    if value is None or value == "":
        return None
    return Dezimal(str(value))


def _optional_int(value) -> Optional[int]:
    if value is None or value == "":
        return None
    return int(value)


def _uuid_list(values) -> Optional[list[UUID]]:
    if not values:
        return None
    if not isinstance(values, list):
        raise ValueError("Expected a list of IDs")
    return list(dict.fromkeys(UUID(str(value)) for value in values))


def _iban_list(values) -> Optional[list[str]]:
    if not values:
        return None
    if not isinstance(values, list):
        raise ValueError("Expected a list of IBANs")
    ibans = [normalize_iban(str(value)) for value in values]
    return list(dict.fromkeys(iban for iban in ibans if iban)) or None


def map_label(body: dict, label_id: Optional[UUID] = None) -> Label:
    if not isinstance(body, dict):
        raise ValueError("Body must be a JSON object")
    return Label(
        id=label_id,
        name=_optional_str(body.get("name")),
        description=_optional_str(body.get("description")),
        color=_optional_str(body.get("color")),
        icon=_optional_str(body.get("icon")),
        category=LabelCategory(body.get("category") or LabelCategory.EXPENSE),
    )


def map_conditions(body: dict) -> LabelingRuleConditions:
    if not isinstance(body, dict):
        raise ValueError("Conditions must be a JSON object")

    text = body.get("text")
    text_condition = None
    if text:
        if not isinstance(text, dict):
            raise ValueError("Text condition must be a JSON object")
        text_condition = TextCondition(
            value=str(text.get("value") or ""),
            operator=TextMatchOperator(text.get("operator", "CONTAINS")),
            field=TextMatchField(text.get("field", "ANY")),
        )

    types = body.get("types")
    currency = _optional_str(body.get("currency"))
    return LabelingRuleConditions(
        types=[TxType(t) for t in types] if types else None,
        min_amount=_optional_dezimal(body.get("min_amount")),
        max_amount=_optional_dezimal(body.get("max_amount")),
        currency=currency.upper() if currency else None,
        from_date=_optional_date(body.get("from_date")),
        to_date=_optional_date(body.get("to_date")),
        day_from=_optional_int(body.get("day_from")),
        day_to=_optional_int(body.get("day_to")),
        entities=_uuid_list(body.get("entities")),
        text=text_condition,
        max_days=_optional_int(body.get("max_days")),
        ibans=_iban_list(body.get("ibans")),
    )


def map_rule(body: dict, rule_id: Optional[UUID] = None) -> LabelingRule:
    if not isinstance(body, dict):
        raise ValueError("Body must be a JSON object")
    return LabelingRule(
        id=rule_id,
        name=_optional_str(body.get("name")),
        enabled=bool(body.get("enabled", True)),
        kind=LabelingRuleKind(body.get("kind") or LabelingRuleKind.MATCH),
        conditions=map_conditions(body.get("conditions") or {}),
        label_ids=_uuid_list(body.get("labels")) or [],
    )


def map_relabel_request(body: dict) -> RelabelRequest:
    if not isinstance(body, dict):
        raise ValueError("Body must be a JSON object")
    origins = body.get("origins")
    return RelabelRequest(
        from_date=_optional_date(body.get("from_date")),
        to_date=_optional_date(body.get("to_date")),
        entities=_uuid_list(body.get("entities")),
        with_labels=_uuid_list(body.get("with_labels")),
        without_labels=_uuid_list(body.get("without_labels")),
        unlabeled_only=bool(body.get("unlabeled_only", False)),
        origins=[LabelOrigin(o) for o in origins] if origins else None,
        include_external=bool(body.get("include_external", False)),
        retry_external_unmatched=bool(body.get("retry_external_unmatched", False)),
        dry_run=bool(body.get("dry_run", False)),
    )
