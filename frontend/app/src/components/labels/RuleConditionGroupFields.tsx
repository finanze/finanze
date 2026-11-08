import { useEffect, useId, useState } from "react"
import { AnimatePresence, motion } from "framer-motion"
import { ChevronDown } from "lucide-react"
import { useI18n } from "@/i18n"
import { DecimalInput } from "@/components/ui/DecimalInput"
import { DatePicker } from "@/components/ui/DatePicker"
import { Input } from "@/components/ui/Input"
import { Label as FieldLabel } from "@/components/ui/Label"
import {
  MultiSelect,
  type MultiSelectOption,
} from "@/components/ui/MultiSelect"
import { TagInput } from "@/components/ui/TagInput"
import { EntitySelector } from "@/components/EntitySelector"
import { cn } from "@/lib/utils"
import type { Entity } from "@/types"
import {
  MAX_TEXT_VALUES,
  TextMatchField,
  TextMatchOperator,
} from "@/types/labeling"
import { LABELABLE_TX_TYPES } from "@/types/transactions"
import { getIconForTxType } from "@/utils/dashboardUtils"
import { groupHasAdvanced, type ConditionGroupForm } from "./ruleForm"

export const SELECT_CLASS =
  "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"

export const pillClass = (active: boolean) =>
  cn(
    "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors disabled:opacity-50",
    active
      ? "border-foreground bg-foreground text-background"
      : "border-border text-muted-foreground hover:text-foreground",
  )

interface RuleAccountsFieldProps {
  value: string[]
  onChange: (value: string[]) => void
  options: MultiSelectOption[]
  hint: string
  disabled: boolean
}

export function RuleAccountsField({
  value,
  onChange,
  options,
  hint,
  disabled,
}: RuleAccountsFieldProps) {
  const { t } = useI18n()
  return (
    <div className="space-y-1.5 sm:col-span-2">
      <FieldLabel className="block">{t.labels.rules.accounts}</FieldLabel>
      <MultiSelect
        options={options}
        value={value}
        onChange={onChange}
        placeholder={t.labels.rules.anyAccount}
        disabled={disabled}
      />
      <p className="text-xs text-muted-foreground">{hint}</p>
    </div>
  )
}

interface RuleConditionGroupFieldsProps {
  group: ConditionGroupForm
  onChange: (patch: Partial<ConditionGroupForm>) => void
  entityOptions: Entity[]
  accountOptions: MultiSelectOption[]
  disabled: boolean
  focusText?: boolean
}

