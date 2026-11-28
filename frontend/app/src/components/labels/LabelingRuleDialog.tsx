import { useEffect, useMemo, useState } from "react"
import { AnimatePresence, motion, useReducedMotion } from "framer-motion"
import {
  ArrowLeftRight,
  Eye,
  Loader2,
  Plus,
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
import { type MultiSelectOption } from "@/components/ui/MultiSelect"
import { EntitySelector } from "@/components/EntitySelector"
import {
  createLabelingRule,
  previewLabelingRule,
  updateLabelingRule,
} from "@/services/api"
import { formatCurrency, formatDate, shortIban } from "@/lib/formatters"
import { cn } from "@/lib/utils"
import { ProductType, type Accounts } from "@/types/position"
import {
  LabelingRuleKind,
  MAX_CONDITION_GROUPS,
  MAX_TEXT_VALUES,
  type LabelingRule,
  type LabelingRulePreview,
} from "@/types/labeling"
import { LabelingModal } from "./LabelingModal"
import { LabelSelector } from "./LabelSelector"
import {
  RuleAccountsField,
  RuleConditionGroupFields,
} from "./RuleConditionGroupFields"
import {
  MAX_TRANSFER_MAX_DAYS,
  buildConditions,
  emptyForm,
  emptyGroup,
  formFromRule,
  formFromTx,
  hasAnyCondition,
  parseOptionalDay,
  type ConditionGroupForm,
  type RuleFormState,
} from "./ruleForm"
import type { LabelableTx } from "./TransactionLabelsDialog"

const PREVIEW_LIMIT = 10
const TRANSFER_LABEL_KEY = "internal_transfer"

const RULE_KINDS = [
  { kind: LabelingRuleKind.MATCH, Icon: Wand2 },
  { kind: LabelingRuleKind.TRANSFER, Icon: ArrowLeftRight },
]

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
  const reducedMotion = useReducedMotion()
  const [form, setForm] = useState<RuleFormState>(emptyForm)
  const [formVersion, setFormVersion] = useState(0)
  const [applyToExisting, setApplyToExisting] = useState(true)
  const [addedGroupKey, setAddedGroupKey] = useState<string | null>(null)
  const [focusedGroupKey, setFocusedGroupKey] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [previewing, setPreviewing] = useState(false)
  const [preview, setPreview] = useState<LabelingRulePreview | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!isOpen) return
    setForm(
      rule ? formFromRule(rule) : fromTx ? formFromTx(fromTx) : emptyForm(),
    )
    setFormVersion(version => version + 1)
    setApplyToExisting(true)
    setAddedGroupKey(null)
    setFocusedGroupKey(null)
    setPreview(null)
    setError(null)
  }, [isOpen, rule, fromTx])

  const selectedIbans = useMemo(
    () => form.groups.flatMap(group => group.ibans),
    [form.groups],
  )

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
    selectedIbans.forEach(iban => {
      if (!options.has(iban)) {
        options.set(iban, { value: iban, label: shortIban(iban) })
      }
    })
    return [...options.values()]
  }, [positionsData, selectedIbans])

  const entityOptions = useMemo(
    () =>
      entities?.filter(
        entity =>
          "TRANSACTIONS" in entity.last_fetch ||
          "TRANSACTIONS" in entity.virtual_features,
      ) || [],
    [entities],
  )

  const resetFeedback = () => {
    setPreview(null)
    setError(null)
  }

  const update = <K extends keyof RuleFormState>(
    key: K,
    value: RuleFormState[K],
  ) => {
    setForm(prev => ({ ...prev, [key]: value }))
    resetFeedback()
  }

  const updateGroup = (key: string, patch: Partial<ConditionGroupForm>) => {
    setForm(prev => ({
      ...prev,
      groups: prev.groups.map(group =>
        group.key === key ? { ...group, ...patch } : group,
      ),
    }))
    resetFeedback()
  }

  const addGroup = () => {
    const group = emptyGroup()
    setForm(prev =>
      prev.groups.length >= MAX_CONDITION_GROUPS
        ? prev
        : { ...prev, groups: [...prev.groups, group] },
    )
    setAddedGroupKey(group.key)
    resetFeedback()
  }

  const removeGroup = (key: string) => {
    setForm(prev =>
      prev.groups.length <= 1
        ? prev
        : { ...prev, groups: prev.groups.filter(group => group.key !== key) },
    )
    resetFeedback()
  }

  const conditions = useMemo(() => buildConditions(form), [form])
  const isTransfer = form.kind === LabelingRuleKind.TRANSFER
  const canChooseKind = !rule && !fromTx
  const primaryGroup = form.groups[0]
  const hasAlternatives = form.groups.length > 1
  const canAddGroup = form.groups.length < MAX_CONDITION_GROUPS

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
    resetFeedback()
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
    const emptyIndex = conditions.findIndex(group => !hasAnyCondition(group))
    if (emptyIndex >= 0) {
      setError(
        conditions.length === 1
          ? t.labels.rules.conditionRequired
          : t.labels.rules.alternativeConditionRequired.replace(
              "{index}",
              `${emptyIndex + 1}`,
            ),
      )
      return false
    }
    if (
      conditions.some(
        group => (group.text?.values.length ?? 0) > MAX_TEXT_VALUES,
      )
    ) {
      setError(
        t.labels.rules.maxTextValues.replace("{max}", `${MAX_TEXT_VALUES}`),
      )
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
                  value={primaryGroup.minAmount}
                  onStringChange={minAmount =>
                    updateGroup(primaryGroup.key, { minAmount })
                  }
                  placeholder={t.labels.rules.min}
                  aria-label={t.labels.rules.minAmount}
                  disabled={saving}
                />
                <span className="text-muted-foreground">–</span>
                <DecimalInput
                  value={primaryGroup.maxAmount}
                  onStringChange={maxAmount =>
                    updateGroup(primaryGroup.key, { maxAmount })
                  }
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
                value={primaryGroup.currency}
                maxLength={10}
                placeholder={t.labels.rules.anyCurrency}
                onChange={event =>
                  updateGroup(primaryGroup.key, {
                    currency: event.target.value.toUpperCase(),
                  })
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
                selectedEntityIds={primaryGroup.entities}
                onSelectionChange={entities =>
                  updateGroup(primaryGroup.key, { entities })
                }
                disabled={saving}
                className="max-w-none"
              />
              <p className="text-xs text-muted-foreground">
                {t.labels.rules.transferEntitiesHint}
              </p>
            </div>
            <RuleAccountsField
              value={primaryGroup.ibans}
              onChange={ibans => updateGroup(primaryGroup.key, { ibans })}
              options={accountOptions}
              hint={t.labels.rules.transferAccountsHint}
              disabled={saving}
            />
          </div>
        </div>
      ) : (
        <div className="space-y-4 border-t border-border pt-4">
          <div className="space-y-1">
            <h3 className="text-sm font-semibold">{t.labels.rules.when}</h3>
            {hasAlternatives && (
              <p className="text-xs text-muted-foreground">
                {t.labels.rules.alternativesHint}
              </p>
            )}
          </div>

          <div key={formVersion}>
            <AnimatePresence initial={false}>
              {form.groups.map((group, index) => (
                <motion.div
                  key={group.key}
                  initial={{ height: 0, opacity: 0, overflow: "hidden" }}
                  animate={{
                    height: "auto",
                    opacity: 1,
                    overflow: "hidden",
                    transitionEnd: { overflow: "visible" },
                  }}
                  exit={{ height: 0, opacity: 0, overflow: "hidden" }}
                  transition={{
                    duration: reducedMotion ? 0 : 0.22,
                    ease: "easeInOut",
                  }}
                  onAnimationComplete={() => {
                    if (group.key === addedGroupKey) {
                      setFocusedGroupKey(group.key)
                    }
                  }}
                >
                  <div className={cn("space-y-4", index > 0 && "pt-4")}>
                    {index > 0 && (
                      <div
                        className="flex items-center gap-3"
                        data-testid="rule-or-divider"
                      >
                        <div className="h-px flex-1 bg-border" />
                        <span className="rounded-full border border-border bg-muted px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                          {t.labels.rules.or}
                        </span>
                        <div className="h-px flex-1 bg-border" />
                      </div>
                    )}
                    <div
                      data-testid="rule-condition-group"
                      className={cn(
                        hasAlternatives &&
                          "space-y-3 sm:rounded-lg sm:border sm:border-border sm:p-4",
                      )}
                    >
                      {hasAlternatives && (
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                            {t.labels.rules.alternative.replace(
                              "{index}",
                              `${index + 1}`,
                            )}
                          </span>
                          <button
                            type="button"
                            onClick={() => removeGroup(group.key)}
                            disabled={saving}
                            aria-label={t.labels.rules.removeAlternative.replace(
                              "{index}",
                              `${index + 1}`,
                            )}
                            title={t.labels.rules.removeAlternative.replace(
                              "{index}",
                              `${index + 1}`,
                            )}
                            className="-mr-1.5 inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-50"
                          >
                            <X className="h-4 w-4" />
                          </button>
                        </div>
                      )}
                      <RuleConditionGroupFields
                        group={group}
                        onChange={patch => updateGroup(group.key, patch)}
                        entityOptions={entityOptions}
                        accountOptions={accountOptions}
                        disabled={saving}
                        focusText={group.key === focusedGroupKey}
                      />
                    </div>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={addGroup}
              disabled={saving || !canAddGroup}
              data-testid="rule-add-alternative"
              className="inline-flex items-center gap-1.5 rounded-full border border-dashed border-border px-3 py-1 text-xs font-medium text-muted-foreground transition-colors hover:border-foreground/40 hover:text-foreground disabled:pointer-events-none disabled:opacity-50"
            >
              <Plus className="h-3.5 w-3.5" />
              {t.labels.rules.addAlternative}
            </button>
            {!canAddGroup && (
              <span className="text-xs text-muted-foreground">
                {t.labels.rules.maxAlternatives.replace(
                  "{max}",
                  `${MAX_CONDITION_GROUPS}`,
                )}
              </span>
            )}
          </div>
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
