import { useCallback, useEffect, useRef, useState } from "react"
import { Label } from "@/components/ui/Label"
import { Input } from "@/components/ui/Input"
import { DatePicker } from "@/components/ui/DatePicker"
import { Badge } from "@/components/ui/Badge"
import { Button } from "@/components/ui/Button"
import {
  Account,
  AccountType,
  Card,
  CardType,
  Loan,
  LoanType,
  InterestType,
  FundDetail,
  FundPortfolio,
  FundType,
  AssetType,
  StockDetail,
  Deposit,
  FactoringDetail,
  RealEstateCFDetail,
  ProductType,
  EquityType,
} from "@/types/position"
import {
  DataSource,
  InstrumentDataRequest,
  InstrumentInfo,
  InstrumentOverview,
  InstrumentType,
} from "@/types"
import type { LoanCalculationRequest } from "@/types"
import { calculateLoan } from "@/services/api"
import { useAppContext } from "@/context/AppContext"
import {
  ManualFormErrors,
  ManualFormFieldRenderProps,
  ManualPositionDraft,
  ManualPositionFormBase,
  ManualPositionConfigMap,
} from "./manualPositionTypes"
import {
  parseNumberInput,
  formatNumberInput,
  normalizeDateInput,
} from "@/utils/manualData"
import { Calculator, Loader2, Plus, Search, X } from "lucide-react"
import { getInstrumentDetails, getInstruments } from "@/services/api"

const renderTextInput = <FormState extends ManualPositionFormBase>(
  field: keyof FormState,
  label: string,
  props: ManualFormFieldRenderProps<FormState>,
  options?: {
    type?: string
    placeholder?: string
    inputMode?: React.HTMLAttributes<HTMLInputElement>["inputMode"]
    step?: string
    onValueChange?: (
      value: string,
      helpers: ManualFormFieldRenderProps<FormState>,
    ) => void
    helperText?: string
  },
) => (
  <div className="space-y-1.5">
    <Label htmlFor={String(field)}>{label}</Label>
    <Input
      id={String(field)}
      type={options?.type ?? "text"}
      inputMode={options?.inputMode}
      step={options?.step}
      placeholder={options?.placeholder}
      value={(props.form[field] as string) ?? ""}
      onChange={event => {
        const value = event.target.value
        props.updateField(field, value)
        props.clearError(field)
        if (options?.onValueChange) {
          options.onValueChange(value, props)
        }
      }}
    />
    {props.errors[field] && (
      <p className="text-xs text-red-600 dark:text-red-400 mt-1">
        {props.errors[field]}
      </p>
    )}
    {options?.helperText && (
      <p className="text-xs text-muted-foreground mt-1">{options.helperText}</p>
    )}
  </div>
)

const renderSelectInput = <FormState extends ManualPositionFormBase>(
  field: keyof FormState,
  label: string,
  props: ManualFormFieldRenderProps<FormState>,
  options: { value: string; label: string }[],
) => (
  <div className="space-y-1.5">
    <Label htmlFor={String(field)}>{label}</Label>
    <select
      id={String(field)}
      className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      value={(props.form[field] as string) ?? ""}
      onChange={event => {
        props.updateField(field, event.target.value)
        props.clearError(field)
      }}
    >
      <option value="">{props.t("common.selectOptions")}</option>
      {options.map(option => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
    {props.errors[field] && (
      <p className="text-xs text-red-600 dark:text-red-400 mt-1">
        {props.errors[field]}
      </p>
    )}
  </div>
)

const renderEntityField = <FormState extends ManualPositionFormBase>(
  props: ManualFormFieldRenderProps<FormState>,
) => {
  const allowEntityChanges = props.canEditEntity
  const isCreating = allowEntityChanges && props.form.entity_mode === "new"

  const switchToCreate = () => {
    if (!allowEntityChanges) return
    props.updateField("entity_mode", "new" as FormState["entity_mode"])
    props.updateField("entity_id", "")
    props.clearError("entity_id")
    props.clearError("new_entity_name" as keyof FormState)
  }

  const switchToSelect = () => {
    if (!allowEntityChanges) return
    props.updateField("entity_mode", "select" as FormState["entity_mode"])
    props.updateField("new_entity_name", "")
    props.clearError("entity_id")
    props.clearError("new_entity_name" as keyof FormState)
  }

  const handleToggle = () => {
    if (!allowEntityChanges) return
    if (isCreating) {
      switchToSelect()
    } else {
      switchToCreate()
    }
  }

  const buttonLabel = isCreating
    ? props.t("management.manualPositions.shared.cancelEntityCreation")
    : props.t("management.manualPositions.shared.createEntity")

  return (
    <div className="space-y-1.5">
      <Label htmlFor={isCreating ? "new_entity_name" : "entity_id"}>
        {props.t("management.manualPositions.shared.entity")}
      </Label>
      <div className="flex items-stretch gap-2">
        <div className="flex-1">
          {isCreating ? (
            <Input
              id="new_entity_name"
              value={props.form.new_entity_name}
              placeholder={props.t(
                "management.manualPositions.shared.newEntityPlaceholder",
              )}
              onChange={event => {
                props.updateField("new_entity_name", event.target.value)
                props.clearError("new_entity_name" as keyof FormState)
              }}
              readOnly={!allowEntityChanges}
              disabled={!allowEntityChanges}
            />
          ) : (
            <select
              id="entity_id"
              className="w-full h-10 rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-70"
              value={props.form.entity_id ?? ""}
              onChange={event => {
                props.updateField("entity_id", event.target.value)
                props.clearError("entity_id")
              }}
              disabled={!allowEntityChanges}
            >
              <option value="">{props.t("common.selectOptions")}</option>
              {props.entityOptions.map(option => (
                <option key={option.id} value={option.id}>
                  {option.name}
                </option>
              ))}
            </select>
          )}
        </div>
        {allowEntityChanges && (
          <Button
            type="button"
            variant="outline"
            size="icon"
            onClick={handleToggle}
            aria-label={buttonLabel}
            title={buttonLabel}
            className="h-10 w-10 shrink-0"
          >
            {isCreating ? (
              <X className="h-4 w-4" />
            ) : (
              <Plus className="h-4 w-4" />
            )}
          </Button>
        )}
      </div>
      {isCreating
        ? props.errors.new_entity_name && (
            <p className="text-xs text-red-600 dark:text-red-400 mt-1">
              {props.errors.new_entity_name}
            </p>
          )
        : props.errors.entity_id && (
            <p className="text-xs text-red-600 dark:text-red-400 mt-1">
              {props.errors.entity_id}
            </p>
          )}
    </div>
  )
}

const renderDateInput = <FormState extends ManualPositionFormBase>(
  field: keyof FormState,
  label: string,
  props: ManualFormFieldRenderProps<FormState>,
) => (
  <div className="space-y-1.5">
    <Label>{label}</Label>
    <DatePicker
      value={(props.form[field] as string) ?? ""}
      onChange={value => {
        props.updateField(field, value)
        props.clearError(field)
      }}
    />
    {props.errors[field] && (
      <p className="text-xs text-red-600 dark:text-red-400 mt-1">
        {props.errors[field]}
      </p>
    )}
  </div>
)

const buildPortfolioLabel = (
  portfolio?: Pick<FundPortfolio, "name" | "currency"> | null,
) => {
  if (!portfolio) return ""
  const name = portfolio.name?.trim()
  const currency = portfolio.currency?.toUpperCase()
  if (name && currency) return `${name} (${currency})`
  if (name) return name
  if (currency) return currency
  return ""
}

const requiredField = <FormState extends ManualPositionFormBase>(
  t: ManualFormFieldRenderProps<FormState>["t"],
): string => t("management.manualPositions.shared.validation.required")

const numberFieldError = <FormState extends ManualPositionFormBase>(
  t: ManualFormFieldRenderProps<FormState>["t"],
): string => t("management.manualPositions.shared.validation.number")

const isManualSource = (entry: { source?: DataSource | null }) =>
  entry.source === DataSource.MANUAL

interface BankLoanFormState extends ManualPositionFormBase {
  name: string
  type: LoanType
  currency: string
  loan_amount: string
  interest_rate: string
  current_installment: string
  principal_outstanding: string
  interest_type: InterestType
  euribor_rate: string
  fixed_years: string
  creation: string
  maturity: string
}

function LoanCalculationHelper(
  props: ManualFormFieldRenderProps<BankLoanFormState>,
) {
  const { showToast } = useAppContext()
  const [isCalculating, setIsCalculating] = useState(false)

  const interestType = props.form.interest_type as InterestType

  const handleCalculate = async () => {
    const interestRatePercent = parseNumberInput(props.form.interest_rate)
    const creationDate = normalizeDateInput(props.form.creation)
    const maturityDate = normalizeDateInput(props.form.maturity)
    const principalOutstanding = parseNumberInput(
      props.form.principal_outstanding,
    )
    const loanAmount = parseNumberInput(props.form.loan_amount)

    if (
      !props.form.interest_type ||
      interestRatePercent === null ||
      !creationDate ||
      !maturityDate ||
      ((principalOutstanding === null || principalOutstanding <= 0) &&
        (loanAmount === null || loanAmount <= 0))
    ) {
      showToast(
        props.t("management.manualPositions.bankLoans.helpers.missingFields"),
        "warning",
      )
      return
    }

    if (
      (interestType === InterestType.VARIABLE ||
        interestType === InterestType.MIXED) &&
      parseNumberInput(props.form.euribor_rate) === null
    ) {
      showToast(
        props.t("management.manualPositions.bankLoans.helpers.missingEuribor"),
        "warning",
      )
      return
    }

    if (
      interestType === InterestType.MIXED &&
      parseNumberInput(props.form.fixed_years) === null
    ) {
      showToast(
        props.t(
          "management.manualPositions.bankLoans.helpers.missingFixedYears",
        ),
        "warning",
      )
      return
    }

    const euriborRate = parseNumberInput(props.form.euribor_rate)
    const fixedYears = parseNumberInput(props.form.fixed_years)

    const request: LoanCalculationRequest = {
      interest_rate: (interestRatePercent ?? 0) / 100,
      interest_type: interestType,
      start: creationDate,
      end: maturityDate,
    }

    if (principalOutstanding !== null && principalOutstanding > 0) {
      request.principal_outstanding = principalOutstanding
    } else if (loanAmount !== null && loanAmount > 0) {
      request.loan_amount = loanAmount
    }

    if (
      interestType === InterestType.VARIABLE ||
      interestType === InterestType.MIXED
    ) {
      request.euribor_rate = euriborRate != null ? euriborRate / 100 : undefined
    }

    if (interestType === InterestType.MIXED && fixedYears !== null) {
      request.fixed_years = fixedYears
    }

    try {
      setIsCalculating(true)
      const result = await calculateLoan(request)

      if (
        typeof result.current_monthly_payment === "number" &&
        Number.isFinite(result.current_monthly_payment)
      ) {
        props.updateField(
          "current_installment",
          formatNumberInput(result.current_monthly_payment, {
            maximumFractionDigits: 2,
          }),
        )
        props.clearError("current_installment")
      }

      const currentPrincipal = parseNumberInput(
        props.form.principal_outstanding,
      )
      if (
        typeof result.principal_outstanding === "number" &&
        Number.isFinite(result.principal_outstanding) &&
        (currentPrincipal === null || currentPrincipal <= 0)
      ) {
        props.updateField(
          "principal_outstanding",
          formatNumberInput(result.principal_outstanding, {
            maximumFractionDigits: 2,
          }),
        )
        props.clearError("principal_outstanding")
      }

      showToast(
        props.t(
          "management.manualPositions.bankLoans.helpers.calculationApplied",
        ),
        "success",
      )
    } catch (error) {
      console.error(error)
      showToast(
        props.t(
          "management.manualPositions.bankLoans.helpers.calculationFailed",
        ),
        "error",
      )
    } finally {
      setIsCalculating(false)
    }
  }

  return (
    <div className="md:col-span-2 rounded-lg border border-dashed border-muted p-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-muted-foreground">
          {props.t(
            "management.manualPositions.bankLoans.helpers.calculationHint",
          )}
        </p>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="self-start sm:self-auto"
          disabled={isCalculating}
          onClick={handleCalculate}
        >
          {isCalculating ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Calculator className="mr-2 h-4 w-4" />
          )}
          {props.t(
            "management.manualPositions.bankLoans.helpers.calculateButton",
          )}
        </Button>
      </div>
    </div>
  )
}

interface FundFormState extends ManualPositionFormBase {
  name: string
  isin: string
  shares: string
  average_buy_price: string
  initial_investment: string
  market_value: string
  currency: string
  type: string
  asset_type: string
  portfolio_id: string
  _portfolio_label: string
  _portfolio_source: string
  _portfolio_name: string
  _portfolio_currency: string
  _last_investment_field: string
  _suggested_market_price: string
}

interface StockFormState extends ManualPositionFormBase {
  name: string
  ticker: string
  isin: string
  shares: string
  average_buy_price: string
  initial_investment: string
  market_value: string
  currency: string
  type: string
  _last_investment_field: string
  _suggested_market_price: string
}

const MAX_INSTRUMENT_RESULTS = 15

const buildInstrumentPrimaryLabel = (
  entry: InstrumentInfo,
  t: ManualFormFieldRenderProps<any>["t"],
) => {
  if (entry.name) return entry.name
  if (entry.symbol) return entry.symbol
  if (entry.isin) return entry.isin
  return t("common.notAvailable")
}

const buildInstrumentSecondaryInfo = (
  entry: InstrumentInfo,
  labels: { isin: string; ticker: string },
) => {
  const parts: string[] = []
  if (entry.isin) {
    parts.push(`${labels.isin}: ${entry.isin}`)
  }
  if (entry.symbol) {
    parts.push(`${labels.ticker}: ${entry.symbol}`)
  }
  return parts.join(" • ")
}

const formatInstrumentPriceLabel = (entry: InstrumentInfo, locale: string) => {
  if (entry.price == null) return null
  const formatted = entry.price.toLocaleString(locale, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 6,
  })
  const currency = entry.currency?.toUpperCase()
  return currency ? `${currency} ${formatted}` : formatted
}

