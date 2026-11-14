import { useEffect, useRef, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { useI18n } from "@/i18n"
import { useAppContext } from "@/context/AppContext"
import { Button } from "@/components/ui/Button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card"
import { cn } from "@/lib/utils"
import {
  ExternalSuggestionsIcon,
  ExternalSuggestionsSurface,
} from "@/components/labels/ExternalSuggestionsSurface"
import {
  AIProviderPriorityEditor,
  hasDuplicateAIEntries,
  normalizeAIEntries,
} from "./AIProviderPriorityEditor"
import { AI_MODELS_FOCUS } from "./TaskAIProviders"
import type { AIProviderEntry } from "@/types/ai"

export function AIModelsCard() {
  const { t } = useI18n()
  const [searchParams] = useSearchParams()
  const { settings, saveSettings } = useAppContext()
  const copy = t.settings.aiModels
  const storedKey = JSON.stringify(
    normalizeAIEntries(settings.ai?.providers ?? []),
  )
  const [draft, setDraft] = useState<AIProviderEntry[]>(() =>
    JSON.parse(storedKey),
  )
  const [saving, setSaving] = useState(false)
  const [highlighted, setHighlighted] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setDraft(JSON.parse(storedKey))
  }, [storedKey])

  useEffect(() => {
    if (searchParams.get("focus")?.toUpperCase() !== AI_MODELS_FOCUS) return
    containerRef.current?.scrollIntoView?.({
      block: "center",
      behavior: "smooth",
    })
    setHighlighted(true)
    const timer = setTimeout(() => setHighlighted(false), 3500)
    return () => clearTimeout(timer)
  }, [searchParams])

  const next = normalizeAIEntries(draft)
  const dirty = JSON.stringify(next) !== storedKey
  const invalid =
    hasDuplicateAIEntries(next) ||
    next.some(entry => !entry.provider || !entry.model)

  const handleSave = async () => {
    setSaving(true)
    await saveSettings({ ai: { providers: next } })
    setSaving(false)
  }

  return (
    <div ref={containerRef}>
      <Card
        className={cn(
          "-mx-6 overflow-hidden rounded-none border-x-0 transition-shadow md:mx-0 md:rounded-lg md:border-x",
          highlighted && "ring-2 ring-yellow-500",
        )}
        data-testid="ai-models-card"
      >
        <ExternalSuggestionsSurface className="rounded-none border-0 border-b border-violet-500/20">
          <CardHeader className="flex-row items-start gap-3 space-y-0 pb-4">
            <ExternalSuggestionsIcon />
            <div className="min-w-0 flex-1 space-y-1.5">
              <CardTitle className="text-lg">{copy.title}</CardTitle>
              <CardDescription>{copy.description}</CardDescription>
            </div>
          </CardHeader>
        </ExternalSuggestionsSurface>
        <CardContent className="space-y-4 pt-4">
          {draft.length === 0 && (
            <p className="text-xs text-muted-foreground">{copy.empty}</p>
          )}
          <AIProviderPriorityEditor
            entries={draft}
            onChange={setDraft}
            disabled={saving}
            notices={{
              priority: copy.priorityNotice,
              customModel: copy.customModelNotice,
              privacy: copy.privacyNotice,
            }}
            testIdPrefix="ai-models"
          />
          {dirty && (
            <div className="flex justify-end">
              <Button
                size="sm"
                onClick={handleSave}
                disabled={saving || invalid}
                data-testid="ai-models-save"
              >
                {saving ? t.common.saving : t.common.save}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
