from datetime import date, datetime
from uuid import uuid4

import pytest
from dateutil.tz import tzlocal

from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType
from domain.exception.exceptions import InvalidLabelingRule
from domain.fetch_record import DataSource
from domain.global_position import ProductType
from domain.labeling import (
    LABELABLE_TX_TYPES,
    MAX_CONDITION_GROUPS,
    MAX_TEXT_VALUES,
    LabelingRule,
    LabelingRuleConditions,
    LabelingRuleKind,
    TextCondition,
    TextMatchField,
    TextMatchOperator,
    candidate_selection,
    groups_match,
    matching_rules,
    normalize_text_values,
    transfer_conditions,
    validate_condition_groups,
    validate_rule,
)
from domain.transactions import AccountTx, TxType

BANK = Entity(
    id=uuid4(),
    name="Bank",
    natural_id=None,
    type=EntityType.FINANCIAL_INSTITUTION,
    origin=EntityOrigin.MANUAL,
    icon_url=None,
)
BROKER_ID = uuid4()


def _tx(name, amount="10", tx_type=TxType.OUTFLOW, day=10, counterparty=None):
    return AccountTx(
        id=uuid4(),
        ref=str(uuid4()),
        name=name,
        amount=Dezimal(amount),
        currency="EUR",
        type=tx_type,
        date=datetime(2025, 3, day, 12, tzinfo=tzlocal()),
        entity=BANK,
        source=DataSource.REAL,
        product_type=ProductType.ACCOUNT,
        fees=Dezimal(0),
        retentions=Dezimal(0),
        counterparty=counterparty,
    )


def _text(*values, operator=TextMatchOperator.CONTAINS, field=TextMatchField.ANY):
    return LabelingRuleConditions(
        text=TextCondition(values=list(values), operator=operator, field=field)
    )


def test_text_condition_matches_any_value():
    groups = [_text("mercadona", "lidl")]

    assert groups_match(groups, _tx("MERCADONA VALENCIA"))
    assert groups_match(groups, _tx("Compra", counterparty="Lidl SA"))
    assert not groups_match(groups, _tx("Cinema"))


def test_text_values_respect_operator_and_field():
    starts = [_text("amzn", "amazon", operator=TextMatchOperator.STARTS_WITH)]
    assert groups_match(starts, _tx("AMZN Mktp"))
    assert not groups_match(starts, _tx("Pago AMAZON"))

    equals = [_text("Netflix", "Spotify", operator=TextMatchOperator.EQUALS)]
    assert groups_match(equals, _tx("SPOTIFY"))
    assert not groups_match(equals, _tx("Spotify Premium"))

    regex = [_text(r"^uber\b", r"cabify$", operator=TextMatchOperator.REGEX)]
    assert groups_match(regex, _tx("UBER TRIP"))
    assert groups_match(regex, _tx("Viaje Cabify"))
    assert not groups_match(regex, _tx("Uberrimo"))

    counterparty = [_text("acme", "globex", field=TextMatchField.COUNTERPARTY)]
    assert groups_match(counterparty, _tx("Nomina", counterparty="Globex Corp"))
    assert not groups_match(counterparty, _tx("ACME payment"))


def test_groups_are_ored_and_conditions_inside_a_group_are_anded():
    groups = [
        _text("mercadona"),
        LabelingRuleConditions(
            text=TextCondition(values=["nomina"]),
            types=[TxType.INFLOW],
            min_amount=Dezimal(100),
        ),
    ]

    assert groups_match(groups, _tx("Mercadona"))
    assert groups_match(groups, _tx("NOMINA", "2000", TxType.INFLOW))
    assert not groups_match(groups, _tx("NOMINA", "50", TxType.INFLOW))
    assert not groups_match(groups, _tx("NOMINA", "2000", TxType.OUTFLOW))
    assert not groups_match([], _tx("Mercadona"))


