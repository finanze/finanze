import React from "react"
import { StyleSheet, Text, type TextProps, type TextStyle } from "react-native"
import { useI18n } from "@/presentation/i18n"
import { usePrivacy } from "@/presentation/context"
import {
  formatCurrency,
  formatDate,
  formatPercentage,
} from "@/presentation/utils/financialDataUtils"
import { Dezimal } from "@/domain"

type Kind =
  | {
      kind: "currency"
      value: Dezimal | null | undefined
      currency: string
    }
  | {
      kind: "percentage"
      value: Dezimal | null | undefined
      decimals?: number
    }
  | {
      kind: "number"
      value: Dezimal | null | undefined
      decimals?: number
    }
  | { kind: "date"; value: string | null | undefined }

export function SensitiveText(
  props: Kind & TextProps & { mask?: string; hide?: boolean },
) {
  const { locale } = useI18n()
  const { hideAmounts } = usePrivacy()

  const { mask: maskProp, hide: hideProp, ...textProps } = props as any
  const shouldHide = hideProp ?? hideAmounts
  const mask = maskProp ?? "••••"

  const flattenedStyle = StyleSheet.flatten((textProps as any).style) as
    | TextStyle
    | undefined

  const maskedStyle: TextStyle = {
    opacity: 0.75,
    textShadowColor: flattenedStyle?.color,
    textShadowOffset: { width: 0, height: 0 },
    textShadowRadius: 8,
  }

  let text = "—"

  if ((props as any).kind === "date") {
    const value = (props as any).value as string | null | undefined
    text = value ? formatDate(value, locale) : "—"
    // Dates are not masked by default
    return <Text {...textProps}>{text}</Text>
  }

  if (shouldHide) {
    return (
      <Text {...textProps} style={[textProps.style, maskedStyle]}>
        {mask}
      </Text>
    )
  }

  if ((props as any).kind === "currency") {
    const value = (props as any).value as Dezimal | null | undefined
    const currency = (props as any).currency as string
    text = formatCurrency(value, currency, locale)
  } else if ((props as any).kind === "percentage") {
    const value = (props as any).value as Dezimal | null | undefined
    const decimals = (props as any).decimals as number | undefined
    text = formatPercentage(value, decimals ?? 1)
  } else {
    const val = (props as any).value as Dezimal | null | undefined
    const decimals = (props as any).decimals as number | undefined
    if (!val || !val.isFinite()) {
      text = "—"
    } else {
      const rounded = val.round(decimals ?? 2)
      const asNumber = rounded.toNumber()
      text = Number.isFinite(asNumber)
        ? new Intl.NumberFormat(locale, {
            minimumFractionDigits: 0,
            maximumFractionDigits: decimals ?? 2,
          }).format(asNumber)
        : "—"
    }
  }

  return <Text {...textProps}>{text}</Text>
}