const mapEquityTypeToInstrumentType = (
  value?: string | null,
): InstrumentType | null => {
  if (value === EquityType.STOCK) return InstrumentType.STOCK
  if (value === EquityType.ETF) return InstrumentType.ETF
  return null
}

const mapInstrumentTypeToEquityType = (
  value?: InstrumentType | null,
): EquityType | null => {
  if (value === InstrumentType.STOCK) return EquityType.STOCK
  if (value === InstrumentType.ETF) return EquityType.ETF
  return null
}

const useInstrumentDropdown = (isOpen: boolean, onClose: () => void) => {
  const ref = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!isOpen) return

    const handlePointerDown = (event: MouseEvent | TouchEvent) => {
      if (!ref.current) return
      const target = event.target as Node | null
      if (target && !ref.current.contains(target)) {
        onClose()
      }
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose()
      }
    }

    document.addEventListener("mousedown", handlePointerDown)
    document.addEventListener("touchstart", handlePointerDown)
    document.addEventListener("keydown", handleKeyDown)

    return () => {
      document.removeEventListener("mousedown", handlePointerDown)
      document.removeEventListener("touchstart", handlePointerDown)
      document.removeEventListener("keydown", handleKeyDown)
    }
  }, [isOpen, onClose])

  return ref
}

interface FundInstrumentSearchFieldProps {
  field: "name" | "isin"
  label: string
  formProps: ManualFormFieldRenderProps<FundFormState>
}

function FundInstrumentSearchField({
  field,
  label,
  formProps,
}: FundInstrumentSearchFieldProps) {
  const { form, updateField, clearError, errors, t, locale } = formProps
  const [results, setResults] = useState<InstrumentInfo[]>([])
  const [hasSearched, setHasSearched] = useState(false)
  const [isSearching, setIsSearching] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [detailsLoadingId, setDetailsLoadingId] = useState<string | null>(null)
  const dropdownLabels = {
    isin: t("management.manualPositions.funds.fields.isin"),
    ticker: t("management.manualPositions.stocks.fields.ticker"),
  }

  const inputValue = (form[field] as string) ?? ""

  useEffect(() => {
    setResults([])
    setHasSearched(false)
    setSearchError(null)
  }, [inputValue])

  const closeDropdown = useCallback(() => {
    setHasSearched(false)
    setSearchError(null)
    setResults([])
  }, [])

  const containerRef = useInstrumentDropdown(
    hasSearched || Boolean(searchError),
    closeDropdown,
  )

  const handleSearch = async () => {
    const normalizedValue =
      field === "isin" ? inputValue.trim().toUpperCase() : inputValue.trim()
    if (!normalizedValue || isSearching) return

    const request: InstrumentDataRequest = {
      type: InstrumentType.MUTUAL_FUND,
    }

    if (field === "name") {
      request.name = normalizedValue
    } else {
      request.isin = normalizedValue
    }

    setIsSearching(true)
    setSearchError(null)
    setHasSearched(false)

    try {
      const response = await getInstruments(request)
      const entries = (response.entries ?? []).slice(0, MAX_INSTRUMENT_RESULTS)
      setResults(entries)
      setHasSearched(true)
    } catch (error) {
      console.error("Instrument search failed", error)
      setSearchError(t("common.error"))
      setResults([])
      setHasSearched(true)
    } finally {
      setIsSearching(false)
    }
  }

  const handleSelect = async (entry: InstrumentInfo, index: number) => {
    if (detailsLoadingId) return

    const entryKey = entry.isin ?? entry.symbol ?? entry.name ?? String(index)
    const detailsRequest: InstrumentDataRequest = {
      type: InstrumentType.MUTUAL_FUND,
    }

    if (entry.isin) {
      detailsRequest.isin = entry.isin
    }

    if (entry.name) {
      detailsRequest.name = entry.name
    }

    if (entry.symbol) {
      detailsRequest.ticker = entry.symbol
    }

    const applySelection = (details: InstrumentOverview | null) => {
      const resolvedName = (
        entry.name ??
        details?.name ??
        form.name ??
        ""
      ).trim()
      if (resolvedName) {
        updateField("name", resolvedName)
        clearError("name")
      }

      const resolvedIsin = (entry.isin ?? details?.isin ?? form.isin ?? "")
        .trim()
        .toUpperCase()
      if (resolvedIsin) {
        updateField("isin", resolvedIsin)
        clearError("isin")
      }

      const resolvedCurrency = (
        entry.currency ??
        details?.currency ??
        form.currency ??
        ""
      ).toString()
      if (resolvedCurrency) {
        updateField("currency", resolvedCurrency.toUpperCase())
        clearError("currency")
      }

      updateField("type", FundType.MUTUAL_FUND)
      clearError("type")

      const resolvedPriceValue =
        details?.price != null
          ? details.price
          : entry.price != null
            ? entry.price
            : null

      if (resolvedPriceValue != null) {
        const formattedPrice = formatNumberInput(resolvedPriceValue, {
          maximumFractionDigits: 6,
        })

        if (formattedPrice) {
          updateField("_suggested_market_price", formattedPrice)

          const sharesValue = parseNumberInput(form.shares)
          if (sharesValue != null && sharesValue > 0) {
            const totalValue = sharesValue * resolvedPriceValue
            const formattedTotal = formatNumberInput(totalValue)
            if (formattedTotal) {
              updateField("market_value", formattedTotal)
            } else {
              updateField("market_value", formattedPrice)
            }
          } else {
            updateField("market_value", formattedPrice)
          }

          clearError("market_value")
        }
      } else {
        updateField("_suggested_market_price", "")
      }
    }

    setDetailsLoadingId(entryKey)
    let details: InstrumentOverview | null = null

    try {
      details = await getInstrumentDetails(detailsRequest)
    } catch (error) {
      console.error("Instrument details fetch failed", error)
    } finally {
      setDetailsLoadingId(null)
    }

    applySelection(details)
    closeDropdown()
  }

  const disabled = !inputValue.trim() || isSearching

  return (
    <div ref={containerRef} className="space-y-1.5">
      <Label htmlFor={field}>{label}</Label>
      <div className="relative">
        <Input
          id={field}
          value={inputValue}
          onChange={event => {
            const value = event.target.value
            updateField(field, value)
            clearError(field)
            if (form._suggested_market_price) {
              updateField("_suggested_market_price", "")
            }
          }}
          onKeyDown={event => {
            if (event.key === "Enter") {
              event.preventDefault()
              handleSearch()
            }
          }}
          className="pr-10"
        />
        <button
          type="button"
          className="absolute inset-y-0 right-2 flex items-center justify-center rounded-md p-1 text-muted-foreground transition hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
          onClick={handleSearch}
          disabled={disabled}
          title={t("common.search")}
        >
          {isSearching ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Search className="h-4 w-4" />
          )}
        </button>
        {(hasSearched || searchError) && (
          <div className="absolute left-0 right-0 top-full z-30 mt-2 overflow-hidden rounded-md border border-border bg-popover shadow-lg">
            {searchError ? (
              <p className="px-3 py-2 text-xs text-red-600 dark:text-red-400">
                {searchError}
              </p>
            ) : results.length > 0 ? (
              <div className="max-h-60 overflow-y-auto py-1">
                {results.map((entry, index) => {
                  const entryKey =
                    entry.isin ?? entry.symbol ?? entry.name ?? String(index)
                  const waiting = detailsLoadingId === entryKey
                  const priceLabel = formatInstrumentPriceLabel(entry, locale)
                  const secondaryInfo = buildInstrumentSecondaryInfo(
                    entry,
                    dropdownLabels,
                  )
                  return (
                    <button
                      key={entryKey + index}
                      type="button"
                      className="flex w-full flex-col gap-1 px-3 py-2 text-left transition hover:bg-muted focus:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
                      onClick={() => handleSelect(entry, index)}
                      disabled={Boolean(detailsLoadingId)}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-medium">
                          {buildInstrumentPrimaryLabel(entry, t)}
                        </span>
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          {entry.currency && (
                            <span>{entry.currency.toUpperCase()}</span>
                          )}
                          {priceLabel && <span>{priceLabel}</span>}
                          {waiting && (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          )}
                        </div>
                      </div>
                      {secondaryInfo && (
                        <p className="text-xs text-muted-foreground">
                          {secondaryInfo}
                        </p>
                      )}
                    </button>
                  )
                })}
              </div>
            ) : (
              <p className="px-3 py-2 text-xs text-muted-foreground">
                {t("common.noOptionsFound")}
              </p>
            )}
          </div>
        )}
      </div>
      {errors[field] && (
        <p className="text-xs text-red-600 dark:text-red-400 mt-1">
          {errors[field]}
        </p>
      )}
    </div>
  )
}

interface StockInstrumentSearchFieldProps {
  field: "name" | "ticker" | "isin"
  label: string
  formProps: ManualFormFieldRenderProps<StockFormState>
}

