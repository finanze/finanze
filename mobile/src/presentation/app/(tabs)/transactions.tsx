import React, { useCallback, useEffect, useState } from "react"
import {
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
  TouchableOpacity,
  Platform,
  UIManager,
  useWindowDimensions,
} from "react-native"
import { SafeAreaView } from "react-native-safe-area-context"
import { SlidersHorizontal, Calendar } from "lucide-react-native"
import { useTheme, useLayoutMenuScroll } from "@/presentation/context"
import { useI18n } from "@/presentation/i18n"
import { getThemeColors, spacing } from "@/presentation/theme"
import { useFloatingTabBarContentInset } from "@/presentation/components/navigation/useFloatingTabBarInset"
import { useTransactions } from "@/presentation/hooks"
import {
  TransactionFilters,
  TransactionEmptyState,
  TransactionSectionList,
} from "@/presentation/components/transactions"
import { ProductType, TxType } from "@/domain"
import { SensitiveText } from "@/presentation/components/ui"
import {
  getIconForAssetType,
  getIconForTxType,
} from "@/presentation/utils/iconUtils"
import { ASSET_TYPE_COLOR_MAP } from "@/presentation/utils/colorUtils"

// Tablet breakpoint and max content width for large screens
const TABLET_BREAKPOINT = 768
const MAX_CONTENT_WIDTH = 900

