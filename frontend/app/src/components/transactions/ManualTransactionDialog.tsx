import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { format } from "date-fns"
import { X } from "lucide-react"
import { useI18n } from "@/i18n"
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { Label } from "@/components/ui/Label"
import { DatePicker } from "@/components/ui/DatePicker"
import { DataSource, EntityOrigin } from "@/types"
import {
  ProductType,
  type StockInvestments,
  type FundInvestments,
  type FundPortfolios,
} from "@/types/position"
import { useFinancialData } from "@/context/FinancialDataContext"
import {
  ManualTransactionPayload,
  type ManualAccountTransactionPayload,
  type ManualStockTransactionPayload,
  type ManualFundTransactionPayload,
  type ManualFundPortfolioTransactionPayload,
  type ManualFactoringTransactionPayload,
  type ManualRealEstateTransactionPayload,
  type ManualDepositTransactionPayload,
  type FundPortfolioTx,
  TransactionsResult,
  TxType,
} from "@/types/transactions"

const SUPPORTED_PRODUCT_TYPES = [
  ProductType.ACCOUNT,
  ProductType.STOCK_ETF,
  ProductType.FUND,
  ProductType.FUND_PORTFOLIO,
  ProductType.FACTORING,
  ProductType.REAL_ESTATE_CF,
  ProductType.DEPOSIT,
] as const

export type SupportedManualProductType =
  (typeof SUPPORTED_PRODUCT_TYPES)[number]

const NET_AMOUNT_PRODUCT_TYPES = new Set<SupportedManualProductType>([
  ProductType.ACCOUNT,
  ProductType.STOCK_ETF,
  ProductType.FUND,
  ProductType.FACTORING,
  ProductType.REAL_ESTATE_CF,
  ProductType.DEPOSIT,
])

const OUTGOING_TX_TYPES = new Set<TxType>([
  TxType.BUY,
  TxType.INVESTMENT,
  TxType.SUBSCRIPTION,
  TxType.FEE,
  TxType.RIGHT_ISSUE,
  TxType.TRANSFER_OUT,
  TxType.SWITCH_FROM,
  TxType.SWAP_FROM,
])

export interface ManualTransactionEntityOption {
  id: string
  name: string
  origin: EntityOrigin
}

export interface ManualTransactionSubmitResult {
  payload: ManualTransactionPayload
  transactionId?: string
}

interface ManualTransactionDialogProps {
  isOpen: boolean
  mode: "create" | "edit"
  transaction?: TransactionsResult["transactions"][number] | null
  entities: ManualTransactionEntityOption[]
  currencyOptions: string[]
  defaultCurrency: string
  onClose: () => void
  onSubmit: (result: ManualTransactionSubmitResult) => Promise<void>
  isSubmitting: boolean
}

type ManualTransactionFormState = {
  id?: string
  ref: string
  entityId: string
  entityName?: string
  entityOrigin?: EntityOrigin
  name: string
  date: string
  type: TxType
  productType: SupportedManualProductType
  amount: string
  currency: string
  extra: Record<string, string>
}

type FieldType = "text" | "number" | "date"

interface FieldConfig {
  name: string
  labelKey: string
  type: FieldType
  required?: boolean
  numericType?: "positive" | "nonNegative"
  step?: string
}

interface SuggestionOption {
  value: string
  label: string
}

const normalizeDateValue = (value?: string | null) => {
  if (!value) return ""
  if (value.length >= 10) {
    return value.slice(0, 10)
  }
  return value
}

const generateTransactionRef = () => {
  const timestamp = format(new Date(), "yyyyMMddHHmmss")
  const random = Math.random().toString(36).slice(2, 6).toUpperCase()
  return `${timestamp}-${random}`
}

const createExtraDefaults = (
  productType: SupportedManualProductType,
): Record<string, string> => {
  switch (productType) {
    case ProductType.ACCOUNT:
      return {
        fees: "0",
        retentions: "0",
        interest_rate: "",
        avg_balance: "",
      }
    case ProductType.STOCK_ETF:
      return {
        ticker: "",
        isin: "",
        shares: "",
        price: "",
        fees: "0",
        retentions: "0",
        market: "",
        order_date: "",
      }
    case ProductType.FUND:
      return {
        isin: "",
        shares: "",
        price: "",
        fees: "0",
        retentions: "0",
        market: "",
        order_date: "",
      }
    case ProductType.FUND_PORTFOLIO:
      return {
        portfolio_name: "",
        fees: "0",
        iban: "",
      }
    case ProductType.FACTORING:
    case ProductType.REAL_ESTATE_CF:
    case ProductType.DEPOSIT:
      return {
        fees: "0",
        retentions: "0",
      }
    default:
      return {}
  }
}

