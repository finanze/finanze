import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { Settings2 } from "lucide-react"
import { useI18n } from "@/i18n"
import { useAppContext } from "@/context/AppContext"
import { Button } from "@/components/ui/Button"
import { Label as FieldLabel } from "@/components/ui/Label"
import { Switch } from "@/components/ui/Switch"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { getAIProviders, validateAIModel } from "@/services/api"
import type { AICatalogModel, AIProviderEntry, AITask } from "@/types/ai"
import {
  AIProviderPriorityEditor,
  type AIProviderEditorNotices,
} from "./AIProviderPriorityEditor"

export const AI_MODELS_FOCUS = "AI_MODELS"
export const AI_SETTINGS_TAB = "ai"
export const AI_MODELS_SETTINGS_PATH = `/settings?tab=${AI_SETTINGS_TAB}&focus=${AI_MODELS_FOCUS}`

export async function compatibleAIEntries(
  entries: AIProviderEntry[],
  task: AITask,
): Promise<AIProviderEntry[]> {
  const { providers } = await getAIProviders(task)
  const checked = await Promise.all(
    entries.map(async entry => {
      const provider = providers.find(item => item.id === entry.provider)
      if (
        !provider ||
        provider.recommended_models.some(
          model => model.id === entry.model && model.eligible !== false,
        )
      ) {
        return entry
      }
      try {
        const validation = await validateAIModel(
          entry.provider,
          entry.model,
          task,
          entry.upstreamProvider,
        )
        return validation.valid || !validation.name ? entry : null
      } catch {
        return entry
      }
    }),
  )
  return checked
    .filter((entry): entry is AIProviderEntry => entry !== null)
    .map(entry => ({ ...entry }))
}

export function TaskAIProviders({
  task,
  override,
  onOverrideChange,
  notices,
  disabled = false,
  testIdPrefix,
  onSelectedModel,
}: {
  task: AITask
  override: AIProviderEntry[]
  onOverrideChange: (entries: AIProviderEntry[]) => void
  notices: AIProviderEditorNotices
  disabled?: boolean
  testIdPrefix: string
  onSelectedModel?: (model: AICatalogModel | undefined) => void
}) {
  const { t } = useI18n()
  const navigate = useNavigate()
  const { settings, fetchExternalIntegrations } = useAppContext()
  const copy = t.settings.aiTaskProviders
  const shared = settings.ai?.providers ?? []
  const [custom, setCustom] = useState(override.length > 0)
  const [cloning, setCloning] = useState(false)

  useEffect(() => {
    void fetchExternalIntegrations()
  }, [fetchExternalIntegrations])

  const toggleCustom = async (next: boolean) => {
    if (!next) {
      setCustom(false)
      onOverrideChange([])
      return
    }
    setCloning(true)
    try {
      onOverrideChange(await compatibleAIEntries(shared, task))
    } catch {
      onOverrideChange(shared.map(entry => ({ ...entry })))
    } finally {
      setCloning(false)
      setCustom(true)
    }
  }

  const switchId = `${testIdPrefix}-custom-toggle`

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 space-y-0.5">
          <FieldLabel htmlFor={switchId}>{copy.customize}</FieldLabel>
          <p className="text-xs text-muted-foreground">
            {custom ? copy.customHint : copy.defaultHint}
          </p>
        </div>
        {cloning ? (
          <div
            className="flex h-6 w-11 shrink-0 items-center justify-center"
            data-testid={`${testIdPrefix}-custom-loading`}
          >
            <LoadingSpinner size="sm" />
          </div>
        ) : (
          <Switch
            id={switchId}
            checked={custom}
            onCheckedChange={value => void toggleCustom(value)}
            disabled={disabled}
            data-testid={switchId}
          />
        )}
      </div>
      {!custom && shared.length === 0 ? (
        <p
          className="text-xs text-amber-700 dark:text-amber-300"
          data-testid={`${testIdPrefix}-no-default`}
        >
          {copy.noDefault}
        </p>
      ) : (
        <AIProviderPriorityEditor
          entries={custom ? override : shared}
          onChange={onOverrideChange}
          task={task}
          readOnly={!custom}
          disabled={disabled}
          notices={notices}
          testIdPrefix={testIdPrefix}
          onSelectedModel={onSelectedModel}
        />
      )}
      {!custom && (
        <Button
          variant="link"
          size="sm"
          className="h-auto gap-1 px-0"
          onClick={() => navigate(AI_MODELS_SETTINGS_PATH)}
          data-testid={`${testIdPrefix}-edit-default`}
        >
          <Settings2 className="h-3.5 w-3.5" />
          {copy.editDefault}
        </Button>
      )}
    </div>
  )
}
