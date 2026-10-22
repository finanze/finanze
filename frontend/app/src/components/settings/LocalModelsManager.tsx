import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import {
  AlertTriangle,
  Download,
  FileUp,
  FolderOpen,
  RefreshCw,
  Search,
  Trash2,
  X,
} from "lucide-react"
import { useI18n } from "@/i18n"
import { useAppContext } from "@/context/AppContext"
import { Badge } from "@/components/ui/Badge"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { ConfirmationDialog } from "@/components/ui/ConfirmationDialog"
import {
  deleteLocalModel,
  downloadLocalModel,
  getApiServerInfo,
  getHuggingFaceQuants,
  importLocalModel,
} from "@/services/api"
import { cn } from "@/lib/utils"
import { formatFileSize } from "@/utils/releaseUtils"
import {
  HuggingFaceModelKind,
  LocalModelSource,
  LocalModelState,
  LocalRuntimeMode,
  type DownloadLocalModelRequest,
  type HuggingFaceQuants,
  type LocalModel,
  type LocalModelCatalogEntry,
  type LocalModelsOverview,
} from "@/types/ai"

const HUGGING_FACE_REPO_REGEX =
  /^[A-Za-z0-9][A-Za-z0-9._-]{0,95}\/[A-Za-z0-9][A-Za-z0-9._-]{0,95}$/
const HUGGING_FACE_URL_PREFIX = /^https?:\/\/(www\.)?huggingface\.co\//i
const PREFERRED_QUANT = "Q4_K_M"
const GIB = 1024 ** 3
const RAM_WARNING_RATIOS: [number, number][] = [
  [4, 0.4],
  [6, 0.5],
  [8, 0.6],
  [16, 0.7],
  [32, 0.75],
]

export const ramWarningRatio = (memory: number) => {
  const gib = memory / GIB
  const upper = RAM_WARNING_RATIOS.findIndex(([size]) => gib <= size)
  if (upper === 0) return RAM_WARNING_RATIOS[0][1]
  if (upper === -1) return RAM_WARNING_RATIOS[RAM_WARNING_RATIOS.length - 1][1]
  const [lowSize, lowRatio] = RAM_WARNING_RATIOS[upper - 1]
  const [highSize, highRatio] = RAM_WARNING_RATIOS[upper]
  return (
    lowRatio + ((gib - lowSize) / (highSize - lowSize)) * (highRatio - lowRatio)
  )
}

const STATE_CLASSES: Record<LocalModelState, string> = {
  [LocalModelState.UNLOADED]: "text-muted-foreground",
  [LocalModelState.LOADING]: "text-amber-600 dark:text-amber-400",
  [LocalModelState.LOADED]: "text-green-600 dark:text-green-400",
  [LocalModelState.SLEEPING]: "text-blue-600 dark:text-blue-400",
  [LocalModelState.DOWNLOADING]: "text-amber-600 dark:text-amber-400",
  [LocalModelState.FAILED]: "text-red-600 dark:text-red-400",
  [LocalModelState.MISSING]: "text-red-600 dark:text-red-400",
}

