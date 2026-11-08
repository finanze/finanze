import re
import unicodedata
from dataclasses import field
from datetime import date
from enum import Enum
from functools import lru_cache
from typing import Optional
from uuid import UUID

from domain.dezimal import Dezimal
from domain.exception.exceptions import InvalidLabelingRule
from domain.transactions import (
    AccountTx,
    AccountTxSelection,
    LabelOrigin,
    TxType,
    is_valid_iban_format,
)
from pydantic.dataclasses import dataclass

LABELABLE_TX_TYPES = {TxType.INFLOW, TxType.OUTFLOW, TxType.INTEREST, TxType.FEE}

MAX_REGEX_LENGTH = 200
MAX_MATCH_TEXT_LENGTH = 500
MAX_LABEL_NAME_LENGTH = 64
MAX_LABEL_DESCRIPTION_LENGTH = 300
DEFAULT_TRANSFER_MAX_DAYS = 3
MAX_TRANSFER_MAX_DAYS = 31
MAX_CONDITION_GROUPS = 5
MAX_TEXT_VALUES = 20


class LabelingRuleKind(str, Enum):
    MATCH = "MATCH"
    TRANSFER = "TRANSFER"


class LabelCategory(str, Enum):
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"
    EXCLUDED = "EXCLUDED"


class LabelSubcategory(str, Enum):
    NEED = "NEED"
    WANTS = "WANTS"
    SAVINGS = "SAVINGS"
    NONE = "NONE"


LABEL_SUBCATEGORIES = {
    LabelCategory.INCOME: {LabelSubcategory.NONE},
    LabelCategory.EXPENSE: {LabelSubcategory.NEED, LabelSubcategory.WANTS},
    LabelCategory.EXCLUDED: {LabelSubcategory.SAVINGS, LabelSubcategory.NONE},
}
PROTECTED_LABEL_KEYS = {"internal_transfer"}


class TextMatchOperator(str, Enum):
    CONTAINS = "CONTAINS"
    STARTS_WITH = "STARTS_WITH"
    EQUALS = "EQUALS"
    REGEX = "REGEX"


class TextMatchField(str, Enum):
    ANY = "ANY"
    NAME = "NAME"
    COUNTERPARTY = "COUNTERPARTY"


@dataclass
class Label:
    id: Optional[UUID]
    key: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    category: LabelCategory = LabelCategory.EXPENSE
    usage: Optional[int] = None
    subcategory: Optional[LabelSubcategory] = None
    protected: bool = field(init=False, default=False)

    def __post_init__(self):
        if self.subcategory is None:
            self.subcategory = (
                LabelSubcategory.NEED
                if self.category == LabelCategory.EXPENSE
                else LabelSubcategory.NONE
            )
        self.protected = self.key in PROTECTED_LABEL_KEYS


@dataclass
class Labels:
    labels: list[Label]


@dataclass
class TextCondition:
    values: list[str]
    operator: TextMatchOperator = TextMatchOperator.CONTAINS
    field: TextMatchField = TextMatchField.ANY


@dataclass
class LabelingRuleConditions:
    types: Optional[list[TxType]] = None
    min_amount: Optional[Dezimal] = None
    max_amount: Optional[Dezimal] = None
    currency: Optional[str] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    day_from: Optional[int] = None
    day_to: Optional[int] = None
    entities: Optional[list[UUID]] = None
    text: Optional[TextCondition] = None
    max_days: Optional[int] = None
    ibans: Optional[list[str]] = None


@dataclass
class LabelingRule:
    id: Optional[UUID]
    conditions: list[LabelingRuleConditions]
    label_ids: list[UUID]
    name: Optional[str] = None
    enabled: bool = True
    kind: LabelingRuleKind = LabelingRuleKind.MATCH


@dataclass
class LabelingRules:
    rules: list[LabelingRule]


@dataclass
class SaveLabelingRuleRequest:
    rule: LabelingRule
    apply_to_existing: bool = False


@dataclass
class SavedLabelingRule:
    rule: LabelingRule
    applied: int = 0


@dataclass
class LabelingRulePreviewRequest:
    conditions: list[LabelingRuleConditions]
    limit: int = 10


@dataclass
class LabelingRulePreview:
    count: int
    samples: list[AccountTx]


@dataclass
class UpdateTransactionLabelsRequest:
    tx_id: UUID
    label_ids: list[UUID]
    locked: bool = True
    unlink: bool = False
    unpair: bool = False


@dataclass
class RelabelRequest:
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    entities: Optional[list[UUID]] = None
    with_labels: Optional[list[UUID]] = None
    without_labels: Optional[list[UUID]] = None
    unlabeled_only: bool = False
    origins: Optional[list[LabelOrigin]] = None
    include_external: bool = False
    retry_external_unmatched: bool = False
    dry_run: bool = False


class LabelingTrigger(str, Enum):
    AUTO = "AUTO"
    MANUAL = "MANUAL"


