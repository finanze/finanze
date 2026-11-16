import { useEffect, useMemo, useState } from "react"
import {
  ArrowRight,
  Check,
  ChevronDown,
  HelpCircle,
  Keyboard,
  ListFilter,
  UserRoundPen,
  Wallet,
  X,
} from "lucide-react"
import { useAppContext } from "@/context/AppContext"
import { useFinancialData } from "@/context/FinancialDataContext"
import { useI18n } from "@/i18n"
import { formatCurrency, formatIban } from "@/lib/formatters"
import { cn } from "@/lib/utils"
import { DataSource } from "@/types"
import { ProductType, type Account, type AccountType } from "@/types/position"
import { getAccountTypeColor, getAccountTypeIcon } from "@/utils/dashboardUtils"
import { tryConvertCurrency } from "@/utils/financialDataUtils"
import { Input } from "@/components/ui/Input"
import { Label } from "@/components/ui/Label"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover"
import { Sensitive } from "@/components/ui/Sensitive"
import { Switch } from "@/components/ui/Switch"

export interface AccountOption {
  id: string
  entityId: string
  entityName: string
  name: string | null
  displayName: string
  type: AccountType
  typeLabel: string
  iban: string | null
  formattedIban: string | null
  shortIban: string | null
  total: number
  formattedTotal: string
  currency: string
  source: DataSource
  isManual: boolean
}

export interface AccountBalancePreview {
  currentFormatted: string
  nextFormatted: string
  isPositive: boolean
}

export function useEntityAccounts({
  entityId,
  manualOnly = false,
}: {
  entityId?: string
  manualOnly?: boolean
} = {}): AccountOption[] {
  const { t, locale } = useI18n()
  const { positionsData } = useFinancialData()
  const { settings } = useAppContext()
  const defaultCurrency = settings.general.defaultCurrency
  const scopedToEntity = entityId !== undefined

  return useMemo<AccountOption[]>(() => {
    if (!positionsData?.positions) return []
    if (scopedToEntity && !entityId) return []

    const groups = scopedToEntity
      ? [positionsData.positions[entityId] ?? []]
      : Object.values(positionsData.positions)

    const list: AccountOption[] = []
    groups.forEach(globalPositions => {
      globalPositions.forEach(gp => {
        const product = gp.products[ProductType.ACCOUNT] as
          { entries?: Account[] } | undefined
        product?.entries?.forEach(account => {
          if (!account.id) return
          const isManual = account.source === DataSource.MANUAL
          if (manualOnly && !isManual) return

          const normalizedIban =
            account.iban?.replace(/\s+/g, "").toUpperCase() || null
          if (!isManual && !normalizedIban) return

          const typeLabel = t.enums.accountType[account.type]
          const trimmedName = account.name?.trim() || null
          const total = Number(account.total) || 0
          const currency = (account.currency || defaultCurrency).toUpperCase()

          list.push({
            id: account.id,
            entityId: gp.entity.id,
            entityName: gp.entity.name,
            name: trimmedName,
            displayName: trimmedName || typeLabel,
            type: account.type,
            typeLabel,
            iban: normalizedIban,
            formattedIban: normalizedIban
              ? formatIban(normalizedIban, true)
              : null,
            shortIban: normalizedIban ? `···${normalizedIban.slice(-4)}` : null,
            total,
            formattedTotal: formatCurrency(
              total,
              locale,
              defaultCurrency,
              currency,
            ),
            currency,
            source: account.source,
            isManual,
          })
        })
      })
    })

    if (!manualOnly) {
      list.sort((a, b) => Number(b.isManual) - Number(a.isManual))
    }

    return list
  }, [
    defaultCurrency,
    entityId,
    locale,
    manualOnly,
    positionsData,
    scopedToEntity,
    t,
  ])
}