const normalizeRepo = (value: string) =>
  value
    .trim()
    .replace(HUGGING_FACE_URL_PREFIX, "")
    .split(/[/?#]/)
    .slice(0, 2)
    .join("/")

export const downloadProgress = (model: LocalModel) =>
  model.state === LocalModelState.DOWNLOADING &&
  model.size &&
  model.downloaded != null
    ? Math.min(100, Math.round((model.downloaded / model.size) * 100))
    : null

const modelRepo = (id: string) => id.split(":")[0].toLowerCase()

export function useDownloadFailures(models: LocalModel[] | undefined) {
  const [failed, setFailed] = useState<string[]>([])
  const downloadingRef = useRef<Map<string, string>>(new Map())
  const knownRef = useRef<Set<string>>(new Set())
  const cancelledRef = useRef<Set<string>>(new Set())

  useEffect(() => {
    if (!models) {
      downloadingRef.current = new Map()
      knownRef.current = new Set()
      return
    }
    const present = new Set(models.map(model => model.id))
    const appeared = new Set(
      models
        .filter(
          model =>
            !knownRef.current.has(model.id) &&
            model.state !== LocalModelState.DOWNLOADING,
        )
        .map(model => modelRepo(model.id)),
    )
    const vanished = [...downloadingRef.current]
      .filter(
        ([id]) =>
          !present.has(id) &&
          !cancelledRef.current.has(id) &&
          !appeared.has(modelRepo(id)),
      )
      .map(([, name]) => name)
    if (vanished.length > 0) {
      setFailed(prev => [
        ...prev,
        ...vanished.filter(name => !prev.includes(name)),
      ])
    }
    knownRef.current = present
    downloadingRef.current = new Map(
      models
        .filter(model => model.state === LocalModelState.DOWNLOADING)
        .map(model => [model.id, model.name]),
    )
  }, [models])

  const dismiss = useCallback(
    (name: string) => setFailed(prev => prev.filter(item => item !== name)),
    [],
  )
  const markCancelled = useCallback((id: string) => {
    cancelledRef.current.add(id)
  }, [])

  return { failed, dismiss, markCancelled }
}

export type DownloadFailures = ReturnType<typeof useDownloadFailures>

export function FailedDownloads({ failures }: { failures: DownloadFailures }) {
  const { t } = useI18n()
  return (
    <>
      {failures.failed.map(name => (
        <div
          key={name}
          className="flex items-start gap-2 rounded-md border border-red-500/40 bg-red-50 p-3 text-xs text-red-800 dark:bg-red-900/10 dark:text-red-300"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span className="flex-1">
            {t.settings.localModels.downloadFailed.replace("{model}", name)}
          </span>
          <button
            type="button"
            onClick={() => failures.dismiss(name)}
            aria-label={t.common.close}
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      ))}
    </>
  )
}

export function LocalModelsManager({
  overview,
  onReload,
  failures,
}: {
  overview: LocalModelsOverview
  onReload: (refresh?: boolean) => Promise<void>
  failures: DownloadFailures
}) {
  const { t } = useI18n()
  const { showToast } = useAppContext()
  const copy = t.settings.localModels
  const [customServer, setCustomServer] = useState(true)
  const [busy, setBusy] = useState<Record<string, boolean>>({})
  const [refreshing, setRefreshing] = useState(false)
  const [pendingDelete, setPendingDelete] = useState<LocalModel | null>(null)
  const [repoInput, setRepoInput] = useState("")
  const [repoError, setRepoError] = useState<string | null>(null)
  const [quants, setQuants] = useState<HuggingFaceQuants | null>(null)
  const [selectedQuant, setSelectedQuant] = useState("")
  const [searching, setSearching] = useState(false)

  const builtIn = overview.mode === LocalRuntimeMode.BUILT_IN
  const capabilities = overview.capabilities

  useEffect(() => {
    getApiServerInfo()
      .then(info => setCustomServer(info.isCustomServer))
      .catch(() => setCustomServer(true))
  }, [])

  const installedIds = useMemo(
    () => new Set(overview.models.map(model => model.id)),
    [overview.models],
  )
  const catalog = overview.catalog.filter(entry => !installedIds.has(entry.id))

  const canImport =
    builtIn &&
    capabilities.can_import_files &&
    !customServer &&
    !!window.ipcAPI?.selectFile
  const canOpenFolder =
    builtIn &&
    !!overview.models_folder &&
    !customServer &&
    !!window.ipcAPI?.showItemInFolder

  const errorMessage = useCallback(
    (error: unknown) => {
      const code = (error as { code?: string } | null)?.code
      return (
        (code && (copy.errors as Record<string, string>)[code]) ||
        t.common.error
      )
    },
    [copy.errors, t.common.error],
  )

  const runAction = useCallback(
    async (key: string, action: () => Promise<void>) => {
      setBusy(prev => ({ ...prev, [key]: true }))
      try {
        await action()
      } catch (error) {
        console.error(error)
        showToast(errorMessage(error), "error", { reportable: false })
      } finally {
        setBusy(prev => ({ ...prev, [key]: false }))
      }
    },
    [errorMessage, showToast],
  )

  const handleRefresh = async () => {
    setRefreshing(true)
    try {
      await onReload(true)
    } finally {
      setRefreshing(false)
    }
  }

  const startDownload = (
    key: string,
    name: string,
    request: DownloadLocalModelRequest,
  ) =>
    runAction(key, async () => {
      await downloadLocalModel(request)
      failures.dismiss(name)
      showToast(copy.downloadStarted.replace("{model}", name), "success")
      await onReload()
    })

  const handleCatalogDownload = (entry: LocalModelCatalogEntry) =>
    startDownload(`catalog-${entry.id}`, entry.name, { catalog_id: entry.id })

  const handleFindQuants = async () => {
    const repo = normalizeRepo(repoInput)
    setQuants(null)
    setRepoError(null)
    if (!HUGGING_FACE_REPO_REGEX.test(repo)) {
      setRepoError(copy.invalidRepo)
      return
    }
    setSearching(true)
    try {
      const result = await getHuggingFaceQuants(repo)
      setQuants(result)
      const preferred =
        result.quants.find(option => option.quant === PREFERRED_QUANT) ??
        result.quants[0]
      setSelectedQuant(preferred?.quant ?? "")
      if (result.quants.length === 0) {
        setRepoError(copy.noQuants)
      }
    } catch (error) {
      console.error(error)
      setRepoError(errorMessage(error))
    } finally {
      setSearching(false)
    }
  }

  const handleQuantDownload = () => {
    if (!quants || !selectedQuant) return
    const id = `${quants.repo}:${selectedQuant}`
    void startDownload("huggingface", id, {
      repo: quants.repo,
      quant: selectedQuant,
    })
  }

  const handleImport = async () => {
    const path = await window.ipcAPI?.selectFile?.({
      title: copy.importTitle,
      extensions: ["gguf"],
    })
    if (!path) return
    await runAction("import", async () => {
      const imported = await importLocalModel(path)
      showToast(copy.importSuccess.replace("{model}", imported.id), "success")
      await onReload()
    })
  }

  const handleCancelDownload = (model: LocalModel) =>
    runAction(`delete-${model.id}`, async () => {
      failures.markCancelled(model.id)
      await deleteLocalModel(model.id)
      await onReload()
    })

  const handleConfirmDelete = async () => {
    const model = pendingDelete
    if (!model) return
    await runAction(`delete-${model.id}`, async () => {
      await deleteLocalModel(model.id)
      showToast(copy.deleted.replace("{model}", model.name), "success")
      await onReload()
    })
    setPendingDelete(null)
  }

  const exceedsMemory = (bytes?: number | null) =>
    !!capabilities.system_memory &&
    !!bytes &&
    bytes >
      capabilities.system_memory * ramWarningRatio(capabilities.system_memory)

  const renderModel = (model: LocalModel) => {
    const downloading = model.state === LocalModelState.DOWNLOADING
    const progress = downloadProgress(model)
    const deleting = !!busy[`delete-${model.id}`]
    const stateLabel = (copy.states as Record<string, string>)[model.state]

    return (
      <div
        key={model.id}
        className="flex items-start justify-between gap-3 rounded-md border border-border p-3"
        data-testid={`local-model-${model.id}`}
      >
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="truncate text-sm font-medium">{model.name}</span>
            <Badge variant="outline" className="text-[10px]">
              {(copy.sources as Record<string, string>)[model.source]}
            </Badge>
            {model.decisions && (
              <Badge variant="outline" className="text-[10px]">
                {copy.decisions}
              </Badge>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span
              className={cn(
                "inline-flex items-center gap-1",
                STATE_CLASSES[model.state],
              )}
            >
              {(downloading || model.state === LocalModelState.LOADING) && (
                <LoadingSpinner size="sm" className="h-3 w-3" />
              )}
              {stateLabel}
              {progress != null && ` ${progress}%`}
            </span>
            {model.size ? (
              <span className="text-muted-foreground">
                {downloading && model.downloaded != null
                  ? `${formatFileSize(model.downloaded)} / ${formatFileSize(model.size)}`
                  : formatFileSize(model.size)}
              </span>
            ) : null}
          </div>
          {downloading && (
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
              <div
                className={cn(
                  "h-full rounded-full bg-violet-500 transition-all",
                  progress == null && "w-1/3 animate-pulse",
                )}
                style={progress != null ? { width: `${progress}%` } : undefined}
              />
            </div>
          )}
          {model.state === LocalModelState.FAILED && (
            <p
              className="flex items-start gap-1 text-xs text-red-600 dark:text-red-400"
              data-testid={`local-model-failed-${model.id}`}
            >
              <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
              <span>
                {copy.failedHint}
                {builtIn && ` ${copy.failedLogHint}`}
              </span>
            </p>
          )}
          {model.path && (
            <p className="truncate font-mono text-xs text-muted-foreground">
              {model.path}
            </p>
          )}
        </div>
        {downloading ? (
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 shrink-0"
            onClick={() => void handleCancelDownload(model)}
            disabled={deleting}
            aria-label={copy.cancelDownload}
            title={copy.cancelDownload}
          >
            {deleting ? (
              <LoadingSpinner size="sm" />
            ) : (
              <X className="h-4 w-4" />
            )}
          </Button>
        ) : model.deletable ? (
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 shrink-0 text-muted-foreground hover:text-red-600"
            onClick={() => setPendingDelete(model)}
            disabled={deleting}
            aria-label={t.common.delete}
            title={t.common.delete}
          >
            {deleting ? (
              <LoadingSpinner size="sm" />
            ) : (
              <Trash2 className="h-4 w-4" />
            )}
          </Button>
        ) : null}
      </div>
    )
  }

  const renderCatalogEntry = (entry: LocalModelCatalogEntry) => {
    const key = `catalog-${entry.id}`
    const ramWarning = exceedsMemory(entry.ram)
    return (
      <div
        key={entry.id}
        className="flex items-start justify-between gap-3 rounded-md border border-dashed border-border p-3"
        data-testid={`local-catalog-${entry.id}`}
      >
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-sm font-medium">{entry.name}</span>
            {entry.decisions && (
              <Badge variant="outline" className="text-[10px]">
                {copy.decisions}
              </Badge>
            )}
          </div>
          <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
            <span>{copy.params.replace("{params}", entry.params)}</span>
            <span>
              {copy.downloadSize.replace("{size}", formatFileSize(entry.size))}
            </span>
            <span
              className={cn(ramWarning && "text-amber-600 dark:text-amber-400")}
              title={ramWarning ? copy.ramWarning : undefined}
            >
              {copy.ram.replace("{ram}", formatFileSize(entry.ram))}
            </span>
            <span>{entry.license}</span>
          </div>
          {entry.languages && entry.languages.length > 0 && (
            <p className="text-xs text-muted-foreground">
              {copy.languages.replace(
                "{languages}",
                entry.languages.join(", "),
              )}
            </p>
          )}
          {ramWarning && (
            <p className="inline-flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400">
              <AlertTriangle className="h-3 w-3" />
              {copy.ramWarning}
            </p>
          )}
        </div>
        <Button
          variant="outline"
          size="sm"
          className="shrink-0"
          onClick={() => void handleCatalogDownload(entry)}
          disabled={!!busy[key]}
        >
          {busy[key] ? (
            <LoadingSpinner size="sm" />
          ) : (
            <>
              <Download className="h-4 w-4 sm:mr-1.5" />
              <span className="hidden sm:inline">{t.common.download}</span>
            </>
          )}
        </Button>
      </div>
    )
  }

  const selectedOption = quants?.quants.find(
    option => option.quant === selectedQuant,
  )
  const unsupportedModel =
    quants !== null &&
    quants.quants.length > 0 &&
    quants.kind === HuggingFaceModelKind.ENCODER

  return (
    <div
      className="grid gap-6 lg:grid-cols-2"
      data-testid="local-models-manager"
    >
      <section className="min-w-0 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h4 className="text-sm font-semibold">{copy.models}</h4>
          <div className="flex flex-wrap items-center gap-1">
            {canOpenFolder && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() =>
                  void window.ipcAPI?.showItemInFolder?.(
                    overview.models_folder as string,
                  )
                }
              >
                <FolderOpen className="h-4 w-4 sm:mr-1.5" />
                <span className="hidden sm:inline">{copy.openFolder}</span>
              </Button>
            )}
            {canImport && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => void handleImport()}
                disabled={!!busy.import}
              >
                {busy.import ? (
                  <LoadingSpinner size="sm" className="sm:mr-1.5" />
                ) : (
                  <FileUp className="h-4 w-4 sm:mr-1.5" />
                )}
                <span className="hidden sm:inline">{copy.import}</span>
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => void handleRefresh()}
              disabled={refreshing}
            >
              <RefreshCw
                className={cn(
                  "h-4 w-4 sm:mr-1.5",
                  refreshing && "animate-spin",
                )}
              />
              <span className="hidden sm:inline">{t.common.refresh}</span>
            </Button>
          </div>
        </div>

        <FailedDownloads failures={failures} />

        {overview.models.length > 0 ? (
          <div className="space-y-2">{overview.models.map(renderModel)}</div>
        ) : (
          <p className="rounded-md border border-dashed border-border p-4 text-center text-sm text-muted-foreground">
            {copy.noModels}
          </p>
        )}

        <p className="text-xs text-muted-foreground">
          {builtIn ? copy.importHint : copy.externalHint}
        </p>
      </section>

      <section className="min-w-0 space-y-6 lg:border-l lg:border-border lg:pl-6">
        {catalog.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-sm font-semibold">{copy.recommended}</h4>
            {catalog.map(renderCatalogEntry)}
          </div>
        )}

        <div className="space-y-2">
          <h4 className="text-sm font-semibold">{copy.huggingFace}</h4>
          <p className="text-xs text-muted-foreground">
            {copy.huggingFaceHint}
          </p>
          <form
            className="flex flex-wrap items-center gap-2"
            onSubmit={event => {
              event.preventDefault()
              void handleFindQuants()
            }}
          >
            <Input
              value={repoInput}
              onChange={event => {
                setRepoInput(event.target.value)
                setRepoError(null)
              }}
              placeholder={copy.repoPlaceholder}
              className="h-9 min-w-0 flex-1 font-mono"
              aria-label={copy.huggingFace}
            />
            <Button
              type="submit"
              variant="outline"
              size="sm"
              disabled={searching || !repoInput.trim()}
            >
              {searching ? (
                <LoadingSpinner size="sm" className="mr-1.5" />
              ) : (
                <Search className="mr-1.5 h-4 w-4" />
              )}
              {copy.find}
            </Button>
          </form>
          {repoError && (
            <p className="text-xs text-red-600 dark:text-red-400">
              {repoError}
            </p>
          )}
          {unsupportedModel && (
            <p
              className="flex items-start gap-1 text-xs text-red-600 dark:text-red-400"
              data-testid="local-model-unsupported"
            >
              <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
              {copy.errors.UNSUPPORTED_MODEL}
            </p>
          )}
          {quants !== null &&
            quants.quants.length > 0 &&
            quants.kind === HuggingFaceModelKind.UNKNOWN && (
              <p className="flex items-start gap-1 text-xs text-amber-600 dark:text-amber-400">
                <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
                {copy.unverifiedModel}
              </p>
            )}
          {quants && !unsupportedModel && quants.quants.length > 0 && (
            <div className="flex flex-wrap items-center gap-2">
              <select
                value={selectedQuant}
                onChange={event => setSelectedQuant(event.target.value)}
                aria-label={copy.variant}
                className="h-9 rounded-md border border-input bg-background px-3 text-sm"
              >
                {quants.quants.map(option => (
                  <option key={option.quant} value={option.quant}>
                    {option.size
                      ? `${option.quant} · ${formatFileSize(option.size)}`
                      : option.quant}
                  </option>
                ))}
              </select>
              <Button
                size="sm"
                onClick={handleQuantDownload}
                disabled={!selectedOption || !!busy.huggingface}
              >
                {busy.huggingface ? (
                  <LoadingSpinner size="sm" color="invert" className="mr-1.5" />
                ) : (
                  <Download className="mr-1.5 h-4 w-4" />
                )}
                {t.common.download}
              </Button>
              {quants.kind === HuggingFaceModelKind.DECISIONS && (
                <Badge variant="outline" className="text-[10px]">
                  {copy.decisions}
                </Badge>
              )}
            </div>
          )}
          {quants &&
            !unsupportedModel &&
            exceedsMemory(selectedOption?.size) && (
              <p
                className="flex items-start gap-1 text-xs text-amber-600 dark:text-amber-400"
                data-testid="local-quant-ram-warning"
              >
                <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
                {copy.ramWarning}
              </p>
            )}
        </div>
      </section>

      <ConfirmationDialog
        isOpen={!!pendingDelete}
        title={copy.deleteTitle}
        message={(pendingDelete?.source === LocalModelSource.IMPORTED
          ? copy.deleteImportedMessage
          : copy.deleteMessage
        ).replace("{model}", pendingDelete?.name ?? "")}
        confirmText={t.common.delete}
        cancelText={t.common.cancel}
        onConfirm={() => void handleConfirmDelete()}
        onCancel={() => setPendingDelete(null)}
        isLoading={!!pendingDelete && !!busy[`delete-${pendingDelete.id}`]}
      />
    </div>
  )
}
