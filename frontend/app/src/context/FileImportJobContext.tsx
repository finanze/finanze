import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react"
import { useNavigate } from "react-router-dom"
import { useAppContext } from "@/context/AppContext"
import { useI18n } from "@/i18n"
import { importFile } from "@/services/api"
import type { FileImportRequest, ImportResult } from "@/types"

export type FileImportJobStatus = "idle" | "running" | "ready"

export interface FileImportJob {
  status: FileImportJobStatus
  fileName: string | null
  useAi: boolean
  background: boolean
  request: FileImportRequest | null
  result: ImportResult | null
  reviewRequested: boolean
}

interface FileImportJobContextValue {
  job: FileImportJob
  run: (
    request: FileImportRequest,
    file: File | null,
  ) => Promise<ImportResult | null>
  sendToBackground: () => void
  requestReview: () => void
  discard: () => void
}

const IDLE_JOB: FileImportJob = {
  status: "idle",
  fileName: null,
  useAi: false,
  background: false,
  request: null,
  result: null,
  reviewRequested: false,
}

const READY_TOAST_DURATION_MS = 15000

const FileImportJobContext = createContext<FileImportJobContextValue | null>(
  null,
)

export function FileImportJobProvider({ children }: { children: ReactNode }) {
  const { showToast, hideToast } = useAppContext()
  const { t } = useI18n()
  const navigate = useNavigate()
  const [job, setJob] = useState<FileImportJob>(IDLE_JOB)
  const backgroundRef = useRef(false)
  const detachRef = useRef<(() => void) | null>(null)

  const requestReview = useCallback(() => {
    hideToast()
    setJob(prev =>
      prev.status === "ready" ? { ...prev, reviewRequested: true } : prev,
    )
    navigate("/export")
  }, [hideToast, navigate])

  const run = useCallback(
    (request: FileImportRequest, file: File | null) => {
      backgroundRef.current = false
      setJob({
        ...IDLE_JOB,
        status: "running",
        fileName: file?.name ?? null,
        useAi: Boolean(request.useAi),
        request,
      })
      const movedToBackground = new Promise<null>(resolve => {
        detachRef.current = () => resolve(null)
      })
      const work = async (): Promise<ImportResult | null> => {
        try {
          const result = await importFile(request, file)
          detachRef.current = null
          if (!backgroundRef.current) {
            setJob(IDLE_JOB)
            return result
          }
          if (result.code !== "COMPLETED") {
            setJob(IDLE_JOB)
            const translated = (t.errors as Record<string, string>)[result.code]
            showToast(translated ?? t.export.fileImport.toast.error, "error")
            return null
          }
          setJob(prev => ({ ...prev, status: "ready", result }))
          showToast(
            <span className="flex items-center gap-3">
              <span>{t.export.fileImport.background.ready}</span>
              <button
                type="button"
                data-testid="file-import-review"
                className="rounded-md border border-current px-2 py-0.5 text-xs font-medium"
                onClick={requestReview}
              >
                {t.export.fileImport.background.review}
              </button>
            </span>,
            "info",
            { reportable: false, duration: READY_TOAST_DURATION_MS },
          )
          return null
        } catch (error) {
          detachRef.current = null
          setJob(IDLE_JOB)
          if (!backgroundRef.current) {
            throw error
          }
          showToast(t.export.fileImport.toast.error, "error")
          return null
        }
      }
      return Promise.race([work(), movedToBackground])
    },
    [requestReview, showToast, t],
  )

  const sendToBackground = useCallback(() => {
    backgroundRef.current = true
    setJob(prev =>
      prev.status === "running" ? { ...prev, background: true } : prev,
    )
    detachRef.current?.()
  }, [])

  const discard = useCallback(() => {
    setJob(prev => (prev.status === "running" ? prev : IDLE_JOB))
  }, [])

  const value = useMemo(
    () => ({ job, run, sendToBackground, requestReview, discard }),
    [job, run, sendToBackground, requestReview, discard],
  )

  return (
    <FileImportJobContext.Provider value={value}>
      {children}
    </FileImportJobContext.Provider>
  )
}

export function useFileImportJob() {
  const context = useContext(FileImportJobContext)
  if (!context) {
    throw new Error(
      "useFileImportJob must be used within FileImportJobProvider",
    )
  }
  return context
}
