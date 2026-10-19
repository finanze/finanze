from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Annotated, Optional
from uuid import UUID

from domain.labeling import (
    Label,
    LabelCategory,
    LabelingRule,
    LabelingRuleKind,
    LabelingRulePreviewRequest,
    LabelSubcategory,
    RelabelRequest,
    SaveLabelingRuleRequest,
    TextMatchField,
    TextMatchOperator,
)
from domain.exception.exceptions import LabelingRuleNotFound, LabelNotFound
from domain.transactions import TxType
from infrastructure.controller.mappers.labeling_mapper import map_conditions
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, Field

from infrastructure.mcp.registry import ToolRegistry
from infrastructure.mcp.tools.common import EntityIds, FromDate, ToDate
from infrastructure.mcp.use_cases import McpUseCases

LabelId = Annotated[UUID, Field(description="Label ID.")]
RuleId = Annotated[UUID, Field(description="Labeling rule ID.")]


class TextConditionInput(BaseModel):
    value: str = Field(min_length=1)
    operator: TextMatchOperator = TextMatchOperator.CONTAINS
    field: TextMatchField = TextMatchField.ANY


class RuleConditionsInput(BaseModel):
    types: Optional[list[TxType]] = Field(
        default=None, description="Account movement types, e.g. INFLOW, OUTFLOW."
    )
    min_amount: Optional[Decimal] = None
    max_amount: Optional[Decimal] = None
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    day_from: Optional[int] = Field(
        default=None, ge=1, le=31, description="Day of month range start."
    )
    day_to: Optional[int] = Field(
        default=None, ge=1, le=31, description="Day of month range end."
    )
    entities: Optional[list[UUID]] = None
    text: Optional[TextConditionInput] = Field(
        default=None, description="Match on transaction name and/or counterparty."
    )
    max_days: Optional[int] = Field(
        default=None,
        ge=0,
        description="TRANSFER rules only: max days between both sides of a transfer.",
    )
    ibans: Optional[list[str]] = Field(
        default=None, description="Match the counterparty IBAN."
    )


def _conditions(conditions: RuleConditionsInput):
    return map_conditions(conditions.model_dump(mode="json", exclude_none=True))


