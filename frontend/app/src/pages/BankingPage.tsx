import React, { useState, useMemo } from "react"
import { useNavigate } from "react-router-dom"
import { motion } from "framer-motion"
import { useI18n } from "@/i18n"
import { useFinancialData } from "@/context/FinancialDataContext"
import { useAppContext } from "@/context/AppContext"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { Card } from "@/components/ui/Card"
import { Button } from "@/components/ui/Button"
import { Badge } from "@/components/ui/Badge"
import { MultiSelect } from "@/components/ui/MultiSelect"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover"
import type { MultiSelectOption } from "@/components/ui/MultiSelect"
import { formatCurrency, formatPercentage } from "@/lib/formatters"
import {
  convertCurrency,
  getEntitiesWithProductType,
} from "@/utils/financialDataUtils"
import {
  ProductType,
  CardType,
  LoanType,
  type Account,
  type Card as CardType2,
  type Loan,
} from "@/types/position"
import {
  CreditCard,
  Building2,
  Wallet,
  TrendingDown,
  Calendar,
  Percent,
  Shield,
  AlertCircle,
  Eye,
  EyeOff,
  ArrowLeft,
} from "lucide-react"
import { PinAssetButton } from "@/components/ui/PinAssetButton"
import { getAccountTypeColor, getAccountTypeIcon } from "@/utils/dashboardUtils"

