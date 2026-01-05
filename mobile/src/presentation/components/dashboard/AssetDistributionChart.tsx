import React from "react"
import { View, Text, StyleSheet } from "react-native"
import { useTheme } from "@/presentation/context"
import { useI18n } from "@/presentation/i18n"
import { getThemeColors, spacing } from "@/presentation/theme"
import { AssetDistributionItem } from "@/domain"
import { formatCurrency } from "@/presentation/utils/financialDataUtils"
import { Dezimal } from "@/domain"
import { ASSET_TYPE_COLOR_MAP } from "@/presentation/utils/colorUtils"

interface AssetDistributionChartProps {
  data: AssetDistributionItem[]
  currency: string
}

const EXTRA_ASSET_COLORS: Record<string, string> = {
  PENDING_FLOWS: "#94a3b8",
}

export function AssetDistributionChart({
  data,
  currency,
}: AssetDistributionChartProps) {
  const { resolvedTheme } = useTheme()
  const colors = getThemeColors(resolvedTheme)
  const { t, locale } = useI18n()

  const getAssetLabel = (type: string): string => {
    return t.assets[type as keyof typeof t.assets]
  }

  if (!data || data.length === 0) {
    return (
      <View style={styles.section}>
        <Text style={[styles.sectionTitle, { color: colors.textMuted }]}>
          {t.dashboard.assetDistribution}
        </Text>
        <View style={styles.emptyContainer}>
          <Text style={[styles.emptyText, { color: colors.textMuted }]}>
            {t.dashboard.noData}
          </Text>
        </View>
      </View>
    )
  }

  // Calculate total for percentages
  const total = data.reduce((sum, item) => sum.add(item.value), Dezimal.zero())

  return (
    <View style={styles.section}>
      <Text style={[styles.sectionTitle, { color: colors.textMuted }]}>
        {t.dashboard.assetDistribution}
      </Text>

      {/* Horizontal bar chart - minimalist style */}
      <View style={styles.barChart}>
        {data.slice(0, 6).map(item => {
          const valueDz = item.value
          const percentage = total.gt(Dezimal.zero())
            ? valueDz.truediv(total).mul(Dezimal.fromInt(100))
            : Dezimal.zero()

          const percentageLabel = percentage.round(1).val.toFixed(1)
          const percentageWidth = Math.min(
            Number.isFinite(percentage.toNumber()) ? percentage.toNumber() : 0,
            100,
          )
          const barColor =
            ASSET_TYPE_COLOR_MAP[item.type] ||
            EXTRA_ASSET_COLORS[item.type] ||
            colors.primary
          return (
            <View key={item.type} style={styles.barRow}>
              <View style={styles.barLabelRow}>
                <View style={[styles.barDot, { backgroundColor: barColor }]} />
                <Text
                  style={[styles.barLabel, { color: colors.textSecondary }]}
                >
                  {getAssetLabel(item.type)}
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
  emptyContainer: {
    alignItems: "center",
    paddingVertical: spacing.xl,
  },
  emptyText: {
    fontSize: 14,
    fontWeight: "300",
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
