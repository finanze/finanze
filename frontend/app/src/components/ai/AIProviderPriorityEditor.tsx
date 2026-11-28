import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import type { ReactNode } from "react"
import { useNavigate } from "react-router-dom"
import { Reorder, useDragControls } from "framer-motion"
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  Check,
  CheckCircle2,
  ChevronDown,
  Coins,
  ExternalLink,
  FileText,
  GripVertical,
  HardDrive,
  Image as ImageIcon,
  Info,
  PenLine,
  Plus,
  Search,
  Settings2,
  Sparkles,
  Trash2,
  XCircle,
} from "lucide-react"
import { useI18n } from "@/i18n"
import { useAppContext } from "@/context/AppContext"
import { AdaptiveLogo } from "@/components/ui/AdaptiveLogo"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { Label as FieldLabel } from "@/components/ui/Label"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover"
import { Badge } from "@/components/ui/Badge"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { LocalModelsManagerDialog } from "@/components/settings/LocalModelsDialog"
import { getAIModels, getAIProviders, validateAIModel } from "@/services/api"
import { ExternalIntegrationStatus, ExternalIntegrationType } from "@/types"
import { cn } from "@/lib/utils"
import { formatCurrency } from "@/lib/formatters"
import { formatFileSize } from "@/utils/releaseUtils"
import {
  externalProviderState,
  resolveAIProvider,
} from "@/lib/externalLabeling"
import {
  getIntegrationFamilyName,
  getIntegrationMethodName,
  getIntegrationName,
} from "@/lib/integrations"
import {
  AIInputModality,
  AITask,
  MAX_AI_PROVIDERS,
  type AICatalogModel,
  type AIProviderDetails,
  type AIProviderEntry,
} from "@/types/ai"

const CUSTOM_MODEL = "__custom__"
const LOCAL_MODELS_PROVIDER = "LOCAL_MODELS"
const SMALL_MODEL_SIZE = 2_000_000_000
const MODEL_SEARCH_THRESHOLD = 6

export const aiEntryKey = (entry: AIProviderEntry) =>
  JSON.stringify([entry.provider, entry.model, entry.upstreamProvider || null])

export const hasDuplicateAIEntries = (entries: AIProviderEntry[]) =>
  new Set(entries.map(aiEntryKey)).size !== entries.length

export const normalizeAIEntries = (
  entries: AIProviderEntry[],
): AIProviderEntry[] =>
  entries.map(entry => ({
    provider: entry.provider,
    model: entry.model.trim(),
    upstreamProvider: entry.upstreamProvider?.trim() || null,
  }))

export interface AIProviderEditorNotices {
  priority: string
  customModel: string
  privacy?: string
  smallModel?: string
}

const formatTokenPrice = (value: number, currency: string, locale: string) =>
  formatCurrency(value, locale, currency, undefined, {
    narrowSymbol: true,
    maximumFractionDigits: 3,
  })

function ProviderLogo({ id, name }: { id: string; name: string }) {
  return (
    <AdaptiveLogo
      src={`icons/external-integrations/${id}.png`}
      alt={name}
      className="flex h-5 w-5 flex-shrink-0 items-center justify-center overflow-hidden rounded"
      imgClassName="h-5 w-5 object-contain"
      lightBgClassName="bg-white p-0.5"
    />
  )
}

function RadioMark({ checked }: { checked: boolean }) {
  return (
    <span
      aria-hidden
      className={cn(
        "mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border transition-colors",
        checked
          ? "border-violet-500 bg-violet-500 text-white"
          : "border-muted-foreground/40 bg-background",
      )}
    >
      <Check
        className={cn("h-2.5 w-2.5", !checked && "invisible")}
        strokeWidth={3.5}
      />
    </span>
  )
}

function ModelChip({
  className,
  title,
  children,
}: {
  className: string
  title?: string
  children: ReactNode
}) {
  return (
    <span
      title={title}
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-1.5 py-0.5 text-[10px] font-medium leading-none",
        className,
      )}
    >
      {children}
    </span>
  )
}

