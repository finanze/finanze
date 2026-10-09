from dataclasses import replace
from datetime import datetime
from itertools import permutations
from uuid import uuid4

import pytest
from dateutil.tz import tzlocal

from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType
from domain.exception.exceptions import InvalidLabelingRule
from domain.fetch_record import DataSource
from domain.global_position import ProductType
from domain.labeling import (
    LabelingRule,
    LabelingRuleConditions,
    LabelingRuleKind,
    TextCondition,
    matching_rules,
    validate_rule,
)
from domain.transactions import AccountTx, TransferPair, TxType, normalize_iban
from domain.transfer_pairing import match_transfers, transfer_max_days


def _entity(name):
    return Entity(
        id=uuid4(),
        name=name,
        natural_id=None,
        type=EntityType.FINANCIAL_INSTITUTION,
        origin=EntityOrigin.MANUAL,
        icon_url=None,
    )


BANK = _entity("Bank")
BROKER = _entity("Broker")
NEOBANK = _entity("Neobank")


def _tx(entity, tx_type, amount, day, currency="EUR", **kwargs):
    return AccountTx(
        id=uuid4(),
        ref=str(uuid4()),
        name="Transfer",
        amount=Dezimal(amount),
        currency=currency,
        type=tx_type,
        date=datetime(2025, 3, day, 12, tzinfo=tzlocal()),
        entity=entity,
        source=DataSource.REAL,
        product_type=ProductType.ACCOUNT,
        fees=Dezimal(0),
        retentions=Dezimal(0),
        **kwargs,
    )


def _ids(pairs):
    return [(outflow.id, inflow.id) for outflow, inflow in pairs]


def test_matches_opposite_movements_across_entities():
    outflow = _tx(BANK, TxType.OUTFLOW, "500", 10)
    inflow = _tx(BROKER, TxType.INFLOW, "500.00", 12)

    pairs = match_transfers([inflow], [outflow, inflow], LabelingRuleConditions())

    assert _ids(pairs) == [(outflow.id, inflow.id)]


@pytest.mark.parametrize(
    "other",
    [
        _tx(BANK, TxType.INFLOW, "500", 10),
        _tx(BROKER, TxType.OUTFLOW, "500", 10),
        _tx(BROKER, TxType.INFLOW, "500.02", 10),
        _tx(BROKER, TxType.INFLOW, "500", 10, currency="USD"),
        _tx(BROKER, TxType.INFLOW, "500", 14),
        _tx(BROKER, TxType.INFLOW, "500", 10, labels_locked=True),
        _tx(BROKER, TxType.INFLOW, "500", 10, linked_tx="ref"),
        _tx(BROKER, TxType.INFLOW, "500", 10, transfer_pair=TransferPair(uuid4())),
        _tx(BROKER, TxType.INTEREST, "500", 10),
    ],
)
def test_rejects_non_matching_counterparts(other):
    outflow = _tx(BANK, TxType.OUTFLOW, "500", 10)

    assert match_transfers([outflow], [other], LabelingRuleConditions()) == []


def test_prefers_closest_dates_and_pairs_one_to_one():
    outflow = _tx(BANK, TxType.OUTFLOW, "100", 10)
    second_outflow = _tx(BANK, TxType.OUTFLOW, "100", 12)
    near = _tx(BROKER, TxType.INFLOW, "100", 11)
    exact = _tx(NEOBANK, TxType.INFLOW, "100", 12)

    pairs = match_transfers(
        [outflow, second_outflow],
        [outflow, second_outflow, near, exact],
        LabelingRuleConditions(),
    )

    assert sorted(_ids(pairs)) == sorted(
        [(second_outflow.id, exact.id), (outflow.id, near.id)]
    )


def test_respects_rule_filters():
    outflow = _tx(BANK, TxType.OUTFLOW, "50", 10)
    inflow = _tx(BROKER, TxType.INFLOW, "50", 10)
    usd_out = _tx(BANK, TxType.OUTFLOW, "200", 10, currency="USD")
    usd_in = _tx(NEOBANK, TxType.INFLOW, "200", 10, currency="USD")
    txs = [outflow, inflow, usd_out, usd_in]

    assert match_transfers(
        txs, txs, LabelingRuleConditions(min_amount=Dezimal(60))
    ) == [(usd_out, usd_in)]
    assert match_transfers(txs, txs, LabelingRuleConditions(currency="eur")) == [
        (outflow, inflow)
    ]
    assert match_transfers(
        txs, txs, LabelingRuleConditions(entities=[BANK.id, BROKER.id])
    ) == [(outflow, inflow)]
    assert (
        match_transfers(txs, txs, LabelingRuleConditions(max_amount=Dezimal(10))) == []
    )


def test_max_days_window():
    outflow = _tx(BANK, TxType.OUTFLOW, "80", 10)
    inflow = _tx(BROKER, TxType.INFLOW, "80", 5)

    assert match_transfers([outflow], [inflow], LabelingRuleConditions()) == []
    assert _ids(
        match_transfers([outflow], [inflow], LabelingRuleConditions(max_days=5))
    ) == [(outflow.id, inflow.id)]
    assert transfer_max_days(LabelingRuleConditions()) == 3
    assert transfer_max_days(LabelingRuleConditions(max_days=0)) == 0


