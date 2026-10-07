import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react"
import { useNavigate } from "react-router-dom"
import {
  ArrowLeftRight,
  ArrowRight,
  Pencil,
  Plus,
  RefreshCcw,
  Sparkles,
  Trash2,
  Wand2,
} from "lucide-react"
import { useI18n } from "@/i18n"
import { useAppContext } from "@/context/AppContext"
import { useLabels } from "@/context/LabelsContext"
import { useFinancialData } from "@/context/FinancialDataContext"
import { Button } from "@/components/ui/Button"
import { Card } from "@/components/ui/Card"
import { Switch } from "@/components/ui/Switch"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { ConfirmationDialog } from "@/components/ui/ConfirmationDialog"
import { EmptyState } from "@/components/ui/EmptyState"
import { LabelChip } from "@/components/labels/LabelChip"
import { LabelDialog } from "@/components/labels/LabelDialog"
import { LabelGallery } from "@/components/labels/LabelGallery"
import { LabelingRuleDialog } from "@/components/labels/LabelingRuleDialog"
import { RelabelDialog } from "@/components/labels/RelabelDialog"
import { ExternalLabelingCard } from "@/components/labels/ExternalLabelingCard"
import {
  deleteLabel,
  deleteLabelingRule,
  getLabelingRules,
  updateLabelingRule,
} from "@/services/api"
import { cn } from "@/lib/utils"
import { shortIban } from "@/lib/formatters"
import { ProductType, type Accounts } from "@/types/position"
import {
  LabelingRuleKind,
  type Label,
  type LabelingRule,
} from "@/types/labeling"

export type LabelsTab = "labels" | "rules" | "automation"

const EDGE_CARD =
  "-mx-6 rounded-none border-x-0 md:mx-0 md:rounded-lg md:border-x"

interface LabelsManagerProps {
  tab: LabelsTab
  onRulesCountChange?: (count: number) => void
  onActionChange?: (action: ReactNode | null) => void
}

