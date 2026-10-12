from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from application.ports.label_port import LabelPort
from application.ports.labeling_rule_port import LabelingRulePort
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.use_cases.create_label import CreateLabelImpl
from application.use_cases.delete_label import DeleteLabelImpl
from application.use_cases.update_label import UpdateLabelImpl
from domain.exception.exceptions import (
    InvalidLabelingRule,
    LabelNotFound,
    ProtectedLabel,
)
from domain.labeling import Label, LabelCategory, LabelSubcategory


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["update", "delete"])
async def test_protected_label_operations_do_not_write_or_start_transaction(operation):
    labels = AsyncMock(spec=LabelPort)
    rules = AsyncMock(spec=LabelingRulePort)
    handler = AsyncMock(spec=TransactionHandlerPort)
    existing = Label(
        id=uuid4(), key="internal_transfer", category=LabelCategory.EXCLUDED
    )
    labels.get_by_id.return_value = existing

    with pytest.raises(ProtectedLabel):
        if operation == "update":
            await UpdateLabelImpl(labels).execute(Label(id=existing.id, name="Changed"))
        else:
            await DeleteLabelImpl(labels, rules, handler).execute(existing.id)

    labels.update.assert_not_awaited()
    labels.delete.assert_not_awaited()
    rules.get_all.assert_not_awaited()
    handler.start.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["update", "delete"])
async def test_missing_label_operations_keep_not_found_error(operation):
    labels = AsyncMock(spec=LabelPort)
    labels.get_by_id.return_value = None
    label_id = uuid4()

    with pytest.raises(LabelNotFound):
        if operation == "update":
            await UpdateLabelImpl(labels).execute(Label(id=label_id, name="Missing"))
        else:
            await DeleteLabelImpl(
                labels,
                AsyncMock(spec=LabelingRulePort),
                AsyncMock(spec=TransactionHandlerPort),
            ).execute(label_id)

    labels.update.assert_not_awaited()
    labels.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_preserves_omitted_subcategory_in_same_category():
    labels = AsyncMock(spec=LabelPort)
    existing = Label(id=uuid4(), name="Leisure", subcategory=LabelSubcategory.WANTS)
    labels.get_by_id.return_value = existing
    updated = Label(id=existing.id, name="Renamed leisure")

    await UpdateLabelImpl(labels).execute(updated, subcategory_provided=False)

    assert updated.subcategory == LabelSubcategory.WANTS
    labels.update.assert_awaited_once_with(updated)


@pytest.mark.asyncio
async def test_update_rejects_incompatible_subcategory_before_write():
    labels = AsyncMock(spec=LabelPort)
    existing = Label(id=uuid4(), name="Expense")
    labels.get_by_id.return_value = existing

    with pytest.raises(InvalidLabelingRule):
        await UpdateLabelImpl(labels).execute(
            Label(id=existing.id, name="Expense", subcategory=LabelSubcategory.SAVINGS)
        )

    labels.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_strips_system_identity_and_protection():
    labels = AsyncMock(spec=LabelPort)
    labels.save.side_effect = lambda label: label
    label = Label(
        id=uuid4(),
        key="internal_transfer",
        name=" Custom label ",
        category=LabelCategory.EXCLUDED,
    )

    created = await CreateLabelImpl(labels).execute(label)

    assert created.id is None
    assert created.key is None
    assert created.protected is False
    assert created.name == "Custom label"
    labels.save.assert_awaited_once_with(created)
