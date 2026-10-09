import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react"
import { getLabels } from "@/services/api"
import { useI18n } from "@/i18n"
import { LabelCategory, type Label } from "@/types/labeling"

interface LabelsContextType {
  labels: Label[]
  loaded: boolean
  loading: boolean
  ensureLoaded: () => void
  refreshLabels: () => Promise<void>
  getLabel: (labelId: string) => Label | undefined
  getLabelName: (label: Label | undefined) => string
  excludedLabelIds: Set<string>
}

const LabelsContext = createContext<LabelsContextType | undefined>(undefined)

export function LabelsProvider({ children }: { children: ReactNode }) {
  const { t, locale } = useI18n()
  const [labels, setLabels] = useState<Label[]>([])
  const [loaded, setLoaded] = useState(false)
  const [loading, setLoading] = useState(false)
  const inflightRef = useRef<Promise<void> | null>(null)

  const refreshLabels = useCallback(async () => {
    if (inflightRef.current) return inflightRef.current
    setLoading(true)
    const request = getLabels()
      .then(response => {
        setLabels(response.labels)
        setLoaded(true)
      })
      .catch(error => {
        console.error("Error fetching labels:", error)
      })
      .finally(() => {
        inflightRef.current = null
        setLoading(false)
      })
    inflightRef.current = request
    return request
  }, [])

  const ensureLoaded = useCallback(() => {
    if (!loaded && !inflightRef.current) {
      void refreshLabels()
    }
  }, [loaded, refreshLabels])

  const getLabelName = useCallback(
    (label: Label | undefined) => {
      if (!label) return ""
      const custom = label.name?.trim()
      if (custom) return custom
      const base = t.labels.base as Record<string, string>
      return (label.key && base[label.key]) || label.key || ""
    },
    [t],
  )

  const sortedLabels = useMemo(
    () =>
      [...labels].sort((a, b) =>
        getLabelName(a).localeCompare(getLabelName(b), locale, {
          sensitivity: "base",
        }),
      ),
    [labels, getLabelName, locale],
  )

  const labelsById = useMemo(
    () => new Map(labels.map(label => [label.id, label])),
    [labels],
  )

  const getLabel = useCallback(
    (labelId: string) => labelsById.get(labelId),
    [labelsById],
  )

  const excludedLabelIds = useMemo(
    () =>
      new Set(
        labels
          .filter(label => label.category === LabelCategory.EXCLUDED)
          .map(label => label.id),
      ),
    [labels],
  )

  const value = useMemo(
    () => ({
      labels: sortedLabels,
      loaded,
      loading,
      ensureLoaded,
      refreshLabels,
      getLabel,
      getLabelName,
      excludedLabelIds,
    }),
    [
      sortedLabels,
      loaded,
      loading,
      ensureLoaded,
      refreshLabels,
      getLabel,
      getLabelName,
      excludedLabelIds,
    ],
  )

  return (
    <LabelsContext.Provider value={value}>{children}</LabelsContext.Provider>
  )
}

export function useLabels() {
  const context = useContext(LabelsContext)
  if (context === undefined) {
    throw new Error("useLabels must be used within a LabelsProvider")
  }
  const { ensureLoaded } = context
  useEffect(() => {
    ensureLoaded()
  }, [ensureLoaded])
  return context
}
