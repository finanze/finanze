import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react"
import { useNavigate } from "react-router-dom"
import { AnimatePresence, motion } from "framer-motion"
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  ChevronDown,
  ExternalLink,
  HardDrive,
  Info,
  PenLine,
  Search,
  Settings2,
  Sparkles,
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
import { Switch } from "@/components/ui/Switch"
import { Badge } from "@/components/ui/Badge"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { LocalModelsManagerDialog } from "@/components/settings/LocalModelsDialog"
import {
  getExternalLabelingModels,
  getExternalLabelingProviders,
  validateAIModel,
} from "@/services/api"
import { cn } from "@/lib/utils"
import { formatFileSize } from "@/utils/releaseUtils"
import { AITask } from "@/types/ai"
import { LabelOrigin } from "@/types/transactions"
import type {
  ExternalLabelingModel,
  ExternalLabelingProviderDetails,
  ExternalLabelingSettings,
} from "@/types/labeling"
import {
  ExternalSuggestionsIcon,
  ExternalSuggestionsSurface,
} from "./ExternalSuggestionsSurface"

const CUSTOM_MODEL = "__custom__"
const LOCAL_MODELS_PROVIDER = "LOCAL_MODELS"
const MAX_INSTRUCTIONS_LENGTH = 2000
const SMALL_MODEL_SIZE = 2_000_000_000
const MODEL_SEARCH_THRESHOLD = 6
const EXAMPLE_ORIGINS = [LabelOrigin.MANUAL, LabelOrigin.RULE]

const SELECT_CLASS =
  "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"

const clampInt = (
  value: string,
  min: number,
  max: number,
  fallback: number,
) => {
  const parsed = Number.parseInt(value, 10)
  if (!Number.isFinite(parsed)) return fallback
  return Math.min(Math.max(parsed, min), max)
}

function SettingRow({
  title,
  hint,
  children,
}: {
  title: string
  hint: string
  children: ReactNode
}) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div className="min-w-0">
        <div className="text-sm font-medium">{title}</div>
        <p className="text-xs text-muted-foreground">{hint}</p>
      </div>
      <div className="flex shrink-0 items-center gap-2">{children}</div>
    </div>
  )
}

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
  children,
}: {
  className: string
  children: ReactNode
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-1.5 py-0.5 text-[10px] font-medium leading-none",
        className,
      )}
    >
      {children}
    </span>
  )
}

