import React from "react"
import { View, Text, StyleSheet } from "react-native"
import { useTheme } from "@/presentation/context"
import { useI18n } from "@/presentation/i18n"
import { getThemeColors, spacing } from "@/presentation/theme"
import {
  EntityDistributionItem,
  formatCurrency,
} from "@/presentation/utils/financialDataUtils"
import { Dezimal } from "@/domain"

interface EntityDistributionChartProps {
  data: EntityDistributionItem[]
  currency: string
}

// Entity colors - varied palette
const ENTITY_COLORS = [
  "#8b5cf6", // violet
  "#06b6d4", // cyan
  "#10b981", // emerald
  "#f59e0b", // amber
  "#ef4444", // red
  "#3b82f6", // blue
  "#84cc16", // lime
  "#f97316", // orange
  "#ec4899", // pink
  "#14b8a6", // teal
  "#a855f7", // purple
  "#6366f1", // indigo
]

export function EntityDistributionChart({
  data,
  currency,
}: EntityDistributionChartProps) {
  const { resolvedTheme } = useTheme()
  const colors = getThemeColors(resolvedTheme)
  const { t, locale } = useI18n()

  if (!data || data.length === 0) {
    return null
  }

  // Calculate total for percentages
  const total = data.reduce((sum, item) => sum.add(item.value), Dezimal.zero())

  return (
    <View style={styles.section}>
      <Text style={[styles.sectionTitle, { color: colors.textMuted }]}>
        {t.dashboard.entityDistribution || "By Entity"}
      </Text>

      {/* Horizontal bar chart - minimalist style */}
      <View style={styles.barChart}>
        {data.slice(0, 6).map((item, index) => {
          const valueDz = item.value
          const percentage = total.gt(Dezimal.zero())
            ? valueDz.truediv(total).mul(Dezimal.fromInt(100))
            : Dezimal.zero()
          const percentageLabel = percentage.round(1).val.toFixed(1)
          const percentageWidth = Math.min(
            Number.isFinite(percentage.toNumber()) ? percentage.toNumber() : 0,
            100,
          )
          const barColor = ENTITY_COLORS[index % ENTITY_COLORS.length]
          return (
            <View key={item.id} style={styles.barRow}>
              <View style={styles.barLabelRow}>
                <View style={[styles.barDot, { backgroundColor: barColor }]} />
                <Text
                  style={[styles.barLabel, { color: colors.textSecondary }]}
                  numberOfLines={1}
                >
                  {item.name}
                </Text>
                <Text style={[styles.barPercent, { color: colors.text }]}>
                  {percentageLabel}%
                </Text>
              </View>
              <View
                style={[styles.barTrack, { backgroundColor: colors.border }]}
              >
                <View
                  style={[
                    styles.barFill,
                    {
                      width: `${percentageWidth}%`,
                      backgroundColor: barColor,
                    },
                  ]}
                />
              </View>
              <Text style={[styles.barValue, { color: colors.textMuted }]}>
                {formatCurrency(valueDz, currency, locale)}
              </Text>
            </View>
          )
        })}
      </View>
    </View>
  )
}

const styles = StyleSheet.create({
  section: {
    paddingTop: spacing.sm,
  },
  sectionTitle: {
    fontSize: 11,
    fontWeight: "400",
    textTransform: "uppercase",
    letterSpacing: 1.5,
    marginBottom: spacing.md,
  },
  barChart: {
    gap: spacing.md,
  },
  barRow: {
    gap: 6,
  },
  barLabelRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  barDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  barLabel: {
    flex: 1,
    fontSize: 13,
    fontWeight: "300",
    letterSpacing: 0.2,
  },
  barPercent: {
    fontSize: 13,
    fontWeight: "500",
    minWidth: 48,
    textAlign: "right",
  },
  barTrack: {
    height: 4,
    borderRadius: 2,
    overflow: "hidden",
  },
  barFill: {
    height: "100%",
    borderRadius: 2,
  },
  barValue: {
    fontSize: 11,
    fontWeight: "300",
    letterSpacing: 0.3,
  },
})
