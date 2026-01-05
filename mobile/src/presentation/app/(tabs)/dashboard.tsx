import React, { useEffect } from "react"
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  TouchableOpacity,
  LayoutAnimation,
  Platform,
  UIManager,
} from "react-native"
import { SafeAreaView } from "react-native-safe-area-context"
import AsyncStorage from "@react-native-async-storage/async-storage"
import { Settings2 } from "lucide-react-native"
import { useFinancial } from "@/presentation/context"
import { useTheme } from "@/presentation/context"
import { useI18n } from "@/presentation/i18n"
import {
  NetWorthCard,
  DistributionChart,
  TransactionList,
  OngoingInvestments,
} from "@/presentation/components/dashboard"
import { ToggleSwitch } from "@/presentation/components/ui"
import { getThemeColors, spacing } from "@/presentation/theme"
import {
  filterRealEstateByOptions,
  getAssetDistribution,
  getEntityDistribution,
  getTotalNetWorth,
  getOngoingProjects,
  type DashboardOptions,
} from "@/presentation/utils/financialDataUtils"

const DASHBOARD_OPTIONS_STORAGE_KEY = "finanze.dashboardOptions.v1"

export default function Dashboard() {
  const { resolvedTheme } = useTheme()
  const colors = getThemeColors(resolvedTheme)
  const { t } = useI18n()

  const {
    positions,
    recentTransactions,
    pendingFlows,
    realEstateList,
    exchangeRates,
    targetCurrency,
    isLoading,
  } = useFinancial()

  // Get ongoing projects from positions
  const ongoingProjects = React.useMemo(
    () => getOngoingProjects(positions, targetCurrency),
    [positions, targetCurrency],
  )

  const [optionsOpen, setOptionsOpen] = React.useState(false)
  const [dashboardOptions, setDashboardOptions] =
    React.useState<DashboardOptions>({
      includePending: true,
      includeCardExpenses: false,
      includeRealEstate: true,
      includeResidences: false,
    })

  useEffect(() => {
    if (
      Platform.OS === "android" &&
      typeof UIManager.setLayoutAnimationEnabledExperimental === "function"
    ) {
      UIManager.setLayoutAnimationEnabledExperimental(true)
    }

    const load = async () => {
      try {
        const raw = await AsyncStorage.getItem(DASHBOARD_OPTIONS_STORAGE_KEY)
        if (raw) {
          const parsed = JSON.parse(raw)
          setDashboardOptions({
            includePending: Boolean(parsed.includePending),
            includeCardExpenses: Boolean(parsed.includeCardExpenses),
            includeRealEstate: Boolean(parsed.includeRealEstate),
            includeResidences: Boolean(parsed.includeResidences),
          })
        }
      } catch {
        // ignore
      }
    }
    load()
  }, [])

  const toggleOptions = React.useCallback(() => {
    LayoutAnimation.configureNext({
      duration: 180,
      create: {
        type: LayoutAnimation.Types.easeInEaseOut,
        property: LayoutAnimation.Properties.opacity,
      },
      update: {
        type: LayoutAnimation.Types.easeInEaseOut,
      },
      delete: {
        type: LayoutAnimation.Types.easeInEaseOut,
        property: LayoutAnimation.Properties.opacity,
      },
    })
    setOptionsOpen(v => !v)
  }, [])

  useEffect(() => {
    const save = async () => {
      try {
        await AsyncStorage.setItem(
          DASHBOARD_OPTIONS_STORAGE_KEY,
          JSON.stringify(dashboardOptions),
        )
      } catch {
        // ignore
      }
    }
    save()
  }, [dashboardOptions])

  const hasData = positions && Object.keys(positions.positions || {}).length > 0

  const filteredRealEstateList = React.useMemo(
    () => filterRealEstateByOptions(realEstateList, dashboardOptions),
    [realEstateList, dashboardOptions],
  )

  const appliedPendingFlows = React.useMemo(
    () => (dashboardOptions.includePending ? pendingFlows : []),
    [dashboardOptions.includePending, pendingFlows],
  )

  const assetDistribution = React.useMemo(
    () =>
      getAssetDistribution(
        positions,
        targetCurrency,
        exchangeRates,
        appliedPendingFlows,
        filteredRealEstateList,
      ),
    [
      positions,
      targetCurrency,
      exchangeRates,
      appliedPendingFlows,
      filteredRealEstateList,
    ],
  )

  const entityDistribution = React.useMemo(
    () =>
      getEntityDistribution(
        positions,
        targetCurrency,
        exchangeRates,
        appliedPendingFlows,
        filteredRealEstateList,
      ),
    [
      positions,
      targetCurrency,
      exchangeRates,
      appliedPendingFlows,
      filteredRealEstateList,
    ],
  )

  const totalNetWorth = React.useMemo(
    () =>
      getTotalNetWorth(
        positions,
        targetCurrency,
        exchangeRates,
        appliedPendingFlows,
        realEstateList,
        dashboardOptions,
      ),
    [
      positions,
      targetCurrency,
      exchangeRates,
      appliedPendingFlows,
      realEstateList,
      dashboardOptions,
    ],
  )

  if (isLoading) {
    return (
      <SafeAreaView
        style={[styles.container, { backgroundColor: colors.background }]}
        edges={["top"]}
      >
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="small" color={colors.textMuted} />
        </View>
      </SafeAreaView>
    )
  }

  return (
    <SafeAreaView
      style={[styles.container, { backgroundColor: colors.background }]}
      edges={["top"]}
    >
      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.topGapRow}>
          <TouchableOpacity
            onPress={toggleOptions}
            style={styles.topGapButton}
            hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
          >
            <Settings2 size={18} color={colors.textMuted} />
          </TouchableOpacity>
        </View>

        {optionsOpen ? (
          <View
            style={[
              styles.optionsPanel,
              {
                borderColor: colors.border,
                backgroundColor: colors.surface,
              },
            ]}
          >
            <View style={styles.optionRow}>
              <Text style={[styles.optionLabel, { color: colors.text }]}>
                {t.dashboard.includePendingMoney}
              </Text>
              <ToggleSwitch
                value={dashboardOptions.includePending}
                onValueChange={val =>
                  setDashboardOptions(prev => ({
                    ...prev,
                    includePending: val,
                  }))
                }
              />
            </View>
            <View style={styles.optionRow}>
              <Text style={[styles.optionLabel, { color: colors.text }]}>
                {t.dashboard.includeCardExpenses}
              </Text>
              <ToggleSwitch
                value={dashboardOptions.includeCardExpenses}
                onValueChange={val =>
                  setDashboardOptions(prev => ({
                    ...prev,
                    includeCardExpenses: val,
                  }))
                }
              />
            </View>
            <View style={styles.optionRow}>
              <Text style={[styles.optionLabel, { color: colors.text }]}>
                {t.dashboard.includeRealEstateEquity}
              </Text>
              <ToggleSwitch
                value={dashboardOptions.includeRealEstate}
                onValueChange={val =>
                  setDashboardOptions(prev => ({
                    ...prev,
                    includeRealEstate: val,
                  }))
                }
              />
            </View>
            <View style={[styles.optionRow, styles.optionRowIndented]}>
              <Text
                style={[styles.optionLabelMuted, { color: colors.textMuted }]}
              >
                {t.dashboard.includeResidences}
              </Text>
              <ToggleSwitch
                value={dashboardOptions.includeResidences}
                onValueChange={val =>
                  setDashboardOptions(prev => ({
                    ...prev,
                    includeResidences: val,
                  }))
                }
                disabled={!dashboardOptions.includeRealEstate}
              />
            </View>
          </View>
        ) : null}

        {!hasData ? (
          <View style={styles.noDataContainer}>
            <View style={[styles.noDataIcon, { borderColor: colors.border }]}>
              <View
                style={[
                  styles.noDataBar,
                  { backgroundColor: colors.textMuted },
                ]}
              />
              <View
                style={[
                  styles.noDataBar,
                  styles.noDataBarShort,
                  { backgroundColor: colors.textMuted },
                ]}
              />
            </View>
            <Text style={[styles.noDataTitle, { color: colors.text }]}>
              {t.dashboard.noData}
            </Text>
            <Text style={[styles.noDataText, { color: colors.textMuted }]}>
              {t.onboarding.noBackupInstructions}
            </Text>
          </View>
        ) : (
          <View style={styles.sections}>
            <NetWorthCard
              totalValue={totalNetWorth}
              currency={targetCurrency}
            />

            <DistributionChart
              assetData={assetDistribution}
              entityData={entityDistribution}
              currency={targetCurrency}
            />

            <TransactionList transactions={recentTransactions} />

            <OngoingInvestments projects={ongoingProjects} />
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  topGapRow: {
    height: spacing.xxxl + spacing.xs,
    alignItems: "flex-end",
    justifyContent: "flex-start",
    paddingTop: spacing.md,
  },
  topGapButton: {
    padding: 8,
  },
  optionsPanel: {
    marginBottom: spacing.sm,
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: 14,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    gap: spacing.xs,
  },
  optionRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.md,
    paddingVertical: spacing.xs,
  },
  optionRowIndented: {
    paddingLeft: spacing.sm,
  },
  optionLabel: {
    flex: 1,
    fontSize: 11,
    fontWeight: "400",
    textTransform: "uppercase",
    letterSpacing: 1.2,
  },
  optionLabelMuted: {
    flex: 1,
    fontSize: 10,
    fontWeight: "400",
    textTransform: "uppercase",
    letterSpacing: 1.2,
  },
  content: {
    padding: spacing.lg,
    paddingTop: spacing.xs,
    paddingBottom: spacing.xxxl,
  },
  sections: {
    gap: spacing.xl,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },
  noDataContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    paddingVertical: 120,
    gap: spacing.lg,
  },
  noDataIcon: {
    width: 64,
    height: 64,
    borderRadius: 16,
    borderWidth: 1,
    justifyContent: "center",
    alignItems: "center",
    gap: 6,
    marginBottom: spacing.md,
  },
  noDataBar: {
    width: 24,
    height: 3,
    borderRadius: 1.5,
  },
  noDataBarShort: {
    width: 16,
  },
  noDataTitle: {
    fontSize: 18,
    fontWeight: "300",
    letterSpacing: 0.5,
  },
  noDataText: {
    fontSize: 14,
    fontWeight: "300",
    textAlign: "center",
    paddingHorizontal: spacing.xxl,
    lineHeight: 20,
    letterSpacing: 0.3,
  },
})