export function ExternalLabelingCard({ className }: { className?: string }) {
  const { t } = useI18n()
  const navigate = useNavigate()
  const {
    settings,
    saveSettings,
    externalIntegrations,
    fetchExternalIntegrations,
  } = useAppContext()
  const [providers, setProviders] = useState<ExternalLabelingProviderDetails[]>(
    [],
  )
  const [loadingProviders, setLoadingProviders] = useState(true)
  const [draft, setDraft] = useState<ExternalLabelingSettings | null>(null)
  const [modelChoice, setModelChoice] = useState<string>("")
  const [customModel, setCustomModel] = useState("")
  const [validation, setValidation] = useState<"valid" | "invalid" | null>(null)
  const [validating, setValidating] = useState(false)
  const [moreOpen, setMoreOpen] = useState(false)
  const [providerOpen, setProviderOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dynamicModels, setDynamicModels] = useState<
    ExternalLabelingModel[] | null
  >(null)
  const [dynamicModelsFailed, setDynamicModelsFailed] = useState(false)
  const [modelsVersion, setModelsVersion] = useState(0)
  const [modelQuery, setModelQuery] = useState("")
  const [managerOpen, setManagerOpen] = useState(false)
  const syncedModelRef = useRef<string | null>(null)

  const refreshModels = useCallback(() => setModelsVersion(v => v + 1), [])
  const closeManager = useCallback(() => {
    setManagerOpen(false)
    refreshModels()
  }, [refreshModels])

  const stored = settings.labeling?.external

  useEffect(() => {
    void fetchExternalIntegrations()
    getExternalLabelingProviders()
      .then(response => setProviders(response.providers))
      .catch(err => console.error("Error loading labeling providers:", err))
      .finally(() => setLoadingProviders(false))
  }, [fetchExternalIntegrations])

  useEffect(() => {
    if (!stored) return
    setDraft({ ...stored, examples: { ...stored.examples } })
  }, [stored])

  const provider = useMemo(
    () =>
      draft?.provider
        ? providers.find(p => p.id === draft.provider)
        : providers[0],
    [providers, draft?.provider],
  )
  const providerUnavailable =
    providers.length > 0 && !!draft?.provider && !provider

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
    getExternalLabelingModels(dynamicProviderId)
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
  }, [dynamicProviderId, modelsVersion])

  const modelOptions = useMemo(
    () =>
      dynamicProviderId
        ? (dynamicModels ?? [])
        : (provider?.recommended_models ?? []),
    [dynamicProviderId, dynamicModels, provider],
  )

  useEffect(() => {
    if (!draft || !provider) return
    const model = draft.model ?? ""
    const key = `${provider.id}:${model}`
    const keepChoice = syncedModelRef.current === key
    syncedModelRef.current = key
    const isListed = (id: string) => modelOptions.some(m => m.id === id)
    const choice = !model
      ? (modelOptions[0]?.id ?? CUSTOM_MODEL)
      : isListed(model)
        ? model
        : CUSTOM_MODEL
    setModelChoice(current =>
      keepChoice && current !== CUSTOM_MODEL && isListed(current)
        ? current
        : choice,
    )
    setCustomModel(choice === CUSTOM_MODEL ? model : "")
  }, [provider, draft?.model, modelOptions])

  const providerName = useCallback(
    (providerId: string) =>
      externalIntegrations.find(integration => integration.id === providerId)
        ?.name ?? providerId,
    [externalIntegrations],
  )

  if (!draft || !stored) return null

  const update = (patch: Partial<ExternalLabelingSettings>) => {
    setDraft(prev => (prev ? { ...prev, ...patch } : prev))
    setError(null)
  }

  const selectedModel =
    modelChoice === CUSTOM_MODEL ? customModel.trim() : modelChoice
  const upstreamProvider =
    modelChoice === CUSTOM_MODEL && provider?.upstream_providers
      ? draft.upstreamProvider?.trim() || null
      : null

  const nextSettings: ExternalLabelingSettings = {
    ...draft,
    ...(provider && {
      provider: provider.id,
      model: selectedModel || null,
      upstreamProvider,
    }),
    instructions: draft.instructions?.trim() ? draft.instructions : null,
  }
  const dirty =
    draft.enabled !== stored.enabled ||
    (draft.enabled && JSON.stringify(nextSettings) !== JSON.stringify(stored))
  const providerDisconnected =
    draft.enabled && !!provider && !provider.connected

  const handleValidate = async () => {
    if (!provider || !customModel.trim()) return
    setValidating(true)
    setValidation(null)
    try {
      const response = await validateAIModel(
        provider.id,
        customModel.trim(),
        AITask.LABELING,
        upstreamProvider,
      )
      setValidation(response.valid ? "valid" : "invalid")
    } catch (err) {
      console.error("Error validating model:", err)
      setValidation("invalid")
    } finally {
      setValidating(false)
    }
  }

  const handleSave = async () => {
    if (providerDisconnected) return
    if (draft.enabled && (provider ? !selectedModel : !draft.provider)) {
      setError(t.labels.external.providerAndModelRequired)
      return
    }
    setSaving(true)
    await saveSettings({ labeling: { external: nextSettings } })
    setSaving(false)
  }

  const selectedRecommended = modelOptions.find(m => m.id === modelChoice)
  const loadingDynamicModels =
    !!dynamicProviderId && !dynamicModels && !dynamicModelsFailed
  const modelUnavailable =
    !!dynamicModels &&
    !provider?.custom_models &&
    !!stored.model &&
    stored.provider === provider?.id &&
    draft.model === stored.model &&
    !dynamicModels.some(m => m.id === stored.model)
  const selectedModelFailed = !!selectedRecommended?.load_failed
  const smallModelSelected =
    !!selectedRecommended?.size && selectedRecommended.size < SMALL_MODEL_SIZE
  const customSelected = modelChoice === CUSTOM_MODEL
  const shownProviderId = provider?.id ?? draft.provider ?? ""

  const showModelSearch =
    !!dynamicProviderId && modelOptions.length > MODEL_SEARCH_THRESHOLD
  const query = showModelSearch ? modelQuery.trim().toLowerCase() : ""
  const visibleModels = query
    ? modelOptions.filter(model =>
        `${model.name} ${model.id}`.toLowerCase().includes(query),
      )
    : modelOptions

  const modelOptionClass = (selected: boolean) =>
    cn(
      "flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-all has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-violet-500/50",
      selected
        ? "border-violet-500/60 bg-violet-500/10 shadow-sm shadow-violet-500/10"
        : "border-border/70 bg-background/70 hover:border-violet-500/40 hover:bg-background",
    )

  return (
    <ExternalSuggestionsSurface
      className={cn(
        "p-4 shadow-sm transition-shadow",
        !draft.enabled && "hover:shadow-md hover:shadow-violet-500/10",
        className,
      )}
      data-testid="external-labeling-card"
    >
      <div className="space-y-5">
        <div className="flex items-start gap-3">
          <button
            type="button"
            onClick={() => update({ enabled: !draft.enabled })}
            aria-expanded={draft.enabled}
            disabled={saving}
            className="flex min-w-0 flex-1 items-start gap-3 rounded-md text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <ExternalSuggestionsIcon />
            <span className="min-w-0 flex-1">
              <span className="block text-sm font-medium">
                {t.labels.external.enable}
              </span>
              <span className="block text-xs text-muted-foreground">
                {t.labels.external.description}
              </span>
            </span>
          </button>
          <Switch
            checked={draft.enabled}
            onCheckedChange={value => update({ enabled: value })}
            disabled={saving}
            data-testid="external-labeling-switch"
          />
        </div>

        {draft.enabled &&
          (loadingProviders ? (
            <div className="flex justify-center py-4">
              <LoadingSpinner size="sm" />
            </div>
          ) : providers.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              {t.labels.external.noProviders}
            </p>
          ) : (
            <div className="space-y-5 border-t border-violet-500/20 pt-5">
              <div className="space-y-1.5">
                <FieldLabel htmlFor="external-provider">
                  {t.labels.external.provider}
                </FieldLabel>
                <div className="flex flex-wrap items-center gap-2">
                  <Popover open={providerOpen} onOpenChange={setProviderOpen}>
                    <PopoverTrigger asChild>
                      <button
                        id="external-provider"
                        type="button"
                        role="combobox"
                        aria-haspopup="listbox"
                        aria-expanded={providerOpen}
                        disabled={saving}
                        className={cn(
                          SELECT_CLASS,
                          "max-w-xs items-center justify-between gap-2",
                        )}
                      >
                        <span className="flex min-w-0 items-center gap-2">
                          <ProviderLogo
                            id={shownProviderId}
                            name={providerName(shownProviderId)}
                          />
                          <span className="truncate">
                            {providerName(shownProviderId)}
                          </span>
                        </span>
                        <ChevronDown className="h-4 w-4 shrink-0 opacity-50" />
                      </button>
                    </PopoverTrigger>
                    <PopoverContent
                      align="start"
                      className="w-[var(--radix-popover-trigger-width)] min-w-56 p-1"
                    >
                      <div role="listbox" aria-labelledby="external-provider">
                        {providers.map(p => {
                          const selected = p.id === provider?.id
                          return (
                            <button
                              key={p.id}
                              type="button"
                              role="option"
                              aria-selected={selected}
                              data-testid={`external-provider-option-${p.id}`}
                              onClick={() => {
                                if (!selected) {
                                  update({ provider: p.id, model: null })
                                  setValidation(null)
                                }
                                setProviderOpen(false)
                              }}
                              className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-sm hover:bg-accent hover:text-accent-foreground focus-visible:bg-accent focus-visible:outline-none"
                            >
                              <ProviderLogo
                                id={p.id}
                                name={providerName(p.id)}
                              />
                              <span className="flex-1 truncate text-left">
                                {providerName(p.id)}
                              </span>
                              <span
                                className={cn(
                                  "h-2 w-2 shrink-0 rounded-full",
                                  p.connected
                                    ? "bg-green-500"
                                    : "bg-muted-foreground/40",
                                )}
                                title={
                                  p.connected
                                    ? t.labels.external.connected
                                    : t.labels.external.notConnected
                                }
                              />
                              <Check
                                className={cn(
                                  "h-4 w-4 shrink-0",
                                  !selected && "invisible",
                                )}
                              />
                            </button>
                          )
                        })}
                      </div>
                    </PopoverContent>
                  </Popover>
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
                      ? t.labels.external.unavailableHere
                      : provider.connected
                        ? t.labels.external.connected
                        : t.labels.external.notConnected}
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
                      {t.labels.external.connectProvider}
                    </Button>
                  )}
                </div>
              </div>

              {providerUnavailable && (
                <div
                  className="flex items-start gap-2 rounded-md border border-amber-500/40 bg-amber-50 p-3 text-xs text-amber-800 dark:bg-amber-900/10 dark:text-amber-300"
                  data-testid="external-provider-unavailable"
                >
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>
                    {t.labels.external.providerUnavailable.replace(
                      "{provider}",
                      providerName(shownProviderId),
                    )}
                  </span>
                </div>
              )}

              {provider && (
                <div className="space-y-2.5">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <FieldLabel>{t.labels.external.model}</FieldLabel>
                    {provider.id === LOCAL_MODELS_PROVIDER &&
                      provider.connected && (
                        <>
                          <Button
                            variant="link"
                            size="sm"
                            className="h-auto gap-1 px-1"
                            onClick={() => setManagerOpen(true)}
                            data-testid="external-manage-models"
                          >
                            <Settings2 className="h-3.5 w-3.5" />
                            {t.labels.external.manageModels}
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
                      {t.labels.external.loadingModels}
                    </div>
                  )}
                  {dynamicModelsFailed && (
                    <p className="text-xs text-red-600 dark:text-red-400">
                      {t.labels.external.modelsError}
                    </p>
                  )}
                  {dynamicModels && dynamicModels.length === 0 && (
                    <p className="text-xs text-muted-foreground">
                      {t.labels.external.noModelsAvailable}
                    </p>
                  )}
                  {showModelSearch && (
                    <div className="relative">
                      <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                      <Input
                        value={modelQuery}
                        onChange={event => setModelQuery(event.target.value)}
                        placeholder={t.labels.external.searchModels}
                        aria-label={t.labels.external.searchModels}
                        className="h-9 pl-8"
                        disabled={saving}
                      />
                    </div>
                  )}
                  <div
                    role="radiogroup"
                    aria-label={t.labels.external.model}
                    className="space-y-2"
                  >
                    {visibleModels.length > 0 && (
                      <div
                        className={cn(
                          "grid grid-cols-1 gap-2 md:grid-cols-2",
                          dynamicProviderId &&
                            "-m-1 max-h-80 overflow-y-auto p-1",
                        )}
                        data-testid="external-model-options"
                      >
                        {visibleModels.map(model => {
                          const checked = modelChoice === model.id
                          return (
                            <label
                              key={model.id}
                              className={modelOptionClass(checked)}
                            >
                              <input
                                type="radio"
                                name="external-model"
                                className="sr-only"
                                checked={checked}
                                onChange={() => {
                                  setModelChoice(model.id)
                                  setValidation(null)
                                  setError(null)
                                }}
                                disabled={saving}
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
                                  !!model.size) && (
                                  <span className="flex flex-wrap gap-1 pt-0.5">
                                    {model.probabilistic && (
                                      <ModelChip className="border-violet-500/30 bg-violet-500/10 text-violet-700 dark:text-violet-300">
                                        <Sparkles className="h-2.5 w-2.5" />
                                        {t.labels.external.decisionModel}
                                      </ModelChip>
                                    )}
                                    {model.loaded && (
                                      <ModelChip className="border-green-500/30 bg-green-500/10 text-green-700 dark:text-green-400">
                                        <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
                                        {t.labels.external.modelLoaded}
                                      </ModelChip>
                                    )}
                                    {model.load_failed && (
                                      <ModelChip className="border-red-500/30 bg-red-500/10 text-red-600 dark:text-red-400">
                                        <span className="h-1.5 w-1.5 rounded-full bg-red-500" />
                                        {t.labels.external.modelFailed}
                                      </ModelChip>
                                    )}
                                    {!!model.size && (
                                      <ModelChip className="border-border bg-muted/60 text-muted-foreground">
                                        <HardDrive className="h-2.5 w-2.5" />
                                        {formatFileSize(model.size)}
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
                        {t.labels.external.noModelsMatch}
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
                            name="external-model"
                            className="sr-only"
                            checked={customSelected}
                            onChange={() => {
                              setModelChoice(CUSTOM_MODEL)
                              setError(null)
                            }}
                            disabled={saving}
                          />
                          <RadioMark checked={customSelected} />
                          <span className="min-w-0 flex-1 space-y-0.5">
                            <span className="flex items-center gap-1.5 text-sm font-medium leading-tight">
                              <PenLine className="h-3.5 w-3.5 text-muted-foreground" />
                              {t.labels.external.customModel}
                            </span>
                            <span className="block text-xs text-muted-foreground">
                              {provider.dynamic_models
                                ? t.labels.external.customModelUnlistedHint
                                : t.labels.external.customModelHint.replace(
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
                                }}
                                placeholder={
                                  (
                                    t.labels.external
                                      .customModelPlaceholders as Record<
                                      string,
                                      string
                                    >
                                  )[provider.id] ??
                                  t.labels.external.customModelPlaceholder
                                }
                                aria-label={t.labels.external.customModel}
                                className="h-9 min-w-0 flex-1 basis-56 font-mono"
                                disabled={saving}
                              />
                              {provider.upstream_providers && (
                                <Input
                                  value={draft.upstreamProvider ?? ""}
                                  onChange={event => {
                                    update({
                                      upstreamProvider: event.target.value,
                                    })
                                    setValidation(null)
                                  }}
                                  placeholder={
                                    t.labels.external
                                      .upstreamProviderPlaceholder
                                  }
                                  aria-label={
                                    t.labels.external.upstreamProvider
                                  }
                                  className="h-9 w-44 font-mono"
                                  disabled={saving}
                                />
                              )}
                              {!provider.dynamic_models && (
                                <Button
                                  variant="outline"
                                  size="sm"
                                  className="h-9"
                                  onClick={handleValidate}
                                  disabled={
                                    saving ||
                                    validating ||
                                    !customModel.trim() ||
                                    !provider.connected
                                  }
                                >
                                  {validating
                                    ? t.common.loading
                                    : t.labels.external.validate}
                                </Button>
                              )}
                            </div>
                            {validation === "valid" && (
                              <p className="flex items-center gap-1 text-xs text-green-600 dark:text-green-400">
                                <CheckCircle2 className="h-3.5 w-3.5" />
                                {t.labels.external.modelValid}
                              </p>
                            )}
                            {validation === "invalid" && (
                              <p className="flex items-center gap-1 text-xs text-red-600 dark:text-red-400">
                                <XCircle className="h-3.5 w-3.5" />
                                {t.labels.external.modelInvalid}
                              </p>
                            )}
                            {provider.upstream_providers && (
                              <p className="text-xs text-muted-foreground">
                                {t.labels.external.upstreamProviderHint}
                              </p>
                            )}
                            <p className="flex items-start gap-1.5 text-xs text-muted-foreground">
                              <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                              {t.labels.external.customModelNotice}
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
                        {t.labels.external.modelUnavailable.replace(
                          "{model}",
                          stored.model ?? "",
                        )}
                      </span>
                    </div>
                  )}
                  {selectedModelFailed && (
                    <div
                      className="flex items-start gap-2 rounded-md border border-red-500/40 bg-red-50 p-3 text-xs text-red-800 dark:bg-red-900/10 dark:text-red-300"
                      data-testid="external-model-load-failed"
                    >
                      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                      <span>
                        {t.labels.external.modelLoadFailed.replace(
                          "{model}",
                          selectedRecommended?.name ?? "",
                        )}
                      </span>
                    </div>
                  )}
                  {smallModelSelected && !selectedModelFailed && (
                    <div
                      className="flex items-start gap-2 rounded-md border border-amber-500/40 bg-amber-50 p-3 text-xs text-amber-800 dark:bg-amber-900/10 dark:text-amber-300"
                      data-testid="external-small-model-warning"
                    >
                      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                      <span>{t.labels.external.smallModelWarning}</span>
                    </div>
                  )}
                </div>
              )}

              {provider && (
                <p className="text-xs text-muted-foreground">
                  {t.labels.external.privacyNotice}
                </p>
              )}

              <div>
                <button
                  type="button"
                  onClick={() => setMoreOpen(open => !open)}
                  aria-expanded={moreOpen}
                  className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
                >
                  {t.labels.external.moreSettings}
                  <ChevronDown
                    className={cn(
                      "h-4 w-4 transition-transform duration-200",
                      moreOpen && "rotate-180",
                    )}
                  />
                </button>
                <AnimatePresence initial={false}>
                  {moreOpen && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.2, ease: "easeInOut" }}
                      className="-mx-1 overflow-hidden px-1"
                    >
                      <div className="space-y-5 pb-1 pt-4">
                        <SettingRow
                          title={t.labels.external.autoRun}
                          hint={t.labels.external.autoRunHint}
                        >
                          <Switch
                            checked={draft.autoRun}
                            onCheckedChange={value =>
                              update({ autoRun: value })
                            }
                            disabled={saving}
                          />
                        </SettingRow>

                        <SettingRow
                          title={t.labels.external.minConfidence}
                          hint={
                            selectedRecommended &&
                            !selectedRecommended.probabilistic
                              ? t.labels.external.minConfidenceNotApplicable
                              : t.labels.external.minConfidenceHint
                          }
                        >
                          <Input
                            type="number"
                            min={0}
                            max={100}
                            value={draft.minConfidence}
                            onChange={event =>
                              update({
                                minConfidence: clampInt(
                                  event.target.value,
                                  0,
                                  100,
                                  70,
                                ),
                              })
                            }
                            className="h-8 w-20"
                            aria-label={t.labels.external.minConfidence}
                            disabled={saving}
                          />
                        </SettingRow>

                        <SettingRow
                          title={t.labels.external.maxPerRun}
                          hint={t.labels.external.maxPerRunHint}
                        >
                          <Input
                            type="number"
                            min={1}
                            max={2000}
                            value={draft.maxPerRun}
                            onChange={event =>
                              update({
                                maxPerRun: clampInt(
                                  event.target.value,
                                  1,
                                  2000,
                                  400,
                                ),
                              })
                            }
                            className="h-8 w-20"
                            aria-label={t.labels.external.maxPerRun}
                            disabled={saving}
                          />
                        </SettingRow>

                        <SettingRow
                          title={t.labels.external.examples}
                          hint={t.labels.external.examplesHint}
                        >
                          {draft.examples.enabled && (
                            <Input
                              type="number"
                              min={1}
                              max={50}
                              value={draft.examples.count}
                              onChange={event =>
                                update({
                                  examples: {
                                    ...draft.examples,
                                    count: clampInt(
                                      event.target.value,
                                      1,
                                      50,
                                      20,
                                    ),
                                  },
                                })
                              }
                              className="h-8 w-20"
                              aria-label={t.labels.external.examplesCount}
                              disabled={saving}
                            />
                          )}
                          <Switch
                            checked={draft.examples.enabled}
                            onCheckedChange={value =>
                              update({
                                examples: { ...draft.examples, enabled: value },
                              })
                            }
                            disabled={saving}
                          />
                        </SettingRow>

                        {draft.examples.enabled && (
                          <div
                            className="-mt-3 flex flex-wrap items-center gap-2"
                            data-testid="external-examples-origins"
                          >
                            <span className="text-xs text-muted-foreground">
                              {t.labels.external.examplesFrom}
                            </span>
                            {EXAMPLE_ORIGINS.map(origin => {
                              const selected =
                                draft.examples.origins.includes(origin)
                              const lastSelected =
                                selected && draft.examples.origins.length === 1
                              return (
                                <button
                                  key={origin}
                                  type="button"
                                  aria-pressed={selected}
                                  disabled={saving || lastSelected}
                                  onClick={() =>
                                    update({
                                      examples: {
                                        ...draft.examples,
                                        origins: selected
                                          ? draft.examples.origins.filter(
                                              value => value !== origin,
                                            )
                                          : EXAMPLE_ORIGINS.filter(
                                              value =>
                                                value === origin ||
                                                draft.examples.origins.includes(
                                                  value,
                                                ),
                                            ),
                                      },
                                    })
                                  }
                                  className={cn(
                                    "rounded-full border px-3 py-1 text-xs font-medium transition-colors disabled:cursor-not-allowed",
                                    selected
                                      ? "border-foreground bg-foreground text-background"
                                      : "border-border text-muted-foreground hover:text-foreground",
                                  )}
                                >
                                  {t.labels.origins[origin]}
                                </button>
                              )
                            })}
                          </div>
                        )}

                        <div className="space-y-1.5">
                          <div className="flex items-baseline justify-between gap-2">
                            <FieldLabel htmlFor="external-instructions">
                              {t.labels.external.instructions}
                            </FieldLabel>
                            <span className="text-[11px] tabular-nums text-muted-foreground">
                              {(draft.instructions ?? "").length}/
                              {MAX_INSTRUCTIONS_LENGTH}
                            </span>
                          </div>
                          <p className="text-xs text-muted-foreground">
                            {t.labels.external.instructionsHint}
                          </p>
                          <textarea
                            id="external-instructions"
                            value={draft.instructions ?? ""}
                            maxLength={MAX_INSTRUCTIONS_LENGTH}
                            rows={4}
                            placeholder={
                              t.labels.external.instructionsPlaceholder
                            }
                            onChange={event =>
                              update({ instructions: event.target.value })
                            }
                            disabled={saving}
                            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                          />
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </div>
          ))}

        {error && (
          <p className="text-sm text-red-600 dark:text-red-400" role="alert">
            {error}
          </p>
        )}

        {dirty && (
          <div className="flex flex-wrap items-center justify-end gap-3">
            {providerDisconnected && (
              <p className="text-xs text-yellow-700 dark:text-yellow-400">
                {t.labels.external.connectRequired}
              </p>
            )}
            <Button
              size="sm"
              onClick={handleSave}
              disabled={saving || providerDisconnected}
            >
              {saving ? t.common.saving : t.common.save}
            </Button>
          </div>
        )}
      </div>
    </ExternalSuggestionsSurface>
  )
}