function PriorityRow({
  entry,
  index,
  value,
  name,
  state,
  selected,
  disabled,
  first,
  last,
  testId,
  edit,
  remove,
  move,
}: {
  entry: AIProviderEntry
  index: number
  value: string
  name: string
  state: string
  selected: boolean
  disabled: boolean
  first: boolean
  last: boolean
  testId: string
  edit: () => void
  remove: () => void
  move: (direction: number) => void
}) {
  const { t } = useI18n()
  const controls = useDragControls()
  const copy = t.labels.external
  return (
    <Reorder.Item
      value={value}
      dragListener={false}
      dragControls={controls}
      className={cn(
        "relative flex min-h-16 items-center gap-1 rounded-md border border-border/60 p-2 sm:p-3",
        selected && "bg-accent/40",
      )}
      whileDrag={{ zIndex: 10 }}
      data-testid={testId}
    >
      <Button
        variant="ghost"
        size="icon"
        className="h-10 w-8 shrink-0 touch-none cursor-grab"
        disabled={disabled}
        aria-label={copy.reorderProvider.replace("{provider}", name)}
        title={copy.reorderProvider.replace("{provider}", name)}
        onPointerDown={event => !disabled && controls.start(event)}
        onTouchStartCapture={event => event.stopPropagation()}
        onKeyDown={event => {
          if (event.key === "ArrowUp" || event.key === "ArrowDown") {
            event.preventDefault()
            move(event.key === "ArrowUp" ? -1 : 1)
          }
        }}
      >
        <GripVertical className="h-4 w-4" />
      </Button>
      <span className="w-4 shrink-0 text-xs tabular-nums text-muted-foreground">
        {index + 1}
      </span>
      <ProviderLogo id={entry.provider} name={name} />
      <button
        type="button"
        onClick={edit}
        disabled={disabled}
        aria-label={copy.editProvider.replace("{provider}", name)}
        aria-current={selected ? "true" : undefined}
        className="min-w-0 flex-1 px-2 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <span className="block break-words text-sm font-medium">{name}</span>
        <span
          className="block truncate font-mono text-[11px] text-muted-foreground"
          title={entry.model}
        >
          {entry.model}
        </span>
        <span className="block text-[11px] text-muted-foreground">{state}</span>
      </button>
      <div className="flex shrink-0 items-center">
        <div className="flex flex-col @[480px]:flex-row">
          <Button
            variant="ghost"
            size="icon"
            className="h-9 w-7"
            disabled={disabled || first}
            onClick={() => move(-1)}
            aria-label={copy.moveUp}
            title={copy.moveUp}
          >
            <ArrowUp className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-9 w-7"
            disabled={disabled || last}
            onClick={() => move(1)}
            aria-label={copy.moveDown}
            title={copy.moveDown}
          >
            <ArrowDown className="h-3.5 w-3.5" />
          </Button>
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="h-9 w-7 text-muted-foreground"
          disabled={disabled}
          onClick={remove}
          aria-label={copy.removeProvider.replace("{provider}", name)}
          title={copy.removeProvider.replace("{provider}", name)}
        >
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>
    </Reorder.Item>
  )
}

export function useAIProviderName() {
  const { t } = useI18n()
  const { externalIntegrations } = useAppContext()
  return useCallback(
    (providerId: string) => {
      const integration = externalIntegrations.find(
        item => item.id === providerId,
      )
      return integration?.family
        ? `${getIntegrationFamilyName(t, integration.family)} - ${getIntegrationMethodName(t, providerId, integration)}`
        : getIntegrationName(t, providerId, integration)
    },
    [externalIntegrations, t],
  )
}

