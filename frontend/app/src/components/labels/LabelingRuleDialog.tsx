import { useEffect, useMemo, useState } from "react"
import {
  ArrowLeftRight,
  ChevronDown,
  Eye,
  Loader2,
  Save,
  Wand2,
  X,
} from "lucide-react"
import { useI18n } from "@/i18n"
import { useAppContext } from "@/context/AppContext"
import { useFinancialData } from "@/context/FinancialDataContext"
import { useLabels } from "@/context/LabelsContext"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { DecimalInput } from "@/components/ui/DecimalInput"
import { Label as FieldLabel } from "@/components/ui/Label"
import { Switch } from "@/components/ui/Switch"
import { DatePicker } from "@/components/ui/DatePicker"
import {
  MultiSelect,
  type MultiSelectOption,
} from "@/components/ui/MultiSelect"
import { EntitySelector } from "@/components/EntitySelector"
import {
  createLabelingRule,
  previewLabelingRule,
  updateLabelingRule,
} from "@/services/api"
import { formatCurrency, formatDate, shortIban } from "@/lib/formatters"
import { cn } from "@/lib/utils"
import { EntityType } from "@/types"
import { ProductType, type Accounts } from "@/types/position"
import { LABELABLE_TX_TYPES, TxType } from "@/types/transactions"
import {
  LabelingRuleKind,
  TextMatchField,
  TextMatchOperator,
  type LabelingRule,
  type LabelingRuleConditions,
  type LabelingRulePreview,
} from "@/types/labeling"
import { getIconForTxType } from "@/utils/dashboardUtils"
import { LabelingModal } from "./LabelingModal"
import { LabelSelector } from "./LabelSelector"
import type { LabelableTx } from "./TransactionLabelsDialog"

const SELECT_CLASS =
  "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"

const PREVIEW_LIMIT = 10
const DEFAULT_TRANSFER_MAX_DAYS = 3
const MAX_TRANSFER_MAX_DAYS = 31
const TRANSFER_LABEL_KEY = "internal_transfer"

const RULE_KINDS = [
  { kind: LabelingRuleKind.MATCH, Icon: Wand2 },
  { kind: LabelingRuleKind.TRANSFER, Icon: ArrowLeftRight },
]

const pillClass = (active: boolean) =>
  cn(
    "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors disabled:opacity-50",
    active
      ? "border-foreground bg-foreground text-background"
      : "border-border text-muted-foreground hover:text-foreground",
  )

interface RuleFormState {
  kind: LabelingRuleKind
  name: string
  enabled: boolean
  labelIds: string[]
  types: string[]
  textValue: string
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
  maxDays: string
}

const emptyForm = (): RuleFormState => ({
  kind: LabelingRuleKind.MATCH,
  name: "",
  enabled: true,
  labelIds: [],
  types: [],
  textValue: "",
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
  maxDays: `${DEFAULT_TRANSFER_MAX_DAYS}`,
})

const formFromRule = (rule: LabelingRule): RuleFormState => {
  const c = rule.conditions
  return {
    kind: rule.kind ?? LabelingRuleKind.MATCH,
    name: rule.name ?? "",
    enabled: rule.enabled,
    labelIds: rule.label_ids,
    types: c.types ?? [],
    textValue: c.text?.value ?? "",
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
    maxDays: `${c.max_days ?? DEFAULT_TRANSFER_MAX_DAYS}`,
  }
}

const formFromTx = (tx: LabelableTx): RuleFormState => {
  const counterparty = tx.counterparty?.trim()
  return {
    ...emptyForm(),
    name: counterparty || tx.name,
    labelIds: (tx.labels ?? []).map(label => label.label_id),
    types: [tx.type],
    textValue: counterparty || tx.name,
    textField: counterparty ? TextMatchField.COUNTERPARTY : TextMatchField.NAME,
  }
}

const parseOptionalNumber = (value: string): number | null => {
  if (!value.trim()) return null
  const parsed = Number.parseFloat(value.replace(",", "."))
  return Number.isFinite(parsed) ? parsed : null
}

