import { useState } from "react"
import { AlertTriangle, ExternalLink } from "lucide-react"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { Label } from "@/components/ui/Label"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { useI18n } from "@/i18n"
import { openExternalAuthPage } from "@/lib/externalAuth"

const CHATGPT_USAGE_URL = "https://chatgpt.com/settings/usage"
const CHATGPT_ICON = "icons/external-integrations/CHATGPT.png"

interface ChatGPTIntegrationPanelProps {
  enabled: boolean
  expired: boolean
  awaiting: boolean
  loading: boolean
  onContinue: () => void
  onSubmitAddress: (address: string) => void
}

export function ChatGPTIntegrationPanel({
  enabled,
  expired,
  awaiting,
  loading,
  onContinue,
  onSubmitAddress,
}: ChatGPTIntegrationPanelProps) {
  const { t } = useI18n()
  const copy = t.settings.chatgpt
  const [address, setAddress] = useState("")

  if (enabled) {
    return (
      <div
        className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-muted/40 p-3"
        data-testid="chatgpt-plan-usage"
      >
        <div className="flex items-center gap-2 text-sm">
          <img
            src={CHATGPT_ICON}
            alt=""
            className="h-5 w-5 rounded"
            draggable={false}
          />
          <span>{copy.usingPlan}</span>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => void openExternalAuthPage(CHATGPT_USAGE_URL)}
        >
          <ExternalLink className="mr-2 h-4 w-4" />
          {copy.manageUsage}
        </Button>
      </div>
    )
  }

  if (awaiting) {
    const submit = () => {
      const value = address.trim()
      if (!value) return
      onSubmitAddress(value)
      setAddress("")
    }

    return (
      <div className="space-y-2" data-testid="chatgpt-callback-address">
        <Label htmlFor="chatgpt-callback-address" className="leading-snug">
          {copy.pasteLabel}
        </Label>
        <div className="flex gap-2">
          <Input
            id="chatgpt-callback-address"
            value={address}
            onChange={event => setAddress(event.target.value)}
            onKeyDown={event => {
              if (event.key === "Enter") submit()
            }}
            placeholder={copy.pastePlaceholder}
            autoComplete="off"
            spellCheck={false}
          />
          <Button
            size="sm"
            className="h-10"
            onClick={submit}
            disabled={!address.trim() || loading}
          >
            {copy.finish}
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {expired && (
        <div className="flex items-start gap-2 rounded-md border border-amber-500/40 bg-amber-50 p-3 text-xs text-amber-800 dark:bg-amber-900/10 dark:text-amber-300">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{copy.expired}</span>
        </div>
      )}
      <div className="flex justify-end">
        <Button
          size="sm"
          onClick={onContinue}
          disabled={loading}
          className="bg-black text-white hover:bg-black/85 dark:bg-white dark:text-black dark:hover:bg-white/85"
          data-testid="chatgpt-continue"
        >
          {loading ? (
            <LoadingSpinner size="sm" color="invert" className="mr-2" />
          ) : (
            <img
              src={CHATGPT_ICON}
              alt=""
              className="mr-2 h-4 w-4 rounded-sm"
              draggable={false}
            />
          )}
          {copy.continue}
        </Button>
      </div>
    </div>
  )
}