export function AIProviderPriorityEditor({
  entries,
  onChange,
  task,
  disabled: disabledProp = false,
  readOnly = false,
  notices,
  testIdPrefix = "external",
  onSelectedModel,
}: {
  entries: AIProviderEntry[]
  onChange: (entries: AIProviderEntry[]) => void
  task?: AITask
  disabled?: boolean
  readOnly?: boolean
  notices: AIProviderEditorNotices
  testIdPrefix?: string
  onSelectedModel?: (model: AICatalogModel | undefined) => void
}) {
  const { t, locale } = useI18n()
  const navigate = useNavigate()
  const { externalIntegrations, fetchExternalIntegrations } = useAppContext()
  const copy = t.labels.external
  const testId = (name: string) => `${testIdPrefix}-${name}`
  const disabled = disabledProp || readOnly
  const [providers, setProviders] = useState<AIProviderDetails[]>([])
  const [loadingProviders, setLoadingProviders] = useState(true)
  const [selectedIndex, setEditingIndex] = useState(entries.length ? 0 : -1)
  const editingIndex = readOnly
    ? -1
    : Math.min(selectedIndex, entries.length - 1)
  const [modelChoice, setModelChoice] = useState<string>("")
  const [customModel, setCustomModel] = useState("")
  const [validation, setValidation] = useState<"valid" | "invalid" | null>(null)
  const [validating, setValidating] = useState(false)
  const [providerOpen, setProviderOpen] = useState(false)
  const [dynamicModels, setDynamicModels] = useState<AICatalogModel[] | null>(
    null,
  )
  const [dynamicModelsFailed, setDynamicModelsFailed] = useState(false)
  const [modelsVersion, setModelsVersion] = useState(0)
  const [modelQuery, setModelQuery] = useState("")
  const [managerOpen, setManagerOpen] = useState(false)
  const entriesRef = useRef(entries)
  entriesRef.current = entries
  const onChangeRef = useRef(onChange)
  onChangeRef.current = onChange

  const refreshModels = useCallback(() => setModelsVersion(v => v + 1), [])
  const closeManager = useCallback(() => {
    setManagerOpen(false)
    refreshModels()
  }, [refreshModels])

  useEffect(() => {
    void fetchExternalIntegrations()
  }, [fetchExternalIntegrations])

  const connectedAIProviders = externalIntegrations
    .filter(
      integration =>
        integration.type === ExternalIntegrationType.AI_PROVIDER &&
        integration.status === ExternalIntegrationStatus.ON,
    )
    .map(integration => integration.id)
    .sort()
    .join(",")

  useEffect(() => {
    let cancelled = false
    getAIProviders(task)
      .then(response => {
        if (!cancelled) setProviders(response.providers)
      })
      .catch(err => console.error("Error loading AI providers:", err))
      .finally(() => {
        if (!cancelled) setLoadingProviders(false)
      })
    return () => {
      cancelled = true
    }
  }, [task, connectedAIProviders])

  const entry = entries[editingIndex]
  const provider = useMemo(
    () =>
      entry?.provider
        ? providers.find(p => p.id === entry.provider)
        : editingIndex >= 0
          ? providers[0]
          : undefined,
    [providers, entry?.provider, editingIndex],
  )
  const providerUnavailable =
    !loadingProviders && !!entry?.provider && !provider

  const dynamicProviderId =
    provider?.dynamic_models && provider.connected ? provider.id : null

  useEffect(() => {
    setDynamicModels(null)
    setDynamicModelsFailed(false)
    setModelQuery("")
  }, [dynamicProviderId])

  useEffect(() => {
    if (!dynamicProviderId) return
    let cancelled = false
    getAIModels(dynamicProviderId, task)
      .then(response => {
        if (cancelled) return
        setDynamicModels(response.models)
        setDynamicModelsFailed(false)
      })
      .catch(err => {
        console.error("Error loading provider models:", err)
        if (!cancelled) setDynamicModelsFailed(true)
      })
    return () => {
      cancelled = true
    }
  }, [dynamicProviderId, modelsVersion, task])

  const modelOptions = useMemo(
    () =>
      dynamicProviderId
        ? (dynamicModels ?? [])
        : (provider?.recommended_models ?? []),
    [dynamicProviderId, dynamicModels, provider],
  )

  const commit = useCallback(
    (index: number, patch: Partial<AIProviderEntry>) => {
      const current = entriesRef.current
      if (!current[index]) return
      const next = [...current]
      next[index] = { ...current[index], ...patch }
      if (JSON.stringify(next) !== JSON.stringify(current)) {
        onChangeRef.current(next)
      }
    },
    [],
  )

  // Only provider, priority or option changes re-derive the choice so model edits are not undone.
  useEffect(() => {
    if (!provider || editingIndex < 0) return
    const model = entriesRef.current[editingIndex]?.model ?? ""
    const isListed = (id: string) =>
      modelOptions.some(option => option.id === id)
    const choice = !model
      ? (modelOptions.find(option => option.eligible !== false)?.id ??
        (provider.custom_models ? CUSTOM_MODEL : ""))
      : isListed(model)
        ? model
        : CUSTOM_MODEL
    setModelChoice(choice)
    setCustomModel(choice === CUSTOM_MODEL ? model : "")
    if (!model && choice && choice !== CUSTOM_MODEL) {
      commit(editingIndex, { model: choice, upstreamProvider: null })
    }
  }, [provider, editingIndex, modelOptions, commit])

  const providerName = useAIProviderName()

  const providerGroups = useMemo(() => {
    const groups = new Map<
      string,
      { name: string | undefined; methods: AIProviderDetails[] }
    >()
    for (const item of providers) {
      const family = externalIntegrations.find(
        integration => integration.id === item.id,
      )?.family
      const key = family ? `family:${family.id}` : `integration:${item.id}`
      const name = family ? getIntegrationFamilyName(t, family) : undefined
      groups.set(key, {
        name,
        methods: [...(groups.get(key)?.methods ?? []), item],
      })
    }
    return [...groups.entries()]
  }, [providers, externalIntegrations, t])

  const effectiveProvider = resolveAIProvider(entries, externalIntegrations)
  const duplicate = hasDuplicateAIEntries(entries)
  const priorityKeys = entries.map(
    (item, index) =>
      `${aiEntryKey(item)}:${entries.slice(0, index).filter(previous => aiEntryKey(previous) === aiEntryKey(item)).length}`,
  )
  const reorder = (keys: string[]) => {
    const selected = entries[editingIndex]
    const next = keys
      .map(key => entries[priorityKeys.indexOf(key)])
      .filter(Boolean)
    onChange(next)
    setEditingIndex(Math.max(0, next.indexOf(selected)))
  }
  const moveEntry = (index: number, direction: number) => {
    const target = index + direction
    if (target < 0 || target >= entries.length) return
    const keys = [...priorityKeys]
    ;[keys[index], keys[target]] = [keys[target], keys[index]]
    reorder(keys)
  }

  const upstreamProvider =
    provider?.upstream_providers && modelChoice === CUSTOM_MODEL
      ? (entry?.upstreamProvider ?? "")
      : ""

  const handleValidate = async () => {
    if (!provider || !customModel.trim()) return
    setValidating(true)
    setValidation(null)
    try {
      const response = await validateAIModel(
        provider.id,
        customModel.trim(),
        task ?? AITask.LABELING,
        upstreamProvider.trim() || null,
      )
      setValidation(response.valid ? "valid" : "invalid")
    } catch (err) {
      console.error("Error validating model:", err)
      setValidation("invalid")
    } finally {
      setValidating(false)
    }
  }

  const selectedRecommended = modelOptions.find(m => m.id === modelChoice)
  useEffect(() => {
    onSelectedModel?.(selectedRecommended)
  }, [onSelectedModel, selectedRecommended])
  const loadingDynamicModels =
    !!dynamicProviderId && !dynamicModels && !dynamicModelsFailed
  const modelUnavailable =
    !!dynamicModels &&
    !provider?.custom_models &&
    !!entry?.model &&
    !dynamicModels.some(m => m.id === entry.model)
  const selectedModelFailed = !!selectedRecommended?.load_failed
  const smallModelSelected =
    !!notices.smallModel &&
    !!selectedRecommended?.size &&
    selectedRecommended.size < SMALL_MODEL_SIZE
  const customSelected = modelChoice === CUSTOM_MODEL
  const shownProviderId = provider?.id ?? entry?.provider ?? ""

  const showModelSearch =
    !!dynamicProviderId && modelOptions.length > MODEL_SEARCH_THRESHOLD
  const query = showModelSearch ? modelQuery.trim().toLowerCase() : ""
  const visibleModels = query
    ? modelOptions.filter(model =>
        `${model.name} ${model.id}`.toLowerCase().includes(query),
      )
    : modelOptions

  const modelOptionClass = (selected: boolean, ineligible: boolean) =>
    cn(
      "flex items-start gap-3 rounded-lg border p-3 transition-all has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-violet-500/50",
      ineligible ? "cursor-not-allowed opacity-60" : "cursor-pointer",
      selected
        ? "border-violet-500/60 bg-violet-500/10 shadow-sm shadow-violet-500/10"
        : "border-border/70 bg-background/70 hover:border-violet-500/40 hover:bg-background",
    )
  const radioName = `${testIdPrefix}-model`

  if (loadingProviders) {
    return (
      <div className="flex justify-center py-4">
        <LoadingSpinner size="sm" />
      </div>
    )
  }

  return (
    <div
      className={cn("space-y-5", readOnly && "opacity-60")}
      aria-disabled={readOnly || undefined}
      data-testid={testId("editor")}
    >
      <div className="space-y-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex min-w-0 items-center gap-1">
            <FieldLabel>{copy.priorityTitle}</FieldLabel>
            <Popover>
              <PopoverTrigger asChild>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6 shrink-0 text-muted-foreground hover:text-foreground"
                  aria-label={copy.priorityTitle}
                  title={copy.priorityTitle}
                  data-testid={testId("priority-info")}
                >
                  <Info className="h-3.5 w-3.5" />
                </Button>
              </PopoverTrigger>
              <PopoverContent
                align="start"
                className="w-80 max-w-[calc(100vw-2rem)] text-xs text-muted-foreground"
                aria-label={copy.priorityTitle}
              >
                <p data-testid={testId("priority-notice")}>
                  {notices.priority}
                </p>
              </PopoverContent>
            </Popover>
          </div>
          <span className="text-xs tabular-nums text-muted-foreground">
            {entries.length}/{MAX_AI_PROVIDERS}
          </span>
        </div>
        <Reorder.Group
          axis="y"
          values={priorityKeys}
          onReorder={reorder}
          className="@container space-y-2"
        >
          {entries.map((item, index) => (
            <PriorityRow
              key={priorityKeys[index]}
              entry={item}
              index={index}
              value={priorityKeys[index]}
              name={providerName(item.provider)}
              state={
                effectiveProvider === item
                  ? copy.preferredHere
                  : copy.priorityStates[
                      externalProviderState(item, externalIntegrations)
                    ]
              }
              selected={index === editingIndex}
              disabled={disabled}
              first={index === 0}
              last={index === entries.length - 1}
              testId={testId(`priority-${index}`)}
              edit={() => {
                setEditingIndex(index)
                setValidation(null)
              }}
              remove={() => {
                onChange(entries.filter((_, position) => position !== index))
                setEditingIndex(current =>
                  entries.length === 1
                    ? -1
                    : Math.max(
                        0,
                        current > index
                          ? current - 1
                          : Math.min(current, entries.length - 2),
                      ),
                )
              }}
              move={direction => moveEntry(index, direction)}
            />
          ))}
        </Reorder.Group>
        {!readOnly && (
          <Popover open={providerOpen} onOpenChange={setProviderOpen}>
            <PopoverTrigger asChild>
              <Button
                id={testId("add-provider")}
                variant="outline"
                size="sm"
                className="gap-1.5"
                aria-haspopup="listbox"
                aria-expanded={providerOpen}
                disabled={
                  disabled ||
                  entries.length >= MAX_AI_PROVIDERS ||
                  !providers.length
                }
                data-testid={testId("add-provider")}
              >
                <Plus className="h-3.5 w-3.5" />
                {copy.addProvider}
                <ChevronDown className="h-3.5 w-3.5 opacity-50" />
              </Button>
            </PopoverTrigger>
            <PopoverContent
              align="start"
              className="w-72 max-w-[calc(100vw-2rem)] p-1"
            >
              <div
                role="listbox"
                aria-labelledby={testId("add-provider")}
                className="max-h-80 overflow-y-auto"
              >
                {providerGroups.map(([key, { name, methods }]) => (
                  <div
                    key={key}
                    role="group"
                    aria-label={name ?? providerName(methods[0].id)}
                  >
                    {name && (
                      <p className="px-2 pb-1 pt-2 text-xs font-medium text-muted-foreground">
                        {name}
                      </p>
                    )}
                    {methods.map(method => {
                      const integration = externalIntegrations.find(
                        item => item.id === method.id,
                      )
                      const optionName = integration?.family
                        ? getIntegrationMethodName(t, method.id, integration)
                        : getIntegrationName(t, method.id, integration)
                      return (
                        <button
                          key={method.id}
                          type="button"
                          role="option"
                          aria-selected={false}
                          data-testid={testId(`provider-option-${method.id}`)}
                          onClick={() => {
                            if (disabled || entries.length >= MAX_AI_PROVIDERS)
                              return
                            onChange([
                              ...entries,
                              {
                                provider: method.id,
                                model: method.recommended_models[0]?.id ?? "",
                                upstreamProvider: null,
                              },
                            ])
                            setEditingIndex(entries.length)
                            setValidation(null)
                            setProviderOpen(false)
                          }}
                          className="flex w-full items-center gap-2 rounded-sm px-2 py-2 text-sm hover:bg-accent hover:text-accent-foreground focus-visible:bg-accent focus-visible:outline-none"
                        >
                          <ProviderLogo id={method.id} name={optionName} />
                          <span className="min-w-0 flex-1 break-words text-left">
                            {optionName}
                          </span>
                          <span
                            className={cn(
                              "h-2 w-2 shrink-0 rounded-full",
                              method.connected
                                ? "bg-green-500"
                                : "bg-muted-foreground/40",
                            )}
                            title={
                              method.connected
                                ? copy.connected
                                : copy.notConnected
                            }
                          />
                          <Plus className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                        </button>
                      )
                    })}
                  </div>
                ))}
              </div>
            </PopoverContent>
          </Popover>
        )}
        {!effectiveProvider && !readOnly && (
          <p className="text-xs text-amber-700 dark:text-amber-300">
            {copy.noEligibleProvider}
          </p>
        )}
        {duplicate && (
          <p className="text-xs text-red-600 dark:text-red-400" role="alert">
            {copy.duplicateProvider}
          </p>
        )}
      </div>
      {editingIndex >= 0 && (
        <fieldset
          className="space-y-5 min-w-0"
          disabled={disabled || providerUnavailable}
          data-testid={testId("entry-editor")}
        >
          <div className="space-y-1.5">
            <FieldLabel>{copy.provider}</FieldLabel>
            <div className="flex flex-wrap items-center gap-2">
              <span className="flex min-w-0 items-center gap-2 text-sm">
                <ProviderLogo
                  id={shownProviderId}
                  name={providerName(shownProviderId)}
                />
                <span className="break-words">
                  {providerName(shownProviderId)}
                </span>
              </span>
              <Badge
                className={cn(
                  !provider
                    ? "bg-muted text-muted-foreground"
                    : provider.connected
                      ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300"
                      : "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
                )}
              >
                {!provider
                  ? copy.unavailableHere
                  : provider.connected
                    ? copy.connected
                    : copy.notConnected}
              </Badge>
              {provider && !provider.connected && (
                <Button
                  variant="link"
                  size="sm"
                  className="h-auto gap-1 px-1"
                  onClick={() =>
                    navigate(`/entities?tab=providers&focus=${provider.id}`)
                  }
                >
                  <ExternalLink className="h-3.5 w-3.5" />
                  {copy.connectProvider}
                </Button>
              )}
            </div>
          </div>

          {providerUnavailable && (
            <div
              className="flex items-start gap-2 rounded-md border border-amber-500/40 bg-amber-50 p-3 text-xs text-amber-800 dark:bg-amber-900/10 dark:text-amber-300"
              data-testid={testId("provider-unavailable")}
            >
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>
                {copy.providerUnavailable.replace(
                  "{provider}",
                  providerName(shownProviderId),
                )}
              </span>
            </div>
          )}

          {provider && (
            <div className="space-y-2.5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <FieldLabel>{copy.model}</FieldLabel>
                {provider.id === LOCAL_MODELS_PROVIDER &&
                  provider.connected && (
                    <>
                      <Button
                        variant="link"
                        size="sm"
                        className="h-auto gap-1 px-1"
                        onClick={() => setManagerOpen(true)}
                        data-testid={testId("manage-models")}
                      >
                        <Settings2 className="h-3.5 w-3.5" />
                        {copy.manageModels}
                      </Button>
                      <LocalModelsManagerDialog
                        open={managerOpen}
                        onClose={closeManager}
                        onModelsChange={refreshModels}
                      />
                    </>
                  )}
              </div>
              {loadingDynamicModels && (
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <LoadingSpinner size="sm" className="h-3.5 w-3.5" />
                  {copy.loadingModels}
                </div>
              )}
              {dynamicModelsFailed && (
                <p className="text-xs text-red-600 dark:text-red-400">
                  {copy.modelsError}
                </p>
              )}
              {dynamicModels && dynamicModels.length === 0 && (
                <p className="text-xs text-muted-foreground">
                  {copy.noModelsAvailable}
                </p>
              )}
              {showModelSearch && (
                <div className="relative">
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    value={modelQuery}
                    onChange={event => setModelQuery(event.target.value)}
                    placeholder={copy.searchModels}
                    aria-label={copy.searchModels}
                    className="h-9 pl-8"
                    disabled={disabled}
                  />
                </div>
              )}
              <div
                role="radiogroup"
                aria-label={copy.model}
                className="space-y-2"
              >
                {visibleModels.length > 0 && (
                  <div
                    className={cn(
                      "grid grid-cols-1 gap-2 md:grid-cols-2",
                      dynamicProviderId && "-m-1 max-h-80 overflow-y-auto p-1",
                    )}
                    data-testid={testId("model-options")}
                  >
                    {visibleModels.map(model => {
                      const checked = modelChoice === model.id
                      const ineligible = model.eligible === false
                      const images = model.input_modalities?.includes(
                        AIInputModality.IMAGE,
                      )
                      const documents = model.input_modalities?.includes(
                        AIInputModality.DOCUMENT,
                      )
                      return (
                        <label
                          key={model.id}
                          className={modelOptionClass(checked, ineligible)}
                        >
                          <input
                            type="radio"
                            name={radioName}
                            className="sr-only"
                            checked={checked}
                            onChange={() => {
                              setModelChoice(model.id)
                              setValidation(null)
                              commit(editingIndex, {
                                model: model.id,
                                upstreamProvider: null,
                              })
                            }}
                            disabled={disabled || (ineligible && !checked)}
                          />
                          <RadioMark checked={checked} />
                          <span className="min-w-0 flex-1 space-y-1">
                            <span className="block truncate text-sm font-medium leading-tight">
                              {model.name}
                            </span>
                            {model.name !== model.id && (
                              <span className="block truncate font-mono text-[11px] text-muted-foreground">
                                {model.id}
                              </span>
                            )}
                            {(model.probabilistic ||
                              model.loaded ||
                              model.load_failed ||
                              ineligible ||
                              images ||
                              documents ||
                              !!model.size ||
                              !!model.pricing) && (
                              <span className="flex flex-wrap gap-1 pt-0.5">
                                {ineligible && (
                                  <ModelChip className="border-border bg-muted/60 text-muted-foreground">
                                    {t.settings.aiModalities.notEligible}
                                  </ModelChip>
                                )}
                                {model.probabilistic && (
                                  <ModelChip className="border-violet-500/30 bg-violet-500/10 text-violet-700 dark:text-violet-300">
                                    <Sparkles className="h-2.5 w-2.5" />
                                    {copy.decisionModel}
                                  </ModelChip>
                                )}
                                {images && (
                                  <ModelChip className="border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-300">
                                    <ImageIcon className="h-2.5 w-2.5" />
                                    {t.settings.aiModalities.IMAGE}
                                  </ModelChip>
                                )}
                                {documents && (
                                  <ModelChip className="border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-300">
                                    <FileText className="h-2.5 w-2.5" />
                                    {t.settings.aiModalities.DOCUMENT}
                                  </ModelChip>
                                )}
                                {model.loaded && (
                                  <ModelChip className="border-green-500/30 bg-green-500/10 text-green-700 dark:text-green-400">
                                    <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
                                    {copy.modelLoaded}
                                  </ModelChip>
                                )}
                                {model.load_failed && (
                                  <ModelChip className="border-red-500/30 bg-red-500/10 text-red-600 dark:text-red-400">
                                    <span className="h-1.5 w-1.5 rounded-full bg-red-500" />
                                    {copy.modelFailed}
                                  </ModelChip>
                                )}
                                {!!model.size && (
                                  <ModelChip className="border-border bg-muted/60 text-muted-foreground">
                                    <HardDrive className="h-2.5 w-2.5" />
                                    {formatFileSize(model.size)}
                                  </ModelChip>
                                )}
                                {model.pricing && (
                                  <ModelChip
                                    className="border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300"
                                    title={copy.tokenPriceHint}
                                  >
                                    <Coins className="h-2.5 w-2.5" />
                                    {copy.tokenPrice
                                      .replace(
                                        "{input}",
                                        formatTokenPrice(
                                          model.pricing.input_per_million,
                                          model.pricing.currency,
                                          locale,
                                        ),
                                      )
                                      .replace(
                                        "{output}",
                                        formatTokenPrice(
                                          model.pricing.output_per_million,
                                          model.pricing.currency,
                                          locale,
                                        ),
                                      )}
                                  </ModelChip>
                                )}
                              </span>
                            )}
                          </span>
                        </label>
                      )
                    })}
                  </div>
                )}
                {query && visibleModels.length === 0 && (
                  <p className="py-2 text-center text-xs text-muted-foreground">
                    {copy.noModelsMatch}
                  </p>
                )}
                {provider.custom_models && (
                  <div
                    className={cn(
                      "rounded-lg border border-dashed transition-colors",
                      customSelected
                        ? "border-violet-500/60 bg-violet-500/5"
                        : "border-border hover:border-violet-500/40",
                    )}
                  >
                    <label className="flex cursor-pointer items-start gap-3 rounded-lg p-3 has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-violet-500/50">
                      <input
                        type="radio"
                        name={radioName}
                        className="sr-only"
                        checked={customSelected}
                        onChange={() => {
                          setModelChoice(CUSTOM_MODEL)
                          commit(editingIndex, { model: customModel.trim() })
                        }}
                        disabled={disabled}
                      />
                      <RadioMark checked={customSelected} />
                      <span className="min-w-0 flex-1 space-y-0.5">
                        <span className="flex items-center gap-1.5 text-sm font-medium leading-tight">
                          <PenLine className="h-3.5 w-3.5 text-muted-foreground" />
                          {copy.customModel}
                        </span>
                        <span className="block text-xs text-muted-foreground">
                          {provider.dynamic_models
                            ? copy.customModelUnlistedHint
                            : copy.customModelHint.replace(
                                "{provider}",
                                providerName(provider.id),
                              )}
                        </span>
                      </span>
                    </label>
                    {customSelected && (
                      <div className="space-y-2 px-3 pb-3 sm:pl-10">
                        <div className="flex flex-wrap items-center gap-2">
                          <Input
                            value={customModel}
                            onChange={event => {
                              setCustomModel(event.target.value)
                              setValidation(null)
                              commit(editingIndex, {
                                model: event.target.value.trim(),
                              })
                            }}
                            placeholder={
                              (
                                copy.customModelPlaceholders as Record<
                                  string,
                                  string
                                >
                              )[provider.id] ?? copy.customModelPlaceholder
                            }
                            aria-label={copy.customModel}
                            className="h-9 min-w-0 flex-1 basis-56 font-mono"
                            disabled={disabled}
                          />
                          {provider.upstream_providers && (
                            <Input
                              value={entry?.upstreamProvider ?? ""}
                              onChange={event => {
                                commit(editingIndex, {
                                  upstreamProvider: event.target.value,
                                })
                                setValidation(null)
                              }}
                              placeholder={copy.upstreamProviderPlaceholder}
                              aria-label={copy.upstreamProvider}
                              className="h-9 w-44 font-mono"
                              disabled={disabled}
                            />
                          )}
                          {!provider.dynamic_models && (
                            <Button
                              variant="outline"
                              size="sm"
                              className="h-9"
                              onClick={handleValidate}
                              disabled={
                                disabled ||
                                validating ||
                                !customModel.trim() ||
                                !provider.connected
                              }
                            >
                              {validating ? t.common.loading : copy.validate}
                            </Button>
                          )}
                        </div>
                        {validation === "valid" && (
                          <p className="flex items-center gap-1 text-xs text-green-600 dark:text-green-400">
                            <CheckCircle2 className="h-3.5 w-3.5" />
                            {copy.modelValid}
                          </p>
                        )}
                        {validation === "invalid" && (
                          <p className="flex items-center gap-1 text-xs text-red-600 dark:text-red-400">
                            <XCircle className="h-3.5 w-3.5" />
                            {copy.modelInvalid}
                          </p>
                        )}
                        {provider.upstream_providers && (
                          <p className="text-xs text-muted-foreground">
                            {copy.upstreamProviderHint}
                          </p>
                        )}
                        <p className="flex items-start gap-1.5 text-xs text-muted-foreground">
                          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                          {notices.customModel}
                        </p>
                      </div>
                    )}
                  </div>
                )}
              </div>
              {modelUnavailable && (
                <div className="flex items-start gap-2 rounded-md border border-amber-500/40 bg-amber-50 p-3 text-xs text-amber-800 dark:bg-amber-900/10 dark:text-amber-300">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>
                    {copy.modelUnavailable.replace(
                      "{model}",
                      entry?.model ?? "",
                    )}
                  </span>
                </div>
              )}
              {selectedModelFailed && (
                <div
                  className="flex items-start gap-2 rounded-md border border-red-500/40 bg-red-50 p-3 text-xs text-red-800 dark:bg-red-900/10 dark:text-red-300"
                  data-testid={testId("model-load-failed")}
                >
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>
                    {copy.modelLoadFailed.replace(
                      "{model}",
                      selectedRecommended?.name ?? "",
                    )}
                  </span>
                </div>
              )}
              {smallModelSelected && !selectedModelFailed && (
                <div
                  className="flex items-start gap-2 rounded-md border border-amber-500/40 bg-amber-50 p-3 text-xs text-amber-800 dark:bg-amber-900/10 dark:text-amber-300"
                  data-testid={testId("small-model-warning")}
                >
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>{notices.smallModel}</span>
                </div>
              )}
            </div>
          )}

          {provider && notices.privacy && (
            <p className="text-xs text-muted-foreground">{notices.privacy}</p>
          )}
        </fieldset>
      )}
    </div>
  )
}