const parseOptionalDay = (value: string): number | null => {
  const parsed = Number.parseInt(value, 10)
  return Number.isFinite(parsed) ? parsed : null
}

const buildConditions = (form: RuleFormState): LabelingRuleConditions => {
  const shared = {
    min_amount: parseOptionalNumber(form.minAmount),
    max_amount: parseOptionalNumber(form.maxAmount),
    currency: form.currency.trim() ? form.currency.trim().toUpperCase() : null,
    entities: form.entities.length ? form.entities : null,
    ibans: form.ibans.length ? form.ibans : null,
  }
  if (form.kind === LabelingRuleKind.TRANSFER) {
    return {
      ...shared,
      max_days: parseOptionalDay(form.maxDays) ?? DEFAULT_TRANSFER_MAX_DAYS,
    }
  }
  return {
    ...shared,
    types: form.types.length ? (form.types as TxType[]) : null,
    from_date: form.fromDate || null,
    to_date: form.toDate || null,
    day_from: parseOptionalDay(form.dayFrom),
    day_to: parseOptionalDay(form.dayTo),
    text: form.textValue.trim()
      ? {
          value: form.textValue.trim(),
          field: form.textField,
          operator: form.textOperator,
        }
      : null,
  }
}

const hasAnyCondition = (conditions: LabelingRuleConditions) =>
  Object.values(conditions).some(value => value !== null)

interface LabelingRuleDialogProps {
  isOpen: boolean
  rule: LabelingRule | null
  fromTx?: LabelableTx | null
  onClose: () => void
  onSaved: () => void
}

