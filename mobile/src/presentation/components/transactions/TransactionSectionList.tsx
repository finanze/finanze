import React, { useCallback, useMemo, useState } from "react"
import {
  View,
  Text,
  StyleSheet,
  SectionList,
  ActivityIndicator,
  TouchableOpacity,
  RefreshControl,
  LayoutAnimation,
  Platform,
  UIManager,
} from "react-native"
import { useTheme } from "@/presentation/context"
import { useI18n } from "@/presentation/i18n"
import { getThemeColors, spacing } from "@/presentation/theme"
import { BaseTx } from "@/domain"
import { TransactionItem } from "./TransactionItem"
import { TransactionDetails } from "./TransactionDetails"
import { TransactionEmptyState } from "./TransactionEmptyState"

interface TransactionSectionListProps {
  transactions: BaseTx[]
  isLoading: boolean
  isLoadingMore?: boolean
  hasMore?: boolean
  onLoadMore?: () => void
  onRefresh?: () => Promise<void>
  ListHeaderComponent?: React.ComponentType<any> | React.ReactElement | null
  contentInset?: { bottom?: number }
  onScroll?: any
  scrollEventThrottle?: number
  isTablet?: boolean
}

interface GroupedSection {
  title: string
  subtitle: string
  data: BaseTx[]
}

function formatSectionDate(
  dateStr: string,
  locale: string,
  t: { transactions: { today: string; yesterday: string } },
): { title: string; subtitle: string } {
  const date = new Date(dateStr)
  const today = new Date()
  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)

  const isToday = date.toDateString() === today.toDateString()
  const isYesterday = date.toDateString() === yesterday.toDateString()

  const dayOfMonth = date.getDate()
  const weekday = date.toLocaleDateString(locale, { weekday: "long" })
  const month = date.toLocaleDateString(locale, {
    month: "short",
    year: "numeric",
  })

  if (isToday) {
    return { title: t.transactions.today, subtitle: month }
  }
  if (isYesterday) {
    return { title: t.transactions.yesterday, subtitle: month }
  }

  return {
    title: `${weekday} ${dayOfMonth}`,
    subtitle: month,
  }
}

function groupTransactionsByDate(
  transactions: BaseTx[],
  locale: string,
  t: { transactions: { today: string; yesterday: string } },
): GroupedSection[] {
  const groups = new Map<string, BaseTx[]>()

  for (const tx of transactions) {
    const dateKey = tx.date?.split("T")[0] ?? "unknown"
    const existing = groups.get(dateKey) ?? []
    existing.push(tx)
    groups.set(dateKey, existing)
  }

  const sections: GroupedSection[] = []
  const sortedKeys = Array.from(groups.keys()).sort((a, b) =>
    b.localeCompare(a),
  )

  for (const key of sortedKeys) {
    const txs = groups.get(key) ?? []
    const { title, subtitle } = formatSectionDate(key, locale, t)
    sections.push({ title, subtitle, data: txs })
  }

  return sections
}