const getFieldConfigs = (
  productType: SupportedManualProductType,
  t: ReturnType<typeof useI18n>["t"],
): FieldConfig[] => {
  switch (productType) {
    case ProductType.ACCOUNT:
      return [
        {
          name: "fees",
          labelKey: t.transactions.fees,
          type: "number",
          numericType: "nonNegative",
          step: "0.01",
        },
        {
          name: "retentions",
          labelKey: t.transactions.retentions,
          type: "number",
          numericType: "nonNegative",
          step: "0.01",
        },
        {
          name: "interest_rate",
          labelKey: t.transactions.interestRate,
          type: "number",
          step: "0.01",
        },
        {
          name: "avg_balance",
          labelKey: t.transactions.avgBalance,
          type: "number",
          step: "0.01",
        },
      ]
    case ProductType.STOCK_ETF:
      return [
        { name: "ticker", labelKey: t.transactions.ticker, type: "text" },
        { name: "isin", labelKey: t.transactions.isin, type: "text" },
        {
          name: "shares",
          labelKey: t.transactions.shares,
          type: "number",
          required: true,
          numericType: "positive",
          step: "0.0001",
        },
        {
          name: "price",
          labelKey: t.transactions.price,
          type: "number",
          required: true,
          numericType: "positive",
          step: "0.0001",
        },
        {
          name: "fees",
          labelKey: t.transactions.fees,
          type: "number",
          numericType: "nonNegative",
          step: "0.01",
        },
        {
          name: "retentions",
          labelKey: t.transactions.retentions,
          type: "number",
          numericType: "nonNegative",
          step: "0.01",
        },
        { name: "market", labelKey: t.transactions.market, type: "text" },
        {
          name: "order_date",
          labelKey: t.transactions.orderDate,
          type: "date",
        },
      ]
    case ProductType.FUND:
      return [
        {
          name: "isin",
          labelKey: t.transactions.isin,
          type: "text",
          required: true,
        },
        {
          name: "shares",
          labelKey: t.transactions.shares,
          type: "number",
          required: true,
          numericType: "positive",
          step: "0.0001",
        },
        {
          name: "price",
          labelKey: t.transactions.price,
          type: "number",
          required: true,
          numericType: "positive",
          step: "0.0001",
        },
        {
          name: "fees",
          labelKey: t.transactions.fees,
          type: "number",
          numericType: "nonNegative",
          step: "0.01",
        },
        {
          name: "retentions",
          labelKey: t.transactions.retentions,
          type: "number",
          numericType: "nonNegative",
          step: "0.01",
        },
        { name: "market", labelKey: t.transactions.market, type: "text" },
        {
          name: "order_date",
          labelKey: t.transactions.orderDate,
          type: "date",
        },
      ]
    case ProductType.FUND_PORTFOLIO:
      return [
        {
          name: "portfolio_name",
          labelKey: t.transactions.portfolioName,
          type: "text",
          required: true,
        },
        {
          name: "fees",
          labelKey: t.transactions.fees,
          type: "number",
          numericType: "nonNegative",
          step: "0.01",
        },
        { name: "iban", labelKey: t.transactions.iban, type: "text" },
      ]
    case ProductType.FACTORING:
    case ProductType.REAL_ESTATE_CF:
    case ProductType.DEPOSIT:
      return [
        {
          name: "fees",
          labelKey: t.transactions.fees,
          type: "number",
          numericType: "nonNegative",
          step: "0.01",
        },
        {
          name: "retentions",
          labelKey: t.transactions.retentions,
          type: "number",
          numericType: "nonNegative",
          step: "0.01",
        },
      ]
    default:
      return []
  }
}

const parseNumberValue = (value: string, fallback = 0) => {
  const trimmed = value.trim()
  if (!trimmed) return fallback
  const parsed = Number.parseFloat(trimmed)
  if (Number.isNaN(parsed)) return fallback
  return parsed
}

const parseOptionalNumber = (value: string) => {
  const trimmed = value.trim()
  if (!trimmed) return undefined
  const parsed = Number.parseFloat(trimmed)
  if (Number.isNaN(parsed)) return undefined
  return parsed
}

