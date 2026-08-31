import { useCallback, useEffect, useState } from "react"
import { motion } from "framer-motion"
import { ShieldCheck } from "lucide-react"

import { useI18n } from "@/i18n"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card"
import { Switch } from "@/components/ui/Switch"
import {
  loadConsent,
  updateTelemetryConsent,
  type TelemetryConsent,
} from "@/lib/telemetry"

export function PrivacyCard() {
  const { t } = useI18n()
  const [consent, setConsent] = useState<TelemetryConsent | null>(null)
  const [restartRequired, setRestartRequired] = useState(false)

  useEffect(() => {
    loadConsent().then(setConsent).catch(console.error)
  }, [])

  const apply = useCallback(
    async (errorReporting: boolean, sessionReplay: boolean) => {
      const previous = consent
      try {
        const saved = await updateTelemetryConsent({
          errorReporting,
          sessionReplay,
        })
        setConsent(saved)
        if (previous?.errorReporting && !saved.errorReporting) {
          setRestartRequired(true)
        }
      } catch (error) {
        console.error("Failed to update telemetry consent:", error)
      }
    },
    [consent],
  )

  if (!consent) return null

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
    >
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-primary" />
            <CardTitle>{t.settings.privacy.title}</CardTitle>
          </div>
          <CardDescription>{t.settings.privacy.description}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1">
              <p className="text-sm font-medium">
                {t.settings.privacy.errorReportingLabel}
              </p>
              <p className="text-xs text-muted-foreground">
                {t.settings.privacy.errorReportingDescription}
              </p>
            </div>
            <Switch
              data-testid="telemetry-error-reporting"
              checked={consent.errorReporting}
              onCheckedChange={checked =>
                apply(checked, checked && consent.sessionReplay)
              }
            />
          </div>

          <div className="flex flex-col gap-3 border-t border-border/50 pt-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1">
              <p className="text-sm font-medium">
                {t.settings.privacy.sessionReplayLabel}
              </p>
              <p className="text-xs text-muted-foreground">
                {t.settings.privacy.sessionReplayDescription}
              </p>
            </div>
            <Switch
              data-testid="telemetry-session-replay"
              checked={consent.sessionReplay}
              disabled={!consent.errorReporting}
              onCheckedChange={checked =>
                apply(consent.errorReporting, checked)
              }
            />
          </div>

          {restartRequired && (
            <p className="text-xs text-muted-foreground">
              {t.settings.privacy.restartRequired}
            </p>
          )}

          <p className="font-mono text-[0.6rem] text-muted-foreground">
            {t.settings.privacy.installId}: {consent.installId}
          </p>
        </CardContent>
      </Card>
    </motion.div>
  )
}
