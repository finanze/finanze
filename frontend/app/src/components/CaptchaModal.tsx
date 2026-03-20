import { useEffect, useRef, useCallback } from "react"
import { motion } from "framer-motion"
import { ShieldCheck } from "lucide-react"
import { useEntityWorkflow } from "@/context/EntityWorkflowContext"
import { useI18n } from "@/i18n"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import { Button } from "@/components/ui/Button"

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

export function CaptchaModal() {
  const { captchaSiteKey, submitCaptchaToken, cancelCaptcha, selectedEntity } =
    useEntityWorkflow()
  const { t } = useI18n()
  const containerRef = useRef<HTMLDivElement>(null)
  const widgetIdRef = useRef<number | null>(null)
  const scriptLoadedRef = useRef(false)
  const submitRef = useRef(submitCaptchaToken)
  submitRef.current = submitCaptchaToken

  const renderWidget = useCallback(() => {
    if (!window.grecaptcha || !containerRef.current || !captchaSiteKey) return
    if (widgetIdRef.current !== null) return

    containerRef.current.innerHTML = ""

    widgetIdRef.current = window.grecaptcha.render(containerRef.current, {
      sitekey: captchaSiteKey,
      callback: (token: string) => {
        submitRef.current(token)
      },
      "expired-callback": () => {
        if (widgetIdRef.current !== null && window.grecaptcha) {
          window.grecaptcha.reset(widgetIdRef.current)
        }
      },
    })
  }, [captchaSiteKey])

  useEffect(() => {
    if (!captchaSiteKey) return

    if (window.grecaptcha) {
      renderWidget()
      return
    }

    if (!scriptLoadedRef.current) {
      scriptLoadedRef.current = true
      window.onRecaptchaLoaded = () => {
        renderWidget()
      }
      const script = document.createElement("script")
      script.src =
        "https://www.google.com/recaptcha/api.js?onload=onRecaptchaLoaded&render=explicit"
      script.async = true
      script.defer = true
      document.head.appendChild(script)
    }
  }, [captchaSiteKey, renderWidget])

  if (!selectedEntity) return null

  return (
    <motion.div
      key="captcha-modal"
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
              {t.login.captchaTitle} {selectedEntity.name}
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col items-center gap-4 py-4">
            <p className="text-center text-muted-foreground text-sm">
              {t.login.captchaMessage}
            </p>
            <div ref={containerRef} />
            <Button variant="outline" onClick={cancelCaptcha}>
              {t.common.cancel}
            </Button>
          </CardContent>
        </Card>
      </motion.div>
    </motion.div>
  )
}