@dataclass
class LabelingResult:
    processed: int = 0
    linked: int = 0
    paired: int = 0
    rule_labeled: int = 0
    external_labeled: int = 0
    skipped_locked: int = 0
    skipped_linked: int = 0
    external_error: Optional[str] = None
    external_error_details: Optional[str] = None
    external_error_code: Optional[str] = None
    external_provider: Optional[str] = None
    external_model: Optional[str] = None


@dataclass
class RelabelResult:
    matched: int
    result: Optional[LabelingResult] = None
    external: Optional[LabelingResult] = None


def normalize_text(value: Optional[str]) -> str:
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKD", value)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(stripped.casefold().split())[:MAX_MATCH_TEXT_LENGTH]


def normalize_text_values(values: list[str]) -> list[str]:
    unique: dict[str, str] = {}
    for value in values:
        stripped = value.strip()
        key = normalize_text(stripped)
        if key and key not in unique:
            unique[key] = stripped
    return list(unique.values())


@lru_cache(maxsize=1024)
def _normalized_value(value: str) -> str:
    return normalize_text(value)


@lru_cache(maxsize=1024)
def _compile_pattern(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.IGNORECASE)


def _has_conditions(conditions: LabelingRuleConditions) -> bool:
    return any(
        [
            conditions.types,
            conditions.min_amount is not None,
            conditions.max_amount is not None,
            conditions.currency,
            conditions.from_date,
            conditions.to_date,
            conditions.day_from is not None,
            conditions.day_to is not None,
            conditions.entities,
            conditions.text is not None,
            conditions.ibans,
        ]
    )


def validate_conditions(conditions: LabelingRuleConditions):
    if not _has_conditions(conditions):
        raise InvalidLabelingRule("At least one condition is required")

    if conditions.max_days is not None:
        raise InvalidLabelingRule("Maximum days only applies to transfer rules")

    if conditions.types and any(t not in LABELABLE_TX_TYPES for t in conditions.types):
        raise InvalidLabelingRule("Unsupported transaction type")

    _validate_amounts(conditions)
    _validate_ibans(conditions)

    if (
        conditions.from_date
        and conditions.to_date
        and conditions.from_date > conditions.to_date
    ):
        raise InvalidLabelingRule("Start date is after end date")

    for day in (conditions.day_from, conditions.day_to):
        if day is not None and not 1 <= day <= 31:
            raise InvalidLabelingRule("Day of month must be between 1 and 31")

    if conditions.text is not None:
        _validate_text(conditions.text)


def _validate_text(text: TextCondition):
    if not text.values or any(not value or not value.strip() for value in text.values):
        raise InvalidLabelingRule("Text condition value is required")
    if len(text.values) > MAX_TEXT_VALUES:
        raise InvalidLabelingRule(
            f"Text condition supports at most {MAX_TEXT_VALUES} values"
        )
    if text.operator != TextMatchOperator.REGEX:
        return
    for value in text.values:
        if len(value) > MAX_REGEX_LENGTH:
            raise InvalidLabelingRule(f"Regular expression is too long: {value}")
        try:
            _compile_pattern(normalize_text(value))
        except re.error as e:
            raise InvalidLabelingRule(f"Invalid regular expression {value}: {e}") from e


def validate_condition_groups(groups: list[LabelingRuleConditions]):
    if not groups:
        raise InvalidLabelingRule("At least one condition group is required")
    if len(groups) > MAX_CONDITION_GROUPS:
        raise InvalidLabelingRule(
            f"A rule supports at most {MAX_CONDITION_GROUPS} condition groups"
        )
    for conditions in groups:
        validate_conditions(conditions)


def _validate_amounts(conditions: LabelingRuleConditions):
    if conditions.min_amount is not None and conditions.min_amount < 0:
        raise InvalidLabelingRule("Minimum amount must be positive")
    if conditions.max_amount is not None and conditions.max_amount < 0:
        raise InvalidLabelingRule("Maximum amount must be positive")
    if (
        conditions.min_amount is not None
        and conditions.max_amount is not None
        and conditions.min_amount > conditions.max_amount
    ):
        raise InvalidLabelingRule("Minimum amount is greater than maximum amount")


def _validate_ibans(conditions: LabelingRuleConditions):
    if conditions.ibans and not all(
        is_valid_iban_format(iban) for iban in conditions.ibans
    ):
        raise InvalidLabelingRule("Invalid IBAN")


def validate_transfer_conditions(conditions: LabelingRuleConditions):
    if any(
        [
            conditions.types,
            conditions.from_date,
            conditions.to_date,
            conditions.day_from is not None,
            conditions.day_to is not None,
            conditions.text is not None,
        ]
    ):
        raise InvalidLabelingRule("Unsupported condition for transfer rules")

    if conditions.max_days is not None and not (
        0 <= conditions.max_days <= MAX_TRANSFER_MAX_DAYS
    ):
        raise InvalidLabelingRule(
            f"Maximum days must be between 0 and {MAX_TRANSFER_MAX_DAYS}"
        )

    _validate_amounts(conditions)
    _validate_ibans(conditions)


