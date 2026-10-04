import { Lock, Sparkles, Wand2, X } from "lucide-react"
import { Icon, type IconName } from "@/components/ui/icon-picker"
import { useI18n } from "@/i18n"
import { cn } from "@/lib/utils"
import { LabelOrigin } from "@/types/transactions"
import type { Label } from "@/types/labeling"

const DEFAULT_LABEL_COLOR = "#6b7280"

export const hexToRgba = (hex: string, alpha: number): string => {
  const normalized = hex.replace("#", "")
  const full =
    normalized.length === 3
      ? normalized
          .split("")
          .map(c => c + c)
          .join("")
      : normalized
  const value = Number.parseInt(full, 16)
  if (full.length !== 6 || Number.isNaN(value)) {
    return `rgba(107, 114, 128, ${alpha})`
  }
  const r = (value >> 16) & 255
  const g = (value >> 8) & 255
  const b = value & 255
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

export const getLabelColor = (label?: Label | null): string =>
  label?.color || DEFAULT_LABEL_COLOR

export function LabelIcon({
  label,
  className,
}: {
  label?: Label | null
  className?: string
}) {
  if (!label?.icon) {
    return (
      <span
        className={cn("inline-block rounded-full", className)}
        style={{ backgroundColor: getLabelColor(label) }}
      />
    )
  }
  return <Icon name={label.icon as IconName} className={className} />
}

interface LabelChipProps {
  label?: Label | null
  name: string
  origin?: LabelOrigin
  confidence?: number | null
  onClick?: () => void
  onRemove?: () => void
  className?: string
  size?: "sm" | "md"
  title?: string
}

export function LabelChip({
  label,
  name,
  origin,
  confidence,
  onClick,
  onRemove,
  className,
  size = "sm",
  title,
}: LabelChipProps) {
  const { t } = useI18n()
  const color = getLabelColor(label)
  const OriginIcon =
    origin === LabelOrigin.RULE
      ? Wand2
      : origin === LabelOrigin.EXTERNAL
        ? Sparkles
        : origin === LabelOrigin.MANUAL
          ? Lock
          : null

  return (
    <span
      data-testid="label-chip"
      title={
        title ??
        (confidence != null ? `${name} · ${Math.round(confidence)}%` : name)
      }
      onClick={onClick}
      className={cn(
        "inline-flex max-w-[11rem] items-center gap-1 rounded-full border font-medium leading-tight",
        size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-sm",
        onClick && "cursor-pointer hover:opacity-80 transition-opacity",
        className,
      )}
      style={{
        backgroundColor: hexToRgba(color, 0.12),
        borderColor: hexToRgba(color, 0.35),
        color,
      }}
    >
      <LabelIcon
        label={label}
        className={cn("shrink-0", size === "sm" ? "h-3 w-3" : "h-3.5 w-3.5")}
      />
      <span className="truncate">{name}</span>
      {OriginIcon && <OriginIcon className="h-2.5 w-2.5 shrink-0 opacity-70" />}
      {onRemove && (
        <button
          type="button"
          aria-label={t.common.delete}
          onClick={event => {
            event.stopPropagation()
            onRemove()
          }}
          className="ml-0.5 shrink-0 rounded-full hover:opacity-70"
        >
          <X className="h-3 w-3" />
        </button>
      )}
    </span>
  )
}