def test_matching_rules_uses_any_group():
    rule = LabelingRule(
        id=uuid4(),
        conditions=[_text("netflix"), _text("spotify")],
        label_ids=[uuid4()],
    )
    disabled = LabelingRule(
        id=uuid4(),
        conditions=[_text("spotify")],
        label_ids=[uuid4()],
        enabled=False,
    )

    assert matching_rules([rule, disabled], _tx("Spotify")) == [rule]
    assert matching_rules([rule, disabled], _tx("Cinema")) == []


def test_normalize_text_values_strips_and_dedupes_keeping_first_spelling():
    assert normalize_text_values(
        ["  Mercadona ", "mercadona", "", "   ", "MERCADÓNA", "Lidl"]
    ) == ["Mercadona", "Lidl"]


def test_validate_condition_groups():
    validate_condition_groups([_text("a")] * MAX_CONDITION_GROUPS)

    invalid = [
        [],
        [_text("a")] * (MAX_CONDITION_GROUPS + 1),
        [_text("a"), LabelingRuleConditions()],
        [_text()],
        [_text("ok", " ")],
        [_text(*[f"v{i}" for i in range(MAX_TEXT_VALUES + 1)])],
        [_text("ok", "(", operator=TextMatchOperator.REGEX)],
        [_text("x" * 201, operator=TextMatchOperator.REGEX)],
    ]
    for groups in invalid:
        with pytest.raises(InvalidLabelingRule):
            validate_condition_groups(groups)

    with pytest.raises(InvalidLabelingRule, match=r"\("):
        validate_condition_groups([_text("ok", "(", operator=TextMatchOperator.REGEX)])


def test_validate_rule_accepts_multiple_match_groups_only():
    labels = [uuid4()]
    validate_rule(
        LabelingRule(id=None, conditions=[_text("a"), _text("b")], label_ids=labels)
    )

    with pytest.raises(InvalidLabelingRule):
        validate_rule(LabelingRule(id=None, conditions=[], label_ids=labels))
    with pytest.raises(InvalidLabelingRule):
        validate_rule(
            LabelingRule(
                id=None,
                conditions=[LabelingRuleConditions(), LabelingRuleConditions()],
                label_ids=labels,
                kind=LabelingRuleKind.TRANSFER,
            )
        )


def test_transfer_conditions_returns_first_group_or_empty():
    group = LabelingRuleConditions(max_days=2)
    rule = LabelingRule(
        id=None,
        conditions=[group],
        label_ids=[uuid4()],
        kind=LabelingRuleKind.TRANSFER,
    )
    assert transfer_conditions(rule) == group

    rule.conditions = []
    assert transfer_conditions(rule) == LabelingRuleConditions()


def test_candidate_selection_is_union_of_groups():
    selection = candidate_selection(
        [
            LabelingRuleConditions(
                types=[TxType.OUTFLOW],
                entities=[BANK.id],
                from_date=date(2025, 3, 1),
                to_date=date(2025, 3, 5),
            ),
            LabelingRuleConditions(
                types=[TxType.INFLOW, TxType.OUTFLOW],
                entities=[BROKER_ID],
                from_date=date(2025, 3, 20),
                to_date=date(2025, 3, 25),
            ),
        ]
    )

    assert selection.types == [TxType.OUTFLOW, TxType.INFLOW]
    assert selection.entities == [BANK.id, BROKER_ID]
    assert selection.from_date == date(2025, 3, 1)
    assert selection.to_date == date(2025, 3, 25)
    assert selection.include_locked is False
    assert selection.include_linked is False


def test_candidate_selection_drops_filters_unbounded_by_any_group():
    selection = candidate_selection(
        [
            LabelingRuleConditions(
                types=[TxType.OUTFLOW],
                entities=[BANK.id],
                from_date=date(2025, 3, 1),
                to_date=date(2025, 3, 5),
            ),
            _text("anything"),
        ]
    )

    assert set(selection.types) == LABELABLE_TX_TYPES
    assert selection.entities is None
    assert selection.from_date is None
    assert selection.to_date is None