def test_validate_transfer_rule():
    label_ids = [uuid4()]
    validate_rule(
        LabelingRule(
            id=None,
            conditions=LabelingRuleConditions(),
            label_ids=label_ids,
            kind=LabelingRuleKind.TRANSFER,
        )
    )

    invalid = [
        LabelingRuleConditions(text=TextCondition(value="x")),
        LabelingRuleConditions(types=[TxType.INFLOW]),
        LabelingRuleConditions(max_days=32),
        LabelingRuleConditions(max_days=-1),
        LabelingRuleConditions(min_amount=Dezimal(10), max_amount=Dezimal(5)),
    ]
    for conditions in invalid:
        with pytest.raises(InvalidLabelingRule):
            validate_rule(
                LabelingRule(
                    id=None,
                    conditions=conditions,
                    label_ids=label_ids,
                    kind=LabelingRuleKind.TRANSFER,
                )
            )

    with pytest.raises(InvalidLabelingRule):
        validate_rule(
            LabelingRule(
                id=None,
                conditions=LabelingRuleConditions(
                    text=TextCondition(value="x"), max_days=2
                ),
                label_ids=label_ids,
            )
        )


def test_matching_rules_ignores_transfer_rules():
    tx = _tx(BANK, TxType.OUTFLOW, "10", 10)
    transfer = LabelingRule(
        id=uuid4(),
        conditions=LabelingRuleConditions(),
        label_ids=[uuid4()],
        kind=LabelingRuleKind.TRANSFER,
    )
    match = LabelingRule(
        id=uuid4(),
        conditions=LabelingRuleConditions(types=[TxType.OUTFLOW]),
        label_ids=[uuid4()],
    )

    assert matching_rules([transfer, match], tx) == [match]


CHECKING = "ES7600000000000000000001"
SAVINGS = "ES7600000000000000000002"


def test_pairs_same_entity_movements_between_different_accounts():
    outflow = _tx(BANK, TxType.OUTFLOW, "200", 10, iban=CHECKING)
    inflow = _tx(BANK, TxType.INFLOW, "200", 10, iban=SAVINGS)
    refund = _tx(BANK, TxType.INFLOW, "200", 10, iban=CHECKING)
    unknown = _tx(BANK, TxType.INFLOW, "200", 10)

    assert _ids(
        match_transfers([outflow], [refund, unknown, inflow], LabelingRuleConditions())
    ) == [(outflow.id, inflow.id)]
    assert match_transfers([outflow], [refund, unknown], LabelingRuleConditions()) == []


def test_same_iban_across_entities_never_pairs():
    outflow = _tx(BANK, TxType.OUTFLOW, "200", 10, iban=CHECKING)
    inflow = _tx(BROKER, TxType.INFLOW, "200", 10, iban=CHECKING)

    assert match_transfers([outflow], [inflow], LabelingRuleConditions()) == []


def test_pass_through_chain_pairs_every_leg_regardless_of_order():
    for _ in range(10):
        external_out = _tx(BANK, TxType.OUTFLOW, "1500", 10)
        main_in = _tx(NEOBANK, TxType.INFLOW, "1500", 10, iban=CHECKING)
        main_out = _tx(NEOBANK, TxType.OUTFLOW, "1500", 10, iban=CHECKING)
        savings_in = _tx(NEOBANK, TxType.INFLOW, "1500", 10, iban=SAVINGS)
        txs = [external_out, main_in, main_out, savings_in]

        for order in permutations(txs):
            pairs = match_transfers(
                list(order), list(reversed(order)), LabelingRuleConditions()
            )
            assert sorted(_ids(pairs)) == sorted(
                [(external_out.id, main_in.id), (main_out.id, savings_in.id)]
            )


def test_same_day_ties_prefer_closest_time():
    outflow = replace(
        _tx(BANK, TxType.OUTFLOW, "300", 10),
        date=datetime(2025, 3, 10, 8, 4, tzinfo=tzlocal()),
    )
    morning = replace(
        _tx(BROKER, TxType.INFLOW, "300", 10),
        date=datetime(2025, 3, 10, 8, 5, tzinfo=tzlocal()),
    )
    evening = replace(
        _tx(NEOBANK, TxType.INFLOW, "300", 10),
        date=datetime(2025, 3, 10, 19, 0, tzinfo=tzlocal()),
    )

    for pool in permutations([morning, evening]):
        assert _ids(
            match_transfers([outflow], list(pool), LabelingRuleConditions())
        ) == [(outflow.id, morning.id)]


def test_iban_condition_requires_both_accounts():
    outflow = _tx(BANK, TxType.OUTFLOW, "200", 10, iban=CHECKING)
    inflow = _tx(BANK, TxType.INFLOW, "200", 10, iban=SAVINGS)
    conditions = LabelingRuleConditions(ibans=[CHECKING, SAVINGS])

    assert _ids(match_transfers([outflow], [inflow], conditions)) == [
        (outflow.id, inflow.id)
    ]
    assert (
        match_transfers([outflow], [inflow], LabelingRuleConditions(ibans=[CHECKING]))
        == []
    )


def test_match_rule_iban_condition():
    rule = LabelingRule(
        id=uuid4(),
        conditions=LabelingRuleConditions(ibans=[SAVINGS]),
        label_ids=[uuid4()],
    )
    validate_rule(rule)

    assert matching_rules([rule], _tx(BANK, TxType.INFLOW, "5", 10, iban=SAVINGS)) == [
        rule
    ]
    assert (
        matching_rules([rule], _tx(BANK, TxType.INFLOW, "5", 10, iban=CHECKING)) == []
    )
    assert matching_rules([rule], _tx(BANK, TxType.INFLOW, "5", 10)) == []

    for kind in LabelingRuleKind:
        with pytest.raises(InvalidLabelingRule):
            validate_rule(
                LabelingRule(
                    id=None,
                    conditions=LabelingRuleConditions(ibans=["ES76-0000"]),
                    label_ids=[uuid4()],
                    kind=kind,
                )
            )


def test_normalize_iban():
    assert normalize_iban(" es76 0000 0000 0001 ") == "ES76000000000001"
    assert normalize_iban("  ") is None
    assert normalize_iban(None) is None
