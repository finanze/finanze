import { useEffect, useRef, useState } from "react"
import { ExternalLink } from "lucide-react"
import { Button } from "@/components/ui/Button"
import { CopyableValue } from "@/components/ui/CopyableValue"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { useI18n } from "@/i18n"
import { copyToClipboard } from "@/lib/clipboard"
import { openExternalAuthPage } from "@/lib/externalAuth"
import { pollIntegrationDevice } from "@/services/api"
import {
  ExternalIntegrationConnectionStatus,
  type ExternalIntegrationDeviceAuthorization,
} from "@/types"

const MIN_POLL_SECONDS = 1

export interface DeviceAuthorization {
  flowId: string
  userCode: string
  verificationUri: string
  expiresAt: number
  interval: number
}

export const toDeviceAuthorization = (
  device: ExternalIntegrationDeviceAuthorization,
): DeviceAuthorization => ({
  flowId: device.flow_id,
  userCode: device.user_code,
  verificationUri: device.verification_uri,
  expiresAt: Date.now() + device.expires_in * 1000,
  interval: device.interval,
})

const formatRemaining = (milliseconds: number) => {
  const total = Math.max(0, Math.ceil(milliseconds / 1000))
  const minutes = Math.floor(total / 60)
  const seconds = total % 60
  return `${minutes}:${seconds.toString().padStart(2, "0")}`
}

const siteOf = (url: string) => {
  try {
    return new URL(url).host
  } catch {
    return url
  }
}

interface DeviceAuthorizationPanelProps {
  integrationId: string
  integrationName: string
  authorization: DeviceAuthorization | null
  onConnected: () => Promise<void> | void
  onError: (error: unknown) => void
  onCancel: () => void
}

export function DeviceAuthorizationPanel({
  integrationId,
  integrationName,
  authorization,
  onConnected,
  onError,
  onCancel,
}: DeviceAuthorizationPanelProps) {
  const { t } = useI18n()
  const copy = t.settings.deviceAuthorization
  const [now, setNow] = useState(() => Date.now())
  const onConnectedRef = useRef(onConnected)
  const onErrorRef = useRef(onError)

  useEffect(() => {
    onConnectedRef.current = onConnected
    onErrorRef.current = onError
  })

  useEffect(() => {
    if (!authorization) return
    setNow(Date.now())
    const ticker = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(ticker)
  }, [authorization])

  useEffect(() => {
    if (!authorization) return
    let active = true
    let timer: ReturnType<typeof setTimeout> | undefined

    const schedule = (seconds: number) => {
      timer = setTimeout(
        () => void poll(),
        Math.max(MIN_POLL_SECONDS, seconds) * 1000,
      )
    }

    const poll = async () => {
      if (Date.now() >= authorization.expiresAt) {
        onErrorRef.current({ code: "AUTHORIZATION_EXPIRED" })
        return
      }
      try {
        const result = await pollIntegrationDevice(
          integrationId,
          authorization.flowId,
        )
        if (!active) return
        if (result.status === ExternalIntegrationConnectionStatus.CONNECTED) {
          await onConnectedRef.current()
          return
        }
        schedule(result.interval ?? authorization.interval)
      } catch (error) {
        if (active) onErrorRef.current(error)
      }
    }

    schedule(authorization.interval)
    return () => {
      active = false
      clearTimeout(timer)
    }
  }, [authorization, integrationId])

  if (!authorization) {
    return (
      <p className="text-sm text-muted-foreground">
        {copy.intro.replace("{integration}", integrationName)}
      </p>
    )
  }

  const site = siteOf(authorization.verificationUri)

  const handleOpen = () => {
    void copyToClipboard(authorization.userCode)
    void openExternalAuthPage(authorization.verificationUri)
  }

  return (
    <div
      className="space-y-4 rounded-lg border border-border bg-muted/40 p-4"
      data-testid={`device-authorization-${integrationId}`}
    >
      <p className="text-sm">{copy.instructions.replace("{site}", site)}</p>
      <div className="flex justify-center">
        <CopyableValue
          value={authorization.userCode}
          className="text-2xl font-semibold tracking-[0.2em]"
        />
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <LoadingSpinner size="sm" />
          <span>
            {copy.waiting.replace(
              "{time}",
              formatRemaining(authorization.expiresAt - now),
            )}
          </span>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="ghost" size="sm" onClick={onCancel}>
            {t.common.cancel}
          </Button>
          <Button size="sm" onClick={handleOpen}>
            <ExternalLink className="mr-2 h-4 w-4" />
            {copy.copyAndOpen.replace("{site}", site)}
          </Button>
        </div>
      </div>
    </div>
  )
}