export function ManualTransactionDialog({
  isOpen,
  mode,
  transaction,
  entities,
  currencyOptions,
  defaultCurrency,
  onClose,
  onSubmit,
  isSubmitting,
}: ManualTransactionDialogProps) {
  const { t, locale } = useI18n()
  const { positionsData } = useFinancialData()
  const [formState, setFormState] = useState<ManualTransactionFormState>(
    () => ({
      ref: generateTransactionRef(),
      entityId: "",
      name: "",
      date: format(new Date(), "yyyy-MM-dd"),
      type: TxType.BUY,
      productType: SUPPORTED_PRODUCT_TYPES[0],
      amount: "",
      currency: defaultCurrency.toUpperCase(),
      extra: createExtraDefaults(SUPPORTED_PRODUCT_TYPES[0]),
    }),
  )
  const [errors, setErrors] = useState<Record<string, string>>({})
  const sharesPriceEditedRef = useRef(false)

  const selectedEntityName = useMemo(() => {
    if (!formState.entityId) return ""
    if (formState.entityName) return formState.entityName
    const option = entities.find(entity => entity.id === formState.entityId)
    if (option) return option.name
    const positionEntityName =
      positionsData?.positions?.[formState.entityId]?.entity?.name
    return positionEntityName || ""
  }, [entities, formState.entityId, formState.entityName, positionsData])

  const suggestionsByField = useMemo<Record<string, SuggestionOption[]>>(() => {
    const suggestions: Record<string, SuggestionOption[]> = {}
    if (!formState.entityId || !positionsData?.positions) {
      return suggestions
    }

    const entityPosition = positionsData.positions[formState.entityId]
    if (!entityPosition) {
      return suggestions
    }

    if (formState.productType === ProductType.STOCK_ETF) {
      const stockPositions = entityPosition.products[ProductType.STOCK_ETF] as
        | StockInvestments
        | undefined
      if (stockPositions?.entries?.length) {
        const seen = new Set<string>()
        const options = stockPositions.entries.reduce<SuggestionOption[]>(
          (acc, entry) => {
            const value = entry.isin?.trim().toUpperCase()
            if (!value || seen.has(value)) return acc
            seen.add(value)
            const parts = [value]
            if (entry.ticker) {
              parts.push(entry.ticker.toUpperCase())
            }
            acc.push({
              value,
              label: parts.join(" · "),
            })
            return acc
          },
          [],
        )
        if (options.length > 0) {
          suggestions.isin = options.slice(0, 6)
        }
      }
    }

    if (formState.productType === ProductType.FUND) {
      const fundPositions = entityPosition.products[ProductType.FUND] as
        | FundInvestments
        | undefined
      if (fundPositions?.entries?.length) {
        const seen = new Set<string>()
        const options = fundPositions.entries.reduce<SuggestionOption[]>(
          (acc, entry) => {
            const value = entry.isin?.trim().toUpperCase()
            if (!value || seen.has(value)) return acc
            seen.add(value)
            const label = entry.name ? `${value} · ${entry.name}` : value
            acc.push({
              value,
              label,
            })
            return acc
          },
          [],
        )
        if (options.length > 0) {
          suggestions.isin = options.slice(0, 6)
        }
      }
    }

    if (formState.productType === ProductType.FUND_PORTFOLIO) {
      const fundPortfolios = entityPosition.products[
        ProductType.FUND_PORTFOLIO
      ] as FundPortfolios | undefined
      if (fundPortfolios?.entries?.length) {
        const nameSeen = new Set<string>()
        const names: SuggestionOption[] = []
        const ibanSeen = new Set<string>()
        const ibans: SuggestionOption[] = []

        fundPortfolios.entries.forEach(portfolio => {
          const portfolioName = portfolio.name?.trim()
          if (portfolioName && !nameSeen.has(portfolioName)) {
            nameSeen.add(portfolioName)
            names.push({ value: portfolioName, label: portfolioName })
          }

          const rawIban = portfolio.account?.iban
          if (rawIban) {
            const normalized = rawIban.replace(/\s+/g, "").toUpperCase()
            if (!ibanSeen.has(normalized)) {
              ibanSeen.add(normalized)
              const display = portfolio.account?.iban || normalized
              const accountLabel = portfolio.account?.name?.trim()
              ibans.push({
                value: normalized,
                label: accountLabel ? `${display} · ${accountLabel}` : display,
              })
            }
          }
        })

        if (names.length > 0) {
          suggestions.portfolio_name = names.slice(0, 6)
        }
        if (ibans.length > 0) {
          suggestions.iban = ibans.slice(0, 6)
        }
      }
    }

    return suggestions
  }, [formState.entityId, formState.productType, positionsData])

  const supportsNetAmount = useMemo(
    () => NET_AMOUNT_PRODUCT_TYPES.has(formState.productType),
    [formState.productType],
  )

  const isOutgoingType = useMemo(
    () => OUTGOING_TX_TYPES.has(formState.type),
    [formState.type],
  )

  const isFeeType = formState.type === TxType.FEE

  const netAmount = useMemo(() => {
    if (!supportsNetAmount) {
      return null
    }

    const gross = Number.parseFloat(formState.amount)
    if (!Number.isFinite(gross) || gross <= 0) {
      return null
    }

    const feesRaw = formState.extra?.fees ?? ""
    const retentionsRaw = formState.extra?.retentions ?? ""
    const fees = Number.parseFloat(feesRaw || "0")
    const retentions = Number.parseFloat(retentionsRaw || "0")

    const safeFees = Number.isFinite(fees) ? fees : 0
    const safeRetentions = Number.isFinite(retentions) ? retentions : 0
    const effectiveFees = isFeeType && Number.isFinite(gross) ? gross : safeFees

    const result = isOutgoingType
      ? gross + effectiveFees + safeRetentions
      : gross - effectiveFees - safeRetentions
    if (!Number.isFinite(result)) {
      return null
    }

    return result
  }, [
    formState.amount,
    formState.extra?.fees,
    formState.extra?.retentions,
    isFeeType,
    isOutgoingType,
    supportsNetAmount,
  ])

  const formattedNetAmount = useMemo(() => {
    if (netAmount === null) {
      return null
    }

    const currency = (formState.currency || defaultCurrency).toUpperCase()
    try {
      return new Intl.NumberFormat(locale ?? "en", {
        style: "currency",
        currency,
      }).format(netAmount)
    } catch {
      return `${netAmount.toFixed(2)} ${currency}`
    }
  }, [defaultCurrency, formState.currency, locale, netAmount])

  const netAmountFormulaText = isOutgoingType
    ? t.transactions.form.netAmountFormulaOutgoing
    : t.transactions.form.netAmountFormulaIncoming

  useEffect(() => {
    if (
      formState.productType !== ProductType.STOCK_ETF &&
      formState.productType !== ProductType.FUND
    ) {
      return
    }

    if (mode === "edit" && !sharesPriceEditedRef.current) {
      return
    }

    setFormState(prev => {
      if (
        prev.productType !== ProductType.STOCK_ETF &&
        prev.productType !== ProductType.FUND
      ) {
        return prev
      }

      const shares = Number.parseFloat(prev.extra?.shares ?? "")
      const price = Number.parseFloat(prev.extra?.price ?? "")

      if (!Number.isFinite(shares) || !Number.isFinite(price)) {
        return prev
      }

      const computed = (shares * price).toFixed(2)
      if (prev.amount === computed) {
        return prev
      }

      return {
        ...prev,
        amount: computed,
      }
    })
  }, [
    formState.extra?.shares,
    formState.extra?.price,
    formState.productType,
    mode,
    setFormState,
  ])

  const getSuggestionLabel = useCallback(
    (fieldName: string) => {
      const suggestions = t.transactions.form.suggestions
      if (!suggestions) {
        return "Suggestions"
      }

      if (fieldName === "isin") {
        return formState.productType === ProductType.STOCK_ETF
          ? suggestions.stocks
          : suggestions.funds
      }

      if (fieldName === "portfolio_name") {
        return suggestions.portfolios
      }

      if (fieldName === "iban") {
        return suggestions.accounts
      }

      return suggestions.label
    },
    [formState.productType, t],
  )

  const resetForm = useCallback(() => {
    setFormState({
      ref: generateTransactionRef(),
      entityId: "",
      name: "",
      date: format(new Date(), "yyyy-MM-dd"),
      type: TxType.BUY,
      productType: SUPPORTED_PRODUCT_TYPES[0],
      amount: "",
      currency: defaultCurrency.toUpperCase(),
      extra: createExtraDefaults(SUPPORTED_PRODUCT_TYPES[0]),
    })
    setErrors({})
    sharesPriceEditedRef.current = false
  }, [defaultCurrency])

  useEffect(() => {
    if (!isOpen) {
      return
    }

    if (mode === "edit" && transaction) {
      const productType = SUPPORTED_PRODUCT_TYPES.includes(
        transaction.product_type as SupportedManualProductType,
      )
        ? (transaction.product_type as SupportedManualProductType)
        : SUPPORTED_PRODUCT_TYPES[0]

      const baseExtra = createExtraDefaults(productType)

      const nextState: ManualTransactionFormState = {
        id: transaction.id,
        ref: transaction.ref,
        entityId: transaction.entity?.id || "",
        entityName: transaction.entity?.name ?? undefined,
        entityOrigin: transaction.entity?.origin,
        name: transaction.name || "",
        date:
          normalizeDateValue(transaction.date) ||
          format(new Date(), "yyyy-MM-dd"),
        type: transaction.type,
        productType,
        amount: `${transaction.amount ?? ""}`,
        currency: (transaction.currency || defaultCurrency).toUpperCase(),
        extra: baseExtra,
      }

      switch (productType) {
        case ProductType.ACCOUNT:
          nextState.extra = {
            ...baseExtra,
            fees: `${transaction.fees ?? 0}`,
            retentions: `${transaction.retentions ?? 0}`,
            interest_rate: transaction.interest_rate
              ? `${transaction.interest_rate}`
              : "",
            avg_balance: transaction.avg_balance
              ? `${transaction.avg_balance}`
              : "",
          }
          break
        case ProductType.STOCK_ETF:
          nextState.extra = {
            ...baseExtra,
            ticker: transaction.ticker ?? "",
            isin: transaction.isin ?? "",
            shares: transaction.shares ? `${transaction.shares}` : "",
            price: transaction.price ? `${transaction.price}` : "",
            fees: `${transaction.fees ?? 0}`,
            retentions: transaction.retentions
              ? `${transaction.retentions}`
              : "0",
            market: transaction.market ?? "",
            order_date: normalizeDateValue(transaction.order_date) ?? "",
          }
          break
        case ProductType.FUND:
          nextState.extra = {
            ...baseExtra,
            isin: transaction.isin ?? "",
            shares: transaction.shares ? `${transaction.shares}` : "",
            price: transaction.price ? `${transaction.price}` : "",
            fees: `${transaction.fees ?? 0}`,
            retentions: transaction.retentions
              ? `${transaction.retentions}`
              : "0",
            market: transaction.market ?? "",
            order_date: normalizeDateValue(transaction.order_date) ?? "",
          }
          break
        case ProductType.FUND_PORTFOLIO: {
          const fundPortfolioTx = transaction as Partial<FundPortfolioTx>
          nextState.extra = {
            ...baseExtra,
            portfolio_name:
              fundPortfolioTx.portfolio_name?.toString() ||
              transaction.name ||
              "",
            fees: `${transaction.fees ?? 0}`,
            iban: fundPortfolioTx.iban ?? "",
          }
          break
        }
        case ProductType.FACTORING:
        case ProductType.REAL_ESTATE_CF:
        case ProductType.DEPOSIT:
          nextState.extra = {
            ...baseExtra,
            fees: `${transaction.fees ?? 0}`,
            retentions: `${transaction.retentions ?? 0}`,
          }
          break
        default:
          break
      }

      setFormState(nextState)
      setErrors({})
      sharesPriceEditedRef.current = false
    } else {
      resetForm()
    }
  }, [isOpen, mode, transaction, defaultCurrency, resetForm])

  const fieldConfigs = useMemo(() => {
    const configs = getFieldConfigs(formState.productType, t)
    if (isFeeType) {
      return configs.filter(field => field.name !== "fees")
    }
    return configs
  }, [formState.productType, isFeeType, t])

  const clearError = useCallback((key: string) => {
    setErrors(prev => {
      if (!(key in prev)) return prev
      const rest = { ...prev }
      delete rest[key]
      return rest
    })
  }, [])

  const handleBaseChange = <K extends keyof ManualTransactionFormState>(
    key: K,
    value: ManualTransactionFormState[K],
  ) => {
    setFormState(prev => ({
      ...prev,
      [key]: value,
    }))
    clearError(key.toString())
  }

  const handleExtraChange = (name: string, value: string) => {
    if (name === "shares" || name === "price") {
      sharesPriceEditedRef.current = true
    }
    setFormState(prev => ({
      ...prev,
      extra: {
        ...prev.extra,
        [name]: value,
      },
    }))
    clearError(`extra.${name}`)
  }

  const handleSuggestionApply = (name: string, value: string) => {
    handleExtraChange(name, value)
  }

  const validate = () => {
    const newErrors: Record<string, string> = {}

    if (!formState.entityId) {
      newErrors.entityId = t.transactions.form.errors.required
    }

    if (!formState.ref.trim()) {
      newErrors.ref = t.transactions.form.errors.required
    }

    if (!formState.name.trim()) {
      newErrors.name = t.transactions.form.errors.required
    }

    if (!formState.date) {
      newErrors.date = t.transactions.form.errors.required
    }

    const amountValue = Number.parseFloat(formState.amount)
    if (!formState.amount || Number.isNaN(amountValue) || amountValue <= 0) {
      newErrors.amount = t.transactions.form.errors.positive
    }

    if (!formState.currency) {
      newErrors.currency = t.transactions.form.errors.required
    }

    const typeExists = Object.values(TxType).includes(formState.type)
    if (!typeExists) {
      newErrors.type = t.transactions.form.errors.required
    }

    if (!SUPPORTED_PRODUCT_TYPES.includes(formState.productType)) {
      newErrors.productType = t.transactions.form.errors.required
    }

    fieldConfigs.forEach(field => {
      const value = formState.extra[field.name] ?? ""
      if (field.required && !value.trim()) {
        newErrors[`extra.${field.name}`] = t.transactions.form.errors.required
        return
      }

      if (field.type === "number" && value.trim()) {
        const numeric = Number.parseFloat(value)
        if (Number.isNaN(numeric)) {
          newErrors[`extra.${field.name}`] =
            t.transactions.form.errors.invalidNumber
          return
        }
        if (field.numericType === "positive" && numeric <= 0) {
          newErrors[`extra.${field.name}`] = t.transactions.form.errors.positive
          return
        }
        if (field.numericType === "nonNegative" && numeric < 0) {
          newErrors[`extra.${field.name}`] =
            t.transactions.form.errors.nonNegative
          return
        }
      }
    })

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const buildPayload = () => {
    const amountValue = parseNumberValue(formState.amount)
    const resolvedFees =
      isFeeType && Number.isFinite(amountValue)
        ? amountValue
        : parseNumberValue(formState.extra.fees ?? "0", 0)

    const base = {
      id: formState.id ?? formState.ref,
      ref: formState.ref.trim(),
      name: formState.name.trim(),
      amount: amountValue,
      currency: formState.currency.toUpperCase(),
      type: formState.type,
      date: formState.date,
      entity_id: formState.entityId,
      source: DataSource.MANUAL,
    }

    switch (formState.productType) {
      case ProductType.ACCOUNT: {
        const payload: ManualAccountTransactionPayload = {
          ...base,
          product_type: ProductType.ACCOUNT,
          fees: resolvedFees,
          retentions: parseNumberValue(formState.extra.retentions, 0),
          interest_rate: parseOptionalNumber(formState.extra.interest_rate),
          avg_balance: parseOptionalNumber(formState.extra.avg_balance),
        }
        return payload
      }
      case ProductType.STOCK_ETF: {
        const payload: ManualStockTransactionPayload = {
          ...base,
          product_type: ProductType.STOCK_ETF,
          ticker: formState.extra.ticker.trim().toUpperCase() || undefined,
          isin: formState.extra.isin.trim().toUpperCase() || undefined,
          shares: parseNumberValue(formState.extra.shares),
          price: parseNumberValue(formState.extra.price),
          fees: resolvedFees,
          retentions: parseNumberValue(formState.extra.retentions, 0),
          market: formState.extra.market.trim() || undefined,
          order_date: formState.extra.order_date || undefined,
        }
        return payload
      }
      case ProductType.FUND: {
        const payload: ManualFundTransactionPayload = {
          ...base,
          product_type: ProductType.FUND,
          isin: formState.extra.isin.trim().toUpperCase(),
          shares: parseNumberValue(formState.extra.shares),
          price: parseNumberValue(formState.extra.price),
          fees: resolvedFees,
          retentions: parseNumberValue(formState.extra.retentions, 0),
          market: formState.extra.market.trim() || undefined,
          order_date: formState.extra.order_date || undefined,
        }
        return payload
      }
      case ProductType.FUND_PORTFOLIO: {
        const payload: ManualFundPortfolioTransactionPayload = {
          ...base,
          product_type: ProductType.FUND_PORTFOLIO,
          portfolio_name: formState.extra.portfolio_name.trim(),
          fees: resolvedFees,
          iban:
            formState.extra.iban.replace(/\s+/g, "").toUpperCase() || undefined,
        }
        return payload
      }
      case ProductType.FACTORING: {
        const payload: ManualFactoringTransactionPayload = {
          ...base,
          product_type: ProductType.FACTORING,
          fees: resolvedFees,
          retentions: parseNumberValue(formState.extra.retentions, 0),
        }
        return payload
      }
      case ProductType.REAL_ESTATE_CF: {
        const payload: ManualRealEstateTransactionPayload = {
          ...base,
          product_type: ProductType.REAL_ESTATE_CF,
          fees: resolvedFees,
          retentions: parseNumberValue(formState.extra.retentions, 0),
        }
        return payload
      }
      case ProductType.DEPOSIT: {
        const payload: ManualDepositTransactionPayload = {
          ...base,
          product_type: ProductType.DEPOSIT,
          fees: resolvedFees,
          retentions: parseNumberValue(formState.extra.retentions, 0),
        }
        return payload
      }
      default:
        return {
          ...base,
          product_type: formState.productType,
        } as ManualTransactionPayload
    }
  }

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!validate()) return
    const payload = buildPayload()
    await onSubmit({ payload, transactionId: formState.id })
  }

  const handleClose = () => {
    if (isSubmitting) return
    onClose()
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-[18000]"
          onClick={e => {
            if (e.target === e.currentTarget) handleClose()
          }}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="w-full max-w-3xl"
          >
            <Card>
              <CardHeader className="flex flex-row items-start justify-between gap-4">
                <div>
                  <CardTitle className="text-xl">
                    {mode === "create"
                      ? t.transactions.form.createTitle
                      : t.transactions.form.editTitle}
                  </CardTitle>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={handleClose}
                  disabled={isSubmitting}
                >
                  <X className="h-4 w-4" />
                </Button>
              </CardHeader>
              <form onSubmit={handleSubmit}>
                <CardContent className="space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <Label htmlFor="transaction-entity">
                        {t.transactions.form.entity}
                      </Label>
                      <select
                        id="transaction-entity"
                        value={formState.entityId}
                        onChange={event => {
                          const option = entities.find(
                            e => e.id === event.target.value,
                          )
                          handleBaseChange("entityId", event.target.value)
                          if (option) {
                            setFormState(prev => ({
                              ...prev,
                              entityName: option.name,
                              entityOrigin: option.origin,
                            }))
                          }
                        }}
                        disabled={mode === "edit"}
                        className={`w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${errors.entityId ? "border-red-500" : ""}`}
                      >
                        <option value="" disabled>
                          {t.common.selectOptions}
                        </option>
                        {entities.map(option => (
                          <option key={option.id} value={option.id}>
                            {option.name}
                          </option>
                        ))}
                      </select>
                      {errors.entityId && (
                        <p className="text-xs text-red-600 dark:text-red-400">
                          {errors.entityId}
                        </p>
                      )}
                    </div>

                    <div className="space-y-1.5">
                      <Label htmlFor="transaction-name">
                        {t.transactions.name}
                      </Label>
                      <Input
                        id="transaction-name"
                        value={formState.name}
                        onChange={event =>
                          handleBaseChange("name", event.target.value)
                        }
                        className={errors.name ? "border-red-500" : ""}
                      />
                      {errors.name && (
                        <p className="text-xs text-red-600 dark:text-red-400">
                          {errors.name}
                        </p>
                      )}
                    </div>

                    <div className="space-y-1.5">
                      <Label>{t.transactions.date}</Label>
                      <DatePicker
                        value={formState.date}
                        onChange={value => {
                          handleBaseChange("date", value || "")
                        }}
                        placeholder={t.transactions.form.pickDate}
                        disabled={isSubmitting}
                        className={errors.date ? "border-red-500" : ""}
                      />
                      {errors.date && (
                        <p className="text-xs text-red-600 dark:text-red-400">
                          {errors.date}
                        </p>
                      )}
                    </div>

                    <div className="space-y-1.5">
                      <Label htmlFor="transaction-type">
                        {t.transactions.form.transactionType}
                      </Label>
                      <select
                        id="transaction-type"
                        value={formState.type}
                        onChange={event =>
                          handleBaseChange("type", event.target.value as TxType)
                        }
                        className={`w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${errors.type ? "border-red-500" : ""}`}
                      >
                        {Object.values(TxType).map(type => (
                          <option key={type} value={type}>
                            {(t.enums as any)?.transactionType?.[type] || type}
                          </option>
                        ))}
                      </select>
                      {errors.type && (
                        <p className="text-xs text-red-600 dark:text-red-400">
                          {errors.type}
                        </p>
                      )}
                    </div>

                    <div className="space-y-1.5">
                      <Label htmlFor="transaction-product">
                        {t.transactions.product}
                      </Label>
                      <select
                        id="transaction-product"
                        value={formState.productType}
                        onChange={event => {
                          const value = event.target
                            .value as SupportedManualProductType
                          clearError("productType")
                          setFormState(prev => ({
                            ...prev,
                            productType: value,
                            extra: createExtraDefaults(value),
                          }))
                          setErrors(prev => {
                            const next: Record<string, string> = {}
                            Object.entries(prev).forEach(([key, message]) => {
                              if (!key.startsWith("extra.")) {
                                next[key] = message
                              }
                            })
                            return next
                          })
                          sharesPriceEditedRef.current = false
                        }}
                        className={`w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${errors.productType ? "border-red-500" : ""}`}
                        disabled={isSubmitting}
                      >
                        {SUPPORTED_PRODUCT_TYPES.map(type => (
                          <option key={type} value={type}>
                            {t.enums?.productType?.[type] || type}
                          </option>
                        ))}
                      </select>
                      {errors.productType && (
                        <p className="text-xs text-red-600 dark:text-red-400">
                          {errors.productType}
                        </p>
                      )}
                    </div>

                    <div className="space-y-1.5">
                      <Label htmlFor="transaction-amount">
                        {t.transactions.amount}
                      </Label>
                      <Input
                        id="transaction-amount"
                        type="number"
                        inputMode="decimal"
                        min="0"
                        step="0.01"
                        value={formState.amount}
                        onChange={event =>
                          handleBaseChange("amount", event.target.value)
                        }
                        className={errors.amount ? "border-red-500" : ""}
                      />
                      {errors.amount && (
                        <p className="text-xs text-red-600 dark:text-red-400">
                          {errors.amount}
                        </p>
                      )}
                      {supportsNetAmount && formattedNetAmount && (
                        <p className="text-xs text-muted-foreground">
                          <span className="font-medium">
                            {t.transactions.form.netAmountLabel}
                          </span>{" "}
                          {formattedNetAmount}
                          <span className="ml-1 text-[11px] uppercase tracking-wide">
                            ({netAmountFormulaText})
                          </span>
                        </p>
                      )}
                    </div>

                    <div className="space-y-1.5">
                      <Label htmlFor="transaction-currency">
                        {t.transactions.currency}
                      </Label>
                      <select
                        id="transaction-currency"
                        value={formState.currency}
                        onChange={event =>
                          handleBaseChange("currency", event.target.value)
                        }
                        className={`w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${errors.currency ? "border-red-500" : ""}`}
                      >
                        {currencyOptions.map(option => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </select>
                      {errors.currency && (
                        <p className="text-xs text-red-600 dark:text-red-400">
                          {errors.currency}
                        </p>
                      )}
                    </div>
                  </div>

                  {fieldConfigs.length > 0 && (
                    <div className="border-t border-border pt-4">
                      <h3 className="text-sm font-semibold mb-3 text-muted-foreground">
                        {t.transactions.form.detailsSection}
                      </h3>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {fieldConfigs.map(field => {
                          const errorKey = `extra.${field.name}`
                          const error = errors[errorKey]
                          if (field.type === "date") {
                            return (
                              <div key={field.name} className="space-y-1.5">
                                <Label>{field.labelKey}</Label>
                                <DatePicker
                                  value={formState.extra[field.name] ?? ""}
                                  onChange={value =>
                                    handleExtraChange(field.name, value || "")
                                  }
                                  placeholder={t.transactions.form.pickDate}
                                  disabled={isSubmitting}
                                />
                                {error && (
                                  <p className="text-xs text-red-600 dark:text-red-400">
                                    {error}
                                  </p>
                                )}
                              </div>
                            )
                          }

                          const fieldSuggestions =
                            suggestionsByField[field.name] ?? []
                          const showSuggestions = fieldSuggestions.length > 0

                          if (
                            (formState.productType === ProductType.STOCK_ETF ||
                              formState.productType === ProductType.FUND) &&
                            field.name === "shares"
                          ) {
                            const priceField = fieldConfigs.find(
                              option => option.name === "price",
                            )
                            const priceError = errors["extra.price"]

                            return (
                              <div
                                key="shares-price"
                                className="space-y-2 md:col-span-2"
                              >
                                <div className="flex flex-col gap-3 md:flex-row md:items-end">
                                  <div className="flex-1 space-y-1.5">
                                    <Label htmlFor="transaction-shares">
                                      {field.labelKey}
                                    </Label>
                                    <Input
                                      id="transaction-shares"
                                      type={
                                        field.type === "number"
                                          ? "number"
                                          : "text"
                                      }
                                      inputMode={
                                        field.type === "number"
                                          ? "decimal"
                                          : undefined
                                      }
                                      step={
                                        field.type === "number"
                                          ? (field.step ?? "0.01")
                                          : undefined
                                      }
                                      value={formState.extra.shares ?? ""}
                                      onChange={event =>
                                        handleExtraChange(
                                          "shares",
                                          event.target.value,
                                        )
                                      }
                                      className={error ? "border-red-500" : ""}
                                    />
                                    {error && (
                                      <p className="text-xs text-red-600 dark:text-red-400">
                                        {error}
                                      </p>
                                    )}
                                  </div>
                                  <span className="flex items-center justify-center text-sm font-semibold text-muted-foreground md:pb-2">
                                    ×
                                  </span>
                                  <div className="flex-1 space-y-1.5">
                                    <Label htmlFor="transaction-price">
                                      {priceField?.labelKey ??
                                        t.transactions.price}
                                    </Label>
                                    <Input
                                      id="transaction-price"
                                      type={
                                        priceField?.type === "number"
                                          ? "number"
                                          : "text"
                                      }
                                      inputMode={
                                        priceField?.type === "number"
                                          ? "decimal"
                                          : undefined
                                      }
                                      step={
                                        priceField?.type === "number"
                                          ? (priceField.step ?? "0.01")
                                          : undefined
                                      }
                                      value={formState.extra.price ?? ""}
                                      onChange={event =>
                                        handleExtraChange(
                                          "price",
                                          event.target.value,
                                        )
                                      }
                                      className={
                                        priceError ? "border-red-500" : ""
                                      }
                                    />
                                    {priceError && (
                                      <p className="text-xs text-red-600 dark:text-red-400">
                                        {priceError}
                                      </p>
                                    )}
                                  </div>
                                </div>
                                {t.transactions.form.autoAmountHint &&
                                  (formState.extra.shares ||
                                    formState.extra.price) && (
                                    <p className="text-xs text-muted-foreground">
                                      {t.transactions.form.autoAmountHint}
                                    </p>
                                  )}
                              </div>
                            )
                          }

                          if (
                            (formState.productType === ProductType.STOCK_ETF ||
                              formState.productType === ProductType.FUND) &&
                            field.name === "price"
                          ) {
                            return null
                          }

                          return (
                            <div key={field.name} className="space-y-1.5">
                              <Label htmlFor={`transaction-${field.name}`}>
                                {field.labelKey}
                              </Label>
                              <Input
                                id={`transaction-${field.name}`}
                                type={
                                  field.type === "number" ? "number" : "text"
                                }
                                inputMode={
                                  field.type === "number"
                                    ? "decimal"
                                    : undefined
                                }
                                step={
                                  field.type === "number"
                                    ? (field.step ?? "0.01")
                                    : undefined
                                }
                                value={formState.extra[field.name] ?? ""}
                                onChange={event =>
                                  handleExtraChange(
                                    field.name,
                                    event.target.value,
                                  )
                                }
                                className={error ? "border-red-500" : ""}
                              />
                              {showSuggestions && (
                                <div className="w-full space-y-1 pt-1">
                                  <span className="text-[11px] uppercase tracking-wide text-muted-foreground">
                                    {getSuggestionLabel(field.name)}
                                    {selectedEntityName
                                      ? ` · ${selectedEntityName}`
                                      : ""}
                                  </span>
                                  <div className="flex max-h-24 flex-wrap items-center gap-1 overflow-y-auto pr-1">
                                    {fieldSuggestions.map(option => (
                                      <button
                                        key={`${field.name}-${option.value}`}
                                        type="button"
                                        onClick={() =>
                                          handleSuggestionApply(
                                            field.name,
                                            option.value,
                                          )
                                        }
                                        className="rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                                      >
                                        {option.label}
                                      </button>
                                    ))}
                                  </div>
                                </div>
                              )}
                              {error && (
                                <p className="text-xs text-red-600 dark:text-red-400">
                                  {error}
                                </p>
                              )}
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  )}
                </CardContent>
                <CardFooter className="flex justify-end gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={handleClose}
                    disabled={isSubmitting}
                  >
                    {t.common.cancel}
                  </Button>
                  <Button type="submit" disabled={isSubmitting}>
                    {isSubmitting ? t.common.saving : t.common.save}
                  </Button>
                </CardFooter>
              </form>
            </Card>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
