import * as React from "react"
import * as SliderPrimitive from "@radix-ui/react-slider"
import { cn } from "@/lib/utils"
import { useI18n } from "@/i18n"

export type SliderScale = "linear" | "exponential"

interface SliderProps {
  value: number | null | undefined
  onValueChange: (value: number) => void
  onValueCommit?: (value: number) => void
  min: number
  max: number
  step?: number
  unit?: string
  scale?: SliderScale
  curve?: number
  showValue?: boolean
  showLimits?: boolean
  formatValue?: (value: number) => string
  disabled?: boolean
  id?: string
  className?: string
  "aria-label"?: string
  "aria-labelledby"?: string
}

const POSITION_STEPS = 200
const DEFAULT_CURVE = 4

const clamp = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, value))

function Slider({
  value,
  onValueChange,
  onValueCommit,
  min,
  max,
  step = 1,
  unit,
  scale = "linear",
  curve = DEFAULT_CURVE,
  showValue = true,
  showLimits = false,
  formatValue,
  disabled,
  id,
  className,
  "aria-label": ariaLabel,
  "aria-labelledby": ariaLabelledBy,
}: SliderProps) {
  const { locale } = useI18n()
  const exponential = scale === "exponential"
  const decimals = (String(step).split(".")[1] ?? "").length

  const numberFormat = React.useMemo(
    () =>
      new Intl.NumberFormat(locale, {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      }),
    [locale, decimals],
  )

  const format = (v: number) => formatValue?.(v) ?? numberFormat.format(v)
  const withUnit = (text: string) => (unit ? `${text} ${unit}` : text)

  const snap = (v: number) =>
    Number(
      clamp(min + Math.round((v - min) / step) * step, min, max).toFixed(
        decimals,
      ),
    )

  const toPosition = (v: number) => {
    if (!exponential) return clamp(v, min, max)
    const ratio = clamp((v - min) / (max - min), 0, 1)
    return (Math.log1p(ratio * Math.expm1(curve)) / curve) * POSITION_STEPS
  }

  const fromPosition = (position: number) =>
    exponential
      ? min +
        ((max - min) * Math.expm1((curve * position) / POSITION_STEPS)) /
          Math.expm1(curve)
      : position

  const current = value ?? null
  const currentPosition = toPosition(current ?? min)

  const resolve = (position: number) => {
    const next = snap(fromPosition(position))
    // The curve is flat near the start, so ensure each move advances at least one step
    if (
      exponential &&
      current !== null &&
      next === current &&
      position !== currentPosition
    ) {
      return snap(current + Math.sign(position - currentPosition) * step)
    }
    return next
  }

  const handleChange = ([position]: number[]) => {
    const next = resolve(position)
    if (next !== current) onValueChange(next)
  }

  const handleCommit = ([position]: number[]) => {
    onValueCommit?.(resolve(position))
  }

  const valueText = current === null ? "—" : format(current)
  const valueWidth =
    Math.max(format(min).length, format(max).length, valueText.length) +
    (unit ? unit.length + 1 : 0)

  return (
    <div className={cn("flex items-center gap-3", className)}>
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <SliderPrimitive.Root
          value={[currentPosition]}
          onValueChange={handleChange}
          onValueCommit={handleCommit}
          min={exponential ? 0 : min}
          max={exponential ? POSITION_STEPS : max}
          step={exponential ? 1 : step}
          disabled={disabled}
          className="relative flex h-6 w-full touch-none select-none items-center data-[disabled]:cursor-not-allowed data-[disabled]:opacity-50"
        >
          <SliderPrimitive.Track className="relative h-1 w-full grow overflow-hidden rounded-full bg-muted">
            <SliderPrimitive.Range className="absolute h-full bg-primary" />
          </SliderPrimitive.Track>
          <SliderPrimitive.Thumb
            id={id}
            aria-label={ariaLabel}
            aria-labelledby={ariaLabelledBy}
            aria-valuemin={min}
            aria-valuemax={max}
            aria-valuenow={current ?? min}
            aria-valuetext={withUnit(valueText)}
            className="relative block h-4 w-4 cursor-grab rounded-full border-2 border-primary bg-background shadow-md transition-transform after:absolute after:-inset-3 after:content-[''] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background active:scale-110 active:cursor-grabbing data-[disabled]:cursor-not-allowed"
          />
        </SliderPrimitive.Root>
        {showLimits && (
          <div className="flex justify-between text-xs tabular-nums text-muted-foreground">
            <span>{withUnit(format(min))}</span>
            <span>{withUnit(format(max))}</span>
          </div>
        )}
      </div>
      {showValue && (
        <span
          className={cn(
            "shrink-0 self-start text-right text-sm font-medium leading-6 tabular-nums",
            disabled && "opacity-50",
          )}
          style={{ minWidth: `${valueWidth}ch` }}
          aria-hidden
        >
          {withUnit(valueText)}
        </span>
      )}
    </div>
  )
}

export { Slider }
