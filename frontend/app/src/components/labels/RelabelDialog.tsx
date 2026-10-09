import { useEffect, useMemo, useState } from "react"
import { Calculator, RefreshCcw, X } from "lucide-react"
import { useI18n } from "@/i18n"
import { useAppContext } from "@/context/AppContext"
import { Button } from "@/components/ui/Button"
import { Label as FieldLabel } from "@/components/ui/Label"
import { Switch } from "@/components/ui/Switch"
import { DatePicker } from "@/components/ui/DatePicker"
import { MultiSelect } from "@/components/ui/MultiSelect"
import { EntitySelector } from "@/components/EntitySelector"
import { relabelTransactions } from "@/services/api"
import { cn } from "@/lib/utils"
import { EntityType } from "@/types"
import { LabelOrigin } from "@/types/transactions"
import type { RelabelRequest, RelabelResult } from "@/types/labeling"
import { LabelingModal } from "./LabelingModal"
import { useLabelOptions } from "./TransactionLabels"
import {
  ExternalSuggestionsIcon,
  ExternalSuggestionsSurface,
} from "./ExternalSuggestionsSurface"

const DEFAULT_ORIGINS = [LabelOrigin.EXTERNAL]

export interface RelabelInitialFilters {
  from_date?: string
  to_date?: string
  entities?: string[]
  with_labels?: string[]
  unlabeled_only?: boolean
}

interface RelabelDialogProps {
  isOpen: boolean
  initial?: RelabelInitialFilters | null
  onClose: () => void
  onDone?: () => void
}

