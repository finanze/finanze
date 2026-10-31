import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type ReactNode,
} from "react"
import { createPortal } from "react-dom"
import { AnimatePresence, motion } from "framer-motion"
import { AlertTriangle, RefreshCw, X } from "lucide-react"
import { useI18n } from "@/i18n"
import { useModalBackHandler } from "@/hooks/useModalBackHandler"
import { Badge } from "@/components/ui/Badge"
import { Button } from "@/components/ui/Button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { getAIServerInfo } from "@/services/api"
import { cn } from "@/lib/utils"
import { formatFileSize } from "@/utils/releaseUtils"
import { AIServerKind, type AIServerInfo } from "@/types/ai"

const SERVER_NAMES: Record<AIServerKind, string> = {
  [AIServerKind.OLLAMA]: "Ollama",
  [AIServerKind.LM_STUDIO]: "LM Studio",
  [AIServerKind.LLAMA_CPP]: "llama.cpp",
  [AIServerKind.VLLM]: "vLLM",
}

const formatContext = (tokens: number) =>
  tokens >= 1024 ? `${Math.round(tokens / 1024)}K` : String(tokens)

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="min-w-0 space-y-0.5">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="break-words text-sm">{children}</dd>
    </div>
  )
}

interface AIServerDetailsDialogProps {
  provider: string | null
  onClose: () => void
}

export function AIServerDetailsDialog({
  provider,
  onClose,
}: AIServerDetailsDialogProps) {
  const { t } = useI18n()
  const copy = t.settings.aiServer
  const titleId = useId()
  const open = provider !== null
  const [info, setInfo] = useState<AIServerInfo | null>(null)
  const [failed, setFailed] = useState(false)
  const [loading, setLoading] = useState(false)
  const requestRef = useRef(0)

  useModalBackHandler(open, onClose)

  const load = useCallback(async () => {
    if (!provider) return
    const request = ++requestRef.current
    setLoading(true)
    setFailed(false)
    try {
      const result = await getAIServerInfo(provider)
      if (request === requestRef.current) setInfo(result)
    } catch (error) {
      console.error("Error loading AI server details:", error)
      if (request === requestRef.current) setFailed(true)
    } finally {
      if (request === requestRef.current) setLoading(false)
    }
  }, [provider])

  useEffect(() => {
    if (!provider) return
    setInfo(null)
    void load()
  }, [provider, load])

  let body
  if (failed && !info) {
    body = (
      <div className="flex items-start gap-2 rounded-md border border-red-500/40 bg-red-50 p-3 text-xs text-red-800 dark:bg-red-900/10 dark:text-red-300">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
        <span className="flex-1">{t.common.fetchError}</span>
      </div>
    )
  } else if (!info) {
    body = (
      <div className="flex justify-center py-8">
        <LoadingSpinner size="md" />
      </div>
    )
  } else {
    const healthy = info.reachable && !info.error
    const statusLabel = !info.reachable
      ? copy.unreachable
      : info.error
        ? copy.respondedWithError
        : copy.connected
    const knowsLoaded = info.models.some(model => model.loaded != null)
    const loadedCount = info.models.filter(model => model.loaded).length
    const errorMessage = info.error
      ? (copy.errors as Record<string, string>)[info.error]
      : null

    body = (
      <div className="space-y-5" data-testid="ai-server-details">
        <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Fact label={copy.status}>
            <span className="inline-flex items-center gap-2">
              <span
                className={cn(
                  "h-2 w-2 shrink-0 rounded-full",
                  healthy
                    ? "bg-green-500"
                    : info.reachable
                      ? "bg-amber-500"
                      : "bg-red-500",
                )}
              />
              <span data-testid="ai-server-status">{statusLabel}</span>
              {info.latency_ms != null && (
                <span className="text-xs text-muted-foreground">
                  {copy.latency.replace("{ms}", String(info.latency_ms))}
                </span>
              )}
            </span>
          </Fact>
          <Fact label={copy.server}>
            <span data-testid="ai-server-kind">
              {info.kind ? SERVER_NAMES[info.kind] : copy.unknownServer}
              {info.version && (
                <span className="ml-1.5 font-mono text-xs text-muted-foreground">
                  {info.version}
                </span>
              )}
            </span>
          </Fact>
          <Fact label={copy.endpoint}>
            <span className="break-all font-mono text-xs">{info.url}</span>
          </Fact>
          <Fact label={copy.apiKey}>
            {info.api_key_set ? copy.apiKeySet : copy.apiKeyNotSet}
          </Fact>
          {healthy && (
            <Fact label={copy.models}>
              {copy.modelCount.replace("{count}", String(info.models.length))}
              {knowsLoaded &&
                ` · ${copy.loadedCount.replace("{count}", String(loadedCount))}`}
            </Fact>
          )}
        </dl>

        {errorMessage && (
          <div
            className={cn(
              "flex items-start gap-2 rounded-md border p-3 text-xs",
              info.reachable
                ? "border-amber-500/40 bg-amber-50 text-amber-800 dark:bg-amber-900/10 dark:text-amber-300"
                : "border-red-500/40 bg-red-50 text-red-800 dark:bg-red-900/10 dark:text-red-300",
            )}
            data-testid="ai-server-error"
          >
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        {healthy && (
          <div className="space-y-2">
            <h4 className="text-sm font-medium">{copy.models}</h4>
            {info.models.length === 0 ? (
              <p className="text-xs text-muted-foreground">{copy.noModels}</p>
            ) : (
              <div className="space-y-2">
                {info.models.map(model => (
                  <div
                    key={model.id}
                    className="flex flex-wrap items-center gap-1.5 rounded-md border border-border px-3 py-2"
                    data-testid={`ai-server-model-${model.id}`}
                  >
                    <span className="mr-auto min-w-0 break-all font-mono text-xs">
                      {model.id}
                    </span>
                    {model.decisions && (
                      <Badge variant="outline" className="text-[10px]">
                        {copy.decisions}
                      </Badge>
                    )}
                    {model.context_length ? (
                      <Badge variant="outline" className="text-[10px]">
                        {copy.context.replace(
                          "{context}",
                          formatContext(model.context_length),
                        )}
                      </Badge>
                    ) : null}
                    {model.size ? (
                      <Badge variant="outline" className="text-[10px]">
                        {formatFileSize(model.size)}
                      </Badge>
                    ) : null}
                    {model.loaded != null && (
                      <Badge
                        variant="outline"
                        className={cn(
                          "text-[10px]",
                          model.loaded
                            ? "border-green-500/40 text-green-700 dark:text-green-400"
                            : "text-muted-foreground",
                        )}
                      >
                        {model.loaded ? copy.loaded : copy.notLoaded}
                      </Badge>
                    )}
                  </div>
                ))}
              </div>
            )}
            {!info.kind && (
              <p className="text-xs text-muted-foreground">
                {copy.unknownHint}
              </p>
            )}
          </div>
        )}
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
            className="w-full max-w-2xl"
          >
            <Card className="flex max-h-[90vh] flex-col">
              <CardHeader className="flex-row items-center justify-between gap-4 space-y-0 border-b border-border pb-4">
                <CardTitle id={titleId} className="text-lg">
                  {copy.title}
                </CardTitle>
                <div className="flex shrink-0 items-center gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => void load()}
                    disabled={loading}
                    aria-label={copy.refresh}
                    title={copy.refresh}
                  >
                    <RefreshCw
                      className={cn("h-4 w-4", loading && "animate-spin")}
                    />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={onClose}
                    aria-label={t.common.close}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
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