export function useAccountBalancePreview(
  account: AccountOption | null,
  delta: number | null,
  currency: string,
  enabled: boolean,
): AccountBalancePreview | null {
  const { locale } = useI18n()
  const { exchangeRates, settings } = useAppContext()
  const defaultCurrency = settings.general.defaultCurrency

  return useMemo(() => {
    if (
      !enabled ||
      !account ||
      delta === null ||
      !Number.isFinite(delta) ||
      delta === 0
    ) {
      return null
    }

    const fromCode = (currency || defaultCurrency).toUpperCase()
    const targetCode = account.currency.toUpperCase()
    const convertedDelta =
      fromCode === targetCode
        ? delta
        : tryConvertCurrency(delta, fromCode, targetCode, exchangeRates)

    if (convertedDelta === null || !Number.isFinite(convertedDelta)) {
      return null
    }

    const currentTotal = account.total
    const nextTotal = currentTotal + convertedDelta

    return {
      currentFormatted: formatCurrency(
        currentTotal,
        locale,
        defaultCurrency,
        targetCode,
      ),
      nextFormatted: formatCurrency(
        nextTotal,
        locale,
        defaultCurrency,
        targetCode,
      ),
      isPositive: convertedDelta >= 0,
    }
  }, [
    account,
    currency,
    defaultCurrency,
    delta,
    enabled,
    exchangeRates,
    locale,
  ])
}

interface AccountSelectDropdownProps {
  id?: string
  testId?: string
  options: AccountOption[]
  value: string
  onChange: (accountId: string) => void
  placeholder: string
  showEntity?: boolean
  showSourceBadge?: boolean
  disableNonManual?: boolean
  allowClear?: boolean
  borderless?: boolean
  error?: boolean
  disabled?: boolean
  open?: boolean
  onOpenChange?: (open: boolean) => void
}

