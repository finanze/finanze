import { useEffect, useState, type ReactNode } from "react"
import { AnimatePresence, motion } from "framer-motion"
import { ChevronDown } from "lucide-react"
import { useI18n } from "@/i18n"
import { useAppContext } from "@/context/AppContext"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { Label as FieldLabel } from "@/components/ui/Label"
import { Switch } from "@/components/ui/Switch"
import { TaskAIProviders } from "@/components/ai/TaskAIProviders"
import {
  hasDuplicateAIEntries,
  normalizeAIEntries,
} from "@/components/ai/AIProviderPriorityEditor"
import { cn } from "@/lib/utils"
import { AITask, type AICatalogModel } from "@/types/ai"
import { LabelOrigin } from "@/types/transactions"
import type { ExternalLabelingSettings } from "@/types/labeling"
import {
  ExternalSuggestionsIcon,
  ExternalSuggestionsSurface,
} from "./ExternalSuggestionsSurface"

const MAX_INSTRUCTIONS_LENGTH = 2000
const EXAMPLE_ORIGINS = [LabelOrigin.MANUAL, LabelOrigin.RULE]

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

export function ExternalLabelingCard({ className }: { className?: string }) {
  const { t } = useI18n()
  const { settings, saveSettings } = useAppContext()
  const [draft, setDraft] = useState<ExternalLabelingSettings | null>(null)
  const [moreOpen, setMoreOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedRecommended, setSelectedRecommended] = useState<
    AICatalogModel | undefined
  >()

  const stored = settings.labeling?.external

  useEffect(() => {
    if (!stored) return
    setDraft({
      ...stored,
      providers: stored.providers.map(entry => ({ ...entry })),
      examples: { ...stored.examples },
    })
  }, [stored])

  if (!draft || !stored) return null

  const update = (patch: Partial<ExternalLabelingSettings>) => {
    setDraft(prev => (prev ? { ...prev, ...patch } : prev))
    setError(null)
  }

  const nextProviders = normalizeAIEntries(draft.providers)
  const nextSettings: ExternalLabelingSettings = {
    ...draft,
    providers: nextProviders,
    instructions: draft.instructions?.trim() ? draft.instructions : null,
  }
  const dirty =
    draft.enabled !== stored.enabled ||
    JSON.stringify(nextSettings) !== JSON.stringify(stored)
  const duplicate = hasDuplicateAIEntries(nextProviders)

  const handleSave = async () => {
    if (nextProviders.some(item => !item.provider || !item.model)) {
      setError(t.labels.external.providerAndModelRequired)
      return
    }
    if (duplicate) {
      setError(t.labels.external.duplicateProvider)
      return
    }
    setSaving(true)
    await saveSettings({ labeling: { external: nextSettings } })
    setSaving(false)
  }

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
            onClick={() =>
              update({ enabled: !draft.enabled, providers: nextProviders })
            }
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
            onCheckedChange={value =>
              update({ enabled: value, providers: nextProviders })
            }
            disabled={saving}
            data-testid="external-labeling-switch"
          />
        </div>

        {draft.enabled && (
          <div className="space-y-5 border-t border-violet-500/20 pt-5">
            <TaskAIProviders
              task={AITask.LABELING}
              override={draft.providers}
              onOverrideChange={providers => update({ providers })}
              notices={{
                priority: t.labels.external.platformPriorityNotice,
                customModel: t.labels.external.customModelNotice,
                privacy: t.labels.external.privacyNotice,
                smallModel: t.labels.external.smallModelWarning,
              }}
              disabled={saving}
              testIdPrefix="external"
              onSelectedModel={setSelectedRecommended}
            />

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
                          onCheckedChange={value => update({ autoRun: value })}
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
        )}

        {error && (
          <p className="text-sm text-red-600 dark:text-red-400" role="alert">
            {error}
          </p>
        )}

        {dirty && (
          <div className="flex flex-wrap items-center justify-end gap-3">
            <Button
              size="sm"
              onClick={handleSave}
              disabled={saving || duplicate}
            >
              {saving ? t.common.saving : t.common.save}
            </Button>
          </div>
        )}
      </div>
    </ExternalSuggestionsSurface>
  )
}