function StockInstrumentSearchField({
  field,
  label,
  formProps,
}: StockInstrumentSearchFieldProps) {
  const { form, updateField, clearError, errors, t, locale } = formProps
  const [results, setResults] = useState<InstrumentInfo[]>([])
  const [hasSearched, setHasSearched] = useState(false)
  const [isSearching, setIsSearching] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [detailsLoadingId, setDetailsLoadingId] = useState<string | null>(null)
  const dropdownLabels = {
    isin: t("management.manualPositions.stocks.fields.isin"),
    ticker: t("management.manualPositions.stocks.fields.ticker"),
  }

  const inputValue = (form[field] as string) ?? ""
  const selectedInstrumentType = mapEquityTypeToInstrumentType(form.type)

  useEffect(() => {
    setResults([])
    setHasSearched(false)
    setSearchError(null)
  }, [inputValue, form.type])

  const closeDropdown = useCallback(() => {
    setHasSearched(false)
    setSearchError(null)
    setResults([])
  }, [])

  const containerRef = useInstrumentDropdown(
    hasSearched || Boolean(searchError),
    closeDropdown,
  )

  const handleSearch = async () => {
    const query = inputValue.trim()
    if (!query || isSearching || !selectedInstrumentType) return

    const trimmedValue = inputValue.trim()
    if (!trimmedValue) return

    const request: InstrumentDataRequest = {
      type: selectedInstrumentType,
    }

    if (field === "name") {
      request.name = trimmedValue
    } else if (field === "ticker") {
      request.ticker = trimmedValue.toUpperCase()
    } else {
      request.isin = trimmedValue.toUpperCase()
    }

    setIsSearching(true)
    setSearchError(null)
    setHasSearched(false)

    try {
      const response = await getInstruments(request)
      const entries = (response.entries ?? []).slice(0, MAX_INSTRUMENT_RESULTS)
      setResults(entries)
      setHasSearched(true)
    } catch (error) {
      console.error("Instrument search failed", error)
      setSearchError(t("common.error"))
      setResults([])
      setHasSearched(true)
    } finally {
      setIsSearching(false)
    }
  }

  const handleSelect = async (entry: InstrumentInfo, index: number) => {
    if (detailsLoadingId) return

    const entryKey = entry.isin ?? entry.symbol ?? entry.name ?? String(index)
    const requestType = entry.type ?? selectedInstrumentType
    const detailsRequest: InstrumentDataRequest = {
      type: requestType ?? InstrumentType.STOCK,
    }

    if (entry.isin) {
      detailsRequest.isin = entry.isin
    }
    if (entry.name) {
      detailsRequest.name = entry.name
    }
    if (entry.symbol) {
      detailsRequest.ticker = entry.symbol
    }

    const applySelection = (details: InstrumentOverview | null) => {
      const resolvedName = (
        entry.name ??
        details?.name ??
        form.name ??
        ""
      ).trim()
      if (resolvedName) {
        updateField("name", resolvedName)
        clearError("name")
      }

      const resolvedTicker = (
        entry.symbol ??
        details?.symbol ??
        form.ticker ??
        ""
      )
        .trim()
        .toUpperCase()
      if (resolvedTicker) {
        updateField("ticker", resolvedTicker)
        clearError("ticker")
      }

      const resolvedIsin = (entry.isin ?? details?.isin ?? form.isin ?? "")
        .trim()
        .toUpperCase()
      if (resolvedIsin) {
        updateField("isin", resolvedIsin)
        clearError("isin")
      }

      const resolvedCurrency = (
        entry.currency ??
        details?.currency ??
        form.currency ??
        ""
      ).toString()
      if (resolvedCurrency) {
        updateField("currency", resolvedCurrency.toUpperCase())
        clearError("currency")
      }

      const mappedType = mapInstrumentTypeToEquityType(
        details?.type ?? entry.type ?? requestType ?? null,
      )
      if (mappedType) {
        updateField("type", mappedType)
        clearError("type")
      }

      const resolvedPriceValue =
        details?.price != null
          ? details.price
          : entry.price != null
            ? entry.price
            : null

      if (resolvedPriceValue != null) {
        const formattedPrice = formatNumberInput(resolvedPriceValue, {
          maximumFractionDigits: 6,
        })

        if (formattedPrice) {
          updateField("_suggested_market_price", formattedPrice)

          const sharesValue = parseNumberInput(form.shares)
          if (sharesValue != null && sharesValue > 0) {
            const totalValue = sharesValue * resolvedPriceValue
            const formattedTotal = formatNumberInput(totalValue)
            if (formattedTotal) {
              updateField("market_value", formattedTotal)
            } else {
              updateField("market_value", formattedPrice)
            }
          } else {
            updateField("market_value", formattedPrice)
          }

          clearError("market_value")
        }
      } else {
        updateField("_suggested_market_price", "")
      }
    }

    setDetailsLoadingId(entryKey)
    let details: InstrumentOverview | null = null

    try {
      details = await getInstrumentDetails(detailsRequest)
    } catch (error) {
      console.error("Instrument details fetch failed", error)
    } finally {
      setDetailsLoadingId(null)
    }

    applySelection(details)
    closeDropdown()
  }

  const disabled =
    !inputValue.trim() ||
    isSearching ||
    !selectedInstrumentType ||
    !!detailsLoadingId

  return (
    <div ref={containerRef} className="space-y-1.5">
      <Label htmlFor={field}>{label}</Label>
      <div className="relative">
        <Input
          id={field}
          value={inputValue}
          onChange={event => {
            const rawValue = event.target.value
            const value =
              field === "ticker" || field === "isin"
                ? rawValue.toUpperCase()
                : rawValue
            updateField(field, value)
            clearError(field)
            if (form._suggested_market_price) {
              updateField("_suggested_market_price", "")
            }
          }}
          onKeyDown={event => {
            if (event.key === "Enter") {
              event.preventDefault()
              handleSearch()
            }
          }}
          className="pr-10"
        />
        <button
          type="button"
          className="absolute inset-y-0 right-2 flex items-center justify-center rounded-md p-1 text-muted-foreground transition hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
          onClick={handleSearch}
          disabled={disabled}
          title={t("common.search")}
        >
          {isSearching ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Search className="h-4 w-4" />
          )}
        </button>
        {(hasSearched || searchError) && (
          <div className="absolute left-0 right-0 top-full z-30 mt-2 overflow-hidden rounded-md border border-border bg-popover shadow-lg">
            {searchError ? (
              <p className="px-3 py-2 text-xs text-red-600 dark:text-red-400">
                {searchError}
              </p>
            ) : results.length > 0 ? (
              <div className="max-h-60 overflow-y-auto py-1">
                {results.map((entry, index) => {
                  const entryKey =
                    entry.isin ?? entry.symbol ?? entry.name ?? String(index)
                  const waiting = detailsLoadingId === entryKey
                  const priceLabel = formatInstrumentPriceLabel(entry, locale)
                  const secondaryInfo = buildInstrumentSecondaryInfo(
                    entry,
                    dropdownLabels,
                  )
                  return (
                    <button
                      key={entryKey + index}
                      type="button"
                      className="flex w-full flex-col gap-1 px-3 py-2 text-left transition hover:bg-muted focus:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
                      onClick={() => handleSelect(entry, index)}
                      disabled={Boolean(detailsLoadingId)}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-medium">
                          {buildInstrumentPrimaryLabel(entry, t)}
                        </span>
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          {entry.currency && (
                            <span>{entry.currency.toUpperCase()}</span>
                          )}
                          {priceLabel && <span>{priceLabel}</span>}
                          {waiting && (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          )}
                        </div>
                      </div>
                      {secondaryInfo && (
                        <p className="text-xs text-muted-foreground">
                          {secondaryInfo}
                        </p>
                      )}
                    </button>
                  )
                })}
              </div>
            ) : (
              <p className="px-3 py-2 text-xs text-muted-foreground">
                {t("common.noOptionsFound")}
              </p>
            )}
          </div>
        )}
      </div>
      {errors[field] && (
        <p className="text-xs text-red-600 dark:text-red-400 mt-1">
          {errors[field]}
        </p>
      )}
    </div>
  )
}

