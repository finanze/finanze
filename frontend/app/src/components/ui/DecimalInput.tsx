import { useEffect, useRef, useState } from "react"
import { Input } from "@/components/ui/Input"

const PATTERN = /^-?\d*\.?\d*$/
const PATTERN_POSITIVE = /^\d*\.?\d*$/

interface DecimalInputBaseProps extends Omit<
  React.ComponentProps<typeof Input>,
  "type" | "onChange" | "value"
> {
  allowNegative?: boolean
}

interface DecimalInputNumericProps extends DecimalInputBaseProps {
  value: number | string | null | undefined
  onValueChange: (value: number | null) => void
  onStringChange?: never
}

interface DecimalInputStringProps extends DecimalInputBaseProps {
  value: string
  onStringChange: (value: string) => void
  onValueChange?: never
}

export type DecimalInputProps =
  | DecimalInputNumericProps
  | DecimalInputStringProps

const fmt = (v: number | string | null | undefined) => {
  if (v == null || v === "") return ""
  if (typeof v === "number") return String(parseFloat(v.toPrecision(12)))
  return String(v)
}

const isValid = (raw: string, allowNegative: boolean) => {
  if (raw === "") return true
  return (allowNegative ? PATTERN : PATTERN_POSITIVE).test(raw)
}

export function DecimalInput({
  value,
  onValueChange,
  onStringChange,
  allowNegative = false,
  onFocus,
  onBlur,
  ...props
}: DecimalInputProps) {
  const isStringMode = Boolean(onStringChange)
  const [local, setLocal] = useState(() => fmt(value))
  const focused = useRef(false)

  useEffect(() => {
    if (!focused.current) setLocal(fmt(value))
  }, [value])

  return (
    <Input
      inputMode="decimal"
      {...props}
      type="text"
      value={
        focused.current ? local : isStringMode ? (value as string) : fmt(value)
      }
      onFocus={e => {
        focused.current = true
        setLocal(isStringMode ? (value as string) : fmt(value))
        onFocus?.(e)
      }}
      onChange={e => {
        const raw = e.target.value.replace(",", ".")
        if (!isValid(raw, allowNegative)) return
        setLocal(raw)
        if (onStringChange) {
          onStringChange(raw)
        } else if (onValueChange) {
          const n = parseFloat(raw)
          onValueChange(raw === "" ? null : isNaN(n) ? null : n)
        }
      }}
      onBlur={e => {
        focused.current = false
        if (!isStringMode) {
          const n = parseFloat(local)
          setLocal(isNaN(n) ? "" : String(n))
        }
        onBlur?.(e)
      }}
    />
  )
}
