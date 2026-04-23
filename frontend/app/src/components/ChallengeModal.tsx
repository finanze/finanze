import { useEffect, useRef, useCallback } from "react"
import { motion } from "framer-motion"
import { ShieldCheck } from "lucide-react"
import { useEntityWorkflow } from "@/context/EntityWorkflowContext"
import { useI18n } from "@/i18n"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import { Button } from "@/components/ui/Button"
import { ChallengeType } from "@/types"

declare global {
  interface Window {
    grecaptcha?: {
      render: (
        container: HTMLElement,
        params: {
          sitekey: string
          callback: (token: string) => void
          "expired-callback"?: () => void
          theme?: "light" | "dark"
        },
      ) => number
      reset: (widgetId: number) => void
    }
    onRecaptchaLoaded?: () => void
  }
}

function RecaptchaChallenge({
  siteKey,
  onToken,
}: {
  siteKey: string
  onToken: (token: string) => void
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const widgetIdRef = useRef<number | null>(null)
  const onTokenRef = useRef(onToken)
  onTokenRef.current = onToken

  const renderWidget = useCallback(() => {
    if (!window.grecaptcha || !containerRef.current || !siteKey) return
    if (widgetIdRef.current !== null) return

    containerRef.current.innerHTML = ""

    widgetIdRef.current = window.grecaptcha.render(containerRef.current, {
      sitekey: siteKey,
      callback: (token: string) => {
        onTokenRef.current(token)
      },
      "expired-callback": () => {
        if (widgetIdRef.current !== null && window.grecaptcha) {
          window.grecaptcha.reset(widgetIdRef.current)
        }
      },
    })
  }, [siteKey])

  useEffect(() => {
    if (!siteKey) return

    if (window.grecaptcha) {
      renderWidget()
      return
    }

    window.onRecaptchaLoaded = () => {
      renderWidget()
    }
    const script = document.createElement("script")
    script.src =
      "https://www.google.com/recaptcha/api.js?onload=onRecaptchaLoaded&render=explicit"
    script.async = true
    script.defer = true
    document.head.appendChild(script)
  }, [siteKey, renderWidget])

  return <div ref={containerRef} />
}

export function ChallengeModal() {
  const {
    challengeProcessId,
    challengeType,
    submitChallengeToken,
    cancelChallenge,
    selectedEntity,
  } = useEntityWorkflow()
  const { t } = useI18n()

  if (!selectedEntity || !challengeProcessId) return null

  return (
    <motion.div
      key="challenge-modal"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60 px-4 py-8"
    >
      <motion.div
        initial={{ scale: 0.95, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.95, opacity: 0 }}
        className="relative w-full max-w-md mx-auto"
      >
        <Card className="w-full">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShieldCheck className="h-5 w-5" />
              {t.login.challengeTitle} {selectedEntity.name}
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col items-center gap-4 py-4">
            <p className="text-center text-muted-foreground text-sm">
              {t.login.challengeMessage}
            </p>
            {challengeType === ChallengeType.RECAPTCHA && (
              <RecaptchaChallenge
                siteKey={challengeProcessId}
                onToken={submitChallengeToken}
              />
            )}
            <Button variant="outline" onClick={cancelChallenge}>
              {t.common.cancel}
            </Button>
          </CardContent>
        </Card>
      </motion.div>
    </motion.div>
  )
}
