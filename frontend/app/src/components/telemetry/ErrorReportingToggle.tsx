import { useState } from "react"
import { ShieldCheck, ShieldOff } from "lucide-react"

import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover"
import { useI18n } from "@/i18n"
import { cn } from "@/lib/utils"
import { isNativeMobile } from "@/lib/platform"
import { updateTelemetryConsent } from "@/lib/telemetry"
import {
  errorReportingPoints,
  useErrorReportingConsent,
} from "@/components/telemetry/TelemetryConsentDialog"

interface ErrorReportingToggleProps {
  mutedClass?: string
  activeClass?: string
  className?: string
}

export function ErrorReportingToggle({
  mutedClass = "text-muted-foreground",
  activeClass = "text-foreground",
  className,
}: ErrorReportingToggleProps) {
  const { t } = useI18n()
  const { enabled, refresh } = useErrorReportingConsent()
  const [isInfoOpen, setIsInfoOpen] = useState(false)

  const isOn = enabled === true
  const Icon = isOn ? ShieldCheck : ShieldOff

  const toggle = async () => {
    try {
      await updateTelemetryConsent({ errorReporting: !isOn })
    } catch (error) {
      console.error("Failed to update telemetry consent:", error)
    } finally {
      refresh()
    }
  }

  return (
    <Popover open={isInfoOpen} onOpenChange={setIsInfoOpen}>
      <PopoverTrigger asChild>
        <span
          className={cn("inline-flex min-w-0", className)}
          onMouseEnter={() => setIsInfoOpen(true)}
          onMouseLeave={() => setIsInfoOpen(false)}
        >
          <button
            type="button"
            role="switch"
            aria-checked={isOn}
            data-testid="error-reporting-toggle"
            onClick={event => {
              // On touch devices the tap also opens the popover with the details.
              if (!isNativeMobile()) event.stopPropagation()
              toggle()
            }}
            className={cn(
              "flex items-center gap-1.5 text-xs leading-tight transition-colors duration-200",
              isOn ? activeClass : mutedClass,
            )}
          >
            <Icon className="h-3.5 w-3.5 shrink-0" />
            <span className="w-min text-left">
              {t.telemetryConsent.shortLabel}
            </span>
          </button>
        </span>
      </PopoverTrigger>
      <PopoverContent
        className="w-60 text-xs"
        align="end"
        side="top"
        sideOffset={8}
        onOpenAutoFocus={event => event.preventDefault()}
      >
        <ul className="space-y-2.5 text-muted-foreground">
          {errorReportingPoints(t.telemetryConsent).map(
            ({ icon: PointIcon, text }) => (
              <li key={text} className="flex items-start gap-2.5">
                <PointIcon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
                <span className="leading-relaxed">{text}</span>
              </li>
            ),
          )}
        </ul>
      </PopoverContent>
    </Popover>
  )
}
