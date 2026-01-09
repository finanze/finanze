import React from "react"
import { View, Text, StyleSheet, TouchableOpacity } from "react-native"
import { ChevronDown, ChevronUp } from "lucide-react-native"
import { useTheme, usePrivacy } from "@/presentation/context"
import { getThemeColors, spacing } from "@/presentation/theme"
import { getTransactionDisplayType } from "@/presentation/utils/transactionDisplay"
import { BaseTx, TxType } from "@/domain"
import {
  ASSET_TYPE_COLOR_MAP,
  ENTITY_COLOR_PALETTE,
  getDeterministicColor,
} from "@/presentation/utils/colorUtils"
import {
  getIconForAssetType,
  getIconForTxType,
} from "@/presentation/utils/iconUtils"
import { SensitiveText } from "../ui"

interface TransactionItemProps {
  transaction: BaseTx
  isExpanded: boolean
  onToggleExpand: () => void
  showBorder?: boolean
}

function getProductTypeColor(productType: string): string {
  return ASSET_TYPE_COLOR_MAP[productType] || "#6b7280"
}

export function TransactionItem({
  transaction: tx,
  isExpanded,
  onToggleExpand,
  showBorder = true,
}: TransactionItemProps) {
  const { resolvedTheme } = useTheme()
  const colors = getThemeColors(resolvedTheme)
  const { hideAmounts } = usePrivacy()

  const displayType = getTransactionDisplayType(tx.type)
  const isIncome = displayType === "in"
  const isFee = tx.type === TxType.FEE

  const amountColor = isIncome
    ? colors.success[500]
    : isFee
      ? colors.danger[500]
      : colors.text

  const prefix = hideAmounts ? "" : isIncome ? "+" : isFee ? "-" : ""
  const productColor = getProductTypeColor(tx.productType)

  const entityColor = tx.entity?.name
    ? getDeterministicColor(tx.entity.name, ENTITY_COLOR_PALETTE)
    : colors.textMuted

  const hasExpandableDetails = checkHasExpandableDetails(tx)

  return (
    <TouchableOpacity
      activeOpacity={hasExpandableDetails ? 0.7 : 1}
      onPress={hasExpandableDetails ? onToggleExpand : undefined}
      style={[
        styles.item,
        showBorder && {
          borderBottomWidth: StyleSheet.hairlineWidth,
          borderBottomColor: colors.border,
        },
      ]}
    >
      <View style={styles.mainRow}>
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
          <Text style={[styles.name, { color: colors.text }]} numberOfLines={1}>
            {tx.name}
          </Text>

          <View style={styles.metaRow}>
            <SensitiveText
              kind="date"
              value={tx.date}
              style={[styles.date, { color: colors.textMuted }]}
            />
            {tx.entity?.name ? (
              <Text
                style={[styles.entityName, { color: entityColor }]}
                numberOfLines={1}
              >
                {tx.entity.name}
              </Text>
            ) : null}
          </View>
        </View>

        <View style={styles.rightSection}>
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

          {hasExpandableDetails ? (
            <View style={styles.chevronWrap}>
              {isExpanded ? (
                <ChevronUp
                  size={16}
                  color={colors.textMuted}
                  strokeWidth={1.5}
                />
              ) : (
                <ChevronDown
                  size={16}
                  color={colors.textMuted}
                  strokeWidth={1.5}
                />
              )}
            </View>
          ) : null}
        </View>
      </View>
    </TouchableOpacity>
  )
}

function checkHasExpandableDetails(tx: BaseTx): boolean {
  // Check if transaction has any detail fields worth showing
  const detailFields = [
    "shares",
    "price",
    "fees",
    "netAmount",
    "isin",
    "ticker",
    "market",
    "retentions",
    "interestRate",
    "avgBalance",
    "currencyAmount",
    "symbol",
    "portfolioName",
    "iban",
  ]

  return detailFields.some(field => {
    const value = (tx as any)[field]
    if (value === null || value === undefined) return false
    if (typeof value === "object" && "isFinite" in value) {
      return value.isFinite() && !value.isZero()
    }
    return Boolean(value)
  })
}

const styles = StyleSheet.create({
  item: {
    paddingVertical: spacing.md,
  },
  mainRow: {
    flexDirection: "row",
    alignItems: "center",
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
    gap: spacing.sm,
  },
  date: {
    fontSize: 12,
    fontWeight: "300",
    letterSpacing: 0.2,
  },
  entityName: {
    fontSize: 11,
    fontWeight: "300",
    letterSpacing: 0.2,
    flex: 1,
  },
  rightSection: {
    alignItems: "flex-end",
    gap: 2,
  },
  amountRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 0,
  },
  amount: {
    fontSize: 15,
    fontWeight: "500",
    letterSpacing: -0.3,
  },
  chevronWrap: {
    marginTop: 2,
  },
})