export function TransactionSectionList({
  transactions,
  isLoading,
  isLoadingMore = false,
  hasMore = false,
  onLoadMore,
  onRefresh,
  ListHeaderComponent,
  contentInset,
  onScroll,
  scrollEventThrottle,
  isTablet = false,
}: TransactionSectionListProps) {
  const { resolvedTheme } = useTheme()
  const colors = getThemeColors(resolvedTheme)
  const { locale, t } = useI18n()

  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set())
  const [isRefreshing, setIsRefreshing] = useState(false)

  // Enable LayoutAnimation for Android
  React.useEffect(() => {
    if (
      Platform.OS === "android" &&
      typeof UIManager.setLayoutAnimationEnabledExperimental === "function"
    ) {
      UIManager.setLayoutAnimationEnabledExperimental(true)
    }
  }, [])

  const sections = useMemo(
    () => groupTransactionsByDate(transactions, locale, t as any),
    [transactions, locale, t],
  )

  const handleToggleExpand = useCallback((txId: string) => {
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
    setExpandedItems(prev => {
      const next = new Set(prev)
      if (next.has(txId)) {
        next.delete(txId)
      } else {
        next.add(txId)
      }
      return next
    })
  }, [])

  const handleRefresh = useCallback(async () => {
    if (!onRefresh) return
    setIsRefreshing(true)
    await onRefresh()
    setIsRefreshing(false)
  }, [onRefresh])

  const renderSectionHeader = useCallback(
    ({ section }: { section: GroupedSection }) => (
      <View
        style={[
          styles.sectionHeader,
          { backgroundColor: colors.background },
          isTablet && styles.sectionHeaderTablet,
        ]}
      >
        <Text
          style={[
            styles.sectionTitle,
            { color: colors.text },
            isTablet && styles.sectionTitleTablet,
          ]}
        >
          {section.title}
        </Text>
        <Text
          style={[
            styles.sectionSubtitle,
            { color: colors.textMuted },
            isTablet && styles.sectionSubtitleTablet,
          ]}
        >
          {section.subtitle}
        </Text>
      </View>
    ),
    [colors, isTablet],
  )

  const renderItem = useCallback(
    ({
      item,
      index,
      section,
    }: {
      item: BaseTx
      index: number
      section: GroupedSection
    }) => {
      const txId = item.id ?? `tx-${item.date}-${index}`
      const isExpanded = expandedItems.has(txId)
      const isLast = index === section.data.length - 1

      return (
        <View>
          <TransactionItem
            transaction={item}
            isExpanded={isExpanded}
            onToggleExpand={() => handleToggleExpand(txId)}
            showBorder={!isLast}
          />
          {isExpanded ? <TransactionDetails transaction={item} /> : null}
        </View>
      )
    },
    [expandedItems, handleToggleExpand],
  )

  const renderFooter = useCallback(
    () => (
      <View
        style={[styles.footer, { paddingBottom: contentInset?.bottom ?? 0 }]}
      >
        {isLoadingMore ? (
          <ActivityIndicator size="small" color={colors.textMuted} />
        ) : hasMore && onLoadMore ? (
          <TouchableOpacity
            onPress={onLoadMore}
            style={[styles.loadMoreButton, { borderColor: colors.border }]}
            activeOpacity={0.7}
          >
            <Text style={[styles.loadMoreText, { color: colors.text }]}>
              {t.transactions.loadMore}
            </Text>
          </TouchableOpacity>
        ) : transactions.length > 0 ? (
          <Text style={[styles.endText, { color: colors.textMuted }]}>•</Text>
        ) : null}
      </View>
    ),
    [
      colors,
      contentInset?.bottom,
      hasMore,
      isLoadingMore,
      onLoadMore,
      t.transactions.loadMore,
      transactions.length,
    ],
  )

  const renderEmpty = useCallback(
    () => (!isLoading ? <TransactionEmptyState /> : null),
    [isLoading],
  )

  if (isLoading && transactions.length === 0) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="small" color={colors.textMuted} />
        <Text style={[styles.loadingText, { color: colors.textMuted }]}>
          {t.transactions.loading}
        </Text>
      </View>
    )
  }

  return (
    <SectionList
      sections={sections}
      keyExtractor={(item, index) => item.id ?? `tx-${item.date}-${index}`}
      renderItem={renderItem}
      renderSectionHeader={renderSectionHeader}
      ListHeaderComponent={ListHeaderComponent}
      ListFooterComponent={renderFooter}
      ListEmptyComponent={renderEmpty}
      contentContainerStyle={styles.listContent}
      showsVerticalScrollIndicator={false}
      stickySectionHeadersEnabled={false}
      onScroll={onScroll}
      scrollEventThrottle={scrollEventThrottle}
      onEndReached={hasMore && onLoadMore ? onLoadMore : undefined}
      onEndReachedThreshold={0.3}
      refreshControl={
        onRefresh ? (
          <RefreshControl
            refreshing={isRefreshing}
            onRefresh={handleRefresh}
            tintColor={colors.textMuted}
          />
        ) : undefined
      }
    />
  )
}

const styles = StyleSheet.create({
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
  sectionHeader: {
    flexDirection: "row",
    alignItems: "baseline",
    justifyContent: "space-between",
    paddingVertical: spacing.sm,
    paddingTop: spacing.lg,
  },
  sectionHeaderTablet: {
    paddingVertical: spacing.md,
    paddingTop: spacing.xl,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: "500",
    letterSpacing: 0.2,
  },
  sectionTitleTablet: {
    fontSize: 17,
    fontWeight: "600",
  },
  sectionSubtitle: {
    fontSize: 12,
    fontWeight: "300",
    letterSpacing: 0.3,
  },
  sectionSubtitleTablet: {
    fontSize: 14,
  },
  footer: {
    alignItems: "center",
    paddingVertical: spacing.xl,
  },
  loadMoreButton: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    borderRadius: 20,
    borderWidth: StyleSheet.hairlineWidth,
  },
  loadMoreText: {
    fontSize: 13,
    fontWeight: "400",
    letterSpacing: 0.2,
  },
  endText: {
    fontSize: 18,
    fontWeight: "300",
  },
})
