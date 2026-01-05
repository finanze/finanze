import React, { useState } from "react"
import { View, Text, StyleSheet, TouchableOpacity } from "react-native"
import Svg, { Path, G, Text as SvgText } from "react-native-svg"
import { useTheme } from "@/presentation/context"
import { usePrivacy } from "@/presentation/context"
import { useI18n } from "@/presentation/i18n"
import { getThemeColors, spacing } from "@/presentation/theme"
import { AssetDistributionItem, Dezimal } from "@/domain"
import { EntityDistributionItem } from "@/presentation/utils/financialDataUtils"
import {
  ASSET_TYPE_COLOR_MAP,
  ENTITY_COLOR_PALETTE,
  getDeterministicColor,
} from "@/presentation/utils/colorUtils"
import { getIconForAssetType } from "@/presentation/utils/iconUtils"
import { SensitiveText } from "../ui"

interface DistributionChartProps {
  assetData: AssetDistributionItem[]
  entityData: EntityDistributionItem[]
  currency: string
}

// Asset type colors: align with desktop DashboardPage palette
const ASSET_TYPE_COLORS: Record<string, string> = {
  ...ASSET_TYPE_COLOR_MAP,
  // Keep a sensible fallback for types not defined on desktop map
  BOND: "#6366f1",
  DERIVATIVE: "#94a3b8",
  LOAN: "#14b8a6",
  CARD: "#f97316",
  FUND_PORTFOLIO: "#d946ef",
}

type TabType = "assets" | "entities"

interface DonutArc {
  path: string
  color: string
  percentage: number
  midAngle: number
}

// Donut chart component using SVG with percentage labels
function DonutChart({
  data,
  colors: colorArray,
  size = 180,
  strokeWidth = 28,
  textColor = "#000",
  maskLabels = false,
  labelMask = "••",
}: {
  data: { value: number; percentage: number }[]
  colors: string[]
  size?: number
  strokeWidth?: number
  textColor?: string
  maskLabels?: boolean
  labelMask?: string
}) {
  const radius = (size - strokeWidth) / 2
  const centerX = size / 2
  const centerY = size / 2

  const angleOffset = 0
  const gapAngle = 1

  // Calculate arcs with label positions
  let cumulativePercentage = 0
  const arcs: DonutArc[] = data.map((item, index) => {
    const startAngle = cumulativePercentage * 3.6 + angleOffset + gapAngle / 2
    const midAngle =
      (cumulativePercentage + item.percentage / 2) * 3.6 + angleOffset
    cumulativePercentage += item.percentage
    const endAngle = cumulativePercentage * 3.6 + angleOffset - gapAngle / 2

    // Convert angles to radians
    const startRad = (startAngle * Math.PI) / 180
    const endRad = (endAngle * Math.PI) / 180

    // Calculate path
    const x1 = centerX + radius * Math.cos(startRad)
    const y1 = centerY + radius * Math.sin(startRad)
    const x2 = centerX + radius * Math.cos(endRad)
    const y2 = centerY + radius * Math.sin(endRad)

    const largeArcFlag = item.percentage > 50 ? 1 : 0

    const pathData = `M ${x1} ${y1} A ${radius} ${radius} 0 ${largeArcFlag} 1 ${x2} ${y2}`

    return {
      path: pathData,
      color: colorArray[index % colorArray.length],
      percentage: item.percentage,
      midAngle,
    }
  })

  // Position labels more inward than the arc centerline, but still close to the chart.
  const labelRadius = Math.max(radius - strokeWidth * 1.15, 0)

  return (
    <Svg width={size} height={size}>
      <G>
        {arcs.map((arc, index) => (
          <Path
            key={index}
            d={arc.path}
            stroke={arc.color}
            strokeWidth={strokeWidth}
            fill="none"
            strokeLinecap="butt"
          />
        ))}
        {/* Percentage labels for segments >= 8% */}
        {arcs.map((arc, index) => {
          if (arc.percentage < 8) return null

          const midRad = (arc.midAngle * Math.PI) / 180
          const labelX = centerX + labelRadius * Math.cos(midRad)
          const labelY = centerY + labelRadius * Math.sin(midRad)

          return (
            <SvgText
              key={`label-${index}`}
              x={labelX}
              y={labelY}
              fill={maskLabels ? "#fff" : textColor}
              stroke={maskLabels ? "#fff" : undefined}
              strokeWidth={maskLabels ? 2 : 0}
              strokeOpacity={maskLabels ? 0.35 : 1}
              fontSize={9}
              fontWeight="600"
              textAnchor="middle"
              alignmentBaseline="central"
            >
              {maskLabels
                ? labelMask
                : `${Dezimal.fromFloat(arc.percentage).round(0).val.toFixed(0)}%`}
            </SvgText>
          )
        })}
      </G>
    </Svg>
  )
}

