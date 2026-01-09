import React from "react"
import { View, Text, StyleSheet } from "react-native"
import Animated, { FadeIn, FadeOut, Layout } from "react-native-reanimated"
import { useTheme } from "@/presentation/context"
import { useI18n } from "@/presentation/i18n"
import { getThemeColors, spacing } from "@/presentation/theme"
import {
  BaseTx,
  StockTx,
  FundTx,
  CryptoCurrencyTx,
  AccountTx,
  FundPortfolioTx,
  FactoringTx,
  RealEstateCFTx,
  DepositTx,
  ProductType,
  Dezimal,
} from "@/domain"
import { SensitiveText } from "../ui"

interface TransactionDetailsProps {
  transaction: BaseTx
}

interface DetailRowProps {
  label: string
  value: Dezimal | string | null | undefined
  currency?: string
  isPercentage?: boolean
  decimals?: number
  kind?: "date"
}

function DetailRow({
  label,
  value,
  currency,
  isPercentage = false,
  decimals,
  kind,
}: DetailRowProps) {
  const { resolvedTheme } = useTheme()
  const colors = getThemeColors(resolvedTheme)

  if (value === null || value === undefined) return null

  // For Dezimal values, check if valid
  if (typeof value === "object" && "isFinite" in value) {
    if (!value.isFinite() || value.isZero()) return null
  }

  // For string values
  if (typeof value === "string" && !value.trim()) return null

  return (
    <View style={styles.detailRow}>
      <Text style={[styles.detailLabel, { color: colors.textMuted }]}>
        {label}
      </Text>
      {typeof value === "string" && kind === "date" ? (
        <SensitiveText
          kind="date"
          value={value}
          style={[styles.detailValue, { color: colors.text }]}
        />
      ) : typeof value === "string" ? (
        <Text style={[styles.detailValue, { color: colors.text }]}>
          {value}
        </Text>
      ) : isPercentage ? (
        <SensitiveText
          kind="percentage"
          value={value}
          decimals={decimals ?? 2}
          style={[styles.detailValue, { color: colors.text }]}
        />
      ) : currency ? (
        <SensitiveText
          kind="currency"
          value={value}
          currency={currency}
          style={[styles.detailValue, { color: colors.text }]}
        />
      ) : (
        <SensitiveText
          kind="number"
          value={value}
          decimals={decimals ?? 4}
          style={[styles.detailValue, { color: colors.text }]}
        />
      )}
    </View>
  )
}