def register(registry: ToolRegistry, ucs: McpUseCases):
    async def find_label(label_id: UUID) -> Label:
        labels = await ucs.get_labels.execute()
        label = next((lb for lb in labels.labels if lb.id == label_id), None)
        if label is None:
            raise LabelNotFound()
        return label

    async def find_rule(rule_id: UUID) -> LabelingRule:
        rules = await ucs.get_labeling_rules.execute()
        rule = next((r for r in rules.rules if r.id == rule_id), None)
        if rule is None:
            raise LabelingRuleNotFound()
        return rule

    @registry.read("List labels")
    async def list_labels():
        """List the labels used to categorize account movements, with category (INCOME, EXPENSE, EXCLUDED), budget subcategory (NEED, WANTS, SAVINGS) and usage count."""
        return await ucs.get_labels.execute()

    @registry.read("List labeling rules")
    async def list_labeling_rules():
        """List the automatic labeling rules: MATCH rules label movements matching the conditions, TRANSFER rules detect transfers between own accounts."""
        return await ucs.get_labeling_rules.execute()

    @registry.read("Preview labeling rule")
    async def preview_labeling_rule(
        conditions: RuleConditionsInput,
        limit: Annotated[int, Field(ge=1, le=50)] = 10,
    ):
        """Preview which existing account movements match the given rule conditions, before saving a rule."""
        return await ucs.preview_labeling_rule.execute(
            LabelingRulePreviewRequest(conditions=_conditions(conditions), limit=limit)
        )

    @registry.write("Save label")
    async def save_label(
        label_id: Annotated[
            Optional[UUID],
            Field(description="Existing label ID to update. Omit to create one."),
        ] = None,
        name: Annotated[Optional[str], Field(min_length=1, max_length=100)] = None,
        category: Optional[LabelCategory] = None,
        subcategory: Annotated[
            Optional[LabelSubcategory],
            Field(description="Budget subcategory, only for EXPENSE labels."),
        ] = None,
        description: Optional[str] = None,
        color: Annotated[
            Optional[str], Field(description="Hex color, e.g. #22c55e.")
        ] = None,
    ):
        """Create a label, or update one by label_id. On update only the provided fields change. Name is required on create, category defaults to EXPENSE."""
        if label_id:
            current = await find_label(label_id)
            changes = {
                "name": name,
                "category": category,
                "subcategory": subcategory,
                "description": description,
                "color": color,
            }
            label = replace(
                current, **{k: v for k, v in changes.items() if v is not None}
            )
            if category and category != current.category and subcategory is None:
                label = replace(label, subcategory=None)
            await ucs.update_label.execute(label, subcategory_provided=True)
            return label

        if not name:
            raise ToolError("name is required to create a label.")
        return await ucs.create_label.execute(
            Label(
                id=None,
                name=name,
                description=description,
                color=color,
                category=category or LabelCategory.EXPENSE,
                subcategory=subcategory,
            )
        )

    @registry.write("Delete label", destructive=True, idempotent=True)
    async def delete_label(label_id: LabelId):
        """Delete a label, removing it from all transactions and rules."""
        await ucs.delete_label.execute(label_id)
        return {"deleted": str(label_id)}

    @registry.write("Save labeling rule")
    async def save_labeling_rule(
        rule_id: Annotated[
            Optional[UUID],
            Field(description="Existing rule ID to update. Omit to create one."),
        ] = None,
        name: Optional[str] = None,
        label_ids: Annotated[
            Optional[list[UUID]], Field(description="Labels to apply.")
        ] = None,
        conditions: Optional[RuleConditionsInput] = None,
        kind: Optional[LabelingRuleKind] = None,
        enabled: Optional[bool] = None,
        apply_to_existing: Annotated[
            bool,
            Field(description="Also apply the rule to existing matching movements."),
        ] = False,
    ):
        """Create an automatic labeling rule, or update one by rule_id. On update only the provided fields change. label_ids and conditions are required on create. Use preview_labeling_rule first."""
        if rule_id:
            current = await find_rule(rule_id)
            changes = {
                "name": name,
                "label_ids": label_ids,
                "conditions": _conditions(conditions) if conditions else None,
                "kind": kind,
                "enabled": enabled,
            }
            rule = replace(
                current, **{k: v for k, v in changes.items() if v is not None}
            )
            use_case = ucs.update_labeling_rule
        else:
            if not label_ids or conditions is None:
                raise ToolError("label_ids and conditions are required.")
            rule = LabelingRule(
                id=None,
                name=name,
                label_ids=label_ids,
                conditions=_conditions(conditions),
                kind=kind or LabelingRuleKind.MATCH,
                enabled=True if enabled is None else enabled,
            )
            use_case = ucs.create_labeling_rule
        return await use_case.execute(
            SaveLabelingRuleRequest(rule=rule, apply_to_existing=apply_to_existing)
        )

    @registry.write("Delete labeling rule", destructive=True, idempotent=True)
    async def delete_labeling_rule(rule_id: RuleId):
        """Delete an automatic labeling rule. Labels already applied are kept."""
        await ucs.delete_labeling_rule.execute(rule_id)
        return {"deleted": str(rule_id)}

    @registry.write("Relabel transactions")
    async def relabel_transactions(
        from_date: FromDate = None,
        to_date: ToDate = None,
        entities: EntityIds = None,
        unlabeled_only: Annotated[
            bool, Field(description="Only process movements without labels.")
        ] = False,
        dry_run: Annotated[
            bool, Field(description="Only count the changes, without applying them.")
        ] = False,
    ):
        """Re-run the labeling rules over existing account movements. Manually set (locked) labels are never changed."""
        return await ucs.relabel_transactions.execute(
            RelabelRequest(
                from_date=from_date,
                to_date=to_date,
                entities=entities,
                unlabeled_only=unlabeled_only,
                dry_run=dry_run,
            )
        )