export default function BankingPage() {
  const { t, locale } = useI18n()
  const { positionsData, isLoading } = useFinancialData()
  const { settings, exchangeRates, entities } = useAppContext()
  const navigate = useNavigate()

  const [selectedEntities, setSelectedEntities] = useState<string[]>([])
  const [showAccountNumbers, setShowAccountNumbers] = useState(false)

  // Get all banking data by entity
  const allBankingData = useMemo(() => {
    if (!positionsData?.positions) return []

    const bankingData: any[] = []

    Object.values(positionsData.positions).forEach((entityPosition: any) => {
      const entityInfo = entities?.find(e => e.id === entityPosition.entity.id)

      // Get accounts
      const accountsProduct = entityPosition.products[ProductType.ACCOUNT]
      if (accountsProduct?.entries) {
        accountsProduct.entries.forEach((account: Account) => {
          bankingData.push({
            type: "account",
            entityId: entityPosition.entity.id,
            entityName: entityInfo?.name || entityPosition.entity.name,
            data: {
              ...account,
              convertedTotal: convertCurrency(
                account.total,
                account.currency,
                settings.general.defaultCurrency,
                exchangeRates,
              ),
              convertedRetained: account.retained
                ? convertCurrency(
                    account.retained,
                    account.currency,
                    settings.general.defaultCurrency,
                    exchangeRates,
                  )
                : null,
              convertedPendingTransfers: account.pending_transfers
                ? convertCurrency(
                    account.pending_transfers,
                    account.currency,
                    settings.general.defaultCurrency,
                    exchangeRates,
                  )
                : null,
            },
          })
        })
      }

      // Get cards
      const cardsProduct = entityPosition.products[ProductType.CARD]
      if (cardsProduct?.entries) {
        cardsProduct.entries.forEach((card: CardType2) => {
          bankingData.push({
            type: "card",
            entityId: entityPosition.entity.id,
            entityName: entityInfo?.name || entityPosition.entity.name,
            data: {
              ...card,
              convertedUsed: convertCurrency(
                card.used,
                card.currency,
                settings.general.defaultCurrency,
                exchangeRates,
              ),
              convertedLimit: card.limit
                ? convertCurrency(
                    card.limit,
                    card.currency,
                    settings.general.defaultCurrency,
                    exchangeRates,
                  )
                : null,
            },
          })
        })
      }

      // Get loans
      const loansProduct = entityPosition.products[ProductType.LOAN]
      if (loansProduct?.entries) {
        loansProduct.entries.forEach((loan: Loan) => {
          bankingData.push({
            type: "loan",
            entityId: entityPosition.entity.id,
            entityName: entityInfo?.name || entityPosition.entity.name,
            data: {
              ...loan,
              convertedCurrentInstallment: convertCurrency(
                loan.current_installment,
                loan.currency,
                settings.general.defaultCurrency,
                exchangeRates,
              ),
              convertedLoanAmount: convertCurrency(
                loan.loan_amount,
                loan.currency,
                settings.general.defaultCurrency,
                exchangeRates,
              ),
              convertedPrincipalOutstanding: convertCurrency(
                loan.principal_outstanding,
                loan.currency,
                settings.general.defaultCurrency,
                exchangeRates,
              ),
              convertedPrincipalPaid: convertCurrency(
                loan.principal_paid,
                loan.currency,
                settings.general.defaultCurrency,
                exchangeRates,
              ),
            },
          })
        })
      }
    })

    return bankingData
  }, [positionsData, entities, settings.general.defaultCurrency, exchangeRates])

  // Filter data based on selected entities
  const filteredBankingData = useMemo(() => {
    if (selectedEntities.length === 0) return allBankingData
    return allBankingData.filter(item =>
      selectedEntities.includes(item.entityId),
    )
  }, [allBankingData, selectedEntities])

  // Get entity options for the filter
  const entityOptions: MultiSelectOption[] = useMemo(() => {
    const entitiesWithBanking = [
      ...getEntitiesWithProductType(positionsData, ProductType.ACCOUNT),
      ...getEntitiesWithProductType(positionsData, ProductType.CARD),
      ...getEntitiesWithProductType(positionsData, ProductType.LOAN),
    ]
    const uniqueEntities = Array.from(new Set(entitiesWithBanking))

    return (
      entities
        ?.filter(entity => uniqueEntities.includes(entity.id))
        .map(entity => ({
          value: entity.id,
          label: entity.name,
        })) || []
    )
  }, [entities, positionsData])

  // Separate data by type
  const accounts = useMemo(
    () => filteredBankingData.filter(item => item.type === "account"),
    [filteredBankingData],
  )
  const cards = useMemo(
    () => filteredBankingData.filter(item => item.type === "card"),
    [filteredBankingData],
  )
  const loans = useMemo(
    () => filteredBankingData.filter(item => item.type === "loan"),
    [filteredBankingData],
  )

  // Calculate KPIs
  const totalAccountBalance = useMemo(() => {
    return accounts.reduce(
      (sum, account) => sum + account.data.convertedTotal,
      0,
    )
  }, [accounts])

  const totalCardUsed = useMemo(() => {
    return cards.reduce((sum, card) => sum + card.data.convertedUsed, 0)
  }, [cards])

  const totalLoanDebt = useMemo(() => {
    return loans.reduce(
      (sum, loan) => sum + loan.data.convertedPrincipalOutstanding,
      0,
    )
  }, [loans])

  const totalMonthlyPayments = useMemo(() => {
    return loans.reduce(
      (sum, loan) => sum + loan.data.convertedCurrentInstallment,
      0,
    )
  }, [loans])

  const weightedAverageAccountInterest = useMemo(() => {
    if (accounts.length === 0) return 0
    // Treat undefined/null interest as 0 and include every account in denominator
    const totalWeightedInterest = accounts.reduce(
      (sum, account) =>
        sum +
        (account.data.interest ? account.data.interest : 0) *
          account.data.convertedTotal,
      0,
    )
    const totalBalance = accounts.reduce(
      (sum, account) => sum + account.data.convertedTotal,
      0,
    )
    return totalBalance > 0 ? totalWeightedInterest / totalBalance : 0
  }, [accounts])

  const weightedAverageLoanInterest = useMemo(() => {
    if (loans.length === 0) return 0

    const totalWeightedInterest = loans.reduce(
      (sum, loan) =>
        sum + loan.data.interest_rate * loan.data.convertedPrincipalOutstanding,
      0,
    )
    const totalDebt = loans.reduce(
      (sum, loan) => sum + loan.data.convertedPrincipalOutstanding,
      0,
    )

    return totalDebt > 0 ? totalWeightedInterest / totalDebt : 0
  }, [loans])

  const formatIban = (iban?: string | null) => {
    if (!iban) return null
    if (showAccountNumbers) {
      return iban.replace(/(.{4})/g, "$1 ").trim()
    }
    return "•••• •••• •••• " + iban.slice(-4)
  }

  const formatCardNumber = (ending?: string | null) => {
    if (!ending) return "•••• •••• •••• ••••"
    return "•••• •••• •••• " + ending
  }

  const container = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1,
      },
    },
  }

  const item = {
    hidden: { opacity: 0, y: 20 },
    show: { opacity: 1, y: 0 },
  }

  // Helper: compute next expected payment date
  const getNextPaymentDate = (dateString: string) => {
    const localeToday = new Date()
    const nextDate = new Date(dateString)
    // advance until in the future
    while (nextDate <= localeToday) {
      nextDate.setMonth(nextDate.getMonth() + 1)
    }
    return nextDate.toLocaleDateString(locale, {
      day: "numeric",
      month: "short",
    })
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <motion.div
      variants={container}
      initial="hidden"
      animate="show"
      className="space-y-6 pb-6"
    >
      {/* Header */}
      <motion.div variants={item}>
        <div className="flex flex-col md:flex-row md:items-center md:justify-between mb-6 gap-4">
          <div>
            <div className="flex items-center gap-4">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => navigate("/investments")}
              >
                <ArrowLeft size={20} />
              </Button>
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-bold">{t.banking.title}</h1>
                <PinAssetButton assetId="banking" />
              </div>
            </div>
            <p className="text-gray-600 dark:text-gray-400">
              {t.banking.subtitle}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowAccountNumbers(!showAccountNumbers)}
              className="flex items-center gap-2"
            >
              {showAccountNumbers ? (
                <EyeOff className="h-4 w-4" />
              ) : (
                <Eye className="h-4 w-4" />
              )}
              {showAccountNumbers
                ? t.banking.hideNumbers
                : t.banking.showNumbers}
            </Button>
            <MultiSelect
              options={entityOptions}
              value={selectedEntities}
              onChange={setSelectedEntities}
              placeholder={t.transactions.selectEntities}
              className="min-w-[200px]"
            />
          </div>
        </div>
      </motion.div>

      {/* KPIs Overview */}
      <motion.div variants={item}>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {/* Total Account Balance - only show if there are accounts */}
          {accounts.length > 0 && (
            <Card className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <Wallet className="h-5 w-5 text-blue-500" />
                <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
                  {t.banking.totalBalance}
                </span>
              </div>
              <div className="text-2xl font-bold">
                {formatCurrency(
                  totalAccountBalance,
                  locale,
                  settings.general.defaultCurrency,
                )}
              </div>
              {weightedAverageAccountInterest > 0 && (
                <div className="text-xs text-green-600 dark:text-green-400 flex items-center gap-1">
                  <Percent className="h-3 w-3" />
                  {formatPercentage(
                    weightedAverageAccountInterest * 100,
                    locale,
                  )}{" "}
                  {t.banking.avgInterest}
                </div>
              )}
            </Card>
          )}

          {/* Total Card Usage - only show if there are cards */}
          {cards.length > 0 && (
            <Card className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <CreditCard className="h-5 w-5 text-orange-500" />
                <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
                  {t.banking.totalCardUsed}
                </span>
              </div>
              <div className="text-2xl font-bold">
                {formatCurrency(
                  totalCardUsed,
                  locale,
                  settings.general.defaultCurrency,
                )}
              </div>
              <div className="text-xs text-gray-500">
                {cards.length}{" "}
                {cards.length === 1 ? t.banking.card : t.banking.cards}
              </div>
            </Card>
          )}
          {/* Outstanding Debt - only show if there are loans */}
          {loans.length > 0 && (
            <Card className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <TrendingDown className="h-5 w-5 text-red-400" />
                <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
                  {t.banking.totalDebt}
                </span>
              </div>
              <div className="text-2xl font-bold">
                {formatCurrency(
                  totalLoanDebt,
                  locale,
                  settings.general.defaultCurrency,
                )}
              </div>
              {weightedAverageLoanInterest > 0 && (
                <div className="text-xs text-red-500 dark:text-red-400 flex items-center gap-1">
                  <Percent className="h-3 w-3" />
                  {formatPercentage(
                    weightedAverageLoanInterest * 100,
                    locale,
                  )}{" "}
                  {t.banking.avgInterest}
                </div>
              )}
            </Card>
          )}

          {/* Monthly Payments - only show if there are loans */}
          {loans.length > 0 && (
            <Card className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <Calendar className="h-5 w-5 text-purple-500" />
                <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
                  {t.banking.monthlyPayments}
                </span>
              </div>
              <div className="text-2xl font-bold">
                {formatCurrency(
                  totalMonthlyPayments,
                  locale,
                  settings.general.defaultCurrency,
                )}
              </div>
              <div className="text-xs text-gray-500">
                {loans.length}{" "}
                {loans.length === 1 ? t.banking.loan : t.banking.loans}
              </div>
            </Card>
          )}
        </div>
      </motion.div>

      {/* Accounts Section */}
      {accounts.length > 0 && (
        <motion.div variants={item}>
          <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
            <Wallet className="h-5 w-5" />
            {t.banking.accounts} ({accounts.length})
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 items-start">
            {accounts.map(account => (
              <Card
                key={account.data.id}
                className="hover:shadow-lg transition-shadow self-center"
              >
                <div className="p-4">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-2">
                      {getAccountTypeIcon(account.data.type)}
                      <Badge
                        variant="secondary"
                        className={`text-xs ${getAccountTypeColor(account.data.type)}`}
                      >
                        {t.accountTypes[
                          account.data.type as keyof typeof t.accountTypes
                        ] || account.data.type}
                      </Badge>
                    </div>
                    <Badge variant="outline" className="text-xs">
                      {account.entityName}
                    </Badge>
                  </div>

                  <div className="space-y-2">
                    {account.data.name && (
                      <div className="font-semibold text-lg">
                        {account.data.name}
                      </div>
                    )}

                    {account.data.iban && (
                      <div className="text-sm text-gray-600 dark:text-gray-400 font-mono">
                        {formatIban(account.data.iban)}
                      </div>
                    )}

                    <div className="text-2xl font-bold">
                      {formatCurrency(
                        account.data.convertedTotal,
                        locale,
                        settings.general.defaultCurrency,
                      )}
                    </div>

                    <div className="text-xs text-gray-500">
                      {account.data.currency !==
                        settings.general.defaultCurrency && (
                        <span>
                          {formatCurrency(
                            account.data.total,
                            locale,
                            account.data.currency,
                          )}{" "}
                          •
                        </span>
                      )}
                      <span className="ml-1">{t.banking.available}</span>
                    </div>

                    {/* Additional info */}
                    {(Number(account.data.interest) || 0) > 0 ||
                    (account.data.convertedRetained &&
                      account.data.convertedRetained > 0) ||
                    (account.data.convertedPendingTransfers &&
                      account.data.convertedPendingTransfers > 0) ? (
                      <div className="flex justify-between text-xs pt-2 border-t border-gray-100 dark:border-gray-800">
                        {(Number(account.data.interest) || 0) > 0 && (
                          <Popover>
                            <PopoverTrigger asChild>
                              <div className="text-green-600 dark:text-green-400 flex items-center gap-1 cursor-help">
                                <Percent className="h-3 w-3" />
                                {formatPercentage(
                                  account.data.interest * 100,
                                  locale,
                                )}
                              </div>
                            </PopoverTrigger>
                            <PopoverContent className="w-auto p-2 text-xs">
                              {t.banking.interestRate}
                            </PopoverContent>
                          </Popover>
                        )}

                        {account.data.convertedRetained &&
                          account.data.convertedRetained > 0 && (
                            <Popover>
                              <PopoverTrigger asChild>
                                <div className="text-orange-600 dark:text-orange-400 flex items-center gap-1 cursor-help">
                                  <Shield className="h-3 w-3" />
                                  {formatCurrency(
                                    account.data.convertedRetained,
                                    locale,
                                    settings.general.defaultCurrency,
                                  )}
                                </div>
                              </PopoverTrigger>
                              <PopoverContent className="w-auto p-2 text-xs">
                                {t.banking.retainedAmount}
                              </PopoverContent>
                            </Popover>
                          )}

                        {account.data.convertedPendingTransfers &&
                          account.data.convertedPendingTransfers > 0 && (
                            <Popover>
                              <PopoverTrigger asChild>
                                <div className="text-blue-600 dark:text-blue-400 flex items-center gap-1 cursor-help">
                                  <AlertCircle className="h-3 w-3" />
                                  {formatCurrency(
                                    account.data.convertedPendingTransfers,
                                    locale,
                                    settings.general.defaultCurrency,
                                  )}
                                </div>
                              </PopoverTrigger>
                              <PopoverContent className="w-auto p-2 text-xs">
                                {t.banking.pendingTransfers}
                              </PopoverContent>
                            </Popover>
                          )}
                      </div>
                    ) : null}
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </motion.div>
      )}

      {/* Cards Section */}
      {cards.length > 0 && (
        <motion.div variants={item}>
          <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
            <CreditCard className="h-5 w-5" />
            {t.banking.cards} ({cards.length})
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {cards.map(card => (
              <Card
                key={card.data.id}
                className={`overflow-hidden transition-all hover:shadow-lg self-center ${
                  !card.data.active ? "opacity-60 grayscale" : ""
                }`}
              >
                {/* Card-like design */}
                <div
                  className={`p-6 bg-gradient-to-br ${
                    card.data.type === CardType.CREDIT
                      ? "from-blue-600 to-blue-800"
                      : "from-green-600 to-green-800"
                  } text-white relative overflow-hidden`}
                >
                  {/* Entity badge */}
                  <div className="absolute top-2 right-2">
                    <Badge
                      variant="secondary"
                      className="text-xs bg-white/20 text-white border-white/30"
                    >
                      {card.entityName}
                    </Badge>
                  </div>

                  {/* Card type */}
                  <div className="flex items-center gap-2 mb-4">
                    <CreditCard className="h-5 w-5" />
                    <span className="text-sm font-medium">
                      {card.data.type === CardType.CREDIT
                        ? t.cardTypes.CREDIT
                        : t.cardTypes.DEBIT}
                    </span>
                  </div>

                  {/* Card number */}
                  <div className="font-mono text-lg mb-2">
                    {formatCardNumber(card.data.ending)}
                  </div>

                  {/* Card name */}
                  {card.data.name && (
                    <div className="text-sm opacity-90 mb-4">
                      {card.data.name}
                    </div>
                  )}

                  {/* Status indicator */}
                  {!card.data.active && (
                    <div className="absolute bottom-2 left-2">
                      <Badge variant="destructive" className="text-xs">
                        {t.banking.inactive}
                      </Badge>
                    </div>
                  )}
                </div>

                {/* Card details */}
                <div className="p-4 space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600 dark:text-gray-400">
                      {t.banking.used}
                    </span>
                    <span className="font-semibold">
                      {formatCurrency(
                        card.data.convertedUsed,
                        locale,
                        settings.general.defaultCurrency,
                      )}
                    </span>
                  </div>

                  {card.data.convertedLimit && (
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-gray-600 dark:text-gray-400">
                        {t.banking.limit}
                      </span>
                      <span className="text-sm">
                        {formatCurrency(
                          card.data.convertedLimit,
                          locale,
                          settings.general.defaultCurrency,
                        )}
                      </span>
                    </div>
                  )}

                  {card.data.convertedLimit && card.data.convertedUsed > 0 && (
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs">
                        <span>{t.banking.utilization}</span>
                        <span>
                          {formatPercentage(
                            (card.data.convertedUsed /
                              card.data.convertedLimit) *
                              100,
                            locale,
                          )}
                        </span>
                      </div>
                      <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                        <div
                          className={`h-2 rounded-full ${
                            card.data.convertedUsed / card.data.convertedLimit >
                            0.8
                              ? "bg-red-500"
                              : card.data.convertedUsed /
                                    card.data.convertedLimit >
                                  0.6
                                ? "bg-yellow-500"
                                : "bg-green-500"
                          }`}
                          style={{
                            width: `${Math.min((card.data.convertedUsed / card.data.convertedLimit) * 100, 100)}%`,
                          }}
                        />
                      </div>
                    </div>
                  )}

                  {card.data.currency !== settings.general.defaultCurrency && (
                    <div className="text-xs text-gray-500 pt-2 border-t border-gray-100 dark:border-gray-800">
                      {formatCurrency(
                        card.data.used,
                        locale,
                        card.data.currency,
                      )}
                      {card.data.limit &&
                        ` / ${formatCurrency(card.data.limit, locale, card.data.currency)}`}
                    </div>
                  )}
                </div>
              </Card>
            ))}
          </div>
        </motion.div>
      )}

      {/* Loans Section */}
      {loans.length > 0 && (
        <motion.div variants={item}>
          <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
            <TrendingDown className="h-5 w-5" />
            {t.banking.loans} ({loans.length})
          </h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {loans.map(loan => (
              <Card key={loan.data.id} className="p-6">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <Badge
                      variant="secondary"
                      className="bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
                    >
                      {loan.data.type === LoanType.MORTGAGE
                        ? t.loanTypes.MORTGAGE
                        : t.loanTypes.STANDARD}
                    </Badge>
                  </div>
                  <Badge variant="outline" className="text-xs">
                    {loan.entityName}
                  </Badge>
                </div>

                {loan.data.name && (
                  <h3 className="font-semibold text-lg mb-4">
                    {loan.data.name}
                  </h3>
                )}

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                  <div>
                    <span className="text-sm text-gray-600 dark:text-gray-400 block">
                      {t.banking.principalOutstanding}
                    </span>
                    <span className="text-xl font-bold text-red-600 dark:text-red-400">
                      {formatCurrency(
                        loan.data.convertedPrincipalOutstanding,
                        locale,
                        settings.general.defaultCurrency,
                      )}
                    </span>
                  </div>

                  <div>
                    <span className="text-sm text-gray-600 dark:text-gray-400 block">
                      {t.banking.monthlyInstallment}
                    </span>
                    <span className="text-lg font-semibold">
                      {formatCurrency(
                        loan.data.convertedCurrentInstallment,
                        locale,
                        settings.general.defaultCurrency,
                      )}
                    </span>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                  <div>
                    <span className="text-sm text-gray-600 dark:text-gray-400 block">
                      {t.banking.interestRate}
                    </span>
                    <span className="text-sm font-medium flex items-center gap-1">
                      <Percent className="h-3 w-3" />
                      {formatPercentage(loan.data.interest_rate * 100, locale)}
                    </span>
                  </div>

                  <div>
                    <span className="text-sm text-gray-600 dark:text-gray-400 block">
                      {t.banking.paymentDate}
                    </span>
                    <span className="text-sm font-medium flex items-center gap-1">
                      <Calendar className="h-3 w-3" />
                      {getNextPaymentDate(
                        loan.data.creation || loan.data.next_payment_date,
                      )}
                    </span>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t border-gray-100 dark:border-gray-800">
                  <div>
                    <span className="text-sm text-gray-600 dark:text-gray-400 block">
                      {t.banking.originalAmount}
                    </span>
                    <span className="text-sm">
                      {formatCurrency(
                        loan.data.convertedLoanAmount,
                        locale,
                        settings.general.defaultCurrency,
                      )}
                    </span>
                  </div>

                  <div>
                    <span className="text-sm text-gray-600 dark:text-gray-400 block">
                      {t.banking.principalPaid}
                    </span>
                    <span className="text-sm text-green-600 dark:text-green-400">
                      {formatCurrency(
                        loan.data.convertedPrincipalPaid,
                        locale,
                        settings.general.defaultCurrency,
                      )}
                    </span>
                  </div>
                </div>

                {/* Progress bar */}
                {loan.data.convertedLoanAmount > 0 && (
                  <div className="mt-4 space-y-1">
                    <div className="flex justify-between text-xs text-gray-600 dark:text-gray-400">
                      <span>{t.banking.repaymentProgress}</span>
                      <span>
                        {formatPercentage(
                          (loan.data.convertedPrincipalPaid /
                            loan.data.convertedLoanAmount) *
                            100,
                          locale,
                        )}
                      </span>
                    </div>
                    <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                      <div
                        className="h-2 rounded-full bg-green-500"
                        style={{
                          width: `${Math.min((loan.data.convertedPrincipalPaid / loan.data.convertedLoanAmount) * 100, 100)}%`,
                        }}
                      />
                    </div>
                  </div>
                )}

                {loan.data.currency !== settings.general.defaultCurrency && (
                  <div className="text-xs text-gray-500 pt-3 border-t border-gray-100 dark:border-gray-800">
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <span className="block">
                          {t.banking.principalOutstanding}:
                        </span>
                        <span>
                          {formatCurrency(
                            loan.data.principal_outstanding,
                            locale,
                            loan.data.currency,
                          )}
                        </span>
                      </div>
                      <div>
                        <span className="block">
                          {t.banking.monthlyInstallment}:
                        </span>
                        <span>
                          {formatCurrency(
                            loan.data.current_installment,
                            locale,
                            loan.data.currency,
                          )}
                        </span>
                      </div>
                    </div>
                  </div>
                )}
              </Card>
            ))}
          </div>
        </motion.div>
      )}

      {/* Empty State */}
      {accounts.length === 0 && cards.length === 0 && loans.length === 0 && (
        <motion.div variants={item}>
          <Card className="p-12 text-center">
            <div className="text-gray-400 dark:text-gray-600 mb-4">
              <Building2 className="h-12 w-12 mx-auto" />
            </div>
            <h3 className="text-lg font-semibold mb-2">{t.banking.noData}</h3>
            <p className="text-gray-600 dark:text-gray-400">
              {t.banking.noDataDescription}
            </p>
          </Card>
        </motion.div>
      )}
    </motion.div>
  )
}
