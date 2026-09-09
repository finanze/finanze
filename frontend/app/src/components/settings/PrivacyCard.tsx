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

  useEffect(() => {
    loadConsent().then(setConsent).catch(console.error)
  }, [])

  const apply = useCallback(async (errorReporting: boolean) => {
    try {
      setConsent(await updateTelemetryConsent({ errorReporting }))
    } catch (error) {
      console.error("Failed to update telemetry consent:", error)
    }
  }, [])

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
              onCheckedChange={checked => apply(checked)}
            />
          </div>

          <p className="font-mono text-[0.6rem] text-muted-foreground">
            {t.settings.privacy.installId}: {consent.installId}
          </p>
        </CardContent>
      </Card>
    </motion.div>
  )
}