export function LabelingRuleDialog({
  isOpen,
  rule,
  fromTx,
  onClose,
  onSaved,
}: LabelingRuleDialogProps) {
  const { t, locale } = useI18n()
  const { entities, showToast, settings } = useAppContext()
  const { positionsData } = useFinancialData()
  const { labels } = useLabels()
  const [form, setForm] = useState<RuleFormState>(emptyForm)
  const [applyToExisting, setApplyToExisting] = useState(true)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [saving, setSaving] = useState(false)
  const [previewing, setPreviewing] = useState(false)
  const [preview, setPreview] = useState<LabelingRulePreview | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!isOpen) return
    const next = rule
      ? formFromRule(rule)
      : fromTx
        ? formFromTx(fromTx)
        : emptyForm()
    setForm(next)
    setApplyToExisting(true)
    setPreview(null)
    setError(null)
    setShowAdvanced(
      Boolean(
        next.minAmount ||
        next.maxAmount ||
        next.currency ||
        next.fromDate ||
        next.toDate ||
        next.dayFrom ||
        next.dayTo ||
        next.entities.length ||
        next.ibans.length,
      ),
    )
  }, [isOpen, rule, fromTx])

  const accountOptions = useMemo<MultiSelectOption[]>(() => {
    const options = new Map<string, MultiSelectOption>()
    Object.values(positionsData?.positions ?? {}).forEach(globalPositions =>
      globalPositions.forEach(position => {
        const accounts = position.products[ProductType.ACCOUNT] as
          Accounts | undefined
        accounts?.entries?.forEach(account => {
          const iban = account.iban?.replace(/\s+/g, "").toUpperCase()
          if (!iban || options.has(iban)) return
          const parts = [position.entity.name, account.name?.trim()]
          options.set(iban, {
            value: iban,
            label: [...parts.filter(Boolean), shortIban(iban)].join(" · "),
          })
        })
      }),
    )
    form.ibans.forEach(iban => {
      if (!options.has(iban)) {
        options.set(iban, { value: iban, label: shortIban(iban) })
      }
    })
    return [...options.values()]
  }, [positionsData, form.ibans])

  const entityOptions = useMemo(
    () =>
      (entities ?? []).filter(
        entity =>
          entity.type === EntityType.FINANCIAL_INSTITUTION ||
          entity.type === EntityType.CRYPTO_EXCHANGE,
      ),
    [entities],
  )

  const update = <K extends keyof RuleFormState>(
    key: K,
    value: RuleFormState[K],
  ) => {
    setForm(prev => ({ ...prev, [key]: value }))
    setPreview(null)
    setError(null)
  }

  const conditions = useMemo(() => buildConditions(form), [form])
  const isTransfer = form.kind === LabelingRuleKind.TRANSFER
  const canChooseKind = !rule && !fromTx

  const changeKind = (kind: LabelingRuleKind) => {
    if (kind === form.kind) return
    const transferLabel = labels.find(label => label.key === TRANSFER_LABEL_KEY)
    setForm(prev => ({
      ...prev,
      kind,
      labelIds:
        kind === LabelingRuleKind.TRANSFER &&
        !prev.labelIds.length &&
        transferLabel
          ? [transferLabel.id]
          : prev.labelIds,
    }))
    setPreview(null)
    setError(null)
  }

  const validate = (): boolean => {
    if (isTransfer) {
      const days = parseOptionalDay(form.maxDays)
      if (days !== null && (days < 0 || days > MAX_TRANSFER_MAX_DAYS)) {
        setError(t.labels.rules.invalidRule)
        return false
      }
      return true
    }
    if (!hasAnyCondition(conditions)) {
      setError(t.labels.rules.conditionRequired)
      return false
    }
    return true
  }

  const handlePreview = async () => {
    if (!validate()) return
    setPreviewing(true)
    try {
      setPreview(await previewLabelingRule(conditions, PREVIEW_LIMIT))
    } catch (err) {
      console.error("Error previewing rule:", err)
      setError(t.labels.rules.invalidRule)
    } finally {
      setPreviewing(false)
    }
  }

  const handleClose = () => {
    if (saving) return
    onClose()
  }

  const handleSave = async () => {
    if (!validate()) return
    if (!form.labelIds.length) {
      setError(t.labels.rules.labelRequired)
      return
    }
    setSaving(true)
    const request = {
      name: form.name.trim() || null,
      enabled: form.enabled,
      kind: form.kind,
      conditions,
      labels: form.labelIds,
      apply_to_existing: applyToExisting,
    }
    try {
      const saved = rule
        ? await updateLabelingRule(rule.id, request)
        : await createLabelingRule(request)
      showToast(
        applyToExisting
          ? t.labels.rules.savedApplied.replace("{count}", `${saved.applied}`)
          : t.labels.rules.saved,
        "success",
      )
      onSaved()
    } catch (err: any) {
      console.error("Error saving rule:", err)
      if (err?.data?.code === "INVALID_LABELING_RULE") {
        setError(t.labels.rules.invalidRule)
      } else {
        showToast(t.labels.saveError, "error")
      }
    } finally {
      setSaving(false)
    }
  }

  const accountsField = (
    <div className="space-y-1.5 sm:col-span-2">
      <FieldLabel className="block">{t.labels.rules.accounts}</FieldLabel>
      <MultiSelect
        options={accountOptions}
        value={form.ibans}
        onChange={value => update("ibans", value)}
        placeholder={t.labels.rules.anyAccount}
        disabled={saving}
      />
      <p className="text-xs text-muted-foreground">
        {isTransfer
          ? t.labels.rules.transferAccountsHint
          : t.labels.rules.accountsHint}
      </p>
    </div>
  )

  return (
    <LabelingModal
      isOpen={isOpen}
      title={rule ? t.labels.rules.editRule : t.labels.rules.newRule}
      onClose={handleClose}
      className="max-w-2xl"
      testId="rule-dialog"
      headerAction={
        <button
          type="button"
          role="switch"
          aria-checked={form.enabled}
          onClick={() => update("enabled", !form.enabled)}
          disabled={saving}
          data-testid="rule-enabled-toggle"
          className={cn(
            "inline-flex h-7 items-center gap-1.5 rounded-full border px-2.5 text-xs font-medium transition-colors disabled:opacity-50",
            form.enabled
              ? "border-green-500/40 bg-green-500/10 text-green-700 dark:text-green-400"
              : "border-border text-muted-foreground hover:text-foreground",
          )}
        >
          <span
            className={cn(
              "h-1.5 w-1.5 rounded-full",
              form.enabled ? "bg-green-500" : "bg-muted-foreground/60",
            )}
          />
          {form.enabled ? t.common.enabled : t.common.disabled}
        </button>
      }
      footer={
        <>
          {!isTransfer && (
            <Button
              variant="ghost"
              size="sm"
              className="mr-auto gap-1.5"
              onClick={handlePreview}
              disabled={saving || previewing}
            >
              <Eye className="h-4 w-4" />
              {t.labels.rules.preview}
            </Button>
          )}
          <Button
            variant="outline"
            onClick={handleClose}
            disabled={saving}
            aria-label={t.common.cancel}
            title={t.common.cancel}
            className="h-9 w-9 p-0"
          >
            <X className="h-4 w-4" />
          </Button>
          <Button
            onClick={handleSave}
            disabled={saving}
            aria-label={saving ? t.common.saving : t.common.save}
            title={saving ? t.common.saving : t.common.save}
            className="h-9 w-9 p-0"
          >
            {saving ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
          </Button>
        </>
      }
    >
      {canChooseKind ? (
        <div
          className="grid grid-cols-1 gap-2 sm:grid-cols-2"
          role="radiogroup"
          aria-label={t.labels.rules.kind}
        >
          {RULE_KINDS.map(({ kind, Icon }) => {
            const active = form.kind === kind
            return (
              <button
                key={kind}
                type="button"
                role="radio"
                aria-checked={active}
                onClick={() => changeKind(kind)}
                disabled={saving}
                data-testid={`rule-kind-${kind.toLowerCase()}`}
                className={cn(
                  "flex items-start gap-3 rounded-lg border p-3 text-left transition-colors disabled:opacity-50",
                  active
                    ? "border-foreground bg-muted/50"
                    : "border-border hover:bg-muted/30",
                )}
              >
                <span
                  className={cn(
                    "flex h-8 w-8 shrink-0 items-center justify-center rounded-md",
                    active
                      ? "bg-foreground text-background"
                      : "bg-muted text-muted-foreground",
                  )}
                >
                  <Icon className="h-4 w-4" />
                </span>
                <span className="min-w-0">
                  <span className="block text-sm font-medium">
                    {t.labels.rules.kinds[kind]}
                  </span>
                  <span className="block text-xs text-muted-foreground">
                    {t.labels.rules.kindHints[kind]}
                  </span>
                </span>
              </button>
            )
          })}
        </div>
      ) : (
        isTransfer && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <ArrowLeftRight className="h-4 w-4" />
            {t.labels.rules.kinds[LabelingRuleKind.TRANSFER]}
          </div>
        )
      )}

      <div className="space-y-1.5">
        <FieldLabel htmlFor="rule-name">{t.labels.rules.name}</FieldLabel>
        <Input
          id="rule-name"
          value={form.name}
          maxLength={100}
          placeholder={t.labels.rules.namePlaceholder}
          onChange={event => update("name", event.target.value)}
          disabled={saving}
        />
      </div>

      {isTransfer ? (
        <div className="space-y-4 border-t border-border pt-4">
          <div className="space-y-1">
            <h3 className="text-sm font-semibold">
              {t.labels.rules.transferWhen}
            </h3>
            <p className="text-xs text-muted-foreground">
              {t.labels.rules.transferExplanation}
            </p>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <FieldLabel htmlFor="rule-max-days">
                {t.labels.rules.maxDays}
              </FieldLabel>
              <Input
                id="rule-max-days"
                type="number"
                min={0}
                max={MAX_TRANSFER_MAX_DAYS}
                value={form.maxDays}
                onChange={event => update("maxDays", event.target.value)}
                disabled={saving}
                data-testid="rule-max-days"
              />
              <p className="text-xs text-muted-foreground">
                {t.labels.rules.maxDaysHint}
              </p>
            </div>
            <div className="space-y-1.5">
              <FieldLabel>{t.labels.rules.amount}</FieldLabel>
              <div className="flex items-center gap-2">
                <DecimalInput
                  value={form.minAmount}
                  onStringChange={value => update("minAmount", value)}
                  placeholder={t.labels.rules.min}
                  aria-label={t.labels.rules.minAmount}
                  disabled={saving}
                />
                <span className="text-muted-foreground">–</span>
                <DecimalInput
                  value={form.maxAmount}
                  onStringChange={value => update("maxAmount", value)}
                  placeholder={t.labels.rules.max}
                  aria-label={t.labels.rules.maxAmount}
                  disabled={saving}
                />
              </div>
            </div>
            <div className="space-y-1.5">
              <FieldLabel htmlFor="rule-currency">
                {t.transactions.currency}
              </FieldLabel>
              <Input
                id="rule-currency"
                value={form.currency}
                maxLength={10}
                placeholder={t.labels.rules.anyCurrency}
                onChange={event =>
                  update("currency", event.target.value.toUpperCase())
                }
                disabled={saving}
              />
            </div>
            <div className="space-y-1.5 sm:col-span-2">
              <FieldLabel className="block">
                {t.transactions.entities}
              </FieldLabel>
              <EntitySelector
                entities={entityOptions}
                selectedEntityIds={form.entities}
                onSelectionChange={value => update("entities", value)}
                disabled={saving}
                className="max-w-none"
              />
              <p className="text-xs text-muted-foreground">
                {t.labels.rules.transferEntitiesHint}
              </p>
            </div>
            {accountsField}
          </div>
        </div>
      ) : (
        <div className="space-y-4 border-t border-border pt-4">
          <h3 className="text-sm font-semibold">{t.labels.rules.when}</h3>

          <div className="space-y-2">
            <FieldLabel htmlFor="rule-text-value">
              {t.labels.rules.textValue}
            </FieldLabel>
            <div className="flex flex-col gap-2 sm:flex-row">
              <select
                aria-label={t.labels.rules.textOperator}
                value={form.textOperator}
                onChange={event =>
                  update(
                    "textOperator",
                    event.target.value as TextMatchOperator,
                  )
                }
                className={cn(SELECT_CLASS, "sm:w-48 sm:shrink-0")}
                disabled={saving}
              >
                {Object.values(TextMatchOperator).map(operator => (
                  <option key={operator} value={operator}>
                    {t.labels.rules.operators[operator]}
                  </option>
                ))}
              </select>
              <Input
                id="rule-text-value"
                data-testid="rule-text-value"
                value={form.textValue}
                maxLength={200}
                placeholder={t.labels.rules.textValuePlaceholder}
                onChange={event => update("textValue", event.target.value)}
                className={cn(
                  "flex-1",
                  form.textOperator === TextMatchOperator.REGEX && "font-mono",
                )}
                disabled={saving}
              />
            </div>
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
                  aria-checked={form.textField === field}
                  onClick={() => update("textField", field)}
                  disabled={saving}
                  className={pillClass(form.textField === field)}
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
                aria-pressed={form.types.length === 0}
                onClick={() => update("types", [])}
                disabled={saving}
                className={pillClass(form.types.length === 0)}
              >
                {t.labels.rules.anyType}
              </button>
              {LABELABLE_TX_TYPES.map(type => {
                const selected = form.types.includes(type)
                return (
                  <button
                    key={type}
                    type="button"
                    aria-pressed={selected}
                    onClick={() =>
                      update(
                        "types",
                        selected
                          ? form.types.filter(value => value !== type)
                          : [...form.types, type],
                      )
                    }
                    disabled={saving}
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

          {showAdvanced && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <FieldLabel>{t.labels.rules.amount}</FieldLabel>
                <div className="flex items-center gap-2">
                  <DecimalInput
                    value={form.minAmount}
                    onStringChange={value => update("minAmount", value)}
                    placeholder={t.labels.rules.min}
                    aria-label={t.labels.rules.minAmount}
                    disabled={saving}
                  />
                  <span className="text-muted-foreground">–</span>
                  <DecimalInput
                    value={form.maxAmount}
                    onStringChange={value => update("maxAmount", value)}
                    placeholder={t.labels.rules.max}
                    aria-label={t.labels.rules.maxAmount}
                    disabled={saving}
                  />
                </div>
              </div>
              <div className="space-y-1.5">
                <FieldLabel htmlFor="rule-currency">
                  {t.transactions.currency}
                </FieldLabel>
                <Input
                  id="rule-currency"
                  value={form.currency}
                  maxLength={10}
                  placeholder={t.labels.rules.anyCurrency}
                  onChange={event =>
                    update("currency", event.target.value.toUpperCase())
                  }
                  disabled={saving}
                />
              </div>
              <div className="space-y-1.5">
                <FieldLabel className="block">
                  {t.labels.rules.dateRange}
                </FieldLabel>
                <div className="flex items-center gap-2">
                  <div className="min-w-0 flex-1">
                    <DatePicker
                      value={form.fromDate}
                      onChange={value => update("fromDate", value)}
                      placeholder={t.transactions.fromDate}
                      disabled={saving}
                    />
                  </div>
                  <span className="text-muted-foreground">–</span>
                  <div className="min-w-0 flex-1">
                    <DatePicker
                      value={form.toDate}
                      onChange={value => update("toDate", value)}
                      placeholder={t.transactions.toDate}
                      disabled={saving}
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
                    value={form.dayFrom}
                    placeholder="1"
                    onChange={event => update("dayFrom", event.target.value)}
                    aria-label={t.labels.rules.dayFrom}
                    disabled={saving}
                  />
                  <span className="text-muted-foreground">–</span>
                  <Input
                    type="number"
                    min={1}
                    max={31}
                    value={form.dayTo}
                    placeholder="31"
                    onChange={event => update("dayTo", event.target.value)}
                    aria-label={t.labels.rules.dayTo}
                    disabled={saving}
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
                  selectedEntityIds={form.entities}
                  onSelectionChange={value => update("entities", value)}
                  disabled={saving}
                  className="max-w-none"
                />
              </div>
              {accountsField}
            </div>
          )}
        </div>
      )}

      <div className="space-y-2 border-t border-border pt-4">
        <h3 className="text-sm font-semibold">
          {isTransfer ? t.labels.rules.transferThen : t.labels.rules.then}
        </h3>
        <LabelSelector
          value={form.labelIds}
          onChange={value => update("labelIds", value)}
          disabled={saving}
        />
      </div>

      <div className="flex items-start justify-between gap-3 border-t border-border pt-4">
        <div>
          <div className="text-sm font-medium">
            {t.labels.rules.applyToExisting}
          </div>
          <p className="text-xs text-muted-foreground">
            {isTransfer
              ? t.labels.rules.transferApplyToExistingHint
              : t.labels.rules.applyToExistingHint}
          </p>
        </div>
        <Switch
          checked={applyToExisting}
          onCheckedChange={setApplyToExisting}
          disabled={saving}
        />
      </div>

      {error && (
        <p className="text-sm text-red-600 dark:text-red-400" role="alert">
          {error}
        </p>
      )}

      {preview && (
        <div
          className="space-y-2 rounded-md border border-border bg-muted/40 p-3"
          data-testid="rule-preview"
        >
          <div className="text-sm font-medium">
            {t.labels.rules.previewCount.replace("{count}", `${preview.count}`)}
          </div>
          {preview.samples.length > 0 && (
            <ul className="space-y-1">
              {preview.samples.map(sample => (
                <li
                  key={sample.id}
                  className="flex items-center justify-between gap-3 text-xs"
                >
                  <span className="min-w-0 truncate">
                    <span className="text-muted-foreground">
                      {formatDate(sample.date, locale)}
                    </span>{" "}
                    {sample.name}
                  </span>
                  <span className="shrink-0 font-medium">
                    {formatCurrency(
                      Math.abs(sample.amount),
                      locale,
                      settings.general.defaultCurrency,
                      sample.currency,
                    )}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </LabelingModal>
  )
}