export function DistributionChart({
  assetData,
  entityData,
  currency,
}: DistributionChartProps) {
  const { resolvedTheme } = useTheme()
  const colors = getThemeColors(resolvedTheme)
  const { t, locale } = useI18n()
  const { hideAmounts } = usePrivacy()
  const [activeTab, setActiveTab] = useState<TabType>("assets")

  const getAssetLabel = (type: string): string => {
    return t.assets[type as keyof typeof t.assets]
  }

  const getEntityLabel = (item: EntityDistributionItem): string => {
    // Check if it's a fake entity that needs translation
    if (item.id === "real-estate") {
      return t.entities.REAL_ESTATE
    }
    if (item.id === "commodity") {
      return t.entities.COMMODITY
    }
    if (item.id === "crypto") {
      return t.entities.CRYPTO
    }
    return item.name
  }

  const getEntityColor = (item: EntityDistributionItem): string => {
    const label = getEntityLabel(item)
    return getDeterministicColor(label, ENTITY_COLOR_PALETTE)
  }

  const isAssetTab = activeTab === "assets"
  const currentData = isAssetTab ? assetData : entityData
  const hasData = currentData && currentData.length > 0

  // Prepare chart data
  const chartData = hasData
    ? currentData.slice(0, 8).map(item => ({
        value: (() => {
          const n = item.value.toNumber()
          return Number.isFinite(n) ? n : 0
        })(),
        percentage: (() => {
          const n = item.percentage.toNumber()
          return Number.isFinite(n) ? n : 0
        })(),
      }))
    : []

  const chartColors = isAssetTab
    ? currentData
        .slice(0, 8)
        .map(
          item =>
            ASSET_TYPE_COLORS[(item as AssetDistributionItem).type] ||
            colors.primary,
        )
    : currentData
        .slice(0, 8)
        .map(item => getEntityColor(item as EntityDistributionItem))

  return (
    <View style={styles.section}>
      {/* Tab selector */}
      <View style={styles.tabContainer}>
        <TouchableOpacity
          style={[
            styles.tab,
            activeTab === "assets" && styles.activeTab,
            { borderColor: colors.border },
          ]}
          onPress={() => setActiveTab("assets")}
        >
          <Text
            style={[
              styles.tabText,
              {
                color: activeTab === "assets" ? colors.text : colors.textMuted,
              },
            ]}
          >
            {t.dashboard.assetDistribution}
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[
            styles.tab,
            activeTab === "entities" && styles.activeTab,
            { borderColor: colors.border },
          ]}
          onPress={() => setActiveTab("entities")}
        >
          <Text
            style={[
              styles.tabText,
              {
                color:
                  activeTab === "entities" ? colors.text : colors.textMuted,
              },
            ]}
          >
            {t.dashboard.entityDistribution}
          </Text>
        </TouchableOpacity>
      </View>

      {!hasData ? (
        <View style={styles.emptyContainer}>
          <Text style={[styles.emptyText, { color: colors.textMuted }]}>
            {t.dashboard.noData}
          </Text>
        </View>
      ) : (
        <View style={styles.chartContainer}>
          {/* Donut Chart */}
          <View style={styles.donutContainer}>
            <DonutChart
              data={chartData}
              colors={chartColors}
              size={160}
              strokeWidth={22}
              textColor={colors.text}
              maskLabels={hideAmounts}
            />
          </View>

          {/* Legend with amounts */}
          <View style={styles.legend}>
            {currentData.slice(0, 8).map((item, index) => {
              const color = isAssetTab
                ? ASSET_TYPE_COLORS[(item as AssetDistributionItem).type] ||
                  colors.primary
                : getEntityColor(item as EntityDistributionItem)
              const label = isAssetTab
                ? getAssetLabel((item as AssetDistributionItem).type)
                : getEntityLabel(item as EntityDistributionItem)

              return (
                <View
                  key={
                    isAssetTab
                      ? (item as AssetDistributionItem).type
                      : (item as EntityDistributionItem).id
                  }
                  style={styles.legendItem}
                >
                  {isAssetTab ? (
                    <View style={styles.legendIcon}>
                      {getIconForAssetType(
                        (item as AssetDistributionItem).type,
                        { color, size: 14 },
                      )}
                    </View>
                  ) : (
                    <View
                      style={[styles.legendDot, { backgroundColor: color }]}
                    />
                  )}
                  <Text
                    style={[
                      styles.legendLabel,
                      { color: colors.textSecondary },
                    ]}
                    numberOfLines={1}
                  >
                    {label}
                  </Text>
                  <SensitiveText
                    kind="currency"
                    value={item.value}
                    currency={currency}
                    style={[styles.legendAmount, { color: colors.text }]}
                  />
                </View>
              )
            })}
          </View>
        </View>
      )}
    </View>
  )
}

const styles = StyleSheet.create({
  section: {
    paddingTop: spacing.sm,
  },
  tabContainer: {
    flexDirection: "row",
    gap: spacing.md,
    marginBottom: spacing.lg,
  },
  tab: {
    paddingBottom: spacing.xs,
  },
  activeTab: {
    borderBottomWidth: 1,
  },
  tabText: {
    fontSize: 11,
    fontWeight: "400",
    textTransform: "uppercase",
    letterSpacing: 1.2,
  },
  emptyContainer: {
    alignItems: "center",
    paddingVertical: spacing.xl,
  },
  emptyText: {
    fontSize: 14,
    fontWeight: "300",
  },
  chartContainer: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.lg,
  },
  donutContainer: {
    alignItems: "center",
    justifyContent: "center",
  },
  legend: {
    flex: 1,
    gap: spacing.sm,
  },
  legendItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  legendDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  legendIcon: {
    width: 14,
    height: 14,
    alignItems: "center",
    justifyContent: "center",
  },
  legendLabel: {
    flex: 1,
    fontSize: 12,
    fontWeight: "300",
    letterSpacing: 0.2,
  },
  legendAmount: {
    fontSize: 11,
    fontWeight: "500",
    minWidth: 60,
    textAlign: "right",
  },
})