export function AccountSelectDropdown({
  id,
  testId = "manual-account-balance-select",
  options,
  value,
  onChange,
  placeholder,
  showEntity = false,
  showSourceBadge = false,
  disableNonManual = false,
  allowClear = false,
  borderless = false,
  error = false,
  disabled = false,
  open: controlledOpen,
  onOpenChange,
}: AccountSelectDropdownProps) {
  const { t } = useI18n()
  const [uncontrolledOpen, setUncontrolledOpen] = useState(false)
  const isOpen = controlledOpen ?? uncontrolledOpen
  const setIsOpen = (next: boolean) => {
    if (disabled) return
    setUncontrolledOpen(next)
    onOpenChange?.(next)
  }

  const selected = useMemo(
    () => options.find(option => option.id === value) ?? null,
    [options, value],
  )

  return (
    <Popover open={isOpen && !disabled} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <span
          id={id}
          data-testid={testId}
          role="combobox"
          tabIndex={disabled ? -1 : 0}
          aria-haspopup="listbox"
          aria-expanded={isOpen}
          aria-disabled={disabled}
          aria-label={placeholder}
          onKeyDown={event => {
            if (disabled) return
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault()
              setIsOpen(!isOpen)
            } else if (event.key === "Escape") {
              setIsOpen(false)
            }
          }}
          className={cn(
            "flex min-h-10 w-full items-center justify-between gap-2 bg-background px-3 py-2 text-sm text-foreground cursor-pointer select-none transition-colors",
            !borderless &&
              "rounded-md border border-input shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            borderless &&
              "focus-visible:outline-none focus-visible:bg-accent/30",
            error && !borderless && "border-red-500 focus-visible:ring-red-500",
            disabled && "cursor-not-allowed opacity-50 pointer-events-none",
          )}
        >
          {selected ? (
            <span className="flex min-w-0 flex-1 items-center gap-2.5">
              <span
                className={cn(
                  "flex h-6 w-6 shrink-0 items-center justify-center rounded-md [&_svg]:h-3.5 [&_svg]:w-3.5",
                  getAccountTypeColor(selected.type),
                )}
              >
                {getAccountTypeIcon(selected.type)}
              </span>
              <span className="truncate font-medium text-foreground">
                {selected.displayName}
              </span>
              {showEntity && (
                <span className="truncate text-xs text-muted-foreground">
                  · {selected.entityName}
                </span>
              )}
              {showSourceBadge && selected.isManual && (
                <span
                  title={t.manualAccountBalance.manualBadge}
                  className="inline-flex shrink-0 items-center text-muted-foreground"
                >
                  <UserRoundPen className="h-3 w-3" />
                </span>
              )}
              {selected.formattedIban && (
                <>
                  <span className="hidden truncate font-mono text-xs text-muted-foreground sm:inline">
                    {showEntity ? selected.shortIban : selected.formattedIban}
                  </span>
                  <span className=" shrink-0 font-mono text-xs text-muted-foreground sm:hidden">
                    {selected.shortIban}
                  </span>
                </>
              )}
            </span>
          ) : (
            <span className="flex min-w-0 flex-1 items-center gap-2 text-muted-foreground">
              <Wallet className="h-4 w-4 shrink-0" />
              <span className="truncate">{placeholder}</span>
            </span>
          )}

          <span className="ml-auto flex shrink-0 items-center gap-1.5">
            {selected && (
              <Sensitive className="text-xs font-medium tabular-nums text-muted-foreground">
                {selected.formattedTotal}
              </Sensitive>
            )}
            {selected && allowClear && !disabled && (
              <button
                type="button"
                aria-label={t.manualAccountBalance.clearAccount}
                title={t.manualAccountBalance.clearAccount}
                onClick={event => {
                  event.stopPropagation()
                  onChange("")
                  setIsOpen(false)
                }}
                className="inline-flex h-5 w-5 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
            <ChevronDown
              className={cn(
                "h-4 w-4 shrink-0 text-muted-foreground transition-transform",
                isOpen && "rotate-180",
              )}
            />
          </span>
        </span>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        className="w-[var(--radix-popover-trigger-width)] max-h-64 overflow-y-auto p-1"
      >
        <div role="listbox" className="space-y-0.5">
          {options.map(option => {
            const isSelected = option.id === value
            const optionDisabled = disableNonManual && !option.isManual
            const secondaryParts: string[] = []
            if (showEntity) secondaryParts.push(option.entityName)
            else if (option.name) secondaryParts.push(option.typeLabel)
            if (option.formattedIban) {
              secondaryParts.push(
                showEntity
                  ? (option.shortIban ?? option.formattedIban)
                  : option.formattedIban,
              )
            }

            return (
              <button
                key={option.id}
                type="button"
                role="option"
                aria-selected={isSelected}
                disabled={optionDisabled}
                onClick={() => {
                  if (optionDisabled) return
                  onChange(option.id)
                  setIsOpen(false)
                }}
                className={cn(
                  "flex w-full items-center justify-between gap-2.5 rounded-md px-2.5 py-2 text-left text-sm transition-colors",
                  optionDisabled
                    ? "cursor-not-allowed opacity-45"
                    : "cursor-pointer hover:bg-accent hover:text-accent-foreground",
                  isSelected && "bg-accent/70 text-accent-foreground",
                )}
              >
                <span className="flex min-w-0 flex-1 items-center gap-2.5">
                  <span
                    className={cn(
                      "flex h-7 w-7 shrink-0 items-center justify-center rounded-lg [&_svg]:h-3.5 [&_svg]:w-3.5",
                      getAccountTypeColor(option.type),
                    )}
                  >
                    {getAccountTypeIcon(option.type)}
                  </span>
                  <span className="flex min-w-0 flex-col">
                    <span className="flex items-center gap-1.5">
                      <span className="truncate font-medium text-foreground">
                        {option.displayName}
                      </span>
                      {showSourceBadge && option.isManual && (
                        <span
                          title={t.manualAccountBalance.manualBadge}
                          className="inline-flex shrink-0 items-center text-muted-foreground"
                        >
                          <UserRoundPen className="h-3 w-3" />
                        </span>
                      )}
                      {showSourceBadge &&
                        !option.isManual &&
                        disableNonManual && (
                          <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
                            {t.manualAccountBalance.syncedBadge}
                          </span>
                        )}
                    </span>
                    {secondaryParts.length > 0 && (
                      <span className="truncate font-mono text-xs text-muted-foreground">
                        {secondaryParts.join(" · ")}
                      </span>
                    )}
                  </span>
                </span>
                <span className="flex shrink-0 items-center gap-2">
                  <Sensitive className="text-xs font-medium tabular-nums text-muted-foreground">
                    {option.formattedTotal}
                  </Sensitive>
                  {isSelected && (
                    <Check className="h-4 w-4 shrink-0 text-foreground" />
                  )}
                </span>
              </button>
            )
          })}
        </div>
      </PopoverContent>
    </Popover>
  )
}

function BalancePreviewValue({
  preview,
  testId = "manual-account-balance-preview",
  className,
}: {
  preview: AccountBalancePreview
  testId?: string
  className?: string
}) {
  return (
    <span
      data-testid={testId}
      className={cn(
        "inline-flex items-center gap-1.5 font-medium tabular-nums",
        className,
      )}
    >
      <Sensitive className="text-muted-foreground">
        {preview.currentFormatted}
      </Sensitive>
      <ArrowRight className="h-3 w-3 shrink-0 text-muted-foreground" />
      <Sensitive
        className={
          preview.isPositive
            ? "text-emerald-600 dark:text-emerald-400"
            : "text-rose-600 dark:text-rose-400"
        }
      >
        {preview.nextFormatted}
      </Sensitive>
    </span>
  )
}

export interface ManualAccountBalanceToggleProps {
  id?: string
  entityId?: string
  delta: number | null
  currency: string
  hint: string
  enabled: boolean
  onEnabledChange: (enabled: boolean) => void
  accountId: string
  onAccountIdChange: (accountId: string) => void
  error?: boolean
  errorMessage?: string
  disabled?: boolean
  className?: string
}

export function ManualAccountBalanceToggle({
  id = "manual-account-balance-switch",
  entityId,
  delta,
  currency,
  hint,
  enabled,
  onEnabledChange,
  accountId,
  onAccountIdChange,
  error = false,
  errorMessage,
  disabled = false,
  className,
}: ManualAccountBalanceToggleProps) {
  const { t } = useI18n()
  const scopedToEntity = entityId !== undefined
  const options = useEntityAccounts({ entityId, manualOnly: true })

  useEffect(() => {
    if (options.length === 0) {
      if (enabled) onEnabledChange(false)
      if (accountId) onAccountIdChange("")
      return
    }
    if (accountId && !options.some(option => option.id === accountId)) {
      onAccountIdChange(enabled && options.length === 1 ? options[0].id : "")
    } else if (enabled && !accountId && options.length === 1) {
      onAccountIdChange(options[0].id)
    }
  }, [accountId, enabled, onAccountIdChange, onEnabledChange, options])

  const selectedAccount = useMemo(
    () => options.find(option => option.id === accountId) ?? null,
    [accountId, options],
  )

  const preview = useAccountBalancePreview(
    selectedAccount,
    delta,
    currency,
    enabled,
  )

  const handleCheckedChange = (checked: boolean) => {
    onEnabledChange(checked)
    if (checked && !accountId && options.length === 1) {
      onAccountIdChange(options[0].id)
    }
  }

  const noAccountsMessage = scopedToEntity
    ? t.manualAccountBalance.noManualAccountsForEntity
    : t.manualAccountBalance.noManualAccounts

  return (
    <span className={cn("block", className)}>
      <span className="flex items-center justify-between gap-3">
        <span className="flex flex-col">
          <span className="text-sm font-medium text-foreground">
            {t.manualAccountBalance.apply}
          </span>
          <span className="text-xs text-muted-foreground">{hint}</span>
        </span>
        <span className="flex items-center gap-2">
          <Switch
            id={id}
            data-testid="manual-account-balance-switch"
            aria-label={t.manualAccountBalance.apply}
            checked={enabled}
            onCheckedChange={handleCheckedChange}
            disabled={disabled || options.length === 0}
          />
          {options.length === 0 && (
            <Popover>
              <PopoverTrigger asChild>
                <button
                  type="button"
                  data-testid="manual-account-balance-help"
                  aria-label={noAccountsMessage}
                  className="inline-flex h-5 w-5 items-center justify-center rounded-full border text-xs text-muted-foreground hover:text-foreground"
                >
                  <HelpCircle size={14} />
                </button>
              </PopoverTrigger>
              <PopoverContent className="w-64 text-sm">
                {noAccountsMessage}
              </PopoverContent>
            </Popover>
          )}
        </span>
      </span>

      {enabled && (
        <span className="mt-3 block space-y-2">
          <AccountSelectDropdown
            options={options}
            value={accountId}
            onChange={onAccountIdChange}
            placeholder={t.manualAccountBalance.selectAccount}
            showEntity={!scopedToEntity}
            error={error}
            disabled={disabled}
          />

          {error && errorMessage && (
            <span className="block text-xs text-red-600 dark:text-red-400">
              {errorMessage}
            </span>
          )}

          {preview && (
            <span className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border/60 bg-muted/40 px-3 py-1.5 text-xs">
              <span className="text-muted-foreground">
                {t.manualAccountBalance.previewLabel}
              </span>
              <BalancePreviewValue preview={preview} />
            </span>
          )}
        </span>
      )}
    </span>
  )
}

export interface ManualTransactionAccountFieldProps {
  mode: "create" | "edit"
  accounts: AccountOption[]
  selectedEntityName?: string
  iban: string
  onIbanChange: (value: string) => void
  ibanError?: string
  selectedAccountId: string
  onSelectedAccountIdChange: (accountId: string) => void
  customIbanMode: boolean
  onCustomIbanModeChange: (custom: boolean) => void
  applyToBalance: boolean
  onApplyToBalanceChange: (enabled: boolean) => void
  balanceAccountError?: boolean
  onClearBalanceError?: () => void
  delta: number | null
  currency: string
  disabled?: boolean
}

export function resolveTransactionManualAccount(
  accounts: AccountOption[],
  selectedAccountId: string,
  customIbanMode: boolean,
  iban: string,
): AccountOption | null {
  if (!customIbanMode && accounts.length > 0) {
    const selected = accounts.find(option => option.id === selectedAccountId)
    return selected?.isManual ? selected : null
  }
  const normalized = iban.replace(/\s+/g, "").toUpperCase()
  if (!normalized) return null
  return (
    accounts.find(option => option.isManual && option.iban === normalized) ??
    null
  )
}

export function ManualTransactionAccountField({
  mode,
  accounts,
  selectedEntityName,
  iban,
  onIbanChange,
  ibanError,
  selectedAccountId,
  onSelectedAccountIdChange,
  customIbanMode,
  onCustomIbanModeChange,
  applyToBalance,
  onApplyToBalanceChange,
  balanceAccountError = false,
  onClearBalanceError,
  delta,
  currency,
  disabled = false,
}: ManualTransactionAccountFieldProps) {
  const { t } = useI18n()
  const [dropdownOpen, setDropdownOpen] = useState(false)

  const hasSavedAccounts = accounts.length > 0
  const showIbanInput = !hasSavedAccounts || customIbanMode
  const manualAccounts = useMemo(
    () => accounts.filter(option => option.isManual),
    [accounts],
  )

  const selectedAccount = useMemo(
    () =>
      !showIbanInput
        ? (accounts.find(option => option.id === selectedAccountId) ?? null)
        : null,
    [accounts, selectedAccountId, showIbanInput],
  )

  const resolvedManualAccount = useMemo(
    () =>
      resolveTransactionManualAccount(
        accounts,
        selectedAccountId,
        showIbanInput,
        iban,
      ),
    [accounts, iban, selectedAccountId, showIbanInput],
  )

  const normalizedIban = iban.replace(/\s+/g, "").toUpperCase()

  const disableBalanceReason = useMemo(() => {
    if (manualAccounts.length === 0) {
      return t.manualAccountBalance.noManualAccountsForEntity
    }
    if (!showIbanInput && selectedAccount && !selectedAccount.isManual) {
      return t.manualAccountBalance.syncedAccountHint
    }
    if (showIbanInput && normalizedIban && !resolvedManualAccount) {
      return t.manualAccountBalance.customIbanHint
    }
    return null
  }, [
    manualAccounts.length,
    normalizedIban,
    resolvedManualAccount,
    selectedAccount,
    showIbanInput,
    t,
  ])

  useEffect(() => {
    if (disableBalanceReason && applyToBalance) {
      onApplyToBalanceChange(false)
    }
  }, [applyToBalance, disableBalanceReason, onApplyToBalanceChange])

  const preview = useAccountBalancePreview(
    resolvedManualAccount,
    delta,
    currency,
    mode === "create" && applyToBalance,
  )

  const handleSelectAccount = (nextId: string) => {
    onSelectedAccountIdChange(nextId)
    onClearBalanceError?.()
    if (!nextId) {
      onIbanChange("")
      if (applyToBalance) {
        onApplyToBalanceChange(false)
      }
      return
    }
    const chosen = accounts.find(option => option.id === nextId)
    onIbanChange(chosen?.iban ?? "")
    if (chosen && !chosen.isManual && applyToBalance) {
      onApplyToBalanceChange(false)
    }
  }

  const handleSwitchMode = () => {
    if (customIbanMode) {
      onCustomIbanModeChange(false)
      const matched = normalizedIban
        ? (accounts.find(
            option => option.isManual && option.iban === normalizedIban,
          ) ?? accounts.find(option => option.iban === normalizedIban))
        : undefined
      if (matched) {
        onSelectedAccountIdChange(matched.id)
      } else {
        onSelectedAccountIdChange("")
        onIbanChange("")
        setDropdownOpen(true)
      }
    } else {
      onCustomIbanModeChange(true)
      onSelectedAccountIdChange("")
    }
    onClearBalanceError?.()
  }

  const handleBalanceToggle = (checked: boolean) => {
    onClearBalanceError?.()
    if (!checked) {
      onApplyToBalanceChange(false)
      return
    }
    if (resolvedManualAccount) {
      onApplyToBalanceChange(true)
      return
    }
    if (manualAccounts.length === 1) {
      const only = manualAccounts[0]
      if (customIbanMode) {
        onCustomIbanModeChange(false)
      }
      onSelectedAccountIdChange(only.id)
      onIbanChange(only.iban ?? "")
      onApplyToBalanceChange(true)
      return
    }
    if (manualAccounts.length > 1) {
      if (customIbanMode) {
        onCustomIbanModeChange(false)
      }
      onApplyToBalanceChange(true)
      setDropdownOpen(true)
    }
  }

  const showBalanceBar = mode === "create"
  const hasFieldError = Boolean(ibanError) || balanceAccountError
  const balanceHint =
    applyToBalance && !resolvedManualAccount && manualAccounts.length > 1
      ? t.manualAccountBalance.selectAccountAboveHint
      : t.manualAccountBalance.transactionHint

  return (
    <div className="space-y-1.5">
      <div className="flex min-h-[20px] items-center justify-between gap-2">
        <Label
          htmlFor={showIbanInput ? "transaction-iban" : "transaction-account"}
          className="shrink-0"
        >
          {showIbanInput
            ? t.transactions.iban
            : t.manualAccountBalance.accountLabel}
        </Label>
        {hasSavedAccounts && !disabled && (
          <button
            type="button"
            data-testid="toggle-custom-iban"
            onClick={handleSwitchMode}
            className="inline-flex min-w-0 items-center gap-1 text-[11px] text-muted-foreground transition-colors hover:text-foreground"
          >
            {showIbanInput ? (
              <>
                <ListFilter className="h-3 w-3 shrink-0" />
                <span className="truncate">
                  {t.manualAccountBalance.selectFromAccounts}
                  {selectedEntityName ? ` · ${selectedEntityName}` : ""}
                </span>
              </>
            ) : (
              <>
                <Keyboard className="h-3 w-3 shrink-0" />
                <span className="truncate">
                  {t.manualAccountBalance.enterIbanManually}
                </span>
              </>
            )}
          </button>
        )}
      </div>

      <div
        className={cn(
          "overflow-hidden rounded-lg border bg-background shadow-sm transition-colors",
          hasFieldError ? "border-red-500" : "border-input",
        )}
      >
        {showIbanInput ? (
          <Input
            id="transaction-iban"
            type="text"
            value={iban}
            onChange={event => {
              onIbanChange(event.target.value)
              onClearBalanceError?.()
            }}
            disabled={disabled}
            className="border-0 font-mono shadow-none focus-visible:ring-0"
          />
        ) : (
          <AccountSelectDropdown
            id="transaction-account"
            testId="transaction-account-select"
            options={accounts}
            value={selectedAccountId}
            onChange={handleSelectAccount}
            placeholder={t.manualAccountBalance.optionalAccountPlaceholder}
            showSourceBadge
            disableNonManual={applyToBalance}
            allowClear
            borderless
            disabled={disabled}
            open={dropdownOpen}
            onOpenChange={setDropdownOpen}
          />
        )}

        {showBalanceBar && (
          <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2 border-t border-border/60 bg-muted/30 px-3 py-2.5">
            <div className="min-w-[180px] flex-1">
              <div className="flex items-center gap-1.5">
                <Label
                  htmlFor="manual-account-balance-switch"
                  className={cn(
                    "text-xs font-medium",
                    disableBalanceReason
                      ? "text-muted-foreground"
                      : "cursor-pointer text-foreground",
                  )}
                >
                  {t.manualAccountBalance.apply}
                </Label>
                {disableBalanceReason && (
                  <Popover>
                    <PopoverTrigger asChild>
                      <button
                        type="button"
                        data-testid="manual-account-balance-help"
                        aria-label={disableBalanceReason}
                        className="inline-flex h-4 w-4 items-center justify-center rounded-full border text-[10px] text-muted-foreground transition-colors hover:text-foreground"
                      >
                        <HelpCircle className="h-3 w-3" />
                      </button>
                    </PopoverTrigger>
                    <PopoverContent className="w-64 text-xs">
                      {disableBalanceReason}
                    </PopoverContent>
                  </Popover>
                )}
              </div>
              {!disableBalanceReason && (
                <p className="text-[11px] leading-snug text-muted-foreground">
                  {balanceHint}
                </p>
              )}
            </div>

            <div className="ml-auto flex items-center gap-2.5">
              {preview && (
                <BalancePreviewValue
                  preview={preview}
                  className="rounded-full border border-border/70 bg-background px-2.5 py-0.5 text-xs shadow-2xs"
                />
              )}
              <Switch
                id="manual-account-balance-switch"
                size="sm"
                data-testid="manual-account-balance-switch"
                aria-label={t.manualAccountBalance.apply}
                checked={applyToBalance}
                onCheckedChange={handleBalanceToggle}
                disabled={disabled || Boolean(disableBalanceReason)}
              />
            </div>
          </div>
        )}
      </div>

      {ibanError && (
        <p className="text-xs text-red-600 dark:text-red-400">{ibanError}</p>
      )}
      {balanceAccountError && !ibanError && (
        <p className="text-xs text-red-600 dark:text-red-400">
          {t.manualAccountBalance.selectAccountError}
        </p>
      )}
    </div>
  )
}
