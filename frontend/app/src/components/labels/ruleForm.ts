import { mergeTags } from "@/components/ui/TagInput"
import {
  LabelingRuleKind,
  TextMatchField,
  TextMatchOperator,
  type LabelingRule,
  type LabelingRuleConditions,
} from "@/types/labeling"
import type { TxType } from "@/types/transactions"
import type { LabelableTx } from "./TransactionLabelsDialog"

export const DEFAULT_TRANSFER_MAX_DAYS = 3
export const MAX_TRANSFER_MAX_DAYS = 31

export interface ConditionGroupForm {
  key: string
  types: string[]
  textValues: string[]
  textDraft: string
  textField: TextMatchField
  textOperator: TextMatchOperator
  minAmount: string
  maxAmount: string
  currency: string
  fromDate: string
  toDate: string
  dayFrom: string
  dayTo: string
  entities: string[]
  ibans: string[]
}

export interface RuleFormState {
  kind: LabelingRuleKind
  name: string
  enabled: boolean
  labelIds: string[]
  groups: ConditionGroupForm[]
  maxDays: string
}

let groupSequence = 0

export const emptyGroup = (): ConditionGroupForm => ({
  key: `group-${++groupSequence}`,
  types: [],
  textValues: [],
  textDraft: "",
  textField: TextMatchField.ANY,
  textOperator: TextMatchOperator.CONTAINS,
  minAmount: "",
  maxAmount: "",
  currency: "",
  fromDate: "",
  toDate: "",
  dayFrom: "",
  dayTo: "",
  entities: [],
  ibans: [],
})

const groupFromConditions = (
  c: LabelingRuleConditions,
): ConditionGroupForm => ({
  ...emptyGroup(),
  types: c.types ?? [],
  textValues: c.text?.values ?? [],
  textField: c.text?.field ?? TextMatchField.ANY,
  textOperator: c.text?.operator ?? TextMatchOperator.CONTAINS,
  minAmount: c.min_amount != null ? `${c.min_amount}` : "",
  maxAmount: c.max_amount != null ? `${c.max_amount}` : "",
  currency: c.currency ?? "",
  fromDate: c.from_date ?? "",
  toDate: c.to_date ?? "",
  dayFrom: c.day_from != null ? `${c.day_from}` : "",
  dayTo: c.day_to != null ? `${c.day_to}` : "",
  entities: c.entities ?? [],
  ibans: c.ibans ?? [],
})

export const emptyForm = (): RuleFormState => ({
  kind: LabelingRuleKind.MATCH,
  name: "",
  enabled: true,
  labelIds: [],
  groups: [emptyGroup()],
  maxDays: `${DEFAULT_TRANSFER_MAX_DAYS}`,
})

export const formFromRule = (rule: LabelingRule): RuleFormState => ({
  kind: rule.kind ?? LabelingRuleKind.MATCH,
  name: rule.name ?? "",
  enabled: rule.enabled,
  labelIds: rule.label_ids,
  groups: rule.conditions.length
    ? rule.conditions.map(groupFromConditions)
    : [emptyGroup()],
  maxDays: `${rule.conditions[0]?.max_days ?? DEFAULT_TRANSFER_MAX_DAYS}`,
})

export const formFromTx = (tx: LabelableTx): RuleFormState => {
  const counterparty = tx.counterparty?.trim()
  return {
    ...emptyForm(),
    name: counterparty || tx.name,
    labelIds: (tx.labels ?? []).map(label => label.label_id),
    groups: [
      {
        ...emptyGroup(),
        types: [tx.type],
        textValues: [counterparty || tx.name],
        textField: counterparty
          ? TextMatchField.COUNTERPARTY
          : TextMatchField.NAME,
      },
    ],
  }
}

export const parseOptionalNumber = (value: string): number | null => {
  if (!value.trim()) return null
  const parsed = Number.parseFloat(value.replace(",", "."))
  return Number.isFinite(parsed) ? parsed : null
}

export const parseOptionalDay = (value: string): number | null => {
  const parsed = Number.parseInt(value, 10)
  return Number.isFinite(parsed) ? parsed : null
}

export const groupTextValues = (group: ConditionGroupForm): string[] =>
  mergeTags(
    group.textValues,
    group.textOperator === TextMatchOperator.REGEX
      ? [group.textDraft]
      : group.textDraft.split(","),
  )

const sharedConditions = (group: ConditionGroupForm) => ({
  min_amount: parseOptionalNumber(group.minAmount),
  max_amount: parseOptionalNumber(group.maxAmount),
  currency: group.currency.trim() ? group.currency.trim().toUpperCase() : null,
  entities: group.entities.length ? group.entities : null,
  ibans: group.ibans.length ? group.ibans : null,
})

const buildGroupConditions = (
  group: ConditionGroupForm,
): LabelingRuleConditions => {
  const values = groupTextValues(group)
  return {
    ...sharedConditions(group),
    types: group.types.length ? (group.types as TxType[]) : null,
    from_date: group.fromDate || null,
    to_date: group.toDate || null,
    day_from: parseOptionalDay(group.dayFrom),
    day_to: parseOptionalDay(group.dayTo),
    text: values.length
      ? { values, field: group.textField, operator: group.textOperator }
      : null,
  }
}

export const buildConditions = (
  form: RuleFormState,
): LabelingRuleConditions[] =>
  form.kind === LabelingRuleKind.TRANSFER
    ? [
        {
          ...sharedConditions(form.groups[0]),
          max_days: parseOptionalDay(form.maxDays) ?? DEFAULT_TRANSFER_MAX_DAYS,
        },
      ]
    : form.groups.map(buildGroupConditions)

export const hasAnyCondition = (conditions: LabelingRuleConditions) =>
  Object.values(conditions).some(value => value !== null)

export const groupHasAdvanced = (group: ConditionGroupForm) =>
  Boolean(
    group.minAmount ||
    group.maxAmount ||
    group.currency ||
    group.fromDate ||
    group.toDate ||
    group.dayFrom ||
    group.dayTo ||
    group.entities.length ||
    group.ibans.length,
  )
