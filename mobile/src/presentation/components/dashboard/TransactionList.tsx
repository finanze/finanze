import React from "react"
import { View, Text, StyleSheet } from "react-native"
import { useTheme } from "@/presentation/context"
import { useI18n } from "@/presentation/i18n"
import { usePrivacy } from "@/presentation/context"
import { getThemeColors, spacing } from "@/presentation/theme"
import { getTransactionDisplayType } from "@/presentation/utils/transactionDisplay"
import { BaseTx } from "@/domain"
import { ASSET_TYPE_COLOR_MAP } from "@/presentation/utils/colorUtils"
import {
  getIconForAssetType,
  getIconForTxType,
} from "@/presentation/utils/iconUtils"
import { SensitiveText } from "../ui"

interface TransactionListProps {
  transactions: BaseTx[]
}

function getProductTypeColor(productType: string): string {
  return ASSET_TYPE_COLOR_MAP[productType] || "#6b7280"
}

export function TransactionList({ transactions }: TransactionListProps) {
  const { resolvedTheme: colorScheme } = useTheme()
  const colors = getThemeColors(colorScheme)
  const { t } = useI18n()
  const { hideAmounts } = usePrivacy()

  if (transactions.length === 0) {
    return (
      <View style={styles.section}>
        <Text style={[styles.sectionTitle, { color: colors.textMuted }]}>
          {t.dashboard.recentTransactions}
        </Text>
        <View style={styles.emptyContainer}>
          <Text style={[styles.emptyText, { color: colors.textMuted }]}>
            {t.dashboard.noTransactions}
          </Text>
        </View>
      </View>
    )
  }

  return (
    <View style={styles.section}>
      <Text style={[styles.sectionTitle, { color: colors.textMuted }]}>
        {t.dashboard.recentTransactions}
      </Text>

      <View style={styles.list}>
        {transactions.slice(0, 5).map((tx, index) => {
          const displayType = getTransactionDisplayType(tx.type)
          const isIncome = displayType === "in"
          const isFee = tx.type === "FEE"
          const amountColor = isIncome
            ? colors.success[500]
            : isFee
              ? colors.danger[500]
              : colors.text
          const prefix = hideAmounts ? "" : isIncome ? "+" : isFee ? "-" : ""
          const productColor = getProductTypeColor(tx.productType)

          return (
            <View
              key={tx.id || index}
              style={[
                styles.item,
                index < Math.min(transactions.length, 5) - 1 && {
                  borderBottomWidth: StyleSheet.hairlineWidth,
                  borderBottomColor: colors.border,
                },
              ]}
            >
              {/* Transaction type icon */}
              <View style={styles.leftIconWrap}>
                <View
                  style={[
                    styles.txIconContainer,
                    { backgroundColor: colors.background },
                  ]}
                >
                  {getIconForTxType(tx.type, {
                    color: colors.textMuted,
                  })}
                </View>

                {/* Product badge overlay */}
                {tx.productType ? (
                  <View
                    style={[
                      styles.productBadge,
                      {
                        borderColor: colors.border,
                        backgroundColor: colors.background,
                      },
                    ]}
                  >
                    {getIconForAssetType(tx.productType, {
                      color: productColor,
                      size: 12,
                    })}
                  </View>
                ) : null}
              </View>

              <View style={styles.content}>
                <Text
                  style={[styles.name, { color: colors.text }]}
                  numberOfLines={1}
                >
                  {tx.name}
                </Text>

                <View style={styles.metaRow}>
                  <SensitiveText
                    kind="date"
                    value={tx.date}
                    style={[styles.date, { color: colors.textMuted }]}
                  />
                </View>
              </View>

              <View style={styles.amountRow}>
                <Text style={[styles.amount, { color: amountColor }]}>
                  {prefix}
                </Text>
                <SensitiveText
                  kind="currency"
                  value={tx.amount.abs()}
                  currency={tx.currency}
                  style={[styles.amount, { color: amountColor }]}
                />
              </View>
            </View>
          )
        })}
      </View>
    </View>
  )
}

const styles = StyleSheet.create({
  section: {
    paddingTop: spacing.md,
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
  list: {
    gap: 0,
  },
  item: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: spacing.md,
    gap: spacing.sm,
  },
  leftIconWrap: {
    width: 30,
    height: 30,
    position: "relative",
    alignItems: "center",
    justifyContent: "center",
  },
  txIconContainer: {
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
  },
  productBadge: {
    position: "absolute",
    right: -4,
    bottom: -4,
    width: 18,
    height: 18,
    borderRadius: 9,
    borderWidth: StyleSheet.hairlineWidth,
    alignItems: "center",
    justifyContent: "center",
  },
  content: {
    flex: 1,
    gap: 2,
  },
  name: {
    fontSize: 14,
    fontWeight: "400",
    letterSpacing: 0.2,
  },
  metaRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  date: {
    fontSize: 12,
    fontWeight: "300",
    letterSpacing: 0.2,
  },
  amount: {
    fontSize: 15,
    fontWeight: "500",
    letterSpacing: -0.3,
  },
  amountRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 0,
  },
})
