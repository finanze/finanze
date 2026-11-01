import React, { useEffect, useRef, useState } from "react"
import { Check, Copy } from "lucide-react"
import { useI18n } from "@/i18n"
import { copyToClipboard } from "@/lib/clipboard"
import { cn } from "@/lib/utils"

const COPIED_FEEDBACK_MS = 1500

interface Props {
  value: string
  className?: string
}

export const CopyableValue: React.FC<Props> = ({ value, className }) => {
  const { t } = useI18n()
  const [copied, setCopied] = useState(false)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
    }
  }, [])

  const handleCopy = async () => {
    const ok = await copyToClipboard(value)
    if (!ok) return

    setCopied(true)
    if (timeoutRef.current) clearTimeout(timeoutRef.current)
    timeoutRef.current = setTimeout(() => setCopied(false), COPIED_FEEDBACK_MS)
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      title={copied ? t.common.copied : t.common.copy}
      className={cn(
        "group inline-flex max-w-full items-center gap-1.5 font-mono text-xs text-foreground transition-colors hover:text-primary",
        className,
      )}
    >
      <span className="min-w-0 break-all text-left">{value}</span>
      {copied ? (
        <Check className="h-2.5 w-2.5 shrink-0 text-green-600 dark:text-green-400" />
      ) : (
        <Copy className="h-2.5 w-2.5 shrink-0 text-muted-foreground opacity-70 transition-opacity group-hover:opacity-100" />
      )}
    </button>
  )
}