export function RuleConditionGroupFields({
  group,
  onChange,
  entityOptions,
  accountOptions,
  disabled,
  focusText,
}: RuleConditionGroupFieldsProps) {
  const { t } = useI18n()
  const fieldId = useId()
  const [showAdvanced, setShowAdvanced] = useState(() =>
    groupHasAdvanced(group),
  )
  const [advancedAnimating, setAdvancedAnimating] = useState(false)

  useEffect(() => {
    if (focusText) document.getElementById(`${fieldId}-text`)?.focus()
  }, [focusText, fieldId])
  const isRegex = group.textOperator === TextMatchOperator.REGEX
  const textHint =
    group.textValues.length >= MAX_TEXT_VALUES
      ? t.labels.rules.maxTextValues.replace("{max}", `${MAX_TEXT_VALUES}`)
      : isRegex
        ? t.labels.rules.textValuesHintRegex
        : t.labels.rules.textValuesHint

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <FieldLabel htmlFor={`${fieldId}-text`}>
          {t.labels.rules.textValue}
        </FieldLabel>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start">
          <select
            aria-label={t.labels.rules.textOperator}
            value={group.textOperator}
            onChange={event =>
              onChange({
                textOperator: event.target.value as TextMatchOperator,
              })
            }
            className={cn(SELECT_CLASS, "sm:w-48 sm:shrink-0")}
            disabled={disabled}
          >
            {Object.values(TextMatchOperator).map(operator => (
              <option key={operator} value={operator}>
                {t.labels.rules.operators[operator]}
              </option>
            ))}
          </select>
          <TagInput
            id={`${fieldId}-text`}
            testId="rule-text-value"
            values={group.textValues}
            onChange={textValues => onChange({ textValues })}
            draft={group.textDraft}
            onDraftChange={textDraft => onChange({ textDraft })}
            separators={isRegex ? ["Enter"] : ["Enter", ","]}
            maxItems={MAX_TEXT_VALUES}
            maxLength={200}
            placeholder={t.labels.rules.textValuePlaceholder}
            removeLabel={value =>
              t.labels.rules.removeValue.replace("{value}", value)
            }
            mono={isRegex}
            disabled={disabled}
            aria-describedby={`${fieldId}-text-hint`}
            className="flex-1"
          />
        </div>
        <p
          id={`${fieldId}-text-hint`}
          className="text-xs text-muted-foreground"
        >
          {textHint}
        </p>
        <div
          className="flex flex-wrap items-center gap-1.5"
          role="radiogroup"
          aria-label={t.labels.rules.textField}
        >
          <span className="mr-1 text-xs text-muted-foreground">
            {t.labels.rules.lookIn}
          </span>
          {Object.values(TextMatchField).map(field => (
            <button
              key={field}
              type="button"
              role="radio"
              aria-checked={group.textField === field}
              onClick={() => onChange({ textField: field })}
              disabled={disabled}
              className={pillClass(group.textField === field)}
            >
              {t.labels.rules.fields[field]}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        <FieldLabel>{t.transactions.transactionTypes}</FieldLabel>
        <div className="flex flex-wrap gap-1.5">
          <button
            type="button"
            aria-pressed={group.types.length === 0}
            onClick={() => onChange({ types: [] })}
            disabled={disabled}
            className={pillClass(group.types.length === 0)}
          >
            {t.labels.rules.anyType}
          </button>
          {LABELABLE_TX_TYPES.map(type => {
            const selected = group.types.includes(type)
            return (
              <button
                key={type}
                type="button"
                aria-pressed={selected}
                onClick={() =>
                  onChange({
                    types: selected
                      ? group.types.filter(value => value !== type)
                      : [...group.types, type],
                  })
                }
                disabled={disabled}
                className={pillClass(selected)}
              >
                {getIconForTxType(type, "h-3.5 w-3.5")}
                {t.enums.transactionType[type] ?? type}
              </button>
            )
          })}
        </div>
      </div>

      <button
        type="button"
        onClick={() => setShowAdvanced(prev => !prev)}
        aria-expanded={showAdvanced}
        className="flex items-center gap-1 text-sm font-medium text-muted-foreground hover:text-foreground"
      >
        {t.labels.rules.moreConditions}
        <ChevronDown
          className={cn(
            "h-4 w-4 transition-transform",
            showAdvanced && "rotate-180",
          )}
        />
      </button>

      <AnimatePresence initial={false}>
        {showAdvanced && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeInOut" }}
            onAnimationStart={() => setAdvancedAnimating(true)}
            onAnimationComplete={() => setAdvancedAnimating(false)}
            className={cn(advancedAnimating && "overflow-hidden")}
          >
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <FieldLabel>{t.labels.rules.amount}</FieldLabel>
                <div className="flex items-center gap-2">
                  <DecimalInput
                    value={group.minAmount}
                    onStringChange={minAmount => onChange({ minAmount })}
                    placeholder={t.labels.rules.min}
                    aria-label={t.labels.rules.minAmount}
                    disabled={disabled}
                  />
                  <span className="text-muted-foreground">–</span>
                  <DecimalInput
                    value={group.maxAmount}
                    onStringChange={maxAmount => onChange({ maxAmount })}
                    placeholder={t.labels.rules.max}
                    aria-label={t.labels.rules.maxAmount}
                    disabled={disabled}
                  />
                </div>
              </div>
              <div className="space-y-1.5">
                <FieldLabel htmlFor={`${fieldId}-currency`}>
                  {t.transactions.currency}
                </FieldLabel>
                <Input
                  id={`${fieldId}-currency`}
                  value={group.currency}
                  maxLength={10}
                  placeholder={t.labels.rules.anyCurrency}
                  onChange={event =>
                    onChange({ currency: event.target.value.toUpperCase() })
                  }
                  disabled={disabled}
                />
              </div>
              <div className="space-y-1.5">
                <FieldLabel className="block">
                  {t.labels.rules.dateRange}
                </FieldLabel>
                <div className="flex items-center gap-2">
                  <div className="min-w-0 flex-1">
                    <DatePicker
                      value={group.fromDate}
                      onChange={fromDate => onChange({ fromDate })}
                      placeholder={t.transactions.fromDate}
                      disabled={disabled}
                    />
                  </div>
                  <span className="text-muted-foreground">–</span>
                  <div className="min-w-0 flex-1">
                    <DatePicker
                      value={group.toDate}
                      onChange={toDate => onChange({ toDate })}
                      placeholder={t.transactions.toDate}
                      disabled={disabled}
                    />
                  </div>
                </div>
              </div>
              <div className="space-y-1.5">
                <FieldLabel>{t.labels.rules.dayOfMonth}</FieldLabel>
                <div className="flex items-center gap-2">
                  <Input
                    type="number"
                    min={1}
                    max={31}
                    value={group.dayFrom}
                    placeholder="1"
                    onChange={event =>
                      onChange({ dayFrom: event.target.value })
                    }
                    aria-label={t.labels.rules.dayFrom}
                    disabled={disabled}
                  />
                  <span className="text-muted-foreground">–</span>
                  <Input
                    type="number"
                    min={1}
                    max={31}
                    value={group.dayTo}
                    placeholder="31"
                    onChange={event => onChange({ dayTo: event.target.value })}
                    aria-label={t.labels.rules.dayTo}
                    disabled={disabled}
                  />
                </div>
                <p className="text-xs text-muted-foreground">
                  {t.labels.rules.dayOfMonthHint}
                </p>
              </div>
              <div className="space-y-1.5 sm:col-span-2">
                <FieldLabel className="block">
                  {t.transactions.entities}
                </FieldLabel>
                <EntitySelector
                  entities={entityOptions}
                  selectedEntityIds={group.entities}
                  onSelectionChange={entities => onChange({ entities })}
                  disabled={disabled}
                  className="max-w-none"
                />
              </div>
              <RuleAccountsField
                value={group.ibans}
                onChange={ibans => onChange({ ibans })}
                options={accountOptions}
                hint={t.labels.rules.accountsHint}
                disabled={disabled}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
