import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { format } from "date-fns"
import {
  X,
  ChevronDown,
  Check,
  ListFilter,
  ChartCandlestick,
  BarChart3,
  Bitcoin,
} from "lucide-react"
import { EntitySelector } from "@/components/EntitySelector"
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
import { DecimalInput } from "@/components/ui/DecimalInput"
import { Label } from "@/components/ui/Label"
import { DatePicker } from "@/components/ui/DatePicker"
import { DataSource, EntityOrigin, type Entity } from "@/types"
import { getCurrencySymbol, cn } from "@/lib/utils"
import { getIconForTxType, getIconForProductType } from "@/utils/dashboardUtils"
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from "@/components/ui/Popover"
import {
  ProductType,
  EquityType,
  type StockInvestments,
  type StockDetail,
  type FundInvestments,
  type FundDetail,
  type FundPortfolios,
  type CryptoCurrencies,
} from "@/types/position"
import { getIssuerIconPath } from "@/utils/issuerIcons"
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
  type ManualCryptoCurrencyTransactionPayload,
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
  ProductType.CRYPTO,
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

export interface ManualTransactionSubmitResult {
  payload: ManualTransactionPayload
  transactionId?: string
}

interface ManualTransactionDialogProps {
  isOpen: boolean
  mode: "create" | "edit"
  transaction?: TransactionsResult["transactions"][number] | null
  entities: Entity[]
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
  name?: string
  ticker?: string
  market?: string
  equityType?: string
  issuer?: string | null
  iconUrls?: string[] | null
}