export function TransactionDetails({
  transaction: tx,
}: TransactionDetailsProps) {
  const { resolvedTheme } = useTheme()
  const colors = getThemeColors(resolvedTheme)
  const { t } = useI18n()

  const renderDetails = () => {
    switch (tx.productType) {
      case ProductType.STOCK_ETF: {
        const stockTx = tx as StockTx
        return (
          <>
            <DetailRow
              label={t.transactions.shares}
              value={stockTx.shares}
              decimals={4}
            />
            <DetailRow
              label={t.transactions.price}
              value={stockTx.price}
              currency={tx.currency}
            />
            <DetailRow
              label={t.transactions.fees}
              value={stockTx.fees}
              currency={tx.currency}
            />
            <DetailRow
              label={t.transactions.retentions}
              value={stockTx.retentions}
              currency={tx.currency}
            />
            <DetailRow
              label={t.transactions.netAmount}
              value={stockTx.netAmount}
              currency={tx.currency}
            />
            <DetailRow label={t.transactions.isin} value={stockTx.isin} />
            <DetailRow label={t.transactions.ticker} value={stockTx.ticker} />
            <DetailRow label={t.transactions.market} value={stockTx.market} />
            <DetailRow
              label={t.transactions.orderDate}
              value={stockTx.orderDate}
              kind="date"
            />
          </>
        )
      }

      case ProductType.FUND: {
        const fundTx = tx as FundTx
        return (
          <>
            <DetailRow
              label={t.transactions.shares}
              value={fundTx.shares}
              decimals={4}
            />
            <DetailRow
              label={t.transactions.price}
              value={fundTx.price}
              currency={tx.currency}
            />
            <DetailRow
              label={t.transactions.fees}
              value={fundTx.fees}
              currency={tx.currency}
            />
            <DetailRow
              label={t.transactions.retentions}
              value={fundTx.retentions}
              currency={tx.currency}
            />
            <DetailRow
              label={t.transactions.netAmount}
              value={fundTx.netAmount}
              currency={tx.currency}
            />
            <DetailRow label={t.transactions.isin} value={fundTx.isin} />
            <DetailRow label={t.transactions.market} value={fundTx.market} />
            <DetailRow
              label={t.transactions.orderDate}
              value={fundTx.orderDate}
              kind="date"
            />
          </>
        )
      }

      case ProductType.CRYPTO: {
        const cryptoTx = tx as CryptoCurrencyTx
        return (
          <>
            <DetailRow label={t.transactions.symbol} value={cryptoTx.symbol} />
            <DetailRow
              label={t.transactions.currencyAmount}
              value={cryptoTx.currencyAmount}
              decimals={8}
            />
            <DetailRow
              label={t.transactions.price}
              value={cryptoTx.price}
              currency={tx.currency}
            />
            <DetailRow
              label={t.transactions.fees}
              value={cryptoTx.fees}
              currency={tx.currency}
            />
            <DetailRow
              label={t.transactions.retentions}
              value={cryptoTx.retentions}
              currency={tx.currency}
            />
            <DetailRow
              label={t.transactions.netAmount}
              value={cryptoTx.netAmount}
              currency={tx.currency}
            />
          </>
        )
      }

      case ProductType.ACCOUNT: {
        const accountTx = tx as AccountTx
        return (
          <>
            <DetailRow
              label={t.transactions.fees}
              value={accountTx.fees}
              currency={tx.currency}
            />
            <DetailRow
              label={t.transactions.retentions}
              value={accountTx.retentions}
              currency={tx.currency}
            />
            <DetailRow
              label={t.transactions.interestRate}
              value={accountTx.interestRate}
              isPercentage
              decimals={2}
            />
            <DetailRow
              label={t.transactions.avgBalance}
              value={accountTx.avgBalance}
              currency={tx.currency}
            />
            <DetailRow
              label={t.transactions.netAmount}
              value={accountTx.netAmount}
              currency={tx.currency}
            />
          </>
        )
      }

      case ProductType.FUND_PORTFOLIO: {
        const portfolioTx = tx as FundPortfolioTx
        return (
          <>
            <DetailRow
              label={t.transactions.portfolioName}
              value={portfolioTx.portfolioName}
            />
            <DetailRow label={t.transactions.iban} value={portfolioTx.iban} />
            <DetailRow
              label={t.transactions.fees}
              value={portfolioTx.fees}
              currency={tx.currency}
            />
          </>
        )
      }

      case ProductType.FACTORING: {
        const factoringTx = tx as FactoringTx
        return (
          <>
            <DetailRow
              label={t.transactions.fees}
              value={factoringTx.fees}
              currency={tx.currency}
            />
            <DetailRow
              label={t.transactions.retentions}
              value={factoringTx.retentions}
              currency={tx.currency}
            />
            <DetailRow
              label={t.transactions.netAmount}
              value={factoringTx.netAmount}
              currency={tx.currency}
            />
          </>
        )
      }

      case ProductType.REAL_ESTATE_CF: {
        const realEstateTx = tx as RealEstateCFTx
        return (
          <>
            <DetailRow
              label={t.transactions.fees}
              value={realEstateTx.fees}
              currency={tx.currency}
            />
            <DetailRow
              label={t.transactions.retentions}
              value={realEstateTx.retentions}
              currency={tx.currency}
            />
            <DetailRow
              label={t.transactions.netAmount}
              value={realEstateTx.netAmount}
              currency={tx.currency}
            />
          </>
        )
      }

      case ProductType.DEPOSIT: {
        const depositTx = tx as DepositTx
        return (
          <>
            <DetailRow
              label={t.transactions.fees}
              value={depositTx.fees}
              currency={tx.currency}
            />
            <DetailRow
              label={t.transactions.retentions}
              value={depositTx.retentions}
              currency={tx.currency}
            />
            <DetailRow
              label={t.transactions.netAmount}
              value={depositTx.netAmount}
              currency={tx.currency}
            />
          </>
        )
      }

      default:
        return null
    }
  }

  const details = renderDetails()
  if (!details) return null

  return (
    <Animated.View
      entering={FadeIn.duration(150)}
      exiting={FadeOut.duration(100)}
      layout={Layout.duration(150)}
      style={[
        styles.container,
        {
          backgroundColor: colors.surface,
          borderColor: colors.border,
        },
      ]}
    >
      {details}
    </Animated.View>
  )
}

const styles = StyleSheet.create({
  container: {
    marginTop: spacing.sm,
    marginLeft: 38, // Align with content after icon
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: 10,
    borderWidth: StyleSheet.hairlineWidth,
    gap: spacing.xs,
  },
  detailRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 2,
  },
  detailLabel: {
    fontSize: 11,
    fontWeight: "400",
    textTransform: "uppercase",
    letterSpacing: 0.8,
  },
  detailValue: {
    fontSize: 13,
    fontWeight: "400",
    letterSpacing: 0.2,
  },
})
