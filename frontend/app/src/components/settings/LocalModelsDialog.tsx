import { useCallback, useEffect, useId, useRef, useState } from "react"
import { createPortal } from "react-dom"
import { AnimatePresence, motion } from "framer-motion"
import { AlertTriangle, X } from "lucide-react"
import { useI18n } from "@/i18n"
import { useModalBackHandler } from "@/hooks/useModalBackHandler"
import { Button } from "@/components/ui/Button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { getLocalModels } from "@/services/api"
import { cn } from "@/lib/utils"
import { LocalModelState, type LocalModelsOverview } from "@/types/ai"
import {
  LocalModelsManager,
  useDownloadFailures,
  type DownloadFailures,
} from "./LocalModelsManager"

const POLL_INTERVAL_MS = 1000
const PENDING_STATES = new Set<LocalModelState>([
  LocalModelState.DOWNLOADING,
  LocalModelState.MISSING,
])

export const ACTIVE_LOCAL_MODEL_STATES = new Set<LocalModelState>([
  LocalModelState.DOWNLOADING,
  LocalModelState.LOADING,
])

export const localModelsSourceLabel = (
  using: Record<string, string>,
  overview: LocalModelsOverview,
) =>
  overview.source
    ? (using[overview.source]?.replace("{url}", overview.server_url ?? "") ??
      null)
    : null

export function useLocalModelsOverview(active: boolean, resetKey?: unknown) {
  const [overview, setOverview] = useState<LocalModelsOverview | null>(null)
  const [loadFailed, setLoadFailed] = useState(false)
  const requestRef = useRef(0)

  const load = useCallback(async (refresh = false) => {
    const request = ++requestRef.current
    try {
      const result = await getLocalModels(refresh)
      if (request === requestRef.current) {
        setOverview(result)
        setLoadFailed(false)
      }
    } catch (error) {
      console.error("Error loading local models:", error)
      if (request === requestRef.current) {
        setLoadFailed(true)
      }
    }
  }, [])

  useEffect(() => {
    requestRef.current++
    setOverview(null)
    setLoadFailed(false)
  }, [resetKey])

  useEffect(() => {
    if (active) void load()
  }, [active, resetKey, load])

  const polling = !!overview?.models.some(model =>
    ACTIVE_LOCAL_MODEL_STATES.has(model.state),
  )

  useEffect(() => {
    if (!polling) return
    const timer = setTimeout(() => void load(), POLL_INTERVAL_MS)
    return () => clearTimeout(timer)
  }, [polling, overview, load])

  return { overview, loadFailed, load }
}

interface LocalModelsDialogProps {
  open: boolean
  onClose: () => void
  overview: LocalModelsOverview | null
  loadFailed: boolean
  onReload: (refresh?: boolean) => Promise<void>
  failures: DownloadFailures
}

export function LocalModelsDialog({
  open,
  onClose,
  overview,
  loadFailed,
  onReload,
  failures,
}: LocalModelsDialogProps) {
  const { t } = useI18n()
  const copy = t.settings.localModels
  const titleId = useId()
  const [retrying, setRetrying] = useState(false)

  useModalBackHandler(open, onClose)

  const retry = async () => {
    setRetrying(true)
    try {
      await onReload(true)
    } finally {
      setRetrying(false)
    }
  }

  const usingLabel = overview
    ? localModelsSourceLabel(copy.using as Record<string, string>, overview)
    : null

  const retryButton = (
    <Button
      variant="outline"
      size="sm"
      className="h-7"
      onClick={() => void retry()}
      disabled={retrying}
    >
      {retrying ? <LoadingSpinner size="sm" /> : t.common.retry}
    </Button>
  )

  let body
  if (overview?.reachable) {
    body = (
      <LocalModelsManager
        overview={overview}
        onReload={onReload}
        failures={failures}
      />
    )
  } else if (overview || loadFailed) {
    const message = loadFailed
      ? t.common.fetchError
      : ((copy.errors as Record<string, string>)[overview?.error ?? ""] ??
        copy.unreachable)
    body = (
      <div className="flex items-start gap-2 rounded-md border border-red-500/40 bg-red-50 p-3 text-xs text-red-800 dark:bg-red-900/10 dark:text-red-300">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
        <span className="flex-1">{message}</span>
        {retryButton}
      </div>
    )
  } else {
    body = (
      <div className="flex justify-center py-8">
        <LoadingSpinner size="md" />
      </div>
    )
  }

  const dialog = (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="fixed inset-0 z-[16000] flex items-center justify-center bg-black/50 p-2 sm:p-4"
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            className="w-full max-w-5xl"
          >
            <Card className="flex max-h-[90vh] flex-col">
              <CardHeader className="flex-row items-start justify-between gap-4 space-y-0 border-b border-border pb-4">
                <div className="min-w-0 space-y-1.5">
                  <CardTitle id={titleId} className="text-lg">
                    {copy.dialogTitle}
                  </CardTitle>
                  {usingLabel && (
                    <p className="inline-flex items-center gap-2 text-xs text-muted-foreground">
                      <span
                        className={cn(
                          "h-2 w-2 shrink-0 rounded-full",
                          overview?.reachable ? "bg-green-500" : "bg-red-500",
                        )}
                      />
                      <span className="break-all">{usingLabel}</span>
                    </p>
                  )}
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 shrink-0"
                  onClick={onClose}
                  aria-label={t.common.close}
                >
                  <X className="h-4 w-4" />
                </Button>
              </CardHeader>
              <CardContent className="min-h-0 flex-1 overflow-y-auto pt-6">
                {body}
              </CardContent>
            </Card>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )

  return typeof document !== "undefined"
    ? createPortal(dialog, document.body)
    : dialog
}

interface LocalModelsManagerDialogProps {
  open: boolean
  onClose: () => void
  onModelsChange?: () => void
}

export function LocalModelsManagerDialog({
  open,
  onClose,
  onModelsChange,
}: LocalModelsManagerDialogProps) {
  const { overview, loadFailed, load } = useLocalModelsOverview(open)
  const failures = useDownloadFailures(overview?.models)
  const readyKey = overview
    ? overview.models
        .filter(model => !PENDING_STATES.has(model.state))
        .map(model => model.id)
        .sort()
        .join("\n")
    : null
  const readyKeyRef = useRef(readyKey)

  useEffect(() => {
    const previous = readyKeyRef.current
    if (readyKey === null) return
    readyKeyRef.current = readyKey
    if (previous !== null && previous !== readyKey) {
      onModelsChange?.()
    }
  }, [readyKey, onModelsChange])

  return (
    <LocalModelsDialog
      open={open}
      onClose={onClose}
      overview={overview}
      loadFailed={loadFailed}
      onReload={load}
      failures={failures}
    />
  )
}