export function LabelsManager({
  tab,
  onRulesCountChange,
  onActionChange,
}: LabelsManagerProps) {
  const { t } = useI18n()
  const navigate = useNavigate()
  const { showToast, entities } = useAppContext()
  const { positionsData } = useFinancialData()
  const { labels, loaded, getLabel, getLabelName, refreshLabels } = useLabels()

  const [rules, setRules] = useState<LabelingRule[]>([])
  const [rulesLoaded, setRulesLoaded] = useState(false)

  const [labelDialogOpen, setLabelDialogOpen] = useState(false)
  const [editingLabel, setEditingLabel] = useState<Label | null>(null)
  const [labelToDelete, setLabelToDelete] = useState<Label | null>(null)

  const [ruleDialogOpen, setRuleDialogOpen] = useState(false)
  const [editingRule, setEditingRule] = useState<LabelingRule | null>(null)
  const [ruleToDelete, setRuleToDelete] = useState<LabelingRule | null>(null)
  const [togglingRuleId, setTogglingRuleId] = useState<string | null>(null)

  const [relabelOpen, setRelabelOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const loadRules = useCallback(async () => {
    try {
      const response = await getLabelingRules()
      setRules(response.rules)
    } catch (error) {
      console.error("Error loading rules:", error)
      showToast(t.common.unexpectedError, "error")
    } finally {
      setRulesLoaded(true)
    }
  }, [showToast, t])

  useEffect(() => {
    void loadRules()
  }, [loadRules])

  useEffect(() => {
    if (rulesLoaded) onRulesCountChange?.(rules.length)
  }, [rulesLoaded, rules.length, onRulesCountChange])

  const entityNames = useMemo(
    () => new Map((entities ?? []).map(entity => [entity.id, entity.name])),
    [entities],
  )

  const accountNames = useMemo(() => {
    const names = new Map<string, string>()
    Object.values(positionsData?.positions ?? {}).forEach(globalPositions =>
      globalPositions.forEach(position => {
        const accounts = position.products[ProductType.ACCOUNT] as
          Accounts | undefined
        accounts?.entries?.forEach(account => {
          const iban = account.iban?.replace(/\s+/g, "").toUpperCase()
          const name = account.name?.trim()
          if (iban && name && !names.has(iban)) {
            names.set(iban, `${name} ${shortIban(iban)}`)
          }
        })
      }),
    )
    return names
  }, [positionsData])

  const describeRule = useCallback(
    (rule: LabelingRule): string[] => {
      const c = rule.conditions
      const parts: string[] = []
      if (rule.kind === LabelingRuleKind.TRANSFER) {
        const days = c.max_days ?? 3
        parts.push(
          days === 0
            ? t.labels.rules.sameDay
            : t.labels.rules.maxDaysSummary.replace("{days}", `${days}`),
        )
      }
      if (c.text) {
        parts.push(
          `${t.labels.rules.fields[c.text.field]} ${t.labels.rules.operators[c.text.operator].toLocaleLowerCase()} "${c.text.value}"`,
        )
      }
      if (c.types?.length) {
        parts.push(
          c.types
            .map(type => t.enums.transactionType[type] ?? type)
            .join(" / "),
        )
      }
      if (c.min_amount != null || c.max_amount != null) {
        parts.push(
          `${c.min_amount ?? "0"} – ${c.max_amount ?? "∞"}${c.currency ? ` ${c.currency}` : ""}`,
        )
      } else if (c.currency) {
        parts.push(c.currency)
      }
      if (c.day_from != null || c.day_to != null) {
        parts.push(
          t.labels.rules.daysSummary
            .replace("{from}", `${c.day_from ?? 1}`)
            .replace("{to}", `${c.day_to ?? 31}`),
        )
      }
      if (c.from_date || c.to_date) {
        parts.push(`${c.from_date ?? "…"} → ${c.to_date ?? "…"}`)
      }
      if (c.entities?.length) {
        parts.push(c.entities.map(id => entityNames.get(id) ?? id).join(", "))
      }
      if (c.ibans?.length) {
        parts.push(
          c.ibans
            .map(iban => accountNames.get(iban) ?? shortIban(iban))
            .join(", "),
        )
      }
      return parts
    },
    [t, entityNames, accountNames],
  )

  const openNewLabel = useCallback(() => {
    setEditingLabel(null)
    setLabelDialogOpen(true)
  }, [])

  const openEditLabel = (label: Label) => {
    setEditingLabel(label)
    setLabelDialogOpen(true)
  }

  const openNewRule = useCallback(() => {
    setEditingRule(null)
    setRuleDialogOpen(true)
  }, [])

  const openEditRule = (rule: LabelingRule) => {
    setEditingRule(rule)
    setRuleDialogOpen(true)
  }

  useEffect(() => {
    const action =
      tab === "labels" ? (
        <Button
          size="sm"
          className="h-8 w-8 gap-1.5 p-1 md:h-9 md:w-auto md:px-3 md:py-0"
          onClick={openNewLabel}
          aria-label={t.labels.newLabel}
          title={t.labels.newLabel}
        >
          <Plus className="h-4 w-4" />
          <span className="hidden md:inline">{t.labels.newLabel}</span>
        </Button>
      ) : tab === "rules" && rulesLoaded ? (
        <Button
          size="sm"
          className="h-8 w-8 gap-1.5 p-1 md:h-9 md:w-auto md:px-3 md:py-0"
          onClick={openNewRule}
          aria-label={t.labels.rules.newRule}
          title={t.labels.rules.newRule}
        >
          <Plus className="h-4 w-4" />
          <span className="hidden md:inline">{t.labels.rules.newRule}</span>
        </Button>
      ) : null

    onActionChange?.(action)
    return () => onActionChange?.(null)
  }, [
    onActionChange,
    openNewLabel,
    openNewRule,
    rulesLoaded,
    t.labels.newLabel,
    t.labels.rules.newRule,
    tab,
  ])

  const handleRuleSaved = async () => {
    setRuleDialogOpen(false)
    setEditingRule(null)
    await Promise.all([loadRules(), refreshLabels()])
  }

  const handleToggleRule = async (rule: LabelingRule, enabled: boolean) => {
    setTogglingRuleId(rule.id)
    try {
      await updateLabelingRule(rule.id, {
        name: rule.name ?? null,
        enabled,
        kind: rule.kind,
        conditions: rule.conditions,
        labels: rule.label_ids,
        apply_to_existing: enabled,
      })
      await Promise.all([loadRules(), refreshLabels()])
    } catch (error) {
      console.error("Error toggling rule:", error)
      showToast(t.labels.saveError, "error")
    } finally {
      setTogglingRuleId(null)
    }
  }

  const handleConfirmDeleteLabel = async () => {
    if (!labelToDelete) return
    setDeleting(true)
    try {
      await deleteLabel(labelToDelete.id)
      showToast(t.labels.labelDeleted, "success")
      setLabelToDelete(null)
      await Promise.all([refreshLabels(), loadRules()])
    } catch (error) {
      console.error("Error deleting label:", error)
      showToast(t.labels.deleteError, "error")
    } finally {
      setDeleting(false)
    }
  }

  const handleConfirmDeleteRule = async () => {
    if (!ruleToDelete) return
    setDeleting(true)
    try {
      await deleteLabelingRule(ruleToDelete.id)
      showToast(t.labels.rules.deleted, "success")
      setRuleToDelete(null)
      await Promise.all([loadRules(), refreshLabels()])
    } catch (error) {
      console.error("Error deleting rule:", error)
      showToast(t.labels.deleteError, "error")
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="space-y-4">
      {tab === "labels" && (
        <>
          {!loaded ? (
            <div className="flex justify-center py-10">
              <LoadingSpinner />
            </div>
          ) : (
            <LabelGallery
              labels={labels}
              getLabelName={getLabelName}
              onEdit={openEditLabel}
              onDelete={setLabelToDelete}
              onOpenMovements={label =>
                navigate(`/transactions?label=${label.id}`)
              }
            />
          )}
        </>
      )}

      {tab === "rules" && (
        <>
          {!rulesLoaded ? (
            <div className="flex justify-center py-10">
              <LoadingSpinner />
            </div>
          ) : rules.length === 0 ? (
            <Card className={EDGE_CARD}>
              <EmptyState
                icon={Wand2}
                title={t.labels.rules.emptyTitle}
                description={t.labels.rules.empty}
              />
            </Card>
          ) : (
            <div className="space-y-2">
              {rules.map(rule => {
                const isTransfer = rule.kind === LabelingRuleKind.TRANSFER
                const RuleIcon = isTransfer ? ArrowLeftRight : Wand2
                return (
                  <Card
                    key={rule.id}
                    className={cn(
                      EDGE_CARD,
                      "flex flex-col gap-3 p-4 transition-opacity sm:flex-row sm:items-center sm:justify-between",
                      !rule.enabled && "opacity-60",
                    )}
                    data-testid="rule-card"
                    data-kind={rule.kind}
                  >
                    <div className="flex min-w-0 items-center gap-3">
                      <div
                        className={cn(
                          "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg",
                          isTransfer
                            ? "bg-sky-500/10 text-sky-600 dark:text-sky-400"
                            : "bg-muted text-muted-foreground",
                        )}
                      >
                        <RuleIcon className="h-4 w-4" />
                      </div>
                      <div className="min-w-0 space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-sm font-medium">
                            {rule.name ||
                              (isTransfer
                                ? t.labels.rules.transferUnnamed
                                : t.labels.rules.unnamed)}
                          </span>
                          {isTransfer && (
                            <span className="rounded-full bg-sky-500/10 px-2 py-0.5 text-[11px] font-medium text-sky-700 dark:text-sky-300">
                              {t.labels.rules.kinds[LabelingRuleKind.TRANSFER]}
                            </span>
                          )}
                        </div>
                        <div className="flex flex-wrap items-center gap-1.5">
                          {describeRule(rule).map((part, index) => (
                            <span
                              key={`${rule.id}-${index}`}
                              className="rounded-md border border-border px-1.5 py-0.5 text-xs text-muted-foreground"
                            >
                              {part}
                            </span>
                          ))}
                          <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" />
                          {rule.label_ids.map(labelId => {
                            const label = getLabel(labelId)
                            if (!label) return null
                            return (
                              <LabelChip
                                key={labelId}
                                label={label}
                                name={getLabelName(label)}
                              />
                            )
                          })}
                        </div>
                      </div>
                    </div>
                    <div className="flex w-full shrink-0 items-center justify-center gap-1 self-center border-t border-dotted border-border pt-2 sm:w-auto sm:self-auto sm:gap-2 sm:border-t-0 sm:pt-0">
                      <Switch
                        checked={rule.enabled}
                        onCheckedChange={value => handleToggleRule(rule, value)}
                        disabled={togglingRuleId === rule.id}
                        size="responsive"
                        aria-label={t.common.enabled}
                      />
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 sm:h-8 sm:w-8"
                        onClick={() => openEditRule(rule)}
                        aria-label={t.common.edit}
                      >
                        <Pencil className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-red-600 hover:text-red-700 dark:text-red-400 sm:h-8 sm:w-8"
                        onClick={() => setRuleToDelete(rule)}
                        aria-label={t.common.delete}
                      >
                        <Trash2 className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
                      </Button>
                    </div>
                  </Card>
                )
              })}
            </div>
          )}
        </>
      )}

      {tab === "automation" && (
        <div className="space-y-8">
          <section className="space-y-3">
            <div className="flex items-center gap-2">
              <Wand2 className="h-4 w-4 text-muted-foreground" />
              <h2 className="text-sm font-semibold">
                {t.labels.automation.rulesTitle}
              </h2>
            </div>
            <Card className={cn(EDGE_CARD, "divide-y divide-border")}>
              <div className="flex items-start justify-between gap-4 p-4">
                <div className="min-w-0">
                  <div className="text-sm font-medium">
                    {t.labels.automation.rulesAlwaysOn}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {t.labels.automation.rulesAlwaysOnHint}
                  </p>
                </div>
                <span className="shrink-0 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800 dark:bg-green-900/30 dark:text-green-300">
                  {t.labels.automation.alwaysOn}
                </span>
              </div>
              <div className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <div className="text-sm font-medium">
                    {t.labels.relabel.title}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {t.labels.relabel.description}
                  </p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  className="shrink-0 gap-1.5"
                  onClick={() => setRelabelOpen(true)}
                >
                  <RefreshCcw className="h-4 w-4" />
                  {t.labels.relabel.open}
                </Button>
              </div>
            </Card>
          </section>

          <section className="space-y-3">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-fuchsia-500" />
              <h2 className="text-sm font-semibold">
                {t.labels.external.title}
              </h2>
              <span className="rounded-full border border-border px-2 py-0.5 text-[11px] text-muted-foreground">
                {t.labels.automation.optional}
              </span>
            </div>
            <ExternalLabelingCard className={EDGE_CARD} />
          </section>
        </div>
      )}

      <LabelDialog
        isOpen={labelDialogOpen}
        label={editingLabel}
        onClose={() => {
          setLabelDialogOpen(false)
          setEditingLabel(null)
        }}
      />

      <LabelingRuleDialog
        isOpen={ruleDialogOpen}
        rule={editingRule}
        onClose={() => {
          setRuleDialogOpen(false)
          setEditingRule(null)
        }}
        onSaved={handleRuleSaved}
      />

      <RelabelDialog
        isOpen={relabelOpen}
        onClose={() => setRelabelOpen(false)}
        onDone={() => void refreshLabels()}
      />

      <ConfirmationDialog
        isOpen={labelToDelete !== null}
        title={t.labels.deleteLabelTitle}
        message={t.labels.deleteLabelMessage.replace(
          "{name}",
          getLabelName(labelToDelete ?? undefined),
        )}
        warning={t.labels.deleteLabelWarning}
        confirmText={t.common.delete}
        cancelText={t.common.cancel}
        onConfirm={handleConfirmDeleteLabel}
        onCancel={() => !deleting && setLabelToDelete(null)}
        isLoading={deleting}
      />

      <ConfirmationDialog
        isOpen={ruleToDelete !== null}
        title={t.labels.rules.deleteTitle}
        message={t.labels.rules.deleteMessage}
        confirmText={t.common.delete}
        cancelText={t.common.cancel}
        onConfirm={handleConfirmDeleteRule}
        onCancel={() => !deleting && setRuleToDelete(null)}
        isLoading={deleting}
      />
    </div>
  )
}