def validate_rule(rule: LabelingRule):
    if not rule.label_ids:
        raise InvalidLabelingRule("At least one label is required")
    if rule.kind == LabelingRuleKind.TRANSFER:
        if len(rule.conditions) != 1:
            raise InvalidLabelingRule("Transfer rules support a single condition group")
        validate_transfer_conditions(rule.conditions[0])
    else:
        validate_condition_groups(rule.conditions)


def transfer_conditions(rule: LabelingRule) -> LabelingRuleConditions:
    return rule.conditions[0] if rule.conditions else LabelingRuleConditions()


def validate_label(label: Label):
    if not label.key and not (label.name and label.name.strip()):
        raise InvalidLabelingRule("Label name is required")
    if label.name and len(label.name) > MAX_LABEL_NAME_LENGTH:
        raise InvalidLabelingRule("Label name is too long")
    if label.description and len(label.description) > MAX_LABEL_DESCRIPTION_LENGTH:
        raise InvalidLabelingRule("Label description is too long")
    if label.subcategory not in LABEL_SUBCATEGORIES[label.category]:
        raise InvalidLabelingRule("Subcategory is not allowed for this label category")


def _value_matches(operator: TextMatchOperator, expected: str, text: str) -> bool:
    if operator == TextMatchOperator.CONTAINS:
        return expected in text
    if operator == TextMatchOperator.STARTS_WITH:
        return text.startswith(expected)
    if operator == TextMatchOperator.EQUALS:
        return text == expected
    return bool(_compile_pattern(expected).search(text))


def _text_matches(condition: TextCondition, candidates: list[str]) -> bool:
    texts = [text for text in map(normalize_text, candidates) if text]
    if not texts:
        return False
    for value in condition.values:
        expected = _normalized_value(value)
        if any(_value_matches(condition.operator, expected, text) for text in texts):
            return True
    return False


def _day_matches(day: int, day_from: Optional[int], day_to: Optional[int]) -> bool:
    if day_from is not None and day_to is not None and day_from > day_to:
        return day >= day_from or day <= day_to
    if day_from is not None and day < day_from:
        return False
    if day_to is not None and day > day_to:
        return False
    return True


def conditions_match(conditions: LabelingRuleConditions, tx: AccountTx) -> bool:
    if tx.type not in LABELABLE_TX_TYPES:
        return False

    if conditions.types and tx.type not in conditions.types:
        return False

    amount = abs(tx.amount)
    if conditions.min_amount is not None and amount < conditions.min_amount:
        return False
    if conditions.max_amount is not None and amount > conditions.max_amount:
        return False

    if conditions.currency and tx.currency.upper() != conditions.currency.upper():
        return False

    tx_date = tx.date.date()
    if conditions.from_date and tx_date < conditions.from_date:
        return False
    if conditions.to_date and tx_date > conditions.to_date:
        return False
    if not _day_matches(tx_date.day, conditions.day_from, conditions.day_to):
        return False

    if conditions.entities and tx.entity.id not in conditions.entities:
        return False

    if conditions.ibans and tx.iban not in conditions.ibans:
        return False

    if conditions.text is not None:
        field = conditions.text.field
        if field == TextMatchField.NAME:
            candidates = [tx.name]
        elif field == TextMatchField.COUNTERPARTY:
            candidates = [tx.counterparty or ""]
        else:
            candidates = [tx.name, tx.counterparty or ""]
        if not _text_matches(conditions.text, candidates):
            return False

    return True


def groups_match(groups: list[LabelingRuleConditions], tx: AccountTx) -> bool:
    return any(conditions_match(conditions, tx) for conditions in groups)


def candidate_selection(groups: list[LabelingRuleConditions]) -> AccountTxSelection:
    from_dates = [conditions.from_date for conditions in groups]
    to_dates = [conditions.to_date for conditions in groups]
    entities = [conditions.entities for conditions in groups]
    types = [conditions.types for conditions in groups]
    return AccountTxSelection(
        from_date=min(from_dates)
        if groups and all(d is not None for d in from_dates)
        else None,
        to_date=max(to_dates)
        if groups and all(d is not None for d in to_dates)
        else None,
        entities=list(dict.fromkeys(e for group in entities for e in group))
        if groups and all(entities)
        else None,
        types=list(dict.fromkeys(t for group in types for t in group))
        if groups and all(types)
        else list(LABELABLE_TX_TYPES),
        include_locked=False,
        include_linked=False,
    )


def matching_rules(rules: list[LabelingRule], tx: AccountTx) -> list[LabelingRule]:
    return [
        rule
        for rule in rules
        if rule.enabled
        and rule.kind == LabelingRuleKind.MATCH
        and groups_match(rule.conditions, tx)
    ]