function SuggestionItemIcon({
  option,
  productType,
}: {
  option: SuggestionOption
  productType: string
}) {
  const [failedCount, setFailedCount] = useState(0)

  const sources = useMemo(() => {
    if (productType === ProductType.STOCK_ETF) {
      if (option.equityType === EquityType.ETF) {
        const issuerPath = getIssuerIconPath(option.issuer ?? null)
        return issuerPath ? [`/${issuerPath}`] : []
      }
      return [
        option.value?.trim()
          ? `https://static.finanze.me/icons/ticker/${encodeURIComponent(option.value.trim())}.png`
          : null,
        option.ticker?.trim()
          ? `https://static.finanze.me/icons/ticker/${encodeURIComponent(option.ticker.trim())}.png`
          : null,
      ].filter((v): v is string => Boolean(v))
    }
    if (productType === ProductType.FUND) {
      const issuerPath = getIssuerIconPath(option.issuer ?? null)
      return issuerPath ? [`/${issuerPath}`] : []
    }
    if (productType === ProductType.CRYPTO) {
      return (option.iconUrls ?? []).filter((v): v is string => Boolean(v))
    }
    return []
  }, [
    option.value,
    option.ticker,
    option.equityType,
    option.issuer,
    option.iconUrls,
    productType,
  ])

  const currentSrc = sources[failedCount]

  if (productType === ProductType.STOCK_ETF) {
    if (!currentSrc) {
      return (
        <div className="h-5 w-5 bg-muted flex items-center justify-center shrink-0 rounded-md">
          <ChartCandlestick className="h-3 w-3 text-muted-foreground" />
        </div>
      )
    }
    return (
      <img
        src={currentSrc}
        alt=""
        className="h-5 w-5 shrink-0 rounded object-contain"
        onError={() => setFailedCount(prev => prev + 1)}
      />
    )
  }

  if (productType === ProductType.FUND) {
    if (!currentSrc) {
      return (
        <div className="h-5 w-5 bg-muted flex items-center justify-center shrink-0 rounded-md">
          <BarChart3 className="h-3 w-3 text-muted-foreground" />
        </div>
      )
    }
    return (
      <img
        src={currentSrc}
        alt=""
        className="h-5 w-5 shrink-0 rounded-md object-contain"
        onError={() => setFailedCount(prev => prev + 1)}
      />
    )
  }

  if (productType === ProductType.CRYPTO) {
    if (!currentSrc) {
      return (
        <div className="h-5 w-5 bg-muted flex items-center justify-center shrink-0 rounded-md">
          <Bitcoin className="h-3 w-3 text-muted-foreground" />
        </div>
      )
    }
    return (
      <img
        src={currentSrc}
        alt=""
        className="h-5 w-5 shrink-0 rounded-md object-contain"
        onError={() => setFailedCount(prev => prev + 1)}
      />
    )
  }

  return null
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
    case ProductType.CRYPTO:
      return {
        symbol: "",
        currency_amount: "",
        price: "",
        fees: "0",
        retentions: "0",
        order_date: "",
        contract_address: "",
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
    case ProductType.CRYPTO:
      return [
        {
          name: "symbol",
          labelKey: t.transactions.symbol,
          type: "text",
          required: true,
        },
        {
          name: "currency_amount",
          labelKey: t.transactions.currencyAmount,
          type: "number",
          required: true,
          numericType: "positive",
          step: "0.00000001",
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
        {
          name: "order_date",
          labelKey: t.transactions.orderDate,
          type: "date",
        },
        {
          name: "contract_address",
          labelKey: t.transactions.contractAddress,
          type: "text",
        },
      ]
    default:
      return []
  }
}

const parseNumberValue = (value: string, fallback = 0) => {
  const trimmed = value.trim().replace(",", ".")
  if (!trimmed) return fallback
  const parsed = Number.parseFloat(trimmed)
  if (Number.isNaN(parsed)) return fallback
  return parsed
}

const parseOptionalNumber = (value: string) => {
  const trimmed = value.trim().replace(",", ".")
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
      positionsData?.positions?.[formState.entityId]?.[0]?.entity?.name
    return positionEntityName || ""
  }, [entities, formState.entityId, formState.entityName, positionsData])

  const suggestionsByField = useMemo<Record<string, SuggestionOption[]>>(() => {
    const suggestions: Record<string, SuggestionOption[]> = {}
    if (!formState.entityId || !positionsData?.positions) {
      return suggestions
    }

    const entityPositions = positionsData.positions[formState.entityId] ?? []
    if (entityPositions.length === 0) {
      return suggestions
    }

    if (formState.productType === ProductType.STOCK_ETF) {
      const seen = new Set<string>()
      const options: SuggestionOption[] = []
      entityPositions.forEach(ep => {
        const stockPositions = ep.products[ProductType.STOCK_ETF] as
          | StockInvestments
          | undefined
        stockPositions?.entries?.forEach((entry: StockDetail) => {
          const value = entry.isin?.trim().toUpperCase()
          if (!value || seen.has(value)) return
          seen.add(value)
          options.push({
            value,
            label: entry.ticker
              ? `${value} · ${entry.ticker.toUpperCase()}`
              : value,
            name: entry.name,
            ticker: entry.ticker?.toUpperCase(),
            market: entry.market || undefined,
            equityType: entry.type,
            issuer: entry.issuer,
          })
        })
      })
      if (options.length > 0) {
        suggestions.isin = options
      }
    }

    if (formState.productType === ProductType.FUND) {
      const seen = new Set<string>()
      const options: SuggestionOption[] = []
      entityPositions.forEach(ep => {
        const fundPositions = ep.products[ProductType.FUND] as
          | FundInvestments
          | undefined
        fundPositions?.entries?.forEach((entry: FundDetail) => {
          const value = entry.isin?.trim().toUpperCase()
          if (!value || seen.has(value)) return
          seen.add(value)
          options.push({
            value,
            label: entry.name ? `${value} · ${entry.name}` : value,
            name: entry.name,
            issuer: entry.issuer,
          })
        })
      })
      if (options.length > 0) {
        suggestions.isin = options
      }
    }

    if (formState.productType === ProductType.FUND_PORTFOLIO) {
      const nameSeen = new Set<string>()
      const names: SuggestionOption[] = []
      const ibanSeen = new Set<string>()
      const ibans: SuggestionOption[] = []

      entityPositions.forEach(ep => {
        const fundPortfolios = ep.products[ProductType.FUND_PORTFOLIO] as
          | FundPortfolios
          | undefined
        fundPortfolios?.entries?.forEach(portfolio => {
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
                name: accountLabel ?? undefined,
              })
            }
          }
        })
      })

      if (names.length > 0) {
        suggestions.portfolio_name = names
      }
      if (ibans.length > 0) {
        suggestions.iban = ibans
      }
    }

    if (formState.productType === ProductType.CRYPTO) {
      const seen = new Set<string>()
      const options: SuggestionOption[] = []
      entityPositions.forEach(ep => {
        const cryptoPositions = ep.products[ProductType.CRYPTO] as
          | CryptoCurrencies
          | undefined
        cryptoPositions?.entries?.forEach(wallet => {
          wallet.assets?.forEach(asset => {
            if (!asset.symbol || !asset.crypto_asset) return
            const value = asset.symbol.trim().toUpperCase()
            if (seen.has(value)) return
            seen.add(value)
            options.push({
              value,
              label: value,
              name: asset.crypto_asset.name || asset.name || undefined,
              iconUrls: asset.crypto_asset.icon_urls,
            })
          })
        })
      })
      if (options.length > 0) {
        suggestions.symbol = options
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

    const gross = Number.parseFloat(formState.amount.replace(",", "."))
    if (!Number.isFinite(gross) || gross <= 0) {
      return null
    }

    const feesRaw = formState.extra?.fees ?? ""
    const retentionsRaw = formState.extra?.retentions ?? ""
    const fees = Number.parseFloat((feesRaw || "0").replace(",", "."))
    const retentions = Number.parseFloat(
      (retentionsRaw || "0").replace(",", "."),
    )

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

  const currencySymbol = useMemo(
    () => getCurrencySymbol(formState.currency || defaultCurrency),
    [formState.currency, defaultCurrency],
  )

  const [suggestionPopoverField, setSuggestionPopoverField] = useState<
    string | null
  >(null)

  const [txTypeDropdownOpen, setTxTypeDropdownOpen] = useState(false)
  const [productTypeDropdownOpen, setProductTypeDropdownOpen] = useState(false)
  const txTypeDropdownRef = useRef<HTMLDivElement>(null)
  const productTypeDropdownRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        txTypeDropdownRef.current &&
        !txTypeDropdownRef.current.contains(event.target as Node)
      ) {
        setTxTypeDropdownOpen(false)
      }
      if (
        productTypeDropdownRef.current &&
        !productTypeDropdownRef.current.contains(event.target as Node)
      ) {
        setProductTypeDropdownOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  useEffect(() => {
    if (
      formState.productType !== ProductType.STOCK_ETF &&
      formState.productType !== ProductType.FUND &&
      formState.productType !== ProductType.CRYPTO
    ) {
      return
    }

    if (mode === "edit" && !sharesPriceEditedRef.current) {
      return
    }

    setFormState(prev => {
      if (
        prev.productType !== ProductType.STOCK_ETF &&
        prev.productType !== ProductType.FUND &&
        prev.productType !== ProductType.CRYPTO
      ) {
        return prev
      }

      const qtyKey =
        prev.productType === ProductType.CRYPTO ? "currency_amount" : "shares"
      const qty = Number.parseFloat(
        (prev.extra?.[qtyKey] ?? "").replace(",", "."),
      )
      const price = Number.parseFloat(
        (prev.extra?.price ?? "").replace(",", "."),
      )

      if (!Number.isFinite(qty) || !Number.isFinite(price)) {
        return prev
      }

      const computed = (qty * price).toFixed(2)
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
    formState.extra?.currency_amount,
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

      if (fieldName === "symbol") {
        return suggestions.crypto
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
        case ProductType.CRYPTO:
          nextState.extra = {
            ...baseExtra,
            symbol: transaction.symbol ?? "",
            currency_amount: transaction.currency_amount
              ? `${transaction.currency_amount}`
              : "",
            price: transaction.price ? `${transaction.price}` : "",
            fees: `${transaction.fees ?? 0}`,
            retentions: transaction.retentions
              ? `${transaction.retentions}`
              : "0",
            order_date: normalizeDateValue(transaction.order_date) ?? "",
            contract_address: transaction.contract_address ?? "",
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
    if (name === "shares" || name === "price" || name === "currency_amount") {
      sharesPriceEditedRef.current = true
    }
    const normalizedValue =
      name === "isin" ||
      name === "ticker" ||
      name === "iban" ||
      name === "symbol"
        ? value.toUpperCase()
        : value
    setFormState(prev => ({
      ...prev,
      extra: {
        ...prev.extra,
        [name]: normalizedValue,
      },
    }))
    clearError(`extra.${name}`)
  }

  const handleSuggestionApply = (
    fieldName: string,
    value: string,
    option?: SuggestionOption,
  ) => {
    handleExtraChange(fieldName, value)
    if (!option) return

    if (
      fieldName === "isin" &&
      formState.productType === ProductType.STOCK_ETF
    ) {
      if (option.ticker && !formState.extra.ticker?.trim()) {
        handleExtraChange("ticker", option.ticker)
      }
      if (option.market && !formState.extra.market?.trim()) {
        handleExtraChange("market", option.market)
      }
    }

    if (fieldName === "isin" && option.name && !formState.name.trim()) {
      setFormState(prev => ({ ...prev, name: option.name! }))
    }

    if (
      fieldName === "symbol" &&
      formState.productType === ProductType.CRYPTO &&
      option.name &&
      !formState.name.trim()
    ) {
      setFormState(prev => ({ ...prev, name: option.name! }))
    }
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

    const amountValue = Number.parseFloat(formState.amount.replace(",", "."))
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
        const numeric = Number.parseFloat(value.replace(",", "."))
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
      case ProductType.CRYPTO: {
        const payload: ManualCryptoCurrencyTransactionPayload = {
          ...base,
          product_type: ProductType.CRYPTO,
          symbol: formState.extra.symbol.trim().toUpperCase(),
          currency_amount: parseNumberValue(formState.extra.currency_amount),
          price: parseNumberValue(formState.extra.price),
          fees: resolvedFees,
          retentions: parseNumberValue(formState.extra.retentions, 0),
          order_date: formState.extra.order_date || undefined,
          contract_address:
            formState.extra.contract_address.trim() || undefined,
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
          className="fixed inset-0 bg-black/50 flex items-center justify-center pt-10 px-4 pb-4 z-[18000]"
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="w-full max-w-3xl"
          >
            <Card className="max-h-[calc(100vh-5rem)] flex flex-col">
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
              <form
                onSubmit={handleSubmit}
                className="flex flex-1 flex-col overflow-hidden"
              >
                <CardContent className="space-y-6 flex-1 overflow-y-auto">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <Label htmlFor="transaction-entity">
                        {t.transactions.form.entity}
                      </Label>
                      <EntitySelector
                        entities={entities}
                        selectedEntityIds={
                          formState.entityId ? [formState.entityId] : []
                        }
                        onSelectionChange={ids => {
                          const entityId = ids[0] ?? ""
                          const option = entities.find(e => e.id === entityId)
                          handleBaseChange("entityId", entityId)
                          if (option) {
                            setFormState(prev => ({
                              ...prev,
                              entityName: option.name,
                              entityOrigin: option.origin,
                            }))
                          }
                        }}
                        singleSelect
                        disabled={mode === "edit"}
                        placeholder={t.common.selectOptions}
                        className="max-w-none"
                      />
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
                      <div className="relative" ref={txTypeDropdownRef}>
                        <div
                          id="transaction-type"
                          role="combobox"
                          tabIndex={0}
                          aria-haspopup="listbox"
                          aria-expanded={txTypeDropdownOpen}
                          className={cn(
                            "flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm cursor-pointer",
                            "focus-within:ring-2 focus-within:ring-ring",
                            errors.type && "border-red-500",
                          )}
                          onClick={() => setTxTypeDropdownOpen(prev => !prev)}
                          onKeyDown={e => {
                            if (e.key === "Enter" || e.key === " ") {
                              e.preventDefault()
                              setTxTypeDropdownOpen(prev => !prev)
                            } else if (e.key === "Escape") {
                              setTxTypeDropdownOpen(false)
                            }
                          }}
                        >
                          <span className="flex items-center gap-2">
                            {getIconForTxType(formState.type, "h-4 w-4")}
                            {(t.enums as any)?.transactionType?.[
                              formState.type
                            ] || formState.type}
                          </span>
                          <ChevronDown
                            className={cn(
                              "h-4 w-4 shrink-0 transition-transform",
                              txTypeDropdownOpen && "rotate-180",
                            )}
                          />
                        </div>
                        {txTypeDropdownOpen && (
                          <div
                            role="listbox"
                            className="absolute z-50 w-full mt-1 bg-background border border-input rounded-md shadow-lg max-h-60 overflow-auto"
                          >
                            {Object.values(TxType).map(type => (
                              <div
                                key={type}
                                role="option"
                                aria-selected={formState.type === type}
                                className={cn(
                                  "flex items-center justify-between px-3 py-2 text-sm cursor-pointer hover:bg-accent hover:text-accent-foreground",
                                  formState.type === type &&
                                    "bg-accent text-accent-foreground",
                                )}
                                onClick={() => {
                                  handleBaseChange("type", type)
                                  setTxTypeDropdownOpen(false)
                                }}
                              >
                                <span className="flex items-center gap-2">
                                  {getIconForTxType(type, "h-4 w-4")}
                                  {(t.enums as any)?.transactionType?.[type] ||
                                    type}
                                </span>
                                {formState.type === type && (
                                  <Check className="h-4 w-4" />
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
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
                      <div className="relative" ref={productTypeDropdownRef}>
                        <div
                          id="transaction-product"
                          role="combobox"
                          tabIndex={0}
                          aria-haspopup="listbox"
                          aria-expanded={productTypeDropdownOpen}
                          className={cn(
                            "flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm cursor-pointer",
                            "focus-within:ring-2 focus-within:ring-ring",
                            isSubmitting && "cursor-not-allowed opacity-50",
                            errors.productType && "border-red-500",
                          )}
                          onClick={() => {
                            if (!isSubmitting)
                              setProductTypeDropdownOpen(prev => !prev)
                          }}
                          onKeyDown={e => {
                            if (isSubmitting) return
                            if (e.key === "Enter" || e.key === " ") {
                              e.preventDefault()
                              setProductTypeDropdownOpen(prev => !prev)
                            } else if (e.key === "Escape") {
                              setProductTypeDropdownOpen(false)
                            }
                          }}
                        >
                          <span className="flex items-center gap-2">
                            {getIconForProductType(
                              formState.productType,
                              "h-4 w-4",
                            )}
                            {t.enums?.productType?.[formState.productType] ||
                              formState.productType}
                          </span>
                          <ChevronDown
                            className={cn(
                              "h-4 w-4 shrink-0 transition-transform",
                              productTypeDropdownOpen && "rotate-180",
                            )}
                          />
                        </div>
                        {productTypeDropdownOpen && !isSubmitting && (
                          <div
                            role="listbox"
                            className="absolute z-50 w-full mt-1 bg-background border border-input rounded-md shadow-lg max-h-60 overflow-auto"
                          >
                            {SUPPORTED_PRODUCT_TYPES.map(type => (
                              <div
                                key={type}
                                role="option"
                                aria-selected={formState.productType === type}
                                className={cn(
                                  "flex items-center justify-between px-3 py-2 text-sm cursor-pointer hover:bg-accent hover:text-accent-foreground",
                                  formState.productType === type &&
                                    "bg-accent text-accent-foreground",
                                )}
                                onClick={() => {
                                  clearError("productType")
                                  setFormState(prev => ({
                                    ...prev,
                                    productType: type,
                                    extra: createExtraDefaults(type),
                                  }))
                                  setErrors(prev => {
                                    const next: Record<string, string> = {}
                                    Object.entries(prev).forEach(
                                      ([key, message]) => {
                                        if (!key.startsWith("extra.")) {
                                          next[key] = message
                                        }
                                      },
                                    )
                                    return next
                                  })
                                  sharesPriceEditedRef.current = false
                                  setProductTypeDropdownOpen(false)
                                }}
                              >
                                <span className="flex items-center gap-2">
                                  {getIconForProductType(type, "h-4 w-4")}
                                  {t.enums?.productType?.[type] || type}
                                </span>
                                {formState.productType === type && (
                                  <Check className="h-4 w-4" />
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
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
                      <div className="relative">
                        <DecimalInput
                          id="transaction-amount"
                          value={formState.amount}
                          onStringChange={value =>
                            handleBaseChange("amount", value)
                          }
                          className={cn(
                            "pr-10",
                            errors.amount && "border-red-500",
                          )}
                        />
                        <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted-foreground pointer-events-none">
                          {currencySymbol}
                        </span>
                      </div>
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
                          <span className="ml-1 text-[11px] tracking-wide">
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
                                    <div className="relative">
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
                                        className={cn(
                                          "pr-10",
                                          priceError && "border-red-500",
                                        )}
                                      />
                                      <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted-foreground pointer-events-none">
                                        {currencySymbol}
                                      </span>
                                    </div>
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
                            formState.productType === ProductType.CRYPTO &&
                            field.name === "currency_amount"
                          ) {
                            const priceField = fieldConfigs.find(
                              option => option.name === "price",
                            )
                            const priceError = errors["extra.price"]

                            return (
                              <div
                                key="currency_amount-price"
                                className="space-y-2 md:col-span-2"
                              >
                                <div className="flex flex-col gap-3 md:flex-row md:items-end">
                                  <div className="flex-1 space-y-1.5">
                                    <Label htmlFor="transaction-currency-amount">
                                      {field.labelKey}
                                    </Label>
                                    <DecimalInput
                                      id="transaction-currency-amount"
                                      value={
                                        formState.extra.currency_amount ?? ""
                                      }
                                      onStringChange={value =>
                                        handleExtraChange(
                                          "currency_amount",
                                          value,
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
                                    <Label htmlFor="transaction-crypto-price">
                                      {priceField?.labelKey ??
                                        t.transactions.price}
                                    </Label>
                                    <div className="relative">
                                      <DecimalInput
                                        id="transaction-crypto-price"
                                        value={formState.extra.price ?? ""}
                                        onStringChange={value =>
                                          handleExtraChange("price", value)
                                        }
                                        className={cn(
                                          priceError ? "border-red-500" : "",
                                          currencySymbol ? "pr-8" : "",
                                        )}
                                      />
                                      {currencySymbol && (
                                        <span className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-muted-foreground text-sm">
                                          {currencySymbol}
                                        </span>
                                      )}
                                    </div>
                                    {priceError && (
                                      <p className="text-xs text-red-600 dark:text-red-400">
                                        {priceError}
                                      </p>
                                    )}
                                  </div>
                                </div>
                                {t.transactions.form.autoAmountHint &&
                                  (formState.extra.currency_amount ||
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
                              formState.productType === ProductType.FUND ||
                              formState.productType === ProductType.CRYPTO) &&
                            field.name === "price"
                          ) {
                            return null
                          }

                          const isMonoField =
                            field.name === "isin" ||
                            field.name === "iban" ||
                            field.name === "symbol" ||
                            field.name === "contract_address"
                          const fieldSuffix =
                            field.name === "interest_rate"
                              ? "%"
                              : ["fees", "retentions", "avg_balance"].includes(
                                    field.name,
                                  )
                                ? currencySymbol
                                : null

                          return (
                            <div key={field.name} className="space-y-1.5">
                              <div className="flex items-center justify-between gap-2 min-h-[20px]">
                                <Label
                                  htmlFor={`transaction-${field.name}`}
                                  className="shrink-0"
                                >
                                  {field.labelKey}
                                </Label>
                                {showSuggestions && (
                                  <Popover
                                    open={suggestionPopoverField === field.name}
                                    onOpenChange={open =>
                                      setSuggestionPopoverField(
                                        open ? field.name : null,
                                      )
                                    }
                                  >
                                    <PopoverTrigger asChild>
                                      <button
                                        type="button"
                                        className="inline-flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground transition-colors min-w-0"
                                      >
                                        <ListFilter className="h-3 w-3 shrink-0" />
                                        <span className="truncate">
                                          {getSuggestionLabel(field.name)}
                                          {selectedEntityName
                                            ? ` · ${selectedEntityName}`
                                            : ""}
                                        </span>
                                      </button>
                                    </PopoverTrigger>
                                    <PopoverContent
                                      align="end"
                                      className="w-80 p-0"
                                    >
                                      <div className="max-h-72 overflow-y-auto py-1">
                                        {fieldSuggestions.map(option => (
                                          <button
                                            key={`${field.name}-${option.value}`}
                                            type="button"
                                            className="flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm transition-colors hover:bg-muted"
                                            onClick={() => {
                                              handleSuggestionApply(
                                                field.name,
                                                option.value,
                                                option,
                                              )
                                              setSuggestionPopoverField(null)
                                            }}
                                          >
                                            <SuggestionItemIcon
                                              option={option}
                                              productType={
                                                formState.productType
                                              }
                                            />
                                            <div className="flex flex-col gap-0.5 overflow-hidden">
                                              {option.name ? (
                                                <>
                                                  <span className="truncate font-medium text-foreground">
                                                    {option.name}
                                                  </span>
                                                  <span
                                                    className={cn(
                                                      "truncate text-xs text-muted-foreground",
                                                      isMonoField &&
                                                        "font-mono",
                                                    )}
                                                  >
                                                    {option.value}
                                                    {option.ticker &&
                                                      option.ticker !==
                                                        option.value && (
                                                        <span className="ml-1.5 text-muted-foreground/70">
                                                          {option.ticker}
                                                        </span>
                                                      )}
                                                  </span>
                                                </>
                                              ) : (
                                                <span
                                                  className={cn(
                                                    "truncate font-medium text-foreground",
                                                    isMonoField && "font-mono",
                                                  )}
                                                >
                                                  {option.value}
                                                </span>
                                              )}
                                            </div>
                                          </button>
                                        ))}
                                      </div>
                                    </PopoverContent>
                                  </Popover>
                                )}
                              </div>
                              <div
                                className={fieldSuffix ? "relative" : undefined}
                              >
                                {field.type === "number" ? (
                                  <DecimalInput
                                    id={`transaction-${field.name}`}
                                    value={formState.extra[field.name] ?? ""}
                                    onStringChange={value =>
                                      handleExtraChange(field.name, value)
                                    }
                                    className={cn(
                                      isMonoField && "font-mono",
                                      fieldSuffix && "pr-10",
                                      error && "border-red-500",
                                    )}
                                  />
                                ) : (
                                  <Input
                                    id={`transaction-${field.name}`}
                                    type="text"
                                    value={formState.extra[field.name] ?? ""}
                                    onChange={event =>
                                      handleExtraChange(
                                        field.name,
                                        event.target.value,
                                      )
                                    }
                                    className={cn(
                                      isMonoField && "font-mono",
                                      fieldSuffix && "pr-10",
                                      error && "border-red-500",
                                    )}
                                  />
                                )}
                                {fieldSuffix && (
                                  <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted-foreground pointer-events-none">
                                    {fieldSuffix}
                                  </span>
                                )}
                              </div>
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