export default function TransactionsScreen() {
  const { resolvedTheme } = useTheme()
  const colors = getThemeColors(resolvedTheme)
  const { t } = useI18n()
  const { onScroll } = useLayoutMenuScroll()
  const bottomInset = useFloatingTabBarContentInset()
  const { width: screenWidth } = useWindowDimensions()

  const isTablet = screenWidth >= TABLET_BREAKPOINT

  // Enable LayoutAnimation for Android
  useEffect(() => {
    if (
      Platform.OS === "android" &&
      typeof UIManager.setLayoutAnimationEnabledExperimental === "function"
    ) {
      UIManager.setLayoutAnimationEnabledExperimental(true)
    }
  }, [])

  const {
    transactions,
    isLoading,
    isLoadingMore,
    error,
    hasMore,
    entities,
    filters,
    setFilters,
    fetchTransactions,
    loadMore,
    clearFilters,
    refresh,
  } = useTransactions()

  const [filtersVisible, setFiltersVisible] = useState(false)
  const [isRefreshing, setIsRefreshing] = useState(false)

  // Initial load
  useEffect(() => {
    fetchTransactions(1, true)
  }, [])

  const handleApplyFilters = useCallback(() => {
    fetchTransactions(1, true)
  }, [fetchTransactions])

  const handleClearFilters = useCallback(() => {
    void clearFilters()
  }, [clearFilters])

  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true)
    await refresh()
    setIsRefreshing(false)
  }, [refresh])

  const handleEndReached = useCallback(() => {
    if (!isLoadingMore && hasMore) {
      loadMore()
    }
  }, [hasMore, isLoadingMore, loadMore])

  const activeFilterCount =
    filters.entities.length +
    filters.productTypes.length +
    filters.txTypes.length +
    (filters.fromDate ? 1 : 0) +
    (filters.toDate ? 1 : 0)

  const activeEntityChips = filters.entities
    .map(id => entities.find(e => e.id === id))
    .filter(Boolean)

  const renderAppliedFilters = useCallback(() => {
    if (activeFilterCount === 0) return null

    return (
      <View style={styles.appliedFiltersWrap}>
        {/* Entities */}
        {activeEntityChips.map(entity => (
          <View
            key={entity!.id ?? entity!.name}
            style={[
              styles.appliedChip,
              { borderColor: colors.border, backgroundColor: colors.surface },
            ]}
          >
            <Text
              style={[styles.appliedChipText, { color: colors.text }]}
              numberOfLines={1}
            >
              {entity!.name}
            </Text>
          </View>
        ))}

        {/* Product types */}
        {filters.productTypes.map(pt => (
          <View
            key={pt}
            style={[
              styles.appliedChip,
              { borderColor: colors.border, backgroundColor: colors.surface },
            ]}
          >
            {getIconForAssetType(pt as ProductType, {
              color: ASSET_TYPE_COLOR_MAP[pt] ?? colors.textMuted,
              size: 14,
            })}
            <Text
              style={[styles.appliedChipText, { color: colors.text }]}
              numberOfLines={1}
            >
              {t.assets[pt] ?? pt}
            </Text>
          </View>
        ))}

        {/* Tx types */}
        {filters.txTypes.map(tt => (
          <View
            key={tt}
            style={[
              styles.appliedChip,
              { borderColor: colors.border, backgroundColor: colors.surface },
            ]}
          >
            {getIconForTxType(tt as TxType, {
              color: colors.textMuted,
              size: 14,
            })}
            <Text
              style={[styles.appliedChipText, { color: colors.text }]}
              numberOfLines={1}
            >
              {t.txTypes[tt] ?? tt}
            </Text>
          </View>
        ))}

        {/* Date range */}
        {filters.fromDate || filters.toDate ? (
          <View
            style={[
              styles.appliedChip,
              { borderColor: colors.border, backgroundColor: colors.surface },
            ]}
          >
            <Calendar size={14} color={colors.textMuted} strokeWidth={1.5} />
            {filters.fromDate ? (
              <SensitiveText
                kind="date"
                value={filters.fromDate}
                style={[styles.appliedChipText, { color: colors.text }]}
              />
            ) : (
              <Text
                style={[styles.appliedChipText, { color: colors.textMuted }]}
              >
                —
              </Text>
            )}
            <Text style={[styles.appliedChipText, { color: colors.textMuted }]}>
              –
            </Text>
            {filters.toDate ? (
              <SensitiveText
                kind="date"
                value={filters.toDate}
                style={[styles.appliedChipText, { color: colors.text }]}
              />
            ) : (
              <Text
                style={[styles.appliedChipText, { color: colors.textMuted }]}
              >
                —
              </Text>
            )}
          </View>
        ) : null}
      </View>
    )
  }, [
    activeEntityChips,
    activeFilterCount,
    colors,
    filters,
    t.assets,
    t.txTypes,
  ])

  const renderHeader = useCallback(
    () => (
      <View style={styles.headerContainer}>
        {/* Top gap with filter button */}
        <View style={styles.topRow}>
          <TouchableOpacity
            onPress={() => setFiltersVisible(true)}
            style={styles.filterButton}
            hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
          >
            <SlidersHorizontal
              size={18}
              color={colors.textMuted}
              strokeWidth={1.5}
            />
            {activeFilterCount > 0 ? (
              <View
                style={[styles.filterBadge, { backgroundColor: colors.text }]}
              >
                <Text
                  style={[styles.filterBadgeText, { color: colors.background }]}
                >
                  {activeFilterCount}
                </Text>
              </View>
            ) : null}
          </TouchableOpacity>
        </View>

        {renderAppliedFilters()}
      </View>
    ),
    [activeFilterCount, colors, renderAppliedFilters],
  )

  const renderEmpty = useCallback(
    () => (!isLoading ? <TransactionEmptyState /> : null),
    [isLoading],
  )

  // Loading state
  if (isLoading && transactions.length === 0) {
    return (
      <SafeAreaView
        style={[styles.container, { backgroundColor: colors.background }]}
        edges={["top"]}
      >
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="small" color={colors.textMuted} />
          <Text style={[styles.loadingText, { color: colors.textMuted }]}>
            {t.transactions.loading}
          </Text>
        </View>
      </SafeAreaView>
    )
  }

  return (
    <SafeAreaView
      style={[styles.container, { backgroundColor: colors.background }]}
      edges={["top"]}
    >
      <View
        style={[
          styles.contentContainer,
          isTablet && {
            maxWidth: MAX_CONTENT_WIDTH,
            alignSelf: "center",
            width: "100%",
          },
        ]}
      >
        <TransactionSectionList
          transactions={transactions}
          isLoading={isLoading}
          isLoadingMore={isLoadingMore}
          hasMore={hasMore}
          onLoadMore={handleEndReached}
          onRefresh={handleRefresh}
          ListHeaderComponent={renderHeader}
          contentInset={{ bottom: bottomInset }}
          onScroll={onScroll}
          scrollEventThrottle={16}
          isTablet={isTablet}
        />
      </View>

      <TransactionFilters
        filters={filters}
        onFiltersChange={setFilters}
        entities={entities}
        onApply={handleApplyFilters}
        onClear={handleClearFilters}
        isVisible={filtersVisible}
        onClose={() => setFiltersVisible(false)}
      />
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  contentContainer: {
    flex: 1,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    gap: spacing.md,
  },
  loadingText: {
    fontSize: 14,
    fontWeight: "300",
    letterSpacing: 0.3,
  },
  listContent: {
    paddingHorizontal: spacing.lg,
    flexGrow: 1,
  },
  headerContainer: {
    paddingTop: spacing.xs,
    paddingBottom: spacing.sm,
  },
  appliedFiltersWrap: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
    marginTop: spacing.xs,
  },
  appliedChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
    borderRadius: 999,
    borderWidth: StyleSheet.hairlineWidth,
    maxWidth: "100%",
  },
  appliedChipText: {
    fontSize: 12,
    fontWeight: "400",
    letterSpacing: 0.2,
  },
  topRow: {
    height: spacing.xxl,
    alignItems: "flex-end",
    justifyContent: "flex-start",
  },
  filterButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    padding: 8,
  },
  filterBadge: {
    minWidth: 16,
    height: 16,
    borderRadius: 8,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 4,
  },
  filterBadgeText: {
    fontSize: 10,
    fontWeight: "600",
  },
})
