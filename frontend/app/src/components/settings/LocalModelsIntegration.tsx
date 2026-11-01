import { useCallback, useEffect, useRef, useState, type ReactNode } from "react"
import { AlertTriangle, Cpu, Info, Server, Settings2 } from "lucide-react"
import { useI18n } from "@/i18n"
import { Badge } from "@/components/ui/Badge"
import { Button } from "@/components/ui/Button"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { cn } from "@/lib/utils"
import { LocalModelState } from "@/types/ai"
import {
  FailedDownloads,
  downloadProgress,
  useDownloadFailures,
} from "./LocalModelsManager"
import {
  ACTIVE_LOCAL_MODEL_STATES,
  LocalModelsDialog,
  localModelsSourceLabel,
  useLocalModelsOverview,
} from "./LocalModelsDialog"

const MAX_SUMMARY_MODELS = 5

export interface IntegrationFieldOptions {
  placeholders?: Record<string, string>
  labelSuffix?: string
}

interface LocalModelsIntegrationProps {
  enabled: boolean
  openManager?: boolean
  renderFields: (options?: IntegrationFieldOptions) => ReactNode
  renderActions: (options: { setup: boolean }) => ReactNode
  onServerModeChange: (serverMode: boolean) => void
}

function Notice({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-start gap-2 rounded-md bg-muted/50 p-3 text-xs text-muted-foreground">
      <Info className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="space-y-1">{children}</div>
    </div>
  )
}

