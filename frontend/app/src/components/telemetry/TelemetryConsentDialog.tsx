import { useCallback, useEffect, useState } from "react"
import { createPortal } from "react-dom"
import { AnimatePresence, motion } from "framer-motion"
import { ShieldCheck } from "lucide-react"

import { Button } from "@/components/ui/Button"
import { useI18n } from "@/i18n"
import { useModalBackHandler } from "@/hooks/useModalBackHandler"
import {
  getCachedConsent,
  loadConsent,
  updateTelemetryConsent,
} from "@/lib/telemetry"

interface TelemetryConsentDialogProps {
  isOpen: boolean
  onClose: () => void
  onEnabled?: () => void
}

export function useErrorReportingConsent() {
  const [enabled, setEnabled] = useState<boolean | null>(
    () => getCachedConsent()?.errorReporting ?? null,
  )

  const refresh = useCallback(() => {
    loadConsent()
      .then(consent => setEnabled(consent.errorReporting))
      .catch(console.error)
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  return { enabled, refresh }
}

export function TelemetryConsentDialog({
  isOpen,
  onClose,
  onEnabled,
}: TelemetryConsentDialogProps) {
  const { t } = useI18n()
  const [isSaving, setIsSaving] = useState(false)

  useModalBackHandler(isOpen, onClose)

  const enable = async () => {
    try {
      setIsSaving(true)
      await updateTelemetryConsent({ errorReporting: true })
      onEnabled?.()
      onClose()
    } catch (error) {
      console.error("Failed to update telemetry consent:", error)
    } finally {
      setIsSaving(false)
    }
  }

  const content = (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="fixed inset-0 z-[18000] flex items-center justify-center bg-black/50 p-4"
          onClick={onClose}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            onClick={event => event.stopPropagation()}
            className="w-full max-w-sm rounded-lg border border-border bg-background p-5 shadow-lg"
          >
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-primary" />
              <h2 className="text-sm font-medium">
                {t.telemetryConsent.title}
              </h2>
            </div>
            <p className="mt-3 text-sm text-muted-foreground">
              {t.telemetryConsent.description}
            </p>
            <p className="mt-2 text-xs text-muted-foreground">
              {t.telemetryConsent.detail}
            </p>
            <div className="mt-5 flex justify-end gap-2">
              <Button variant="ghost" size="sm" onClick={onClose}>
                {t.telemetryConsent.notNow}
              </Button>
              <Button
                size="sm"
                onClick={enable}
                disabled={isSaving}
                data-testid="telemetry-consent-enable"
              >
                {t.telemetryConsent.enable}
              </Button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )

  return typeof document !== "undefined"
    ? createPortal(content, document.body)
    : content
}
