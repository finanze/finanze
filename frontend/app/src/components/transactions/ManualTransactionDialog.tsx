import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { format } from "date-fns"
import {
  X,
  Save,
  ChevronDown,
  Check,
  ListFilter,
  ChartCandlestick,
  BarChart3,
  Bitcoin,
  ArrowLeftRight,
  Repeat,
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
import { Switch } from "@/components/ui/Switch"
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
  ProductType.STOCK_ETF,
  ProductType.ACCOUNT,
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

const NO_ORDER_DATE_TX_TYPES = new Set<TxType>([
  TxType.SWAP_FROM,
  TxType.SWAP_TO,
  TxType.FEE,
  TxType.DIVIDEND,
])

const MANUAL_INPUT_EXCLUDED_TX_TYPES = new Set<TxType>([
  TxType.SWITCH_FROM,
  TxType.SWITCH_TO,
])

const LOCKED_EDIT_TX_TYPES = new Set<TxType>([
  TxType.TRANSFER_IN,
  TxType.TRANSFER_OUT,
  TxType.SWAP_FROM,
  TxType.SWAP_TO,
])

const INVESTMENT_FLOW_TX_TYPES = [
  TxType.INVESTMENT,
  TxType.REPAYMENT,
  TxType.INTEREST,
  TxType.FEE,
] as const

const TRANSFER_UI_TYPE = "TRANSFER"
const SWAP_UI_TYPE = "SWAP"

type ManualTxTypeOption = TxType | typeof TRANSFER_UI_TYPE | typeof SWAP_UI_TYPE

type TransferLegState = {
  enabled: boolean
  name: string
  date: string
  entityId: string
  extra: Record<string, string>
}

const TRANSFER_PRODUCT_TYPES = new Set<SupportedManualProductType>([
  ProductType.FUND,
  ProductType.STOCK_ETF,
])

const SWAP_PRODUCT_TYPES = new Set<SupportedManualProductType>([
  ProductType.STOCK_ETF,
])

const isTransferUiType = (
  type: ManualTxTypeOption,
): type is typeof TRANSFER_UI_TYPE => type === TRANSFER_UI_TYPE

const isSwapUiType = (type: ManualTxTypeOption): type is typeof SWAP_UI_TYPE =>
  type === SWAP_UI_TYPE

const isDomainTxType = (type: ManualTxTypeOption): type is TxType =>
  !isTransferUiType(type) && !isSwapUiType(type)

const DEFAULT_MORE_DETAILS_FIELDS = new Set(["fees", "retentions", "market"])

const getMoreDetailsFieldNames = (type: ManualTxTypeOption): Set<string> => {
  if (isTransferUiType(type) || isSwapUiType(type)) {
    return DEFAULT_MORE_DETAILS_FIELDS
  }
  switch (type) {
    case TxType.BUY:
    case TxType.INVESTMENT:
      return new Set(["retentions", "market"])
    case TxType.SELL:
    case TxType.REPAYMENT:
      return new Set(["market"])
    case TxType.DIVIDEND:
    case TxType.INTEREST:
      return new Set(["fees", "market"])
    case TxType.TRANSFER_IN:
    case TxType.TRANSFER_OUT:
    case TxType.FEE:
    case TxType.SWAP_FROM:
    case TxType.SWAP_TO:
      return DEFAULT_MORE_DETAILS_FIELDS
    default:
      return DEFAULT_MORE_DETAILS_FIELDS
  }
}

const TX_TYPES_BY_PRODUCT: Record<
  SupportedManualProductType,
  readonly TxType[]
> = {
  [ProductType.ACCOUNT]: [TxType.INTEREST, TxType.FEE],
  [ProductType.STOCK_ETF]: [
    TxType.BUY,
    TxType.SELL,
    TxType.DIVIDEND,
    TxType.FEE,
  ],
  [ProductType.FUND]: [TxType.BUY, TxType.SELL, TxType.DIVIDEND, TxType.FEE],
  [ProductType.FUND_PORTFOLIO]: [TxType.FEE],
  [ProductType.FACTORING]: INVESTMENT_FLOW_TX_TYPES,
  [ProductType.REAL_ESTATE_CF]: INVESTMENT_FLOW_TX_TYPES,
  [ProductType.DEPOSIT]: INVESTMENT_FLOW_TX_TYPES,
  [ProductType.CRYPTO]: [TxType.BUY, TxType.SELL, TxType.DIVIDEND, TxType.FEE],
}

const getTxTypesForProduct = (
  productType: SupportedManualProductType,
): readonly TxType[] => TX_TYPES_BY_PRODUCT[productType] ?? []

const getDefaultTxType = (
  productType: SupportedManualProductType,
): ManualTxTypeOption => getTxTypesForProduct(productType)[0] ?? TxType.FEE

const getCreateTxTypeOptions = (
  productType: SupportedManualProductType,
): ManualTxTypeOption[] => {
  const types: ManualTxTypeOption[] = [...getTxTypesForProduct(productType)]
  if (TRANSFER_PRODUCT_TYPES.has(productType)) {
    types.push(TRANSFER_UI_TYPE)
  }
  if (SWAP_PRODUCT_TYPES.has(productType)) {
    types.push(SWAP_UI_TYPE)
  }
  return types
}

export interface ManualTransactionSubmitResult {
  payload: ManualTransactionPayload | ManualTransactionPayload[]
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
  type: ManualTxTypeOption
  productType: SupportedManualProductType
  amount: string
  currency: string
  extra: Record<string, string>
  origin: TransferLegState
  dest: TransferLegState
  destSameAsOrigin: boolean
  orderDate: string
  swapRatio: string
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

const COPY_FROM_ORIGIN_FIELDS = [
  "isin",
  "ticker",
  "shares",
  "price",
  "market",
] as const

const getCopiedDestExtra = (
  originExtra: Record<string, string>,
  destExtra: Record<string, string>,
): Record<string, string> => {
  const next = { ...destExtra }
  COPY_FROM_ORIGIN_FIELDS.forEach(field => {
    if (field in originExtra) {
      next[field] = originExtra[field]
    }
  })
  return next
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

const createTransferLeg = (
  productType: SupportedManualProductType,
  date: string,
): TransferLegState => ({
  enabled: true,
  name: "",
  date,
  entityId: "",
  extra: createExtraDefaults(productType),
})

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
        {
          name: "ticker",
          labelKey: t.transactions.ticker,
          type: "text",
          required: true,
        },
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

function ExtraFieldsGrid({
  fields,
  extra,
  errors,
  errorPrefix,
  idPrefix,
  disabled = false,
  lockedFields,
  productType,
  currencySymbol,
  suggestionsByField,
  selectedEntityName,
  suggestionPopoverField,
  setSuggestionPopoverField,
  getSuggestionLabel,
  onExtraChange,
  onSuggestionApply,
  t,
  isSubmitting,
  showAutoAmountHint = true,
}: {
  fields: FieldConfig[]
  extra: Record<string, string>
  errors: Record<string, string>
  errorPrefix: string
  idPrefix: string
  disabled?: boolean
  lockedFields?: Set<string>
  productType: SupportedManualProductType
  currencySymbol: string
  suggestionsByField: Record<string, SuggestionOption[]>
  selectedEntityName: string
  suggestionPopoverField: string | null
  setSuggestionPopoverField: (value: string | null) => void
  getSuggestionLabel: (fieldName: string) => string
  onExtraChange: (name: string, value: string) => void
  onSuggestionApply: (
    fieldName: string,
    value: string,
    option?: SuggestionOption,
  ) => void
  t: ReturnType<typeof useI18n>["t"]
  isSubmitting: boolean
  showAutoAmountHint?: boolean
}) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {fields.map(field => {
        const errorKey = `${errorPrefix}.${field.name}`
        const error = errors[errorKey]
        const fieldDisabled = disabled || lockedFields?.has(field.name)
        const fieldId = `${idPrefix}-${field.name}`
        if (field.type === "date") {
          return (
            <div key={field.name} className="space-y-1.5">
              <Label htmlFor={fieldId}>{field.labelKey}</Label>
              <DatePicker
                id={fieldId}
                value={extra[field.name] ?? ""}
                onChange={value => onExtraChange(field.name, value || "")}
                placeholder={t.transactions.form.pickDate}
                disabled={isSubmitting || fieldDisabled}
              />
              {error && (
                <p className="text-xs text-red-600 dark:text-red-400">
                  {error}
                </p>
              )}
            </div>
          )
        }

        const fieldSuggestions = suggestionsByField[field.name] ?? []
        const showSuggestions = fieldSuggestions.length > 0 && !fieldDisabled

        if (
          (productType === ProductType.STOCK_ETF ||
            productType === ProductType.FUND) &&
          field.name === "shares"
        ) {
          const priceField = fields.find(option => option.name === "price")
          const priceError = errors[`${errorPrefix}.price`]
          const priceDisabled = disabled || lockedFields?.has("price")

          return (
            <div key="shares-price" className="space-y-2 md:col-span-2">
              <div className="flex flex-col gap-3 md:flex-row md:items-end">
                <div className="flex-1 space-y-1.5">
                  <Label htmlFor={`${idPrefix}-shares`}>{field.labelKey}</Label>
                  <DecimalInput
                    id={`${idPrefix}-shares`}
                    value={extra.shares ?? ""}
                    onStringChange={value => onExtraChange("shares", value)}
                    disabled={fieldDisabled}
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
                  <Label htmlFor={`${idPrefix}-price`}>
                    {priceField?.labelKey ?? t.transactions.price}
                  </Label>
                  <DecimalInput
                    id={`${idPrefix}-price`}
                    value={extra.price ?? ""}
                    onStringChange={value => onExtraChange("price", value)}
                    suffix={currencySymbol}
                    disabled={priceDisabled}
                    className={cn(priceError && "border-red-500")}
                  />
                  {priceError && (
                    <p className="text-xs text-red-600 dark:text-red-400">
                      {priceError}
                    </p>
                  )}
                </div>
              </div>
              {showAutoAmountHint &&
                t.transactions.form.autoAmountHint &&
                (extra.shares || extra.price) && (
                  <p className="text-xs text-muted-foreground">
                    {t.transactions.form.autoAmountHint}
                  </p>
                )}
            </div>
          )
        }

        if (
          productType === ProductType.CRYPTO &&
          field.name === "currency_amount"
        ) {
          const priceField = fields.find(option => option.name === "price")
          const priceError = errors[`${errorPrefix}.price`]

          return (
            <div
              key="currency_amount-price"
              className="space-y-2 md:col-span-2"
            >
              <div className="flex flex-col gap-3 md:flex-row md:items-end">
                <div className="flex-1 space-y-1.5">
                  <Label htmlFor={`${idPrefix}-currency_amount`}>
                    {field.labelKey}
                  </Label>
                  <DecimalInput
                    id={`${idPrefix}-currency_amount`}
                    value={extra.currency_amount ?? ""}
                    onStringChange={value =>
                      onExtraChange("currency_amount", value)
                    }
                    disabled={fieldDisabled}
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
                  <Label htmlFor={`${idPrefix}-price`}>
                    {priceField?.labelKey ?? t.transactions.price}
                  </Label>
                  <div className="relative">
                    <DecimalInput
                      id={`${idPrefix}-price`}
                      value={extra.price ?? ""}
                      onStringChange={value => onExtraChange("price", value)}
                      disabled={disabled || lockedFields?.has("price")}
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
              {showAutoAmountHint &&
                t.transactions.form.autoAmountHint &&
                (extra.currency_amount || extra.price) && (
                  <p className="text-xs text-muted-foreground">
                    {t.transactions.form.autoAmountHint}
                  </p>
                )}
            </div>
          )
        }

        if (
          (productType === ProductType.STOCK_ETF ||
            productType === ProductType.FUND ||
            productType === ProductType.CRYPTO) &&
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
            : ["fees", "retentions", "avg_balance"].includes(field.name)
              ? currencySymbol
              : null
        const popoverKey = `${idPrefix}-${field.name}`

        return (
          <div key={field.name} className="space-y-1.5">
            <div className="flex items-center justify-between gap-2 min-h-[20px]">
              <Label htmlFor={fieldId} className="shrink-0">
                {field.labelKey}
              </Label>
              {showSuggestions && (
                <Popover
                  open={suggestionPopoverField === popoverKey}
                  onOpenChange={open =>
                    setSuggestionPopoverField(open ? popoverKey : null)
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
                        {selectedEntityName ? ` · ${selectedEntityName}` : ""}
                      </span>
                    </button>
                  </PopoverTrigger>
                  <PopoverContent align="end" className="w-80 p-0">
                    <div className="max-h-72 overflow-y-auto py-1">
                      {fieldSuggestions.map(option => (
                        <button
                          key={`${field.name}-${option.value}`}
                          type="button"
                          className="flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm transition-colors hover:bg-muted"
                          onClick={() => {
                            onSuggestionApply(field.name, option.value, option)
                            setSuggestionPopoverField(null)
                          }}
                        >
                          <SuggestionItemIcon
                            option={option}
                            productType={productType}
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
                                    isMonoField && "font-mono",
                                  )}
                                >
                                  {option.value}
                                  {option.ticker &&
                                    option.ticker !== option.value && (
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
            <div className={fieldSuffix ? "relative" : undefined}>
              {field.type === "number" ? (
                <DecimalInput
                  id={fieldId}
                  value={extra[field.name] ?? ""}
                  onStringChange={value => onExtraChange(field.name, value)}
                  disabled={fieldDisabled}
                  className={cn(
                    isMonoField && "font-mono",
                    fieldSuffix && "pr-10",
                    error && "border-red-500",
                  )}
                />
              ) : (
                <Input
                  id={fieldId}
                  type="text"
                  value={extra[field.name] ?? ""}
                  onChange={event =>
                    onExtraChange(field.name, event.target.value)
                  }
                  disabled={fieldDisabled}
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
              <p className="text-xs text-red-600 dark:text-red-400">{error}</p>
            )}
          </div>
        )
      })}
    </div>
  )
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
  const [formState, setFormState] = useState<ManualTransactionFormState>(() => {
    const today = format(new Date(), "yyyy-MM-dd")
    const productType = SUPPORTED_PRODUCT_TYPES[0]
    return {
      ref: generateTransactionRef(),
      entityId: "",
      name: "",
      date: today,
      type: getDefaultTxType(productType),
      productType,
      amount: "",
      currency: defaultCurrency.toUpperCase(),
      extra: createExtraDefaults(productType),
      origin: createTransferLeg(productType, today),
      dest: createTransferLeg(productType, today),
      destSameAsOrigin: false,
      orderDate: "",
      swapRatio: "",
    }
  })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const sharesPriceEditedRef = useRef(false)
  const [originMoreOpen, setOriginMoreOpen] = useState(false)
  const [destMoreOpen, setDestMoreOpen] = useState(false)
  const [editMoreOpen, setEditMoreOpen] = useState(false)

  const isTransferCreate = mode === "create" && isTransferUiType(formState.type)
  const isSwapCreate = mode === "create" && isSwapUiType(formState.type)
  const isPairedCreate = isTransferCreate || isSwapCreate
  const lockProductAndType =
    mode === "edit" &&
    isDomainTxType(formState.type) &&
    LOCKED_EDIT_TX_TYPES.has(formState.type)

  const stockBothLegsCopy =
    isTransferCreate &&
    formState.productType === ProductType.STOCK_ETF &&
    formState.origin.enabled &&
    formState.dest.enabled

  const destCopiesOrigin =
    isTransferCreate &&
    formState.dest.enabled &&
    (stockBothLegsCopy ||
      (formState.productType === ProductType.FUND &&
        formState.destSameAsOrigin &&
        formState.origin.enabled))

  const resolveEntityName = useCallback(
    (entityId: string, fallbackName?: string) => {
      if (!entityId) return ""
      if (fallbackName) return fallbackName
      const option = entities.find(entity => entity.id === entityId)
      if (option) return option.name
      return positionsData?.positions?.[entityId]?.[0]?.entity?.name || ""
    },
    [entities, positionsData],
  )

  const selectedEntityName = useMemo(
    () => resolveEntityName(formState.entityId, formState.entityName),
    [formState.entityId, formState.entityName, resolveEntityName],
  )

  const originEntityName = useMemo(
    () => resolveEntityName(formState.origin.entityId),
    [formState.origin.entityId, resolveEntityName],
  )

  const destEntityName = useMemo(
    () => resolveEntityName(formState.dest.entityId),
    [formState.dest.entityId, resolveEntityName],
  )

  const buildSuggestionsForEntity = useCallback(
    (entityId: string): Record<string, SuggestionOption[]> => {
      const suggestions: Record<string, SuggestionOption[]> = {}
      if (!entityId || !positionsData?.positions) {
        return suggestions
      }

      const entityPositions = positionsData.positions[entityId] ?? []
      if (entityPositions.length === 0) {
        return suggestions
      }

      if (formState.productType === ProductType.STOCK_ETF) {
        const seen = new Set<string>()
        const options: SuggestionOption[] = []
        entityPositions.forEach(ep => {
          const stockPositions = ep.products[ProductType.STOCK_ETF] as
            StockInvestments | undefined
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
            FundInvestments | undefined
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
            FundPortfolios | undefined
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
                  label: accountLabel
                    ? `${display} · ${accountLabel}`
                    : display,
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
            CryptoCurrencies | undefined
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
    },
    [formState.productType, positionsData],
  )

  const suggestionsByField = useMemo(
    () => buildSuggestionsForEntity(formState.entityId),
    [buildSuggestionsForEntity, formState.entityId],
  )

  const originSuggestionsByField = useMemo(
    () => buildSuggestionsForEntity(formState.origin.entityId),
    [buildSuggestionsForEntity, formState.origin.entityId],
  )

  const destSuggestionsByField = useMemo(
    () => buildSuggestionsForEntity(formState.dest.entityId),
    [buildSuggestionsForEntity, formState.dest.entityId],
  )

  const supportsNetAmount = useMemo(
    () => NET_AMOUNT_PRODUCT_TYPES.has(formState.productType),
    [formState.productType],
  )

  const isOutgoingType = useMemo(() => {
    const type = formState.type
    return isDomainTxType(type) && OUTGOING_TX_TYPES.has(type)
  }, [formState.type])

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

      const extraSource =
        mode === "create" && isSwapUiType(prev.type)
          ? prev.origin.extra
          : mode === "create" && isTransferUiType(prev.type)
            ? prev.origin.enabled
              ? prev.origin.extra
              : prev.dest.enabled
                ? prev.dest.extra
                : prev.extra
            : prev.extra

      const qtyKey =
        prev.productType === ProductType.CRYPTO ? "currency_amount" : "shares"
      const qty = Number.parseFloat(
        (extraSource?.[qtyKey] ?? "").replace(",", "."),
      )
      const price = Number.parseFloat(
        (extraSource?.price ?? "").replace(",", "."),
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
    formState.origin.extra?.shares,
    formState.origin.extra?.price,
    formState.dest.extra?.shares,
    formState.dest.extra?.price,
    formState.origin.enabled,
    formState.dest.enabled,
    formState.type,
    formState.productType,
    mode,
    setFormState,
  ])

  useEffect(() => {
    if (!isSwapCreate) return
    const ratio = Number.parseFloat(
      (formState.swapRatio || "").replace(",", "."),
    )
    const originShares = Number.parseFloat(
      (formState.origin.extra.shares ?? "").replace(",", "."),
    )
    if (
      !Number.isFinite(ratio) ||
      ratio <= 0 ||
      !Number.isFinite(originShares) ||
      originShares <= 0
    ) {
      return
    }
    const destShares = originShares * ratio
    const amount = Number.parseFloat((formState.amount || "").replace(",", "."))
    const originPrice = Number.parseFloat(
      (formState.origin.extra.price ?? "").replace(",", "."),
    )
    const total =
      Number.isFinite(amount) && amount > 0
        ? amount
        : Number.isFinite(originPrice) && originPrice > 0
          ? originShares * originPrice
          : Number.NaN
    if (!Number.isFinite(total) || destShares <= 0) return
    const destPrice = total / destShares
    const nextShares = destShares.toFixed(8).replace(/\.?0+$/, "")
    const nextPrice = destPrice.toFixed(8).replace(/\.?0+$/, "")
    setFormState(prev => {
      if (
        prev.dest.extra.shares === nextShares &&
        prev.dest.extra.price === nextPrice
      ) {
        return prev
      }
      return {
        ...prev,
        dest: {
          ...prev.dest,
          extra: {
            ...prev.dest.extra,
            shares: nextShares,
            price: nextPrice,
          },
        },
      }
    })
  }, [
    isSwapCreate,
    formState.swapRatio,
    formState.origin.extra.shares,
    formState.origin.extra.price,
    formState.amount,
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
    const today = format(new Date(), "yyyy-MM-dd")
    const productType = SUPPORTED_PRODUCT_TYPES[0]
    setFormState({
      ref: generateTransactionRef(),
      entityId: "",
      name: "",
      date: today,
      type: getDefaultTxType(productType),
      productType,
      amount: "",
      currency: defaultCurrency.toUpperCase(),
      extra: createExtraDefaults(productType),
      origin: createTransferLeg(productType, today),
      dest: createTransferLeg(productType, today),
      destSameAsOrigin: false,
      orderDate: "",
      swapRatio: "",
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
        origin: createTransferLeg(
          productType,
          format(new Date(), "yyyy-MM-dd"),
        ),
        dest: createTransferLeg(productType, format(new Date(), "yyyy-MM-dd")),
        destSameAsOrigin: false,
        orderDate: "",
        swapRatio: "",
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
    const type = formState.type
    const hideOrderDate =
      isTransferCreate ||
      isSwapCreate ||
      (isDomainTxType(type) && NO_ORDER_DATE_TX_TYPES.has(type))
    return configs.filter(field => {
      if (isFeeType && (field.name === "fees" || field.name === "retentions")) {
        return false
      }
      if (hideOrderDate && field.name === "order_date") {
        return false
      }
      return true
    })
  }, [
    formState.productType,
    formState.type,
    isFeeType,
    isTransferCreate,
    isSwapCreate,
    t,
  ])

  const moreDetailsFieldNames = useMemo(
    () => getMoreDetailsFieldNames(formState.type),
    [formState.type],
  )

  const mainFieldConfigs = useMemo(
    () => fieldConfigs.filter(field => !moreDetailsFieldNames.has(field.name)),
    [fieldConfigs, moreDetailsFieldNames],
  )

  const moreDetailsFieldConfigs = useMemo(
    () => fieldConfigs.filter(field => moreDetailsFieldNames.has(field.name)),
    [fieldConfigs, moreDetailsFieldNames],
  )

  const availableTxTypes = useMemo((): ManualTxTypeOption[] => {
    if (mode === "create") {
      return getCreateTxTypeOptions(formState.productType)
    }
    const types: ManualTxTypeOption[] = [
      ...getTxTypesForProduct(formState.productType),
    ]
    const type = formState.type
    if (
      type &&
      isDomainTxType(type) &&
      !types.includes(type) &&
      !MANUAL_INPUT_EXCLUDED_TX_TYPES.has(type)
    ) {
      types.unshift(type)
    }
    return types
  }, [formState.productType, formState.type, mode])

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
    setFormState(prev => {
      const next = {
        ...prev,
        [key]: value,
      }
      if (key === "type" && isSwapUiType(value as ManualTxTypeOption)) {
        next.origin = { ...prev.origin, enabled: true }
        next.dest = { ...prev.dest, enabled: true }
      }
      return next
    })
    clearError(key.toString())
  }

  const normalizeExtraValue = (name: string, value: string) =>
    name === "isin" || name === "ticker" || name === "iban" || name === "symbol"
      ? value.toUpperCase()
      : value

  const handleExtraChange = (name: string, value: string) => {
    if (name === "shares" || name === "price" || name === "currency_amount") {
      sharesPriceEditedRef.current = true
    }
    const normalizedValue = normalizeExtraValue(name, value)
    setFormState(prev => ({
      ...prev,
      extra: {
        ...prev.extra,
        [name]: normalizedValue,
      },
    }))
    clearError(`extra.${name}`)
  }

  const handleLegChange = (
    leg: "origin" | "dest",
    patch: Partial<TransferLegState>,
  ) => {
    setFormState(prev => {
      const nextLeg = {
        ...prev[leg],
        ...patch,
      }
      if (leg === "dest") {
        return {
          ...prev,
          dest: nextLeg,
        }
      }
      const copyDest =
        isTransferUiType(prev.type) &&
        prev.dest.enabled &&
        (prev.productType === ProductType.STOCK_ETF || prev.destSameAsOrigin)
      return {
        ...prev,
        origin: nextLeg,
        dest: copyDest
          ? {
              ...prev.dest,
              extra: getCopiedDestExtra(nextLeg.extra, prev.dest.extra),
              name: nextLeg.name,
            }
          : prev.dest,
      }
    })
    Object.keys(patch).forEach(key => {
      if (key === "extra") return
      clearError(`${leg}.${key}`)
    })
    clearError("legs")
  }

  const handleLegExtraChange = (
    leg: "origin" | "dest",
    name: string,
    value: string,
  ) => {
    if (name === "shares" || name === "price" || name === "currency_amount") {
      sharesPriceEditedRef.current = true
    }
    const normalizedValue = normalizeExtraValue(name, value)
    setFormState(prev => {
      const nextExtra = {
        ...prev[leg].extra,
        [name]: normalizedValue,
      }
      if (leg === "dest") {
        return {
          ...prev,
          dest: {
            ...prev.dest,
            extra: nextExtra,
          },
        }
      }
      const copyDest =
        isTransferUiType(prev.type) &&
        prev.dest.enabled &&
        (prev.productType === ProductType.STOCK_ETF || prev.destSameAsOrigin)
      return {
        ...prev,
        origin: {
          ...prev.origin,
          extra: nextExtra,
        },
        dest: copyDest
          ? {
              ...prev.dest,
              extra: getCopiedDestExtra(nextExtra, prev.dest.extra),
              name: prev.origin.name,
            }
          : prev.dest,
      }
    })
    clearError(`${leg}.extra.${name}`)
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

  const handleLegSuggestionApply = (
    leg: "origin" | "dest",
    fieldName: string,
    value: string,
    option?: SuggestionOption,
  ) => {
    handleLegExtraChange(leg, fieldName, value)
    if (!option) return
    if (
      fieldName === "isin" &&
      formState.productType === ProductType.STOCK_ETF
    ) {
      const extra = formState[leg].extra
      if (option.ticker && !extra.ticker?.trim()) {
        handleLegExtraChange(leg, "ticker", option.ticker)
      }
      if (option.market && !extra.market?.trim()) {
        handleLegExtraChange(leg, "market", option.market)
      }
    }
    if (fieldName === "isin" && option.name && !formState[leg].name.trim()) {
      handleLegChange(leg, { name: option.name })
    }
  }

  const getTypeLabel = (type: ManualTxTypeOption) =>
    isTransferUiType(type)
      ? t.transactions.form.transfer
      : isSwapUiType(type)
        ? t.transactions.form.swap
        : (t.enums as { transactionType?: Record<string, string> })
            ?.transactionType?.[type] || type

  const getTypeIcon = (type: ManualTxTypeOption) =>
    isTransferUiType(type) ? (
      <ArrowLeftRight className="h-4 w-4" />
    ) : isSwapUiType(type) ? (
      <Repeat className="h-4 w-4" />
    ) : (
      getIconForTxType(type, "h-4 w-4")
    )

  const validateExtraFields = (
    extra: Record<string, string>,
    prefix: string,
    fields: FieldConfig[],
    newErrors: Record<string, string>,
  ) => {
    fields.forEach(field => {
      const value = extra[field.name] ?? ""
      const errorKey = `${prefix}.${field.name}`
      if (field.required && !value.trim()) {
        newErrors[errorKey] = t.transactions.form.errors.required
        return
      }

      if (field.type === "number" && value.trim()) {
        const numeric = Number.parseFloat(value.replace(",", "."))
        if (Number.isNaN(numeric)) {
          newErrors[errorKey] = t.transactions.form.errors.invalidNumber
          return
        }
        if (field.numericType === "positive" && numeric <= 0) {
          newErrors[errorKey] = t.transactions.form.errors.positive
          return
        }
        if (field.numericType === "nonNegative" && numeric < 0) {
          newErrors[errorKey] = t.transactions.form.errors.nonNegative
        }
      }
    })
  }

  const validate = () => {
    const newErrors: Record<string, string> = {}

    const amountValue = Number.parseFloat(formState.amount.replace(",", "."))
    if (!formState.amount || Number.isNaN(amountValue) || amountValue <= 0) {
      newErrors.amount = t.transactions.form.errors.positive
    }

    if (!formState.currency) {
      newErrors.currency = t.transactions.form.errors.required
    }

    if (!SUPPORTED_PRODUCT_TYPES.includes(formState.productType)) {
      newErrors.productType = t.transactions.form.errors.required
    }

    if (isSwapCreate) {
      if (!formState.entityId) {
        newErrors.entityId = t.transactions.form.errors.required
      }
      if (!formState.date) {
        newErrors.date = t.transactions.form.errors.required
      }
      ;(["origin", "dest"] as const).forEach(leg => {
        const state = formState[leg]
        if (!state.name.trim()) {
          newErrors[`${leg}.name`] = t.transactions.form.errors.required
        }
        validateExtraFields(
          state.extra,
          `${leg}.extra`,
          fieldConfigs,
          newErrors,
        )
      })
    } else if (isTransferCreate) {
      if (!formState.origin.enabled && !formState.dest.enabled) {
        newErrors.legs = t.transactions.form.errors.needOneLeg
      }

      const validateLeg = (leg: "origin" | "dest", state: TransferLegState) => {
        if (!state.enabled) return
        if (!state.name.trim()) {
          newErrors[`${leg}.name`] = t.transactions.form.errors.required
        }
        if (!state.date) {
          newErrors[`${leg}.date`] = t.transactions.form.errors.required
        }
        if (!state.entityId) {
          const fundDestOptional =
            formState.productType === ProductType.FUND &&
            formState.origin.enabled
          if (leg === "origin") {
            newErrors[`${leg}.entityId`] = t.transactions.form.errors.required
          } else if (!fundDestOptional) {
            const destEntityRequired =
              formState.productType === ProductType.STOCK_ETF &&
              formState.origin.enabled &&
              formState.dest.enabled
            newErrors[`${leg}.entityId`] = destEntityRequired
              ? t.transactions.form.errors.destEntityRequired
              : t.transactions.form.errors.required
          }
        }
        validateExtraFields(
          state.extra,
          `${leg}.extra`,
          fieldConfigs,
          newErrors,
        )
      }

      validateLeg("origin", formState.origin)
      validateLeg(
        "dest",
        destCopiesOrigin
          ? {
              ...formState.dest,
              name: formState.origin.name,
              extra: getCopiedDestExtra(
                formState.origin.extra,
                formState.dest.extra,
              ),
            }
          : formState.dest,
      )
    } else {
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

      const allowedTypes = getTxTypesForProduct(formState.productType)
      const type = formState.type
      const typeAllowed =
        (isDomainTxType(type) && allowedTypes.includes(type)) ||
        (mode === "edit" && transaction?.type === type)
      if (!typeAllowed) {
        newErrors.type = t.transactions.form.errors.required
      }

      validateExtraFields(formState.extra, "extra", fieldConfigs, newErrors)
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const buildInvestmentPayload = (
    txType: TxType,
    name: string,
    date: string,
    entityId: string,
    extra: Record<string, string>,
    ref: string,
    amountValue: number,
  ): ManualTransactionPayload => {
    const fees = parseNumberValue(extra.fees ?? "0", 0)
    const retentions = parseNumberValue(extra.retentions ?? "0", 0)
    const orderDate = formState.orderDate || extra.order_date || undefined
    if (formState.productType === ProductType.STOCK_ETF) {
      const payload: ManualStockTransactionPayload = {
        id: ref,
        ref,
        name: name.trim(),
        amount: amountValue,
        currency: formState.currency.toUpperCase(),
        type: txType,
        date,
        entity_id: entityId,
        source: DataSource.MANUAL,
        product_type: ProductType.STOCK_ETF,
        ticker: extra.ticker.trim().toUpperCase() || undefined,
        isin: extra.isin.trim().toUpperCase() || undefined,
        shares: parseNumberValue(extra.shares),
        price: parseNumberValue(extra.price),
        fees,
        retentions,
        market: extra.market.trim() || undefined,
        order_date: orderDate,
      }
      return payload
    }
    const payload: ManualFundTransactionPayload = {
      id: ref,
      ref,
      name: name.trim(),
      amount: amountValue,
      currency: formState.currency.toUpperCase(),
      type: txType,
      date,
      entity_id: entityId,
      source: DataSource.MANUAL,
      product_type: ProductType.FUND,
      isin: extra.isin.trim().toUpperCase(),
      shares: parseNumberValue(extra.shares),
      price: parseNumberValue(extra.price),
      fees,
      retentions,
      market: extra.market.trim() || undefined,
      order_date: orderDate,
    }
    return payload
  }

  const buildPayload = ():
    ManualTransactionPayload | ManualTransactionPayload[] => {
    const amountValue = parseNumberValue(formState.amount)
    if (isSwapCreate) {
      return [
        buildInvestmentPayload(
          TxType.SWAP_FROM,
          formState.origin.name,
          formState.date,
          formState.entityId,
          formState.origin.extra,
          generateTransactionRef(),
          amountValue,
        ),
        buildInvestmentPayload(
          TxType.SWAP_TO,
          formState.dest.name,
          formState.date,
          formState.entityId,
          formState.dest.extra,
          generateTransactionRef(),
          amountValue,
        ),
      ]
    }
    if (isTransferCreate) {
      const payloads: ManualTransactionPayload[] = []
      if (formState.origin.enabled) {
        payloads.push(
          buildInvestmentPayload(
            TxType.TRANSFER_OUT,
            formState.origin.name,
            formState.origin.date,
            formState.origin.entityId,
            formState.origin.extra,
            generateTransactionRef(),
            amountValue,
          ),
        )
      }
      if (formState.dest.enabled) {
        const destExtra = destCopiesOrigin
          ? getCopiedDestExtra(formState.origin.extra, formState.dest.extra)
          : formState.dest.extra
        const destName = destCopiesOrigin
          ? formState.origin.name
          : formState.dest.name
        const destEntityId =
          formState.dest.entityId || formState.origin.entityId
        payloads.push(
          buildInvestmentPayload(
            TxType.TRANSFER_IN,
            destName,
            formState.dest.date,
            destEntityId,
            destExtra,
            generateTransactionRef(),
            amountValue,
          ),
        )
      }
      return payloads.length === 1 ? payloads[0] : payloads
    }

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
      type: formState.type as TxType,
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
              <CardHeader className="flex flex-row items-center justify-between gap-4">
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
                    {!isTransferCreate && (
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
                          id="transaction-entity"
                          placeholder={t.common.selectOptions}
                          className="max-w-none"
                        />
                        {errors.entityId && (
                          <p className="text-xs text-red-600 dark:text-red-400">
                            {errors.entityId}
                          </p>
                        )}
                      </div>
                    )}

                    {!isPairedCreate && (
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
                    )}

                    {!isTransferCreate && (
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
                    )}

                    <div className="space-y-1.5">
                      <Label htmlFor="transaction-product">
                        {t.transactions.product}
                      </Label>
                      <Popover
                        open={
                          productTypeDropdownOpen &&
                          !isSubmitting &&
                          !lockProductAndType
                        }
                        onOpenChange={open => {
                          if (!isSubmitting && !lockProductAndType) {
                            setProductTypeDropdownOpen(open)
                          }
                        }}
                      >
                        <PopoverTrigger asChild>
                          <div
                            id="transaction-product"
                            role="combobox"
                            tabIndex={lockProductAndType ? -1 : 0}
                            aria-haspopup="listbox"
                            aria-expanded={productTypeDropdownOpen}
                            aria-disabled={lockProductAndType || isSubmitting}
                            className={cn(
                              "flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm cursor-pointer",
                              "focus-within:ring-2 focus-within:ring-ring",
                              (isSubmitting || lockProductAndType) &&
                                "cursor-not-allowed opacity-50 pointer-events-none",
                              errors.productType && "border-red-500",
                            )}
                            onKeyDown={e => {
                              if (isSubmitting || lockProductAndType) return
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
                        </PopoverTrigger>
                        <PopoverContent
                          align="start"
                          className="w-[var(--radix-popover-trigger-width)] max-h-60 overflow-auto p-0"
                        >
                          <div role="listbox">
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
                                  clearError("type")
                                  setFormState(prev => {
                                    const nextTypes = getTxTypesForProduct(type)
                                    const keepTransfer =
                                      isTransferUiType(prev.type) &&
                                      TRANSFER_PRODUCT_TYPES.has(type)
                                    const keepSwap =
                                      isSwapUiType(prev.type) &&
                                      SWAP_PRODUCT_TYPES.has(type)
                                    const nextType = keepTransfer
                                      ? TRANSFER_UI_TYPE
                                      : keepSwap
                                        ? SWAP_UI_TYPE
                                        : nextTypes.includes(
                                              prev.type as TxType,
                                            )
                                          ? prev.type
                                          : getDefaultTxType(type)
                                    const today =
                                      prev.origin?.date ||
                                      format(new Date(), "yyyy-MM-dd")
                                    return {
                                      ...prev,
                                      productType: type,
                                      type: nextType,
                                      extra: createExtraDefaults(type),
                                      origin: createTransferLeg(type, today),
                                      dest: createTransferLeg(type, today),
                                      destSameAsOrigin: false,
                                      swapRatio: "",
                                    }
                                  })
                                  setErrors(prev => {
                                    const next: Record<string, string> = {}
                                    Object.entries(prev).forEach(
                                      ([key, message]) => {
                                        if (
                                          !key.startsWith("extra.") &&
                                          key !== "type"
                                        ) {
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
                        </PopoverContent>
                      </Popover>
                      {errors.productType && (
                        <p className="text-xs text-red-600 dark:text-red-400">
                          {errors.productType}
                        </p>
                      )}
                    </div>

                    <div className="space-y-1.5">
                      <Label htmlFor="transaction-type">
                        {t.transactions.form.transactionType}
                      </Label>
                      <Popover
                        open={txTypeDropdownOpen && !lockProductAndType}
                        onOpenChange={open => {
                          if (!lockProductAndType) setTxTypeDropdownOpen(open)
                        }}
                      >
                        <PopoverTrigger asChild>
                          <div
                            id="transaction-type"
                            role="combobox"
                            tabIndex={lockProductAndType ? -1 : 0}
                            aria-haspopup="listbox"
                            aria-expanded={txTypeDropdownOpen}
                            aria-disabled={lockProductAndType}
                            className={cn(
                              "flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm cursor-pointer",
                              "focus-within:ring-2 focus-within:ring-ring",
                              lockProductAndType &&
                                "cursor-not-allowed opacity-50 pointer-events-none",
                              errors.type && "border-red-500",
                            )}
                            onKeyDown={e => {
                              if (lockProductAndType) return
                              if (e.key === "Enter" || e.key === " ") {
                                e.preventDefault()
                                setTxTypeDropdownOpen(prev => !prev)
                              } else if (e.key === "Escape") {
                                setTxTypeDropdownOpen(false)
                              }
                            }}
                          >
                            <span className="flex items-center gap-2">
                              {getTypeIcon(formState.type)}
                              {getTypeLabel(formState.type)}
                            </span>
                            <ChevronDown
                              className={cn(
                                "h-4 w-4 shrink-0 transition-transform",
                                txTypeDropdownOpen && "rotate-180",
                              )}
                            />
                          </div>
                        </PopoverTrigger>
                        <PopoverContent
                          align="start"
                          className="w-[var(--radix-popover-trigger-width)] max-h-60 overflow-auto p-0"
                        >
                          <div role="listbox">
                            {availableTxTypes.map(type => (
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
                                  {getTypeIcon(type)}
                                  {getTypeLabel(type)}
                                </span>
                                {formState.type === type && (
                                  <Check className="h-4 w-4" />
                                )}
                              </div>
                            ))}
                          </div>
                        </PopoverContent>
                      </Popover>
                      {errors.type && (
                        <p className="text-xs text-red-600 dark:text-red-400">
                          {errors.type}
                        </p>
                      )}
                      {isTransferCreate && (
                        <p className="text-xs text-muted-foreground">
                          {t.transactions.form.transferHint}
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
                      {supportsNetAmount &&
                        formattedNetAmount &&
                        !isPairedCreate && (
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
                    {isTransferCreate && (
                      <div className="space-y-1.5">
                        <Label htmlFor="transaction-order-date">
                          {t.transactions.orderDate}
                        </Label>
                        <DatePicker
                          id="transaction-order-date"
                          value={formState.orderDate}
                          onChange={value =>
                            handleBaseChange("orderDate", value || "")
                          }
                          placeholder={t.transactions.form.pickDate}
                          disabled={isSubmitting}
                        />
                      </div>
                    )}
                    {isSwapCreate && (
                      <div className="space-y-1.5">
                        <Label htmlFor="transaction-swap-ratio">
                          {t.transactions.form.swapRatio}
                        </Label>
                        <DecimalInput
                          id="transaction-swap-ratio"
                          value={formState.swapRatio}
                          onStringChange={value =>
                            handleBaseChange("swapRatio", value)
                          }
                        />
                        {t.transactions.form.swapRatioHint && (
                          <p className="text-xs text-muted-foreground">
                            {t.transactions.form.swapRatioHint}
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                  {errors.legs && (
                    <p className="text-xs text-red-600 dark:text-red-400">
                      {errors.legs}
                    </p>
                  )}

                  {isPairedCreate ? (
                    <>
                      {(["origin", "dest"] as const).map(leg => {
                        const state = formState[leg]
                        const isOrigin = leg === "origin"
                        const moreOpen = isOrigin
                          ? originMoreOpen
                          : destMoreOpen
                        const setMoreOpen = isOrigin
                          ? setOriginMoreOpen
                          : setDestMoreOpen
                        const prefix = isOrigin ? "origin" : "dest"
                        const extraPrefix = `${prefix}.extra`
                        const lockedFields =
                          !isSwapCreate && !isOrigin && destCopiesOrigin
                            ? new Set([
                                "isin",
                                "ticker",
                                "shares",
                                "price",
                                "market",
                              ])
                            : undefined
                        const nameLocked =
                          !isSwapCreate && !isOrigin && destCopiesOrigin
                        const extra = nameLocked
                          ? getCopiedDestExtra(
                              formState.origin.extra,
                              state.extra,
                            )
                          : state.extra
                        const nameValue = nameLocked
                          ? formState.origin.name
                          : state.name
                        const suggestions = isSwapCreate
                          ? suggestionsByField
                          : isOrigin
                            ? originSuggestionsByField
                            : destSuggestionsByField
                        const entityName = isSwapCreate
                          ? selectedEntityName
                          : isOrigin
                            ? originEntityName
                            : destEntityName
                        const destEntityOptional =
                          !isSwapCreate &&
                          !isOrigin &&
                          formState.productType === ProductType.FUND
                        const showSameAsOrigin =
                          !isSwapCreate &&
                          !isOrigin &&
                          formState.productType === ProductType.FUND &&
                          formState.origin.enabled
                        const showLegToggles = !isSwapCreate
                        const showPerLegDateAndEntity = !isSwapCreate
                        const legMainFields = mainFieldConfigs
                        return (
                          <div
                            key={leg}
                            className={cn(
                              "border-t border-border pt-4 space-y-4",
                              !state.enabled && "opacity-60",
                            )}
                          >
                            <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
                              <h3 className="text-sm font-semibold text-muted-foreground">
                                {isOrigin
                                  ? t.transactions.form.origin
                                  : t.transactions.form.destination}
                              </h3>
                              {showLegToggles && (
                                <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
                                  {showSameAsOrigin && (
                                    <label
                                      htmlFor="dest-same-as-origin"
                                      className="flex items-center gap-1.5"
                                    >
                                      <span className="whitespace-nowrap text-xs font-medium text-muted-foreground">
                                        {t.transactions.form.sameAsOrigin}
                                      </span>
                                      <Switch
                                        id="dest-same-as-origin"
                                        size="sm"
                                        checked={formState.destSameAsOrigin}
                                        disabled={!state.enabled}
                                        onCheckedChange={checked => {
                                          setFormState(prev => ({
                                            ...prev,
                                            destSameAsOrigin: checked,
                                            dest: checked
                                              ? {
                                                  ...prev.dest,
                                                  name: prev.origin.name,
                                                  extra: getCopiedDestExtra(
                                                    prev.origin.extra,
                                                    prev.dest.extra,
                                                  ),
                                                }
                                              : prev.dest,
                                          }))
                                        }}
                                      />
                                    </label>
                                  )}
                                  <label
                                    htmlFor={`${prefix}-enabled`}
                                    className="flex items-center gap-1.5"
                                  >
                                    <span className="whitespace-nowrap text-xs font-medium text-muted-foreground">
                                      {isOrigin
                                        ? t.transactions.form.createOrigin
                                        : t.transactions.form.createDestination}
                                    </span>
                                    <Switch
                                      id={`${prefix}-enabled`}
                                      size="sm"
                                      checked={state.enabled}
                                      onCheckedChange={checked =>
                                        handleLegChange(leg, {
                                          enabled: checked,
                                        })
                                      }
                                    />
                                  </label>
                                </div>
                              )}
                            </div>
                            <fieldset
                              disabled={!state.enabled}
                              className="space-y-4"
                            >
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div className="space-y-1.5">
                                  <Label htmlFor={`${prefix}-name`}>
                                    {t.transactions.name}
                                  </Label>
                                  <Input
                                    id={`${prefix}-name`}
                                    value={nameValue}
                                    disabled={nameLocked}
                                    onChange={event =>
                                      handleLegChange(leg, {
                                        name: event.target.value,
                                      })
                                    }
                                    className={
                                      errors[`${prefix}.name`]
                                        ? "border-red-500"
                                        : ""
                                    }
                                  />
                                  {errors[`${prefix}.name`] && (
                                    <p className="text-xs text-red-600 dark:text-red-400">
                                      {errors[`${prefix}.name`]}
                                    </p>
                                  )}
                                </div>
                                {showPerLegDateAndEntity && (
                                  <>
                                    <div className="space-y-1.5">
                                      <Label htmlFor={`${prefix}-date`}>
                                        {t.transactions.date}
                                      </Label>
                                      <DatePicker
                                        id={`${prefix}-date`}
                                        value={state.date}
                                        onChange={value =>
                                          handleLegChange(leg, {
                                            date: value || "",
                                          })
                                        }
                                        placeholder={
                                          t.transactions.form.pickDate
                                        }
                                        disabled={
                                          isSubmitting || !state.enabled
                                        }
                                        className={
                                          errors[`${prefix}.date`]
                                            ? "border-red-500"
                                            : ""
                                        }
                                      />
                                      {errors[`${prefix}.date`] && (
                                        <p className="text-xs text-red-600 dark:text-red-400">
                                          {errors[`${prefix}.date`]}
                                        </p>
                                      )}
                                    </div>
                                    <div className="space-y-1.5 md:col-span-2">
                                      <Label htmlFor={`${prefix}-entity`}>
                                        {t.transactions.form.entity}
                                      </Label>
                                      <EntitySelector
                                        id={`${prefix}-entity`}
                                        entities={entities}
                                        selectedEntityIds={
                                          state.entityId ? [state.entityId] : []
                                        }
                                        onSelectionChange={ids =>
                                          handleLegChange(leg, {
                                            entityId: ids[0] ?? "",
                                          })
                                        }
                                        singleSelect
                                        disabled={!state.enabled}
                                        placeholder={t.common.selectOptions}
                                        className="max-w-none"
                                      />
                                      {destEntityOptional && (
                                        <p className="text-xs text-muted-foreground">
                                          {
                                            t.transactions.form
                                              .destEntityOptional
                                          }
                                        </p>
                                      )}
                                      {errors[`${prefix}.entityId`] && (
                                        <p className="text-xs text-red-600 dark:text-red-400">
                                          {errors[`${prefix}.entityId`]}
                                        </p>
                                      )}
                                    </div>
                                  </>
                                )}
                              </div>
                              <ExtraFieldsGrid
                                fields={legMainFields}
                                extra={extra}
                                errors={errors}
                                errorPrefix={extraPrefix}
                                idPrefix={prefix}
                                disabled={!state.enabled}
                                lockedFields={lockedFields}
                                productType={formState.productType}
                                currencySymbol={currencySymbol}
                                suggestionsByField={suggestions}
                                selectedEntityName={entityName}
                                suggestionPopoverField={suggestionPopoverField}
                                setSuggestionPopoverField={
                                  setSuggestionPopoverField
                                }
                                getSuggestionLabel={getSuggestionLabel}
                                onExtraChange={(name, value) =>
                                  handleLegExtraChange(leg, name, value)
                                }
                                onSuggestionApply={(name, value, option) =>
                                  handleLegSuggestionApply(
                                    leg,
                                    name,
                                    value,
                                    option,
                                  )
                                }
                                t={t}
                                isSubmitting={isSubmitting}
                                showAutoAmountHint={isOrigin}
                              />
                              {moreDetailsFieldConfigs.length > 0 && (
                                <div>
                                  <button
                                    type="button"
                                    className="flex items-center gap-2 text-sm font-semibold text-muted-foreground focus:outline-none"
                                    onClick={() => setMoreOpen(open => !open)}
                                    aria-expanded={moreOpen}
                                    aria-controls={`${prefix}-more-details`}
                                  >
                                    {t.transactions.form.moreDetails}
                                    <ChevronDown
                                      className={cn(
                                        "h-4 w-4 transition-transform duration-200",
                                        moreOpen && "rotate-180",
                                      )}
                                    />
                                  </button>
                                  <AnimatePresence initial={false}>
                                    {moreOpen && (
                                      <motion.div
                                        id={`${prefix}-more-details`}
                                        initial={{ height: 0, opacity: 0 }}
                                        animate={{ height: "auto", opacity: 1 }}
                                        exit={{ height: 0, opacity: 0 }}
                                        transition={{
                                          duration: 0.2,
                                          ease: "easeInOut",
                                        }}
                                        className="overflow-hidden"
                                      >
                                        <div className="pt-3">
                                          <ExtraFieldsGrid
                                            fields={moreDetailsFieldConfigs}
                                            extra={extra}
                                            errors={errors}
                                            errorPrefix={extraPrefix}
                                            idPrefix={`${prefix}-more`}
                                            disabled={!state.enabled}
                                            lockedFields={lockedFields}
                                            productType={formState.productType}
                                            currencySymbol={currencySymbol}
                                            suggestionsByField={suggestions}
                                            selectedEntityName={entityName}
                                            suggestionPopoverField={
                                              suggestionPopoverField
                                            }
                                            setSuggestionPopoverField={
                                              setSuggestionPopoverField
                                            }
                                            getSuggestionLabel={
                                              getSuggestionLabel
                                            }
                                            onExtraChange={(name, value) =>
                                              handleLegExtraChange(
                                                leg,
                                                name,
                                                value,
                                              )
                                            }
                                            onSuggestionApply={(
                                              name,
                                              value,
                                              option,
                                            ) =>
                                              handleLegSuggestionApply(
                                                leg,
                                                name,
                                                value,
                                                option,
                                              )
                                            }
                                            t={t}
                                            isSubmitting={isSubmitting}
                                            showAutoAmountHint={false}
                                          />
                                        </div>
                                      </motion.div>
                                    )}
                                  </AnimatePresence>
                                </div>
                              )}
                            </fieldset>
                          </div>
                        )
                      })}
                    </>
                  ) : (
                    fieldConfigs.length > 0 && (
                      <div className="border-t border-border pt-4 space-y-4">
                        <h3 className="text-sm font-semibold text-muted-foreground">
                          {t.transactions.form.detailsSection}
                        </h3>
                        <ExtraFieldsGrid
                          fields={
                            moreDetailsFieldConfigs.length > 0
                              ? mainFieldConfigs
                              : fieldConfigs
                          }
                          extra={formState.extra}
                          errors={errors}
                          errorPrefix="extra"
                          idPrefix="transaction"
                          productType={formState.productType}
                          currencySymbol={currencySymbol}
                          suggestionsByField={suggestionsByField}
                          selectedEntityName={selectedEntityName}
                          suggestionPopoverField={suggestionPopoverField}
                          setSuggestionPopoverField={setSuggestionPopoverField}
                          getSuggestionLabel={getSuggestionLabel}
                          onExtraChange={handleExtraChange}
                          onSuggestionApply={handleSuggestionApply}
                          t={t}
                          isSubmitting={isSubmitting}
                        />
                        {moreDetailsFieldConfigs.length > 0 && (
                          <div>
                            <button
                              type="button"
                              className="flex items-center gap-2 text-sm font-semibold text-muted-foreground focus:outline-none"
                              onClick={() => setEditMoreOpen(open => !open)}
                              aria-expanded={editMoreOpen}
                              aria-controls="edit-more-details"
                            >
                              {t.transactions.form.moreDetails}
                              <ChevronDown
                                className={cn(
                                  "h-4 w-4 transition-transform duration-200",
                                  editMoreOpen && "rotate-180",
                                )}
                              />
                            </button>
                            <AnimatePresence initial={false}>
                              {editMoreOpen && (
                                <motion.div
                                  id="edit-more-details"
                                  initial={{ height: 0, opacity: 0 }}
                                  animate={{ height: "auto", opacity: 1 }}
                                  exit={{ height: 0, opacity: 0 }}
                                  transition={{
                                    duration: 0.2,
                                    ease: "easeInOut",
                                  }}
                                  className="overflow-hidden"
                                >
                                  <div className="pt-3">
                                    <ExtraFieldsGrid
                                      fields={moreDetailsFieldConfigs}
                                      extra={formState.extra}
                                      errors={errors}
                                      errorPrefix="extra"
                                      idPrefix="transaction-more"
                                      productType={formState.productType}
                                      currencySymbol={currencySymbol}
                                      suggestionsByField={suggestionsByField}
                                      selectedEntityName={selectedEntityName}
                                      suggestionPopoverField={
                                        suggestionPopoverField
                                      }
                                      setSuggestionPopoverField={
                                        setSuggestionPopoverField
                                      }
                                      getSuggestionLabel={getSuggestionLabel}
                                      onExtraChange={handleExtraChange}
                                      onSuggestionApply={handleSuggestionApply}
                                      t={t}
                                      isSubmitting={isSubmitting}
                                      showAutoAmountHint={false}
                                    />
                                  </div>
                                </motion.div>
                              )}
                            </AnimatePresence>
                          </div>
                        )}
                      </div>
                    )
                  )}
                </CardContent>
                <CardFooter className="flex justify-end gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={handleClose}
                    disabled={isSubmitting}
                    aria-label={t.common.cancel}
                    title={t.common.cancel}
                    className="h-9 w-9 p-0"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                  <Button
                    type="submit"
                    disabled={isSubmitting}
                    aria-label={isSubmitting ? t.common.saving : t.common.save}
                    title={isSubmitting ? t.common.saving : t.common.save}
                    className="h-9 w-9 p-0"
                  >
                    <Save className="h-4 w-4" />
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