export function LocalModelsIntegration({
  enabled,
  openManager = false,
  renderFields,
  renderActions,
  onServerModeChange,
}: LocalModelsIntegrationProps) {
  const { t } = useI18n()
  const copy = t.settings.localModels
  const { overview, loadFailed, load } = useLocalModelsOverview(true, enabled)
  const [retrying, setRetrying] = useState(false)
  const [serverMode, setServerMode] = useState(false)
  const [managerOpen, setManagerOpen] = useState(false)
  const autoOpenedRef = useRef(false)
  const failures = useDownloadFailures(enabled ? overview?.models : undefined)
  const managerVisible = managerOpen && enabled && !!overview?.reachable
  const closeManager = useCallback(() => setManagerOpen(false), [])

  useEffect(() => {
    if (
      openManager &&
      enabled &&
      overview?.reachable &&
      !autoOpenedRef.current
    ) {
      autoOpenedRef.current = true
      setManagerOpen(true)
    }
  }, [openManager, enabled, overview?.reachable])

  const handleRetry = async () => {
    setRetrying(true)
    try {
      await load(true)
    } finally {
      setRetrying(false)
    }
  }

  const selectMode = (server: boolean) => {
    setServerMode(server)
    onServerModeChange(server)
  }

  if (!overview) {
    if (!loadFailed) {
      return (
        <div className="flex justify-center py-4">
          <LoadingSpinner size="sm" />
        </div>
      )
    }
    return (
      <div className="flex items-center justify-between gap-2 text-sm text-muted-foreground">
        <span>{t.common.fetchError}</span>
        <Button
          variant="outline"
          size="sm"
          onClick={() => void handleRetry()}
          disabled={retrying}
        >
          {t.common.retry}
        </Button>
      </div>
    )
  }

  if (enabled) {
    const usingLabel = localModelsSourceLabel(
      copy.using as Record<string, string>,
      overview,
    )
    const errorLabel = overview.error
      ? ((copy.errors as Record<string, string>)[overview.error] ??
        t.common.error)
      : null

    const summaryModels = overview.models.slice(0, MAX_SUMMARY_MODELS)
    const hiddenModels = overview.models.length - summaryModels.length

    return (
      <div className="space-y-4" data-testid="local-models-status">
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-md bg-muted/50 px-3 py-2 text-sm">
          <span className="inline-flex min-w-0 items-center gap-2">
            <span
              className={cn(
                "h-2 w-2 shrink-0 rounded-full",
                overview.reachable ? "bg-green-500" : "bg-red-500",
              )}
            />
            <span className="break-all">{usingLabel}</span>
          </span>
          {!overview.reachable && (
            <span className="text-xs text-red-600 dark:text-red-400">
              {copy.unreachable}
            </span>
          )}
        </div>
        {errorLabel && (
          <div className="flex items-start gap-2 rounded-md border border-red-500/40 bg-red-50 p-3 text-xs text-red-800 dark:bg-red-900/10 dark:text-red-300">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <span className="flex-1">{errorLabel}</span>
            <Button
              variant="outline"
              size="sm"
              className="h-7"
              onClick={() => void handleRetry()}
              disabled={retrying}
            >
              {retrying ? <LoadingSpinner size="sm" /> : t.common.retry}
            </Button>
          </div>
        )}
        {overview.reachable && (
          <>
            <FailedDownloads failures={failures} />
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border p-3">
              <div className="min-w-0 flex-1">
                {summaryModels.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5">
                    {summaryModels.map(model => {
                      const progress = downloadProgress(model)
                      const failed = model.state === LocalModelState.FAILED
                      return (
                        <Badge
                          key={model.id}
                          variant="outline"
                          className={cn(
                            "max-w-full gap-1.5 font-normal",
                            failed &&
                              "border-red-500/40 text-red-600 dark:text-red-400",
                          )}
                          title={
                            failed
                              ? (copy.states as Record<string, string>)[
                                  model.state
                                ]
                              : undefined
                          }
                        >
                          {ACTIVE_LOCAL_MODEL_STATES.has(model.state) && (
                            <LoadingSpinner size="sm" className="h-3 w-3" />
                          )}
                          {failed && (
                            <AlertTriangle className="h-3 w-3 shrink-0" />
                          )}
                          <span className="truncate">{model.name}</span>
                          {progress != null && (
                            <span className="text-muted-foreground">
                              {progress}%
                            </span>
                          )}
                        </Badge>
                      )
                    })}
                    {hiddenModels > 0 && (
                      <Badge
                        variant="outline"
                        className="font-normal text-muted-foreground"
                      >
                        {copy.moreModels.replace(
                          "{count}",
                          String(hiddenModels),
                        )}
                      </Badge>
                    )}
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    {copy.noModels}
                  </p>
                )}
              </div>
              <Button
                size="sm"
                variant={summaryModels.length > 0 ? "outline" : "default"}
                className="shrink-0"
                onClick={() => setManagerOpen(true)}
              >
                <Settings2 className="mr-1.5 h-4 w-4" />
                {copy.manage}
              </Button>
            </div>
          </>
        )}
        {renderActions({ setup: false })}
        <LocalModelsDialog
          open={managerVisible}
          onClose={closeManager}
          overview={overview}
          loadFailed={loadFailed}
          onReload={load}
          failures={failures}
        />
      </div>
    )
  }

  const capabilities = overview.capabilities
  const envUrl = capabilities.env_server_url || null
  const showModeSelector = capabilities.built_in_available && !envUrl
  const showFields = !showModeSelector || serverMode
  const fieldOptions: IntegrationFieldOptions = envUrl
    ? {
        placeholders: {
          server_url: envUrl,
          ...(capabilities.env_api_key_set
            ? { api_key: copy.envKeyPlaceholder }
            : {}),
        },
        labelSuffix: copy.overridesEnvironment,
      }
    : {}

  return (
    <div className="space-y-4">
      {showModeSelector && (
        <div className="grid grid-cols-2 gap-2" role="radiogroup">
          {[false, true].map(server => {
            const selected = serverMode === server
            const Icon = server ? Server : Cpu
            return (
              <button
                key={String(server)}
                type="button"
                role="radio"
                aria-checked={selected}
                onClick={() => selectMode(server)}
                className={cn(
                  "flex items-center gap-2 rounded-md border p-3 text-left text-sm transition-colors",
                  selected
                    ? "border-primary bg-primary/5 font-medium"
                    : "border-border hover:bg-muted/50",
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                {server ? copy.serverMode : copy.builtInMode}
              </button>
            )
          })}
        </div>
      )}
      {envUrl ? (
        <Notice>
          <p>
            {copy.envUrlNotice
              .replace("{url}", envUrl)
              .replace(
                "{key}",
                capabilities.env_api_key_set ? copy.envKeySuffix : "",
              )}
          </p>
          {capabilities.built_in_available && <p>{copy.precedence}</p>}
        </Notice>
      ) : (
        <Notice>
          <p>
            {showModeSelector && !serverMode
              ? copy.builtInNotice
              : copy.serverNotice}
          </p>
        </Notice>
      )}
      {showFields && renderFields(fieldOptions)}
      {renderActions({ setup: true })}
    </div>
  )
}