const manualPositionConfigs: ManualPositionConfigMap = {
  bankAccounts: {
    assetKey: "bankAccounts",
    productType: ProductType.ACCOUNT,
    buildDraftsFromPositions: ({ positionsData, manualEntities }) => {
      if (!positionsData?.positions) return []
      const result: ManualPositionDraft<Account>[] = []
      manualEntities.forEach(entity => {
        const entityPosition = positionsData.positions[entity.id]
        if (!entityPosition) return
        const product = entityPosition.products[ProductType.ACCOUNT] as
          | { entries?: Account[] }
          | undefined
        const entries = product?.entries ?? []
        entries.forEach(account => {
          if (!isManualSource(account)) return
          result.push({
            ...account,
            localId: account.id || `${entity.id}-account-${account.name}`,
            originalId: account.id,
            entityId: entity.id,
            entityName: entity.name,
          })
        })
      })
      return result
    },
    createEmptyForm: ({ defaultCurrency }) => ({
      entity_id: "",
      entity_mode: "select" as const,
      new_entity_name: "",
      name: "",
      type: AccountType.CHECKING,
      currency: defaultCurrency,
      total: "",
      iban: "",
      interest: "",
      retained: "",
      pending_transfers: "",
    }),
    draftToForm: draft => ({
      entity_id: draft.isNewEntity ? "" : draft.entityId,
      entity_mode: draft.isNewEntity ? "new" : "select",
      new_entity_name: draft.isNewEntity
        ? (draft.newEntityName ?? draft.entityName ?? "")
        : "",
      name: draft.name ?? "",
      type: draft.type,
      currency: draft.currency,
      total: formatNumberInput(draft.total ?? 0),
      iban: draft.iban ?? "",
      interest:
        draft.interest != null ? formatNumberInput(draft.interest * 100) : "",
      retained: draft.retained != null ? formatNumberInput(draft.retained) : "",
      pending_transfers:
        draft.pending_transfers != null
          ? formatNumberInput(draft.pending_transfers)
          : "",
    }),
    buildEntryFromForm: (form, { previous }) => {
      const total = parseNumberInput(form.total)
      if (total === null) return null
      const interestPercent = parseNumberInput(form.interest)
      const retained = parseNumberInput(form.retained)
      const pending = parseNumberInput(form.pending_transfers)
      const entry: Account = {
        id: previous?.id || previous?.originalId || "",
        total,
        currency: form.currency,
        type: form.type as AccountType,
        name: form.name.trim() || null,
        iban: form.iban.trim() || null,
        interest: interestPercent !== null ? interestPercent / 100 : null,
        retained: retained,
        pending_transfers: pending,
        source: DataSource.MANUAL,
      }
      if (!entry.id) {
        delete (entry as any).id
      }
      return entry
    },
    validateForm: (form, { t }) => {
      const errors: ManualFormErrors<typeof form> = {}
      if (!form.name.trim()) errors.name = requiredField(t)
      if (!form.type) errors.type = requiredField(t)
      if (!form.currency) errors.currency = requiredField(t)
      const total = parseNumberInput(form.total)
      if (total === null || total < 0) errors.total = numberFieldError(t)
      const interest = form.interest.trim()
      if (interest && parseNumberInput(interest) === null)
        errors.interest = numberFieldError(t)
      const retained = form.retained.trim()
      if (retained && parseNumberInput(retained) === null)
        errors.retained = numberFieldError(t)
      const pending = form.pending_transfers.trim()
      if (pending && parseNumberInput(pending) === null)
        errors.pending_transfers = numberFieldError(t)
      return errors
    },
    renderFormFields: props => (
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {renderEntityField(props)}
        {renderSelectInput(
          "type",
          props.t("management.manualPositions.bankAccounts.fields.type"),
          props,
          Object.values(AccountType).map(value => ({
            value,
            label:
              props.t(`enums.accountType.${value}`) ||
              value.charAt(0) + value.slice(1).toLowerCase(),
          })),
        )}
        {renderSelectInput(
          "currency",
          props.t("management.manualPositions.shared.currency"),
          props,
          props.currencyOptions.map(value => ({ value, label: value })),
        )}
        {renderTextInput(
          "total",
          props.t("management.manualPositions.bankAccounts.fields.total"),
          props,
          { type: "number", step: "0.01", inputMode: "decimal" },
        )}
        {renderTextInput(
          "interest",
          props.t("management.manualPositions.bankAccounts.fields.interest"),
          props,
          { type: "number", step: "0.01", inputMode: "decimal" },
        )}
        {renderTextInput(
          "retained",
          props.t("management.manualPositions.bankAccounts.fields.retained"),
          props,
          { type: "number", step: "0.01", inputMode: "decimal" },
        )}
        {renderTextInput(
          "pending_transfers",
          props.t(
            "management.manualPositions.bankAccounts.fields.pendingTransfers",
          ),
          props,
          { type: "number", step: "0.01", inputMode: "decimal" },
        )}
        {renderTextInput(
          "iban",
          props.t("management.manualPositions.bankAccounts.fields.iban"),
          props,
          {
            helperText: props.t(
              "management.manualPositions.bankAccounts.helpers.ibanRecommendation",
            ),
          },
        )}
      </div>
    ),
    getDisplayName: draft => draft.name ?? draft.iban ?? draft.entityName,
    renderDraftSummary: (draft, helpers) => (
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <span className="font-medium text-base">{draft.name || "—"}</span>
          <Badge variant="secondary">
            {helpers.t(`enums.accountType.${draft.type}`) || draft.type}
          </Badge>
        </div>
        <div className="text-sm text-muted-foreground">
          {helpers.formatCurrency(draft.total, draft.currency)}
        </div>
        {draft.iban && (
          <div className="text-xs text-muted-foreground">{draft.iban}</div>
        )}
      </div>
    ),
    normalizeDraftForCompare: draft => ({
      entityId: draft.entityId,
      name: draft.name ?? "",
      type: draft.type,
      currency: draft.currency,
      total: draft.total,
      iban: draft.iban ?? "",
      interest: draft.interest ?? null,
      retained: draft.retained ?? null,
      pending_transfers: draft.pending_transfers ?? null,
    }),
    toPayloadEntry: draft => ({
      id: draft.id || draft.originalId,
      name: draft.name ?? null,
      type: draft.type,
      currency: draft.currency,
      total: draft.total,
      iban: draft.iban ?? null,
      interest: draft.interest ?? null,
      retained: draft.retained ?? null,
      pending_transfers: draft.pending_transfers ?? null,
    }),
  },
  bankCards: {
    assetKey: "bankCards",
    productType: ProductType.CARD,
    buildDraftsFromPositions: ({ positionsData, manualEntities }) => {
      if (!positionsData?.positions) return []
      const result: ManualPositionDraft<Card>[] = []
      manualEntities.forEach(entity => {
        const entityPosition = positionsData.positions[entity.id]
        if (!entityPosition) return
        const product = entityPosition.products[ProductType.CARD] as
          | { entries?: Card[] }
          | undefined
        const entries = product?.entries ?? []
        entries.forEach(card => {
          if (!isManualSource(card)) return
          result.push({
            ...card,
            localId: card.id || `${entity.id}-card-${card.name}`,
            originalId: card.id,
            entityId: entity.id,
            entityName: entity.name,
          })
        })
      })
      return result
    },
    createEmptyForm: ({ defaultCurrency }) => ({
      entity_id: "",
      entity_mode: "select" as const,
      new_entity_name: "",
      name: "",
      type: CardType.DEBIT,
      currency: defaultCurrency,
      used: "",
      limit: "",
      ending: "",
      related_account: "",
      active: "true",
    }),
    draftToForm: draft => ({
      entity_id: draft.isNewEntity ? "" : draft.entityId,
      entity_mode: draft.isNewEntity ? "new" : "select",
      new_entity_name: draft.isNewEntity
        ? (draft.newEntityName ?? draft.entityName ?? "")
        : "",
      name: draft.name ?? "",
      type: draft.type,
      currency: draft.currency,
      used: formatNumberInput(draft.used ?? 0),
      limit: draft.limit != null ? formatNumberInput(draft.limit) : "",
      ending: draft.ending ?? "",
      related_account: draft.related_account ?? "",
      active: draft.active ? "true" : "false",
    }),
    buildEntryFromForm: (form, { previous }) => {
      const used = parseNumberInput(form.used)
      if (used === null) return null
      const limit = parseNumberInput(form.limit)
      const entry: Card = {
        id: previous?.id || previous?.originalId || "",
        currency: form.currency,
        type: form.type as CardType,
        used,
        active: form.active !== "false",
        limit: limit,
        name: form.name.trim() || null,
        ending: form.ending.trim() || null,
        related_account: form.related_account.trim() || null,
        source: DataSource.MANUAL,
      }
      if (!entry.id) {
        delete (entry as any).id
      }
      return entry
    },
    validateForm: (form, { t }) => {
      const errors: ManualFormErrors<typeof form> = {}
      if (!form.name.trim()) errors.name = requiredField(t)
      if (!form.type) errors.type = requiredField(t)
      if (!form.currency) errors.currency = requiredField(t)
      const used = parseNumberInput(form.used)
      if (used === null || used < 0) errors.used = numberFieldError(t)
      const limit = form.limit.trim()
      if (limit && parseNumberInput(limit) === null)
        errors.limit = numberFieldError(t)
      return errors
    },
    renderFormFields: props => (
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {renderEntityField(props)}
        {renderSelectInput(
          "type",
          props.t("management.manualPositions.bankCards.fields.type"),
          props,
          Object.values(CardType).map(value => ({
            value,
            label: props.t(`enums.cardType.${value}`) || value,
          })),
        )}
        {renderTextInput(
          "name",
          props.t("management.manualPositions.shared.name"),
          props,
        )}
        {renderSelectInput(
          "currency",
          props.t("management.manualPositions.shared.currency"),
          props,
          props.currencyOptions.map(value => ({ value, label: value })),
        )}
        {renderTextInput(
          "used",
          props.t("management.manualPositions.bankCards.fields.used"),
          props,
          { type: "number", step: "0.01", inputMode: "decimal" },
        )}
        {renderTextInput(
          "limit",
          props.t("management.manualPositions.bankCards.fields.limit"),
          props,
          { type: "number", step: "0.01", inputMode: "decimal" },
        )}
        {renderTextInput(
          "ending",
          props.t("management.manualPositions.bankCards.fields.ending"),
          props,
        )}
        {(() => {
          const options = props.accountOptions?.(props.form.entity_id) ?? []
          return options.length > 0
            ? renderSelectInput(
                "related_account",
                props.t(
                  "management.manualPositions.bankCards.fields.relatedAccount",
                ),
                props,
                options,
              )
            : renderTextInput(
                "related_account",
                props.t(
                  "management.manualPositions.bankCards.fields.relatedAccount",
                ),
                props,
              )
        })()}
        {renderSelectInput(
          "active",
          props.t("management.manualPositions.bankCards.fields.active"),
          props,
          [
            { value: "true", label: props.t("common.enabled") },
            { value: "false", label: props.t("common.disabled") },
          ],
        )}
      </div>
    ),
    getDisplayName: draft => draft.name ?? draft.ending ?? draft.entityName,
    renderDraftSummary: (draft, helpers) => (
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <span className="font-medium text-base">{draft.name || "—"}</span>
          <Badge variant="secondary">
            {helpers.t(`enums.cardType.${draft.type}`) || draft.type}
          </Badge>
          <Badge variant="outline">
            {helpers.t(
              draft.active
                ? "management.manualPositions.bankCards.summary.active"
                : "management.manualPositions.bankCards.summary.inactive",
            )}
          </Badge>
        </div>
        <div className="text-sm text-muted-foreground">
          {helpers.formatCurrency(draft.used, draft.currency)}
        </div>
        {draft.limit != null && (
          <div className="text-xs text-muted-foreground">
            {helpers.formatCurrency(draft.limit, draft.currency)}
          </div>
        )}
        {draft.ending && (
          <div className="text-xs text-muted-foreground">
            •••• {draft.ending}
          </div>
        )}
      </div>
    ),
    normalizeDraftForCompare: draft => ({
      entityId: draft.entityId,
      name: draft.name ?? "",
      type: draft.type,
      currency: draft.currency,
      used: draft.used,
      limit: draft.limit ?? null,
      ending: draft.ending ?? "",
      related_account: draft.related_account ?? "",
      active: draft.active,
    }),
    toPayloadEntry: draft => ({
      id: draft.id || draft.originalId,
      name: draft.name ?? null,
      type: draft.type,
      currency: draft.currency,
      used: draft.used,
      limit: draft.limit ?? null,
      ending: draft.ending ?? null,
      related_account: draft.related_account ?? null,
      active: draft.active,
    }),
  },
  bankLoans: {
    assetKey: "bankLoans",
    productType: ProductType.LOAN,
    buildDraftsFromPositions: ({ positionsData, manualEntities }) => {
      if (!positionsData?.positions) return []
      const result: ManualPositionDraft<Loan>[] = []
      manualEntities.forEach(entity => {
        const entityPosition = positionsData.positions[entity.id]
        if (!entityPosition) return
        const product = entityPosition.products[ProductType.LOAN] as
          | { entries?: Loan[] }
          | undefined
        const entries = product?.entries ?? []
        entries.forEach(loan => {
          if (!isManualSource(loan)) return
          result.push({
            ...loan,
            localId: loan.id || `${entity.id}-loan-${loan.name}`,
            originalId: loan.id,
            entityId: entity.id,
            entityName: entity.name,
          })
        })
      })
      return result
    },
    createEmptyForm: ({ defaultCurrency }) => ({
      entity_id: "",
      entity_mode: "select" as const,
      new_entity_name: "",
      name: "",
      type: LoanType.STANDARD,
      currency: defaultCurrency,
      loan_amount: "",
      interest_rate: "",
      current_installment: "",
      principal_outstanding: "",
      interest_type: InterestType.FIXED,
      euribor_rate: "",
      fixed_years: "",
      creation: "",
      maturity: "",
    }),
    draftToForm: draft => ({
      entity_id: draft.isNewEntity ? "" : draft.entityId,
      entity_mode: draft.isNewEntity ? "new" : "select",
      new_entity_name: draft.isNewEntity
        ? (draft.newEntityName ?? draft.entityName ?? "")
        : "",
      name: draft.name ?? "",
      type: draft.type,
      currency: draft.currency,
      loan_amount: formatNumberInput(draft.loan_amount ?? 0),
      interest_rate:
        draft.interest_rate != null
          ? formatNumberInput(draft.interest_rate * 100)
          : "",
      current_installment: formatNumberInput(draft.current_installment ?? 0),
      principal_outstanding: formatNumberInput(
        draft.principal_outstanding ?? 0,
      ),
      interest_type: draft.interest_type,
      euribor_rate:
        draft.euribor_rate != null
          ? formatNumberInput(draft.euribor_rate * 100)
          : "",
      fixed_years:
        draft.fixed_years != null
          ? formatNumberInput(draft.fixed_years, {
              maximumFractionDigits: 0,
            })
          : "",
      creation: draft.creation ?? "",
      maturity: draft.maturity ?? "",
    }),
    buildEntryFromForm: (form, { previous }) => {
      const loanAmount = parseNumberInput(form.loan_amount)
      const interestRatePercent = parseNumberInput(form.interest_rate)
      const currentInstallment = parseNumberInput(form.current_installment)
      const principalOutstanding = parseNumberInput(form.principal_outstanding)
      const interestType = form.interest_type as InterestType

      if (
        loanAmount === null ||
        interestRatePercent === null ||
        currentInstallment === null ||
        principalOutstanding === null
      ) {
        return null
      }

      const requiresEuribor =
        interestType === InterestType.VARIABLE ||
        interestType === InterestType.MIXED
      const euriborPercent = requiresEuribor
        ? parseNumberInput(form.euribor_rate)
        : null
      if (requiresEuribor && euriborPercent === null) {
        return null
      }

      const requiresFixedYears = interestType === InterestType.MIXED
      const fixedYearsValue = requiresFixedYears
        ? parseNumberInput(form.fixed_years)
        : null
      if (requiresFixedYears && fixedYearsValue === null) {
        return null
      }

      const creationDate = normalizeDateInput(form.creation)
      const maturityDate = normalizeDateInput(form.maturity)
      if (!creationDate || !maturityDate) {
        return null
      }

      const entry: Loan = {
        id: previous?.id || previous?.originalId || "",
        type: form.type as LoanType,
        currency: form.currency,
        current_installment: currentInstallment,
        interest_rate: interestRatePercent / 100,
        loan_amount: loanAmount,
        next_payment_date: previous?.next_payment_date ?? null,
        principal_outstanding: principalOutstanding,
        principal_paid: previous?.principal_paid ?? null,
        interest_type: interestType,
        euribor_rate: requiresEuribor ? (euriborPercent ?? 0) / 100 : null,
        fixed_years: requiresFixedYears
          ? (fixedYearsValue ?? previous?.fixed_years ?? null)
          : null,
        name: form.name.trim() || null,
        creation: creationDate,
        maturity: maturityDate,
        unpaid: previous?.unpaid ?? null,
        source: DataSource.MANUAL,
      }

      if (!entry.id) {
        delete (entry as any).id
      }
      return entry
    },
    validateForm: (form, { t }) => {
      const errors: ManualFormErrors<typeof form> = {}
      if (!form.name.trim()) errors.name = requiredField(t)
      if (!form.type) errors.type = requiredField(t)
      if (!form.currency) errors.currency = requiredField(t)
      if (!form.interest_type) errors.interest_type = requiredField(t)
      const loanAmount = parseNumberInput(form.loan_amount)
      if (loanAmount === null || loanAmount <= 0)
        errors.loan_amount = numberFieldError(t)
      const interestRate = parseNumberInput(form.interest_rate)
      if (interestRate === null) errors.interest_rate = numberFieldError(t)
      const currentInstallment = parseNumberInput(form.current_installment)
      if (currentInstallment === null)
        errors.current_installment = numberFieldError(t)
      const outstanding = parseNumberInput(form.principal_outstanding)
      if (outstanding === null)
        errors.principal_outstanding = numberFieldError(t)
      const interestType = form.interest_type as InterestType
      if (
        (interestType === InterestType.VARIABLE ||
          interestType === InterestType.MIXED) &&
        parseNumberInput(form.euribor_rate) === null
      ) {
        errors.euribor_rate = numberFieldError(t)
      }
      if (
        interestType === InterestType.MIXED &&
        parseNumberInput(form.fixed_years) === null
      ) {
        errors.fixed_years = numberFieldError(t)
      }
      if (!normalizeDateInput(form.creation)) {
        errors.creation = requiredField(t)
      }
      if (!normalizeDateInput(form.maturity)) {
        errors.maturity = requiredField(t)
      }
      return errors
    },
    renderFormFields: props => {
      const loanProps = props as ManualFormFieldRenderProps<BankLoanFormState>
      const showEuriborField =
        props.form.interest_type === InterestType.VARIABLE ||
        props.form.interest_type === InterestType.MIXED
      const showFixedYearsField =
        props.form.interest_type === InterestType.MIXED

      return (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {renderEntityField(props)}
          {renderSelectInput(
            "type",
            props.t("management.manualPositions.bankLoans.fields.type"),
            props,
            Object.values(LoanType).map(value => ({
              value,
              label: props.t(`enums.loanType.${value}`) || value,
            })),
          )}
          {renderTextInput(
            "name",
            props.t("management.manualPositions.shared.name"),
            props,
          )}
          {renderSelectInput(
            "currency",
            props.t("management.manualPositions.shared.currency"),
            props,
            props.currencyOptions.map(value => ({ value, label: value })),
          )}
          {renderTextInput(
            "loan_amount",
            props.t("management.manualPositions.bankLoans.fields.loanAmount"),
            props,
            { type: "number", step: "0.01", inputMode: "decimal" },
          )}
          {renderTextInput(
            "interest_rate",
            props.t("management.manualPositions.bankLoans.fields.interestRate"),
            props,
            { type: "number", step: "0.01", inputMode: "decimal" },
          )}
          {renderTextInput(
            "current_installment",
            props.t(
              "management.manualPositions.bankLoans.fields.currentInstallment",
            ),
            props,
            { type: "number", step: "0.01", inputMode: "decimal" },
          )}
          {renderTextInput(
            "principal_outstanding",
            props.t(
              "management.manualPositions.bankLoans.fields.principalOutstanding",
            ),
            props,
            { type: "number", step: "0.01", inputMode: "decimal" },
          )}
          {renderSelectInput(
            "interest_type",
            props.t("management.manualPositions.bankLoans.fields.interestType"),
            props,
            Object.values(InterestType).map(value => ({
              value,
              label: props.t(`enums.interestType.${value}`) || value,
            })),
          )}
          {showEuriborField &&
            renderTextInput(
              "euribor_rate",
              props.t(
                "management.manualPositions.bankLoans.fields.euriborRate",
              ),
              props,
              { type: "number", step: "0.01", inputMode: "decimal" },
            )}
          {showFixedYearsField &&
            renderTextInput(
              "fixed_years",
              props.t("management.manualPositions.bankLoans.fields.fixedYears"),
              props,
              { type: "number", step: "1", inputMode: "numeric" },
            )}
          <LoanCalculationHelper {...loanProps} />
          {renderDateInput(
            "creation",
            props.t("management.manualPositions.bankLoans.fields.creation"),
            props,
          )}
          {renderDateInput(
            "maturity",
            props.t("management.manualPositions.bankLoans.fields.maturity"),
            props,
          )}
        </div>
      )
    },
    getDisplayName: draft => draft.name ?? draft.entityName,
    renderDraftSummary: (draft, helpers) => (
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <span className="font-medium text-base">{draft.name || "—"}</span>
          <Badge variant="secondary">
            {helpers.t(`enums.loanType.${draft.type}`) || draft.type}
          </Badge>
        </div>
        <div className="text-sm text-muted-foreground">
          {helpers.formatCurrency(draft.loan_amount, draft.currency)}
        </div>
        <div className="text-xs text-muted-foreground">
          {draft.interest_rate != null
            ? helpers.t(
                "management.manualPositions.bankLoans.summary.interest",
                { rate: (draft.interest_rate * 100).toFixed(2) },
              )
            : ""}
        </div>
      </div>
    ),
    normalizeDraftForCompare: draft => ({
      entityId: draft.entityId,
      name: draft.name ?? "",
      type: draft.type,
      currency: draft.currency,
      loan_amount: draft.loan_amount,
      interest_rate: draft.interest_rate,
      current_installment: draft.current_installment,
      principal_outstanding: draft.principal_outstanding,
      interest_type: draft.interest_type,
      euribor_rate: draft.euribor_rate ?? null,
      fixed_years: draft.fixed_years ?? null,
      creation: draft.creation ?? "",
      maturity: draft.maturity ?? "",
    }),
    toPayloadEntry: draft => ({
      id: draft.id || draft.originalId,
      type: draft.type,
      currency: draft.currency,
      loan_amount: draft.loan_amount,
      interest_rate: draft.interest_rate,
      current_installment: draft.current_installment,
      principal_outstanding: draft.principal_outstanding,
      principal_paid: draft.principal_paid,
      interest_type: draft.interest_type,
      next_payment_date: draft.next_payment_date ?? null,
      creation: draft.creation ?? null,
      maturity: draft.maturity ?? null,
      name: draft.name ?? null,
      euribor_rate: draft.euribor_rate ?? null,
      fixed_years: draft.fixed_years ?? null,
      unpaid: draft.unpaid ?? null,
    }),
  },
  fundPortfolios: {
    assetKey: "fundPortfolios",
    productType: ProductType.FUND_PORTFOLIO,
    buildDraftsFromPositions: ({ positionsData, manualEntities }) => {
      if (!positionsData?.positions) return []
      const result: ManualPositionDraft<FundPortfolio>[] = []
      manualEntities.forEach(entity => {
        const entityPosition = positionsData.positions[entity.id]
        if (!entityPosition) return
        const product = entityPosition.products[ProductType.FUND_PORTFOLIO] as
          | { entries?: FundPortfolio[] }
          | undefined
        const accountProduct = entityPosition.products[ProductType.ACCOUNT] as
          | { entries?: Account[] }
          | undefined
        const accountEntries = accountProduct?.entries ?? []

        const entries = product?.entries ?? []
        entries.forEach(portfolio => {
          if (!isManualSource(portfolio)) return
          let resolvedAccountId = portfolio.account_id ?? null

          if (portfolio.account && accountEntries.length > 0) {
            const targetIban = portfolio.account.iban?.trim().toUpperCase()
            const targetName = portfolio.account.name?.trim().toLowerCase()

            const matchedAccount = accountEntries.find(account => {
              if (account.type !== AccountType.FUND_PORTFOLIO) return false
              if (!account.id) return false

              const accountIban = account.iban?.trim().toUpperCase()
              if (!targetIban || !accountIban || accountIban !== targetIban) {
                return false
              }

              const accountName = account.name?.trim().toLowerCase()
              if (targetName && accountName) {
                return accountName === targetName
              }

              return true
            })

            if (matchedAccount?.id) {
              resolvedAccountId = matchedAccount.id
            }
          }

          result.push({
            ...portfolio,
            account_id: resolvedAccountId,
            localId: portfolio.id || `${entity.id}-portfolio-${portfolio.name}`,
            originalId: portfolio.id,
            entityId: entity.id,
            entityName: entity.name,
          })
        })
      })
      return result
    },
    createEmptyForm: ({ defaultCurrency, entityId }) => ({
      entity_id: entityId ?? "",
      entity_mode: "select" as const,
      new_entity_name: "",
      name: "",
      currency: defaultCurrency,
      related_account: "",
    }),
    draftToForm: draft => ({
      entity_id: draft.isNewEntity ? "" : draft.entityId,
      entity_mode: draft.isNewEntity ? "new" : "select",
      new_entity_name: draft.isNewEntity
        ? (draft.newEntityName ?? draft.entityName ?? "")
        : "",
      name: draft.name ?? "",
      currency: draft.currency ?? "",
      related_account: draft.account_id ?? "",
    }),
    buildEntryFromForm: (form, { previous }) => {
      if (!form.name.trim()) return null
      const entry: FundPortfolio = {
        id: previous?.id || previous?.originalId || "",
        name: form.name.trim(),
        currency: form.currency,
        initial_investment: previous?.initial_investment ?? null,
        market_value: previous?.market_value ?? null,
        account_id: form.related_account?.trim() || null,
        source: DataSource.MANUAL,
      }
      if (!entry.id) {
        delete (entry as any).id
      }
      return entry
    },
    validateForm: (form, { t }) => {
      const errors: ManualFormErrors<typeof form> = {}
      if (!form.name.trim()) errors.name = requiredField(t)
      if (!form.currency) errors.currency = requiredField(t)
      return errors
    },
    renderFormFields: props => {
      const accountOptions = props.accountOptions?.(props.form.entity_id)

      return (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {renderEntityField(props)}
          {renderTextInput(
            "name",
            props.t("management.manualPositions.fundPortfolios.fields.name"),
            props,
          )}
          {renderSelectInput(
            "currency",
            props.t("management.manualPositions.shared.currency"),
            props,
            props.currencyOptions.map(value => ({ value, label: value })),
          )}
          <div className="space-y-1.5">
            <Label htmlFor="related_account">
              {props.t(
                "management.manualPositions.fundPortfolios.fields.relatedAccount",
              )}
            </Label>
            {accountOptions && accountOptions.length > 0 ? (
              <select
                id="related_account"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                value={props.form.related_account ?? ""}
                onChange={event => {
                  props.updateField("related_account", event.target.value)
                  props.clearError("related_account")
                }}
              >
                <option value="">{props.t("common.selectOptions")}</option>
                {accountOptions.map(option => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            ) : (
              <p className="text-xs text-muted-foreground">
                {props.t(
                  "management.manualPositions.fundPortfolios.helpers.accountRecommendation",
                )}
              </p>
            )}
            <p className="text-xs text-muted-foreground">
              {props.t(
                "management.manualPositions.fundPortfolios.helpers.accountHint",
              )}
            </p>
          </div>
        </div>
      )
    },
    getDisplayName: draft => draft.name ?? draft.entityName,
    renderDraftSummary: (draft, helpers) => (
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <span className="font-medium text-base">{draft.name || "—"}</span>
          {draft.currency && (
            <Badge variant="secondary" className="text-xs">
              {draft.currency}
            </Badge>
          )}
        </div>
        {draft.related_account && (
          <span className="text-xs text-muted-foreground">
            {helpers.t(
              "management.manualPositions.fundPortfolios.summary.relatedAccount",
            )}
            : {draft.related_account}
          </span>
        )}
      </div>
    ),
    normalizeDraftForCompare: draft => ({
      ...draft,
      related_account: draft.related_account ?? null,
    }),
    toPayloadEntry: draft => {
      const resolvedId = (() => {
        const rawId = typeof draft.id === "string" ? draft.id.trim() : ""
        if (rawId) return rawId
        const rawOriginalId =
          typeof draft.originalId === "string" ? draft.originalId.trim() : ""
        if (rawOriginalId) return rawOriginalId
        return draft.localId
      })()

      return {
        id: resolvedId,
        name: draft.name ?? null,
        currency: draft.currency ?? null,
        initial_investment: draft.initial_investment ?? null,
        market_value: draft.market_value ?? null,
        account_id: draft.account_id ?? null,
        source: draft.source ?? DataSource.MANUAL,
      }
    },
  },
  funds: {
    assetKey: "funds",
    productType: ProductType.FUND,
    buildDraftsFromPositions: ({ positionsData, manualEntities }) => {
      if (!positionsData?.positions) return []
      const result: ManualPositionDraft<FundDetail>[] = []
      manualEntities.forEach(entity => {
        const entityPosition = positionsData.positions[entity.id]
        if (!entityPosition) return
        const product = entityPosition.products[ProductType.FUND] as
          | { entries?: FundDetail[] }
          | undefined
        const entries = product?.entries ?? []
        entries.forEach(fund => {
          if (!isManualSource(fund)) return
          result.push({
            ...fund,
            localId: fund.id || `${entity.id}-fund-${fund.isin || fund.name}`,
            originalId: fund.id,
            entityId: entity.id,
            entityName: entity.name,
          })
        })
      })
      return result
    },
    createEmptyForm: ({ defaultCurrency }) => {
      const form: FundFormState = {
        entity_id: "",
        entity_mode: "select",
        new_entity_name: "",
        name: "",
        isin: "",
        shares: "",
        average_buy_price: "",
        initial_investment: "",
        market_value: "",
        currency: defaultCurrency,
        type: FundType.MUTUAL_FUND,
        asset_type: "",
        portfolio_id: "",
        _portfolio_label: "",
        _portfolio_source: "",
        _portfolio_name: "",
        _portfolio_currency: "",
        _last_investment_field: "",
        _suggested_market_price: "",
      }
      return form
    },
    draftToForm: draft => {
      const form: FundFormState = {
        entity_id: draft.isNewEntity ? "" : draft.entityId,
        entity_mode: draft.isNewEntity ? "new" : "select",
        new_entity_name: draft.isNewEntity
          ? (draft.newEntityName ?? draft.entityName ?? "")
          : "",
        name: draft.name ?? "",
        isin: draft.isin ?? "",
        shares: formatNumberInput(draft.shares ?? 0),
        average_buy_price:
          draft.average_buy_price != null
            ? formatNumberInput(draft.average_buy_price)
            : "",
        initial_investment:
          draft.initial_investment != null
            ? formatNumberInput(draft.initial_investment)
            : "",
        market_value:
          draft.market_value != null
            ? formatNumberInput(draft.market_value)
            : "",
        currency: draft.currency,
        type: draft.type ?? FundType.MUTUAL_FUND,
        asset_type: draft.asset_type ?? "",
        portfolio_id: draft.portfolio?.id ?? "",
        _portfolio_label: buildPortfolioLabel(draft.portfolio ?? null),
        _portfolio_source: draft.portfolio?.source ?? "",
        _portfolio_name: draft.portfolio?.name?.trim() ?? "",
        _portfolio_currency: draft.portfolio?.currency?.toUpperCase() ?? "",
        _last_investment_field: "average",
        _suggested_market_price: "",
      }
      return form
    },
    buildEntryFromForm: (form, { previous }) => {
      const shares = parseNumberInput(form.shares)
      if (shares === null || shares <= 0) return null

      let averageBuy = parseNumberInput(form.average_buy_price)
      let initialInvestment = parseNumberInput(form.initial_investment)
      const marketValueInput = parseNumberInput(form.market_value)
      const lastField = form._last_investment_field

      if (lastField === "initial" && initialInvestment != null) {
        averageBuy = initialInvestment / shares
      } else if (averageBuy != null) {
        initialInvestment = averageBuy * shares
      } else if (initialInvestment != null) {
        averageBuy = initialInvestment / shares
      }

      const resolvedInitialInvestment =
        initialInvestment ?? (averageBuy != null ? averageBuy * shares : 0)
      const resolvedAverageBuy =
        averageBuy ?? (shares > 0 ? resolvedInitialInvestment / shares : 0)
      const resolvedMarketValue = marketValueInput ?? resolvedInitialInvestment

      const trimmedPortfolioId = form.portfolio_id?.trim() ?? ""
      const normalizedSource = (() => {
        const sourceCandidate = form._portfolio_source?.trim()
        if (sourceCandidate) {
          const values = Object.values(DataSource)
          if (values.includes(sourceCandidate as DataSource)) {
            return sourceCandidate as DataSource
          }
        }
        return previous?.portfolio?.source ?? DataSource.MANUAL
      })()
      const isSamePortfolio =
        trimmedPortfolioId && previous?.portfolio?.id === trimmedPortfolioId

      const portfolio: FundPortfolio | null = trimmedPortfolioId
        ? {
            id: trimmedPortfolioId,
            name:
              form._portfolio_name?.trim() ||
              (isSamePortfolio ? (previous?.portfolio?.name ?? null) : null),
            currency:
              form._portfolio_currency?.trim().toUpperCase() ||
              (isSamePortfolio
                ? (previous?.portfolio?.currency ?? null)
                : null),
            initial_investment: isSamePortfolio
              ? (previous?.portfolio?.initial_investment ?? null)
              : null,
            market_value: isSamePortfolio
              ? (previous?.portfolio?.market_value ?? null)
              : null,
            account_id: isSamePortfolio
              ? (previous?.portfolio?.account_id ?? null)
              : null,
            source: normalizedSource,
          }
        : null

      const entry: FundDetail = {
        id: previous?.id || previous?.originalId || "",
        name: form.name.trim(),
        isin: form.isin.trim().toUpperCase(),
        market: previous?.market || "",
        shares,
        average_buy_price: resolvedAverageBuy,
        market_value: resolvedMarketValue,
        initial_investment: resolvedInitialInvestment,
        type: (form.type as FundType) || FundType.MUTUAL_FUND,
        asset_type: (form.asset_type as AssetType) || null,
        currency: form.currency,
        portfolio,
        source: DataSource.MANUAL,
      }
      if (!entry.id) {
        delete (entry as any).id
      }
      return entry
    },
    validateForm: (form, { t }) => {
      const errors: ManualFormErrors<typeof form> = {}
      if (!form.name.trim()) errors.name = requiredField(t)
      if (!form.isin.trim()) errors.isin = requiredField(t)
      if (!form.currency) errors.currency = requiredField(t)
      if (!form.type) errors.type = requiredField(t)
      const shares = parseNumberInput(form.shares)
      if (shares === null || shares <= 0) errors.shares = numberFieldError(t)
      const avg = parseNumberInput(form.average_buy_price)
      const init = parseNumberInput(form.initial_investment)
      if (
        (avg === null || Number.isNaN(avg)) &&
        (init === null || Number.isNaN(init))
      ) {
        errors.average_buy_price = t(
          "management.manualPositions.funds.validation.investment",
        )
        errors.initial_investment = t(
          "management.manualPositions.funds.validation.investment",
        )
      }
      const market = form.market_value.trim()
      if (market && parseNumberInput(market) === null)
        errors.market_value = numberFieldError(t)
      return errors
    },
    renderFormFields: props => {
      const rawOptions = props.portfolioOptions?.(props.form.entity_id) ?? []
      const resolveSource = (source?: string) => {
        if (!source) return DataSource.MANUAL
        const values = Object.values(DataSource)
        return values.includes(source as DataSource)
          ? (source as DataSource)
          : DataSource.MANUAL
      }

      const selectedId = props.form.portfolio_id ?? ""
      const hasSelectedPortfolio = Boolean(selectedId)
      const preparedOptions = (() => {
        if (!hasSelectedPortfolio) {
          return rawOptions
        }
        const exists = rawOptions.some(option => option.value === selectedId)
        if (exists) return rawOptions
        return [
          ...rawOptions,
          {
            value: selectedId,
            label:
              props.form._portfolio_label ||
              props.t(
                "management.manualPositions.funds.helpers.unknownLinkedPortfolio",
              ),
            source: resolveSource(props.form._portfolio_source),
            name: props.form._portfolio_name || null,
            currency: props.form._portfolio_currency || null,
          },
        ]
      })()

      const shouldRenderSelect =
        preparedOptions.length > 0 || hasSelectedPortfolio

      return (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {renderEntityField(props)}
          <FundInstrumentSearchField
            field="name"
            label={props.t("management.manualPositions.shared.name")}
            formProps={props}
          />
          <FundInstrumentSearchField
            field="isin"
            label={props.t("management.manualPositions.funds.fields.isin")}
            formProps={props}
          />
          {renderSelectInput(
            "type",
            props.t("management.manualPositions.funds.fields.type"),
            props,
            Object.values(FundType).map(value => ({
              value,
              label: props.t(`enums.fundType.${value}`) || value,
            })),
          )}
          {renderSelectInput(
            "currency",
            props.t("management.manualPositions.shared.currency"),
            props,
            props.currencyOptions.map(value => ({ value, label: value })),
          )}
          {renderTextInput(
            "shares",
            props.t("management.manualPositions.funds.fields.shares"),
            props,
            {
              type: "number",
              step: "0.0001",
              inputMode: "decimal",
              onValueChange: (value, helpers) => {
                const suggestedPriceString =
                  helpers.form._suggested_market_price?.trim() ?? ""
                if (!suggestedPriceString) return

                const price = parseNumberInput(suggestedPriceString)
                const sharesValue = parseNumberInput(value)

                if (price === null || sharesValue === null || sharesValue <= 0)
                  return

                const total = price * sharesValue
                const formattedTotal = formatNumberInput(total)
                if (formattedTotal) {
                  helpers.updateField("market_value", formattedTotal)
                  helpers.clearError("market_value")
                }
              },
            },
          )}
          <div className="space-y-1.5">
            <Label>
              {props.t(
                "management.manualPositions.funds.fields.initialInvestment",
              )}
            </Label>
            <Input
              value={props.form.initial_investment}
              type="number"
              step="0.01"
              inputMode="decimal"
              onChange={event => {
                props.updateField("initial_investment", event.target.value)
                props.updateField("_last_investment_field", "initial" as any)
                props.clearError("initial_investment")
                props.clearError("average_buy_price")
              }}
            />
            {props.errors.initial_investment && (
              <p className="text-xs text-red-600 dark:text-red-400 mt-1">
                {props.errors.initial_investment}
              </p>
            )}
          </div>
          <div className="space-y-1.5">
            <Label>
              {props.t(
                "management.manualPositions.funds.fields.averageBuyPrice",
              )}
            </Label>
            <Input
              value={props.form.average_buy_price}
              type="number"
              step="0.01"
              inputMode="decimal"
              onChange={event => {
                props.updateField("average_buy_price", event.target.value)
                props.updateField("_last_investment_field", "average" as any)
                props.clearError("average_buy_price")
                props.clearError("initial_investment")
              }}
            />
            {props.errors.average_buy_price && (
              <p className="text-xs text-red-600 dark:text-red-400 mt-1">
                {props.errors.average_buy_price}
              </p>
            )}
            <p className="text-xs text-muted-foreground">
              {props.t(
                "management.manualPositions.funds.helpers.investmentExclusive",
              )}
            </p>
          </div>
          {renderTextInput(
            "market_value",
            props.t("management.manualPositions.funds.fields.marketValue"),
            props,
            {
              type: "number",
              step: "0.01",
              inputMode: "decimal",
              onValueChange: (_value, helpers) => {
                if (helpers.form._suggested_market_price) {
                  helpers.updateField("_suggested_market_price", "")
                }
              },
            },
          )}
          {renderSelectInput(
            "asset_type",
            props.t("management.manualPositions.funds.fields.assetType"),
            props,
            Object.values(AssetType).map(value => ({
              value,
              label: props.t(`enums.assetType.${value}`) || value,
            })),
          )}
          <div className="space-y-1.5">
            <Label htmlFor="portfolio_id">
              {props.t("management.manualPositions.funds.fields.portfolio")}
            </Label>
            {shouldRenderSelect ? (
              <select
                id="portfolio_id"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                value={selectedId}
                onChange={event => {
                  const value = event.target.value
                  props.updateField("portfolio_id", value)
                  if (!value) {
                    props.updateField("_portfolio_label", "")
                    props.updateField("_portfolio_source", "")
                    props.updateField("_portfolio_name", "")
                    props.updateField("_portfolio_currency", "")
                  } else {
                    const option = preparedOptions.find(
                      candidate => candidate.value === value,
                    )
                    props.updateField("_portfolio_label", option?.label ?? "")
                    props.updateField(
                      "_portfolio_source",
                      (option?.source ?? DataSource.MANUAL) as string,
                    )
                    props.updateField(
                      "_portfolio_name",
                      option?.name?.trim() ?? "",
                    )
                    props.updateField(
                      "_portfolio_currency",
                      option?.currency?.toUpperCase() ?? "",
                    )
                  }
                  props.clearError("portfolio_id")
                }}
              >
                <option value="">{props.t("common.selectOptions")}</option>
                {preparedOptions.map(option => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            ) : (
              <p className="text-xs text-muted-foreground">
                {props.t(
                  "management.manualPositions.funds.helpers.portfolioRecommendation",
                )}
              </p>
            )}
            {props.errors.portfolio_id && (
              <p className="text-xs text-red-600 dark:text-red-400 mt-1">
                {props.errors.portfolio_id}
              </p>
            )}
            {hasSelectedPortfolio && rawOptions.length === 0 && (
              <p className="text-xs text-muted-foreground">
                {props.t(
                  "management.manualPositions.funds.helpers.keepingLinkedPortfolio",
                )}
              </p>
            )}
          </div>
        </div>
      )
    },
    getDisplayName: draft => draft.name,
    renderDraftSummary: (draft, helpers) => (
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <span className="font-medium text-base">{draft.name}</span>
          {draft.asset_type && (
            <Badge variant="secondary">
              {helpers.t(`enums.assetType.${draft.asset_type}`) ||
                draft.asset_type}
            </Badge>
          )}
        </div>
        <div className="text-sm text-muted-foreground">
          {helpers.formatCurrency(draft.market_value, draft.currency)}
        </div>
        <div className="text-xs text-muted-foreground">
          {helpers.t("management.manualPositions.shared.summary.shares")}:{" "}
          {draft.shares}
        </div>
        {draft.portfolio?.id && (
          <div className="text-xs text-muted-foreground">
            {helpers.t("management.manualPositions.funds.summary.portfolio")}:{" "}
            {buildPortfolioLabel(draft.portfolio)}
          </div>
        )}
      </div>
    ),
    normalizeDraftForCompare: draft => ({
      entityId: draft.entityId,
      name: draft.name,
      isin: draft.isin,
      shares: draft.shares,
      average_buy_price: draft.average_buy_price ?? null,
      initial_investment: draft.initial_investment ?? null,
      market_value: draft.market_value ?? null,
      currency: draft.currency,
      type: draft.type,
      asset_type: draft.asset_type ?? null,
      portfolio_id: draft.portfolio?.id ?? null,
    }),
    toPayloadEntry: draft => ({
      id: draft.id || draft.originalId,
      name: draft.name,
      isin: draft.isin,
      shares: draft.shares,
      average_buy_price: draft.average_buy_price ?? null,
      initial_investment: draft.initial_investment ?? null,
      market_value: draft.market_value ?? null,
      currency: draft.currency,
      type: draft.type,
      asset_type: draft.asset_type ?? null,
      market: draft.market ?? "",
      portfolio: draft.portfolio
        ? {
            id: draft.portfolio.id,
            name: draft.portfolio.name ?? null,
            currency: draft.portfolio.currency ?? null,
            initial_investment: draft.portfolio.initial_investment ?? null,
            market_value: draft.portfolio.market_value ?? null,
            account_id: draft.portfolio.account_id ?? null,
            source: draft.portfolio.source ?? DataSource.MANUAL,
          }
        : null,
    }),
  },
  stocks: {
    assetKey: "stocks",
    productType: ProductType.STOCK_ETF,
    buildDraftsFromPositions: ({ positionsData, manualEntities }) => {
      if (!positionsData?.positions) return []
      const result: ManualPositionDraft<StockDetail>[] = []
      manualEntities.forEach(entity => {
        const entityPosition = positionsData.positions[entity.id]
        if (!entityPosition) return
        const product = entityPosition.products[ProductType.STOCK_ETF] as
          | { entries?: StockDetail[] }
          | undefined
        const entries = product?.entries ?? []
        entries.forEach(stock => {
          if (!isManualSource(stock)) return
          result.push({
            ...stock,
            localId:
              stock.id || `${entity.id}-stock-${stock.isin || stock.ticker}`,
            originalId: stock.id,
            entityId: entity.id,
            entityName: entity.name,
          })
        })
      })
      return result
    },
    createEmptyForm: ({ defaultCurrency }) => ({
      entity_id: "",
      entity_mode: "select" as const,
      new_entity_name: "",
      name: "",
      ticker: "",
      isin: "",
      shares: "",
      average_buy_price: "",
      initial_investment: "",
      market_value: "",
      currency: defaultCurrency,
      type: "",
      _last_investment_field: "",
      _suggested_market_price: "",
    }),
    draftToForm: draft => ({
      entity_id: draft.isNewEntity ? "" : draft.entityId,
      entity_mode: draft.isNewEntity ? "new" : "select",
      new_entity_name: draft.isNewEntity
        ? (draft.newEntityName ?? draft.entityName ?? "")
        : "",
      name: draft.name ?? "",
      ticker: draft.ticker ?? "",
      isin: draft.isin ?? "",
      shares: formatNumberInput(draft.shares ?? 0),
      average_buy_price:
        draft.average_buy_price != null
          ? formatNumberInput(draft.average_buy_price)
          : "",
      initial_investment:
        draft.initial_investment != null
          ? formatNumberInput(draft.initial_investment)
          : "",
      market_value:
        draft.market_value != null ? formatNumberInput(draft.market_value) : "",
      currency: draft.currency,
      type: draft.type ?? "",
      _last_investment_field: "average",
      _suggested_market_price: "",
    }),
    buildEntryFromForm: (form, { previous }) => {
      const shares = parseNumberInput(form.shares)
      if (shares === null || shares <= 0) return null
      let averageBuy = parseNumberInput(form.average_buy_price)
      let initialInvestment = parseNumberInput(form.initial_investment)
      const marketValueInput = parseNumberInput(form.market_value)
      const lastField = form._last_investment_field
      if (lastField === "initial" && initialInvestment != null) {
        averageBuy = initialInvestment / shares
      } else if (averageBuy != null) {
        initialInvestment = averageBuy * shares
      } else if (initialInvestment != null) {
        averageBuy = initialInvestment / shares
      }

      const resolvedInitialInvestment =
        initialInvestment ?? (averageBuy != null ? averageBuy * shares : 0)
      const resolvedAverageBuy =
        averageBuy ?? (shares > 0 ? resolvedInitialInvestment / shares : 0)
      const resolvedMarketValue = marketValueInput ?? resolvedInitialInvestment
      const entry: StockDetail = {
        id: previous?.id || previous?.originalId || "",
        name: form.name.trim(),
        ticker: form.ticker.trim().toUpperCase(),
        isin: form.isin.trim().toUpperCase(),
        market: previous?.market || "",
        shares,
        average_buy_price: resolvedAverageBuy,
        market_value: resolvedMarketValue,
        initial_investment: resolvedInitialInvestment,
        currency: form.currency,
        type: (form.type as EquityType) || EquityType.STOCK,
        subtype: previous?.subtype ?? null,
        source: DataSource.MANUAL,
      }
      if (!entry.id) {
        delete (entry as any).id
      }
      return entry
    },
    validateForm: (form, { t }) => {
      const errors: ManualFormErrors<typeof form> = {}
      if (!form.name.trim()) errors.name = requiredField(t)
      if (!form.currency) errors.currency = requiredField(t)
      if (!form.type) errors.type = requiredField(t)
      if (!form.ticker.trim() && !form.isin.trim()) {
        errors.ticker = t("management.manualPositions.stocks.validation.ticker")
        errors.isin = t("management.manualPositions.stocks.validation.isin")
      }
      const shares = parseNumberInput(form.shares)
      if (shares === null || shares <= 0) errors.shares = numberFieldError(t)
      const avg = parseNumberInput(form.average_buy_price)
      const init = parseNumberInput(form.initial_investment)
      if (
        (avg === null || Number.isNaN(avg)) &&
        (init === null || Number.isNaN(init))
      ) {
        errors.average_buy_price = t(
          "management.manualPositions.stocks.validation.investment",
        )
        errors.initial_investment = t(
          "management.manualPositions.stocks.validation.investment",
        )
      }
      const market = form.market_value.trim()
      if (market && parseNumberInput(market) === null)
        errors.market_value = numberFieldError(t)
      return errors
    },
    renderFormFields: props => (
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {renderEntityField(props)}
        <div className="space-y-1.5">
          <Label htmlFor="type">
            {props.t("management.manualPositions.stocks.fields.type")}
          </Label>
          <select
            id="type"
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            value={(props.form.type as string) ?? ""}
            onChange={event => {
              props.updateField("type", event.target.value)
              props.clearError("type")
            }}
          >
            <option value="">{props.t("common.selectOptions")}</option>
            {Object.values(EquityType).map(value => (
              <option key={value} value={value}>
                {props.t(`enums.equityType.${value}`) || value}
              </option>
            ))}
          </select>
          {props.errors.type && (
            <p className="text-xs text-red-600 dark:text-red-400 mt-1">
              {props.errors.type}
            </p>
          )}
        </div>
        <StockInstrumentSearchField
          field="name"
          label={props.t("management.manualPositions.shared.name")}
          formProps={props as ManualFormFieldRenderProps<StockFormState>}
        />
        <StockInstrumentSearchField
          field="ticker"
          label={props.t("management.manualPositions.stocks.fields.ticker")}
          formProps={props as ManualFormFieldRenderProps<StockFormState>}
        />
        <StockInstrumentSearchField
          field="isin"
          label={props.t("management.manualPositions.stocks.fields.isin")}
          formProps={props as ManualFormFieldRenderProps<StockFormState>}
        />
        {renderSelectInput(
          "currency",
          props.t("management.manualPositions.shared.currency"),
          props,
          props.currencyOptions.map(value => ({ value, label: value })),
        )}
        {renderTextInput(
          "shares",
          props.t("management.manualPositions.stocks.fields.shares"),
          props,
          {
            type: "number",
            step: "0.0001",
            inputMode: "decimal",
            onValueChange: (value, helpers) => {
              const suggestedPriceString =
                helpers.form._suggested_market_price?.trim() ?? ""
              if (!suggestedPriceString) return

              const price = parseNumberInput(suggestedPriceString)
              const sharesValue = parseNumberInput(value)

              if (price === null || sharesValue === null || sharesValue <= 0)
                return

              const total = price * sharesValue
              const formattedTotal = formatNumberInput(total)
              if (formattedTotal) {
                helpers.updateField("market_value", formattedTotal)
                helpers.clearError("market_value")
              }
            },
          },
        )}
        <div className="space-y-1.5">
          <Label>
            {props.t(
              "management.manualPositions.stocks.fields.initialInvestment",
            )}
          </Label>
          <Input
            value={props.form.initial_investment}
            type="number"
            step="0.01"
            inputMode="decimal"
            onChange={event => {
              props.updateField("initial_investment", event.target.value)
              props.updateField("_last_investment_field", "initial" as any)
              props.clearError("initial_investment")
              props.clearError("average_buy_price")
            }}
          />
          {props.errors.initial_investment && (
            <p className="text-xs text-red-600 dark:text-red-400 mt-1">
              {props.errors.initial_investment}
            </p>
          )}
        </div>
        <div className="space-y-1.5">
          <Label>
            {props.t(
              "management.manualPositions.stocks.fields.averageBuyPrice",
            )}
          </Label>
          <Input
            value={props.form.average_buy_price}
            type="number"
            step="0.01"
            inputMode="decimal"
            onChange={event => {
              props.updateField("average_buy_price", event.target.value)
              props.updateField("_last_investment_field", "average" as any)
              props.clearError("average_buy_price")
              props.clearError("initial_investment")
            }}
          />
          {props.errors.average_buy_price && (
            <p className="text-xs text-red-600 dark:text-red-400 mt-1">
              {props.errors.average_buy_price}
            </p>
          )}
          <p className="text-xs text-muted-foreground">
            {props.t(
              "management.manualPositions.stocks.helpers.investmentExclusive",
            )}
          </p>
        </div>
        {renderTextInput(
          "market_value",
          props.t("management.manualPositions.stocks.fields.marketValue"),
          props,
          {
            type: "number",
            step: "0.01",
            inputMode: "decimal",
            onValueChange: (_value, helpers) => {
              if (helpers.form._suggested_market_price) {
                helpers.updateField("_suggested_market_price", "")
              }
            },
          },
        )}
      </div>
    ),
    getDisplayName: draft => draft.name,
    renderDraftSummary: (draft, helpers) => (
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <span className="font-medium text-base">
            {draft.name} {draft.ticker ? `(${draft.ticker})` : ""}
          </span>
        </div>
        <div className="text-sm text-muted-foreground">
          {helpers.formatCurrency(draft.market_value, draft.currency)}
        </div>
        <div className="text-xs text-muted-foreground">
          {helpers.t("management.manualPositions.shared.summary.shares")}:{" "}
          {draft.shares}
        </div>
      </div>
    ),
    normalizeDraftForCompare: draft => ({
      entityId: draft.entityId,
      name: draft.name,
      ticker: draft.ticker ?? "",
      isin: draft.isin ?? "",
      shares: draft.shares,
      average_buy_price: draft.average_buy_price ?? null,
      initial_investment: draft.initial_investment ?? null,
      market_value: draft.market_value ?? null,
      currency: draft.currency,
      type: draft.type ?? EquityType.STOCK,
    }),
    toPayloadEntry: draft => ({
      id: draft.id || draft.originalId,
      name: draft.name,
      ticker: draft.ticker,
      isin: draft.isin,
      shares: draft.shares,
      average_buy_price: draft.average_buy_price ?? null,
      initial_investment: draft.initial_investment ?? null,
      market_value: draft.market_value ?? null,
      currency: draft.currency,
      type: (draft.type ?? EquityType.STOCK) as EquityType,
      market: draft.market ?? "",
      subtype: draft.subtype ?? null,
    }),
  },
  deposits: {
    assetKey: "deposits",
    productType: ProductType.DEPOSIT,
    buildDraftsFromPositions: ({ positionsData, manualEntities }) => {
      if (!positionsData?.positions) return []
      const result: ManualPositionDraft<Deposit>[] = []
      manualEntities.forEach(entity => {
        const entityPosition = positionsData.positions[entity.id]
        if (!entityPosition) return
        const product = entityPosition.products[ProductType.DEPOSIT] as
          | { entries?: Deposit[] }
          | undefined
        const entries = product?.entries ?? []
        entries.forEach(deposit => {
          if (!isManualSource(deposit)) return
          result.push({
            ...deposit,
            localId: deposit.id || `${entity.id}-deposit-${deposit.name}`,
            originalId: deposit.id,
            entityId: entity.id,
            entityName: entity.name,
          })
        })
      })
      return result
    },
    createEmptyForm: ({ defaultCurrency }) => ({
      entity_id: "",
      entity_mode: "select" as const,
      new_entity_name: "",
      name: "",
      amount: "",
      currency: defaultCurrency,
      interest_rate: "",
      creation: "",
      maturity: "",
    }),
    draftToForm: draft => ({
      entity_id: draft.isNewEntity ? "" : draft.entityId,
      entity_mode: draft.isNewEntity ? "new" : "select",
      new_entity_name: draft.isNewEntity
        ? (draft.newEntityName ?? draft.entityName ?? "")
        : "",
      name: draft.name ?? "",
      amount: formatNumberInput(draft.amount ?? 0),
      currency: draft.currency,
      interest_rate:
        draft.interest_rate != null
          ? formatNumberInput(draft.interest_rate * 100)
          : "",
      creation: normalizeDateInput(draft.creation ?? ""),
      maturity: normalizeDateInput(draft.maturity ?? ""),
    }),
    buildEntryFromForm: (form, { previous }) => {
      const amount = parseNumberInput(form.amount)
      const interestRatePercent = parseNumberInput(form.interest_rate)
      if (amount === null || interestRatePercent === null) return null
      const entry: Deposit = {
        id: previous?.id || previous?.originalId || "",
        name: form.name.trim(),
        amount,
        currency: form.currency,
        expected_interests: 0,
        interest_rate: interestRatePercent / 100,
        creation: form.creation || "",
        maturity: form.maturity || "",
        source: DataSource.MANUAL,
      }
      if (!entry.id) {
        delete (entry as any).id
      }
      return entry
    },
    validateForm: (form, { t }) => {
      const errors: ManualFormErrors<typeof form> = {}
      if (!form.name.trim()) errors.name = requiredField(t)
      if (!form.currency) errors.currency = requiredField(t)
      const amount = parseNumberInput(form.amount)
      if (amount === null || amount < 0) errors.amount = numberFieldError(t)
      const interest = parseNumberInput(form.interest_rate)
      if (interest === null) errors.interest_rate = numberFieldError(t)
      if (!form.creation) errors.creation = requiredField(t)
      if (!form.maturity) errors.maturity = requiredField(t)
      return errors
    },
    renderFormFields: props => (
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {renderEntityField(props)}
        {renderTextInput(
          "name",
          props.t("management.manualPositions.shared.name"),
          props,
        )}
        {renderSelectInput(
          "currency",
          props.t("management.manualPositions.shared.currency"),
          props,
          props.currencyOptions.map(value => ({ value, label: value })),
        )}
        {renderTextInput(
          "amount",
          props.t("management.manualPositions.deposits.fields.amount"),
          props,
          { type: "number", step: "0.01", inputMode: "decimal" },
        )}
        {renderTextInput(
          "interest_rate",
          props.t("management.manualPositions.deposits.fields.interestRate"),
          props,
          { type: "number", step: "0.01", inputMode: "decimal" },
        )}
        {renderDateInput(
          "creation",
          props.t("management.manualPositions.deposits.fields.creation"),
          props,
        )}
        {renderDateInput(
          "maturity",
          props.t("management.manualPositions.deposits.fields.maturity"),
          props,
        )}
      </div>
    ),
    getDisplayName: draft => draft.name,
    renderDraftSummary: (draft, helpers) => (
      <div className="flex flex-col gap-1">
        <span className="font-medium text-base">{draft.name}</span>
        <div className="text-sm text-muted-foreground">
          {helpers.formatCurrency(draft.amount, draft.currency)}
        </div>
        {draft.interest_rate != null && (
          <div className="text-xs text-muted-foreground">
            {(draft.interest_rate * 100).toFixed(2)}%
          </div>
        )}
      </div>
    ),
    normalizeDraftForCompare: draft => ({
      entityId: draft.entityId,
      name: draft.name,
      amount: draft.amount,
      currency: draft.currency,
      interest_rate: draft.interest_rate,
      creation: normalizeDateInput(draft.creation ?? ""),
      maturity: normalizeDateInput(draft.maturity ?? ""),
    }),
    toPayloadEntry: draft => ({
      id: draft.id || draft.originalId,
      name: draft.name,
      amount: draft.amount,
      currency: draft.currency,
      expected_interests: 0,
      interest_rate: draft.interest_rate,
      creation: draft.creation,
      maturity: draft.maturity,
    }),
  },
  factoring: {
    assetKey: "factoring",
    productType: ProductType.FACTORING,
    buildDraftsFromPositions: ({ positionsData, manualEntities }) => {
      if (!positionsData?.positions) return []
      const result: ManualPositionDraft<FactoringDetail>[] = []
      manualEntities.forEach(entity => {
        const entityPosition = positionsData.positions[entity.id]
        if (!entityPosition) return
        const product = entityPosition.products[ProductType.FACTORING] as
          | { entries?: FactoringDetail[] }
          | undefined
        const entries = product?.entries ?? []
        entries.forEach(factor => {
          if (!isManualSource(factor)) return
          result.push({
            ...factor,
            localId: factor.id || `${entity.id}-factoring-${factor.name}`,
            originalId: factor.id,
            entityId: entity.id,
            entityName: entity.name,
          })
        })
      })
      return result
    },
    createEmptyForm: ({ defaultCurrency }) => ({
      entity_id: "",
      entity_mode: "select" as const,
      new_entity_name: "",
      name: "",
      amount: "",
      currency: defaultCurrency,
      interest_rate: "",
      last_invest_date: "",
      maturity: "",
      type: "",
      state: "",
    }),
    draftToForm: draft => ({
      entity_id: draft.isNewEntity ? "" : draft.entityId,
      entity_mode: draft.isNewEntity ? "new" : "select",
      new_entity_name: draft.isNewEntity
        ? (draft.newEntityName ?? draft.entityName ?? "")
        : "",
      name: draft.name ?? "",
      amount: formatNumberInput(draft.amount ?? 0),
      currency: draft.currency,
      interest_rate:
        draft.interest_rate != null
          ? formatNumberInput(draft.interest_rate * 100)
          : "",
      last_invest_date: normalizeDateInput(draft.last_invest_date ?? ""),
      maturity: normalizeDateInput(draft.maturity ?? ""),
      type: draft.type ?? "",
      state: draft.state ?? "",
    }),
    buildEntryFromForm: (form, { previous }) => {
      const amount = parseNumberInput(form.amount)
      const interestRatePercent = parseNumberInput(form.interest_rate)
      if (amount === null || interestRatePercent === null) return null
      const entry: FactoringDetail = {
        id: previous?.id || previous?.originalId || "",
        name: form.name.trim(),
        amount,
        currency: form.currency,
        interest_rate: interestRatePercent / 100,
        profitability: 0,
        gross_interest_rate: interestRatePercent / 100,
        last_invest_date: form.last_invest_date || "",
        maturity: form.maturity || "",
        type: form.type || "",
        state: form.state || "",
        source: DataSource.MANUAL,
      }
      if (!entry.id) {
        delete (entry as any).id
      }
      return entry
    },
    validateForm: (form, { t }) => {
      const errors: ManualFormErrors<typeof form> = {}
      if (!form.name.trim()) errors.name = requiredField(t)
      if (!form.currency) errors.currency = requiredField(t)
      if (!form.type.trim()) errors.type = requiredField(t)
      if (!form.state.trim()) errors.state = requiredField(t)
      const amount = parseNumberInput(form.amount)
      if (amount === null || amount < 0) errors.amount = numberFieldError(t)
      const interest = parseNumberInput(form.interest_rate)
      if (interest === null) errors.interest_rate = numberFieldError(t)
      if (!form.last_invest_date) errors.last_invest_date = requiredField(t)
      if (!form.maturity) errors.maturity = requiredField(t)
      return errors
    },
    renderFormFields: props => (
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {renderEntityField(props)}
        {renderTextInput(
          "name",
          props.t("management.manualPositions.shared.name"),
          props,
        )}
        {renderSelectInput(
          "currency",
          props.t("management.manualPositions.shared.currency"),
          props,
          props.currencyOptions.map(value => ({ value, label: value })),
        )}
        {renderTextInput(
          "amount",
          props.t("management.manualPositions.factoring.fields.amount"),
          props,
          { type: "number", step: "0.01", inputMode: "decimal" },
        )}
        {renderTextInput(
          "interest_rate",
          props.t("management.manualPositions.factoring.fields.interestRate"),
          props,
          { type: "number", step: "0.01", inputMode: "decimal" },
        )}
        {renderDateInput(
          "last_invest_date",
          props.t("management.manualPositions.factoring.fields.lastInvestDate"),
          props,
        )}
        {renderDateInput(
          "maturity",
          props.t("management.manualPositions.factoring.fields.maturity"),
          props,
        )}
        {renderTextInput(
          "type",
          props.t("management.manualPositions.factoring.fields.type"),
          props,
        )}
        {renderTextInput(
          "state",
          props.t("management.manualPositions.factoring.fields.state"),
          props,
        )}
      </div>
    ),
    getDisplayName: draft => draft.name,
    renderDraftSummary: (draft, helpers) => (
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <span className="font-medium text-base">{draft.name}</span>
          <Badge variant="secondary">{draft.state}</Badge>
        </div>
        <div className="text-sm text-muted-foreground">
          {helpers.formatCurrency(draft.amount, draft.currency)}
        </div>
        {draft.interest_rate != null && (
          <div className="text-xs text-muted-foreground">
            {(draft.interest_rate * 100).toFixed(2)}%
          </div>
        )}
      </div>
    ),
    normalizeDraftForCompare: draft => ({
      entityId: draft.entityId,
      name: draft.name,
      amount: draft.amount,
      currency: draft.currency,
      interest_rate: draft.interest_rate,
      last_invest_date: normalizeDateInput(draft.last_invest_date ?? ""),
      maturity: normalizeDateInput(draft.maturity ?? ""),
      type: draft.type,
      state: draft.state,
    }),
    toPayloadEntry: draft => ({
      id: draft.id || draft.originalId,
      name: draft.name,
      amount: draft.amount,
      currency: draft.currency,
      interest_rate: draft.interest_rate,
      profitability: 0,
      gross_interest_rate: draft.interest_rate,
      last_invest_date: draft.last_invest_date,
      maturity: draft.maturity,
      type: draft.type,
      state: draft.state,
    }),
  },
  realEstateCf: {
    assetKey: "realEstateCf",
    productType: ProductType.REAL_ESTATE_CF,
    buildDraftsFromPositions: ({ positionsData, manualEntities }) => {
      if (!positionsData?.positions) return []
      const result: ManualPositionDraft<RealEstateCFDetail>[] = []
      manualEntities.forEach(entity => {
        const entityPosition = positionsData.positions[entity.id]
        if (!entityPosition) return
        const product = entityPosition.products[ProductType.REAL_ESTATE_CF] as
          | { entries?: RealEstateCFDetail[] }
          | undefined
        const entries = product?.entries ?? []
        entries.forEach(realEstate => {
          if (!isManualSource(realEstate)) return
          result.push({
            ...realEstate,
            localId:
              realEstate.id || `${entity.id}-realestate-${realEstate.name}`,
            originalId: realEstate.id,
            entityId: entity.id,
            entityName: entity.name,
          })
        })
      })
      return result
    },
    createEmptyForm: ({ defaultCurrency }) => ({
      entity_id: "",
      entity_mode: "select" as const,
      new_entity_name: "",
      name: "",
      amount: "",
      pending_amount: "",
      currency: defaultCurrency,
      interest_rate: "",
      last_invest_date: "",
      maturity: "",
      type: "",
      business_type: "",
      state: "",
      extended_maturity: "",
    }),
    draftToForm: draft => ({
      entity_id: draft.isNewEntity ? "" : draft.entityId,
      entity_mode: draft.isNewEntity ? "new" : "select",
      new_entity_name: draft.isNewEntity
        ? (draft.newEntityName ?? draft.entityName ?? "")
        : "",
      name: draft.name ?? "",
      amount: formatNumberInput(draft.amount ?? 0),
      pending_amount:
        draft.pending_amount != null
          ? formatNumberInput(draft.pending_amount)
          : "",
      currency: draft.currency,
      interest_rate:
        draft.interest_rate != null
          ? formatNumberInput(draft.interest_rate * 100)
          : "",
      last_invest_date: normalizeDateInput(draft.last_invest_date ?? ""),
      maturity: normalizeDateInput(draft.maturity ?? ""),
      type: draft.type ?? "",
      business_type: draft.business_type ?? "",
      state: draft.state ?? "",
      extended_maturity: normalizeDateInput(draft.extended_maturity ?? ""),
    }),
    buildEntryFromForm: (form, { previous }) => {
      const amount = parseNumberInput(form.amount)
      if (amount === null) return null
      const pending = parseNumberInput(form.pending_amount)
      const interestPercent = parseNumberInput(form.interest_rate)
      if (interestPercent === null) return null
      const resolvedPending = pending ?? amount
      const entry: RealEstateCFDetail = {
        id: previous?.id || previous?.originalId || "",
        name: form.name.trim(),
        amount,
        pending_amount: resolvedPending,
        currency: form.currency,
        interest_rate: interestPercent / 100,
        profitability: 0,
        last_invest_date: form.last_invest_date || null,
        maturity: form.maturity || null,
        type: form.type.trim(),
        business_type: form.business_type.trim(),
        state: form.state.trim(),
        extended_maturity: form.extended_maturity || null,
        source: DataSource.MANUAL,
      }
      if (!entry.id) {
        delete (entry as any).id
      }
      return entry
    },
    validateForm: (form, { t }) => {
      const errors: ManualFormErrors<typeof form> = {}
      if (!form.name.trim()) errors.name = requiredField(t)
      if (!form.currency) errors.currency = requiredField(t)
      if (!form.type.trim()) errors.type = requiredField(t)
      if (!form.business_type.trim()) errors.business_type = requiredField(t)
      if (!form.state.trim()) errors.state = requiredField(t)
      const amount = parseNumberInput(form.amount)
      if (amount === null || amount < 0) errors.amount = numberFieldError(t)
      const pending = form.pending_amount.trim()
      if (pending && parseNumberInput(pending) === null)
        errors.pending_amount = numberFieldError(t)
      const interest = parseNumberInput(form.interest_rate)
      if (interest === null) errors.interest_rate = numberFieldError(t)
      if (!form.last_invest_date) errors.last_invest_date = requiredField(t)
      if (!form.maturity) errors.maturity = requiredField(t)
      return errors
    },
    renderFormFields: props => (
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {renderEntityField(props)}
        {renderTextInput(
          "name",
          props.t("management.manualPositions.shared.name"),
          props,
        )}
        {renderSelectInput(
          "currency",
          props.t("management.manualPositions.shared.currency"),
          props,
          props.currencyOptions.map(value => ({ value, label: value })),
        )}
        {renderTextInput(
          "amount",
          props.t("management.manualPositions.realEstateCf.fields.amount"),
          props,
          {
            type: "number",
            step: "0.01",
            inputMode: "decimal",
            onValueChange: (value, helpers) => {
              const previousPending = helpers.form.pending_amount ?? ""
              const previousAmount = helpers.form.amount ?? ""
              if (
                previousPending === "" ||
                previousPending === previousAmount
              ) {
                helpers.updateField("pending_amount", value)
                helpers.clearError("pending_amount")
              }
            },
          },
        )}
        {renderTextInput(
          "pending_amount",
          props.t(
            "management.manualPositions.realEstateCf.fields.pendingAmount",
          ),
          props,
          { type: "number", step: "0.01", inputMode: "decimal" },
        )}
        {renderTextInput(
          "interest_rate",
          props.t(
            "management.manualPositions.realEstateCf.fields.interestRate",
          ),
          props,
          { type: "number", step: "0.01", inputMode: "decimal" },
        )}
        {renderDateInput(
          "last_invest_date",
          props.t(
            "management.manualPositions.realEstateCf.fields.lastInvestDate",
          ),
          props,
        )}
        {renderDateInput(
          "maturity",
          props.t("management.manualPositions.realEstateCf.fields.maturity"),
          props,
        )}
        {renderTextInput(
          "type",
          props.t("management.manualPositions.realEstateCf.fields.type"),
          props,
        )}
        {renderTextInput(
          "business_type",
          props.t(
            "management.manualPositions.realEstateCf.fields.businessType",
          ),
          props,
        )}
        {renderTextInput(
          "state",
          props.t("management.manualPositions.realEstateCf.fields.state"),
          props,
        )}
        {renderDateInput(
          "extended_maturity",
          props.t(
            "management.manualPositions.realEstateCf.fields.extendedMaturity",
          ),
          props,
        )}
      </div>
    ),
    getDisplayName: draft => draft.name,
    renderDraftSummary: (draft, helpers) => (
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <span className="font-medium text-base">{draft.name}</span>
          <Badge variant="secondary">{draft.state}</Badge>
        </div>
        <div className="text-sm text-muted-foreground">
          {helpers.formatCurrency(draft.amount, draft.currency)}
        </div>
        {draft.pending_amount != null && (
          <div className="text-xs text-muted-foreground">
            {helpers.formatCurrency(draft.pending_amount, draft.currency)}
          </div>
        )}
      </div>
    ),
    normalizeDraftForCompare: draft => ({
      entityId: draft.entityId,
      name: draft.name,
      amount: draft.amount,
      pending_amount: draft.pending_amount ?? null,
      currency: draft.currency,
      interest_rate: draft.interest_rate,
      last_invest_date: draft.last_invest_date,
      maturity: draft.maturity,
      type: draft.type,
      business_type: draft.business_type,
      state: draft.state,
      extended_maturity: draft.extended_maturity ?? null,
    }),
    toPayloadEntry: draft => ({
      id: draft.id || draft.originalId,
      name: draft.name,
      amount: draft.amount,
      pending_amount: draft.pending_amount ?? 0,
      currency: draft.currency,
      interest_rate: draft.interest_rate,
      profitability: 0,
      last_invest_date: draft.last_invest_date,
      maturity: draft.maturity,
      type: draft.type,
      business_type: draft.business_type,
      state: draft.state,
      extended_maturity: draft.extended_maturity ?? null,
    }),
  },
}

export { manualPositionConfigs }
