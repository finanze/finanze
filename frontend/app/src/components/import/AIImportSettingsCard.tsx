import { useEffect, useState } from "react"
import { AnimatePresence, motion } from "framer-motion"
import { ChevronDown } from "lucide-react"
import { useI18n } from "@/i18n"
import { useAppContext } from "@/context/AppContext"
import { Button } from "@/components/ui/Button"
import { CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import { TaskAIProviders } from "@/components/ai/TaskAIProviders"
import {
  hasDuplicateAIEntries,
  normalizeAIEntries,
} from "@/components/ai/AIProviderPriorityEditor"
import { CollapsibleNotes } from "@/components/import/CollapsibleNotes"
import {
  ExternalSuggestionsIcon,
  ExternalSuggestionsSurface,
} from "@/components/labels/ExternalSuggestionsSurface"
import { cn } from "@/lib/utils"
import { AITask, type AIImportSettings } from "@/types/ai"

const MAX_INSTRUCTIONS_LENGTH = 1000

const toStored = (draft: AIImportSettings): AIImportSettings => ({
  providers: normalizeAIEntries(draft.providers),
  instructions: draft.instructions?.trim() ? draft.instructions.trim() : null,
})

export function AIImportSettingsCard({ className }: { className?: string }) {
  const { t } = useI18n()
  const { settings, saveSettings } = useAppContext()
  const copy = t.export.fileImport.ai.settings
  const stored = settings.importing?.ai
  const [draft, setDraft] = useState<AIImportSettings | null>(null)
  const [open, setOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!stored) return
    setDraft({
      providers: stored.providers.map(entry => ({ ...entry })),
      instructions: stored.instructions ?? null,
    })
  }, [stored])

  if (!draft || !stored) return null

  const next = toStored(draft)
  const dirty = JSON.stringify(next) !== JSON.stringify(toStored(stored))

  const handleSave = async () => {
    if (next.providers.some(entry => !entry.provider || !entry.model)) {
      setError(t.labels.external.providerAndModelRequired)
      return
    }
    if (hasDuplicateAIEntries(next.providers)) {
      setError(t.labels.external.duplicateProvider)
      return
    }
    setSaving(true)
    await saveSettings({ importing: { ...settings.importing, ai: next } })
    setSaving(false)
  }

  return (
    <ExternalSuggestionsSurface
      className={cn("shadow-sm", className)}
      data-testid="import-ai-settings-card"
    >
      <CardHeader className="p-0">
        <button
          type="button"
          aria-expanded={open}
          onClick={() => setOpen(current => !current)}
          className="flex w-full items-center gap-3 rounded-lg px-4 py-3 text-left sm:px-6"
          data-testid="import-ai-settings-toggle"
        >
          <ExternalSuggestionsIcon className="h-9 w-9" />
          <span className="min-w-0 flex-1">
            <CardTitle className="text-base">{copy.title}</CardTitle>
            <span className="block text-xs text-muted-foreground">
              {copy.description}
            </span>
          </span>
          <ChevronDown
            className={cn(
              "h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200",
              open && "rotate-180",
            )}
          />
        </button>
      </CardHeader>
      <AnimatePresence initial={false}>
        {open ? (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeInOut" }}
            className="overflow-hidden"
          >
            <CardContent className="space-y-5 border-t border-violet-500/20 pt-4">
              <TaskAIProviders
                task={AITask.IMPORTING}
                override={draft.providers}
                onOverrideChange={providers => {
                  setDraft(prev => (prev ? { ...prev, providers } : prev))
                  setError(null)
                }}
                notices={{
                  priority: copy.priorityNotice,
                  customModel: t.settings.aiModels.customModelNotice,
                  privacy: copy.privacyNotice,
                }}
                disabled={saving}
                testIdPrefix="import-ai"
              />
              <CollapsibleNotes
                id="import-ai-instructions"
                label={copy.instructionsLabel}
                hint={copy.instructionsHint}
                value={draft.instructions ?? ""}
                maxLength={MAX_INSTRUCTIONS_LENGTH}
                disabled={saving}
                placeholder={t.export.fileImport.ai.instructionsPlaceholder}
                onChange={instructions =>
                  setDraft(prev => (prev ? { ...prev, instructions } : prev))
                }
              />
              {error ? <p className="text-xs text-red-500">{error}</p> : null}
              {dirty ? (
                <div className="flex justify-end">
                  <Button
                    onClick={handleSave}
                    disabled={saving}
                    data-testid="import-ai-save"
                  >
                    {t.common.save}
                  </Button>
                </div>
              ) : null}
            </CardContent>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </ExternalSuggestionsSurface>
  )
}