export function RelabelDialog({
  isOpen,
  initial,
  onClose,
  onDone,
}: RelabelDialogProps) {
  const { t } = useI18n()
  const { entities, settings, showToast, externalIntegrations } =
    useAppContext()
  const labelOptions = useLabelOptions()
  const externalSettings = settings.labeling?.external
  const externalEnabled = Boolean(externalSettings?.enabled)
  const externalAutoRun = Boolean(externalSettings?.autoRun)
  const externalProvider = externalSettings?.provider ?? ""
  const externalProviderName =
    externalIntegrations.find(
      integration => integration.id === externalProvider,
    )?.name ?? externalProvider

  const [fromDate, setFromDate] = useState("")
  const [toDate, setToDate] = useState("")
  const [entityIds, setEntityIds] = useState<string[]>([])
  const [withLabels, setWithLabels] = useState<string[]>([])
  const [withoutLabels, setWithoutLabels] = useState<string[]>([])
  const [unlabeledOnly, setUnlabeledOnly] = useState(false)
  const [origins, setOrigins] = useState<LabelOrigin[]>(DEFAULT_ORIGINS)
  const [includeExternal, setIncludeExternal] = useState(false)
  const [retryUnmatched, setRetryUnmatched] = useState(false)
  const [matched, setMatched] = useState<number | null>(null)
  const [result, setResult] = useState<RelabelResult | null>(null)
  const [running, setRunning] = useState(false)

  useEffect(() => {
    if (!isOpen) return
    setFromDate(initial?.from_date ?? "")
    setToDate(initial?.to_date ?? "")
    setEntityIds(initial?.entities ?? [])
    setWithLabels(initial?.with_labels ?? [])
    setWithoutLabels([])
    setUnlabeledOnly(initial?.unlabeled_only ?? !initial?.with_labels?.length)
    setOrigins(DEFAULT_ORIGINS)
    setIncludeExternal(externalAutoRun)
    setRetryUnmatched(false)
    setMatched(null)
    setResult(null)
  }, [isOpen, initial, externalAutoRun])

  const entityOptions = useMemo(
    () =>
      (entities ?? []).filter(
        entity =>
          entity.type === EntityType.FINANCIAL_INSTITUTION ||
          entity.type === EntityType.CRYPTO_EXCHANGE,
      ),
    [entities],
  )

  const resetOutcome = () => {
    setMatched(null)
    setResult(null)
  }

  const buildRequest = (dryRun: boolean): RelabelRequest => ({
    from_date: fromDate || undefined,
    to_date: toDate || undefined,
    entities: entityIds.length ? entityIds : undefined,
    with_labels: withLabels.length ? withLabels : undefined,
    without_labels: withoutLabels.length ? withoutLabels : undefined,
    unlabeled_only: unlabeledOnly,
    origins: origins.length ? origins : DEFAULT_ORIGINS,
    include_external: externalEnabled && includeExternal,
    retry_external_unmatched:
      externalEnabled && includeExternal && retryUnmatched,
    dry_run: dryRun,
  })

  const handleCount = async () => {
    setRunning(true)
    try {
      const response = await relabelTransactions(buildRequest(true))
      setMatched(response.matched)
      setResult(null)
    } catch (error) {
      console.error("Error counting relabel matches:", error)
      showToast(t.common.unexpectedError, "error")
    } finally {
      setRunning(false)
    }
  }

  const handleRun = async () => {
    setRunning(true)
    try {
      const response = await relabelTransactions(buildRequest(false))
      setMatched(response.matched)
      setResult(response)
      const externalError =
        response.external?.external_error_details ||
        response.external?.external_error
      if (externalError) {
        showToast(
          `${t.labels.relabel.externalFailed}: ${externalError}`,
          "warning",
        )
      } else {
        showToast(t.labels.relabel.done, "success")
      }
      onDone?.()
    } catch (error) {
      console.error("Error relabeling transactions:", error)
      showToast(t.common.unexpectedError, "error")
    } finally {
      setRunning(false)
    }
  }

  const toggleOrigin = (origin: LabelOrigin) => {
    resetOutcome()
    setOrigins(prev =>
      prev.includes(origin)
        ? prev.filter(value => value !== origin)
        : [...prev, origin],
    )
  }

  const handleClose = () => {
    if (running) return
    onClose()
  }

  const ruleLabeled = result?.result?.rule_labeled ?? 0
  const externalLabeled = result?.external?.external_labeled ?? 0

  return (
    <LabelingModal
      isOpen={isOpen}
      title={t.labels.relabel.title}
      description={t.labels.relabel.description}
      onClose={handleClose}
      className="max-w-2xl"
      testId="relabel-dialog"
      footer={
        <>
          <Button
            variant="outline"
            size="sm"
            className="mr-auto gap-1.5"
            onClick={handleCount}
            disabled={running}
          >
            <Calculator className="h-4 w-4" />
            {t.labels.relabel.count}
          </Button>
          <Button
            variant="outline"
            onClick={handleClose}
            disabled={running}
            aria-label={t.common.close}
            title={t.common.close}
            className="h-9 w-9 p-0"
          >
            <X className="h-4 w-4" />
          </Button>
          <Button
            size="sm"
            className="gap-1.5"
            onClick={handleRun}
            disabled={running}
          >
            <RefreshCcw className={cn("h-4 w-4", running && "animate-spin")} />
            {t.labels.relabel.run}
          </Button>
        </>
      }
    >
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <FieldLabel>{t.transactions.fromDate}</FieldLabel>
          <DatePicker
            value={fromDate}
            onChange={value => {
              setFromDate(value)
              resetOutcome()
            }}
            placeholder={t.transactions.fromDate}
          />
        </div>
        <div className="space-y-1.5">
          <FieldLabel>{t.transactions.toDate}</FieldLabel>
          <DatePicker
            value={toDate}
            onChange={value => {
              setToDate(value)
              resetOutcome()
            }}
            placeholder={t.transactions.toDate}
          />
        </div>
        <div className="space-y-1.5 sm:col-span-2">
          <FieldLabel className="block">{t.transactions.entities}</FieldLabel>
          <EntitySelector
            entities={entityOptions}
            selectedEntityIds={entityIds}
            onSelectionChange={value => {
              setEntityIds(value)
              resetOutcome()
            }}
            className="max-w-none"
          />
        </div>
        <div className="space-y-1.5">
          <FieldLabel>{t.labels.relabel.withLabels}</FieldLabel>
          <MultiSelect
            options={labelOptions}
            value={withLabels}
            onChange={value => {
              setWithLabels(value)
              resetOutcome()
            }}
            placeholder={t.labels.anyLabel}
            disabled={unlabeledOnly}
          />
        </div>
        <div className="space-y-1.5">
          <FieldLabel>{t.labels.relabel.withoutLabels}</FieldLabel>
          <MultiSelect
            options={labelOptions}
            value={withoutLabels}
            onChange={value => {
              setWithoutLabels(value)
              resetOutcome()
            }}
            placeholder={t.labels.anyLabel}
            disabled={unlabeledOnly}
          />
        </div>
      </div>

      <div className="flex items-center justify-between gap-3">
        <span className="text-sm font-medium">
          {t.labels.relabel.unlabeledOnly}
        </span>
        <Switch
          checked={unlabeledOnly}
          onCheckedChange={value => {
            setUnlabeledOnly(value)
            resetOutcome()
          }}
        />
      </div>

      {!unlabeledOnly && (
        <div className="space-y-1.5">
          <div className="text-sm font-medium">{t.labels.relabel.replace}</div>
          <div className="flex flex-wrap gap-2">
            {Object.values(LabelOrigin).map(origin => (
              <button
                key={origin}
                type="button"
                aria-pressed={origins.includes(origin)}
                onClick={() => toggleOrigin(origin)}
                className={cn(
                  "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                  origins.includes(origin)
                    ? "border-foreground bg-foreground text-background"
                    : "border-border text-muted-foreground hover:text-foreground",
                )}
              >
                {t.labels.origins[origin]}
              </button>
            ))}
          </div>
          <p className="text-xs text-muted-foreground">
            {t.labels.relabel.lockedHint}
          </p>
        </div>
      )}

      {externalEnabled && (
        <ExternalSuggestionsSurface
          className="-mx-4 rounded-none border-x-0 px-4 py-3 sm:-mx-6 sm:px-6"
          data-testid="relabel-external"
        >
          <div className="flex items-start gap-3">
            <button
              type="button"
              onClick={() => setIncludeExternal(value => !value)}
              aria-pressed={includeExternal}
              disabled={running}
              className="flex min-w-0 flex-1 items-start gap-3 rounded-md text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <ExternalSuggestionsIcon className="hidden h-9 w-9 sm:flex" />
              <span className="min-w-0 flex-1 space-y-0.5">
                <span className="block text-sm font-medium">
                  {t.labels.relabel.includeExternal.replace(
                    "{provider}",
                    externalProviderName,
                  )}
                </span>
                <span className="block text-xs text-muted-foreground">
                  {t.labels.relabel.includeExternalHint.replace(
                    "{provider}",
                    externalProviderName,
                  )}
                </span>
                {externalSettings?.model && (
                  <span className="block truncate font-mono text-[11px] text-violet-700 dark:text-violet-300">
                    {externalSettings.model}
                  </span>
                )}
              </span>
            </button>
            <Switch
              checked={includeExternal}
              onCheckedChange={setIncludeExternal}
              disabled={running}
              data-testid="relabel-external-switch"
            />
          </div>
          {includeExternal && (
            <div className="mt-3 flex items-center justify-between gap-3 sm:pl-12">
              <span className="space-y-0.5">
                <span className="block text-sm">
                  {t.labels.relabel.retryUnmatched.replace(
                    "{provider}",
                    externalProviderName,
                  )}
                </span>
                <span className="block text-xs text-muted-foreground">
                  {t.labels.relabel.retryUnmatchedHint}
                </span>
              </span>
              <Switch
                checked={retryUnmatched}
                onCheckedChange={setRetryUnmatched}
                disabled={running}
                data-testid="relabel-retry-unmatched-switch"
              />
            </div>
          )}
        </ExternalSuggestionsSurface>
      )}

      {matched !== null && (
        <div
          className="rounded-md border border-border bg-muted/40 p-3 text-sm"
          data-testid="relabel-outcome"
        >
          <div className="font-medium">
            {t.labels.relabel.matched.replace("{count}", `${matched}`)}
          </div>
          {result && (
            <div className="mt-1 text-xs text-muted-foreground">
              {t.labels.relabel.summary
                .replace("{rules}", `${ruleLabeled}`)
                .replace("{external}", `${externalLabeled}`)}
            </div>
          )}
        </div>
      )}
    </LabelingModal>
  )
}
