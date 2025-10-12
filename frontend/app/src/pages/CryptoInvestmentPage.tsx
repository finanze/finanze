import React, { useMemo, useState, useCallback, useRef } from "react"
import { useI18n } from "@/i18n"
import { useFinancialData } from "@/context/FinancialDataContext"
import { useAppContext } from "@/context/AppContext"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import { Button } from "@/components/ui/Button"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { InvestmentFilters } from "@/components/InvestmentFilters"
import { InvestmentDistributionChart } from "@/components/InvestmentDistributionChart"
import { formatCurrency, formatPercentage } from "@/lib/formatters"
import { calculateCryptoValue } from "@/utils/financialDataUtils"
import { ProductType, CryptoCurrencyWallet } from "@/types/position"
import { Entity } from "@/types"
import {
  ArrowLeft,
  Wallet,
  TrendingUp,
  Copy,
  Check,
  Pencil,
} from "lucide-react"
import { getIconForAssetType } from "@/utils/dashboardUtils"
import { PinAssetButton } from "@/components/ui/PinAssetButton"
import { useNavigate } from "react-router-dom"
import { MultiSelectOption } from "@/components/ui/MultiSelect"
import { motion } from "framer-motion"
import { fadeListContainer, fadeListItem } from "@/lib/animations"

export default function CryptoInvestmentPage() {
  const { t, locale } = useI18n()
  const navigate = useNavigate()
  const { positionsData, isLoading } = useFinancialData()
  const { settings, exchangeRates, entities } = useAppContext()

  const [selectedEntities, setSelectedEntities] = useState<string[]>([])
  const [copiedAddress, setCopiedAddress] = useState<string | null>(null)
  const symbolRefs = useRef<Record<string, HTMLDivElement | null>>({})
  const [highlightedAsset, setHighlightedAsset] = useState<string | null>(null)

  // Helper function to get crypto display name
  const getCryptoDisplayName = useCallback(
    (symbol: string, cryptoName?: string) => {
      // First, try to get the i18n translation for the symbol
      const translatedName = (t.crypto as any)?.[symbol]
      if (translatedName) {
        return translatedName
      }

      // If it's a token with a proper name (not all uppercase and not equal to symbol), use that name
      if (
        cryptoName &&
        cryptoName !== symbol &&
        cryptoName !== cryptoName.toUpperCase()
      ) {
        return cryptoName
      }

      // Fallback to symbol
      return symbol
    },
    [t.crypto],
  )

  // Helper function to calculate total wallet value
  const getTotalWalletValue = useCallback(
    (wallet: CryptoCurrencyWallet) => {
      let totalValue = 0

      if (wallet.amount && wallet.symbol && wallet.symbol !== "N/A") {
        totalValue += calculateCryptoValue(
          wallet.amount,
          wallet.symbol,
          settings.general.defaultCurrency,
          exchangeRates,
        )
      }

      if (wallet.tokens) {
        wallet.tokens.forEach(token => {
          if (token.amount && token.symbol) {
            totalValue += calculateCryptoValue(
              token.amount,
              token.symbol,
              settings.general.defaultCurrency,
              exchangeRates,
            )
          }
        })
      }

      return totalValue
    },
    [settings.general.defaultCurrency, exchangeRates],
  )

  // Get all crypto wallets grouped by entity
  const allCryptoWallets = useMemo(() => {
    if (!positionsData?.positions || !entities) return []

    const walletsByEntity: Array<{
      entity: Entity
      wallets: CryptoCurrencyWallet[]
      totalValue: number
    }> = []

    entities.forEach(entity => {
      const entityPosition = positionsData.positions[entity.id]
      if (!entityPosition) return

      const cryptoProduct = entityPosition.products[ProductType.CRYPTO]
      if (
        !cryptoProduct ||
        !("entries" in cryptoProduct) ||
        !cryptoProduct.entries?.length
      )
        return

      const positionWallets = cryptoProduct.entries as CryptoCurrencyWallet[]
      const connectedWallets = entity.connected || []

      const combinedWallets: CryptoCurrencyWallet[] = []

      // Add wallets with position data
      positionWallets.forEach(wallet => {
        const connection = connectedWallets.find(
          conn => conn.address === wallet.address,
        )
        const walletWithConnectionName = {
          ...wallet,
          name: connection?.name || wallet.name,
        }
        combinedWallets.push(walletWithConnectionName)
      })

      // Add connected wallets without position data
      connectedWallets.forEach(connection => {
        const existsInPositions = positionWallets.some(
          wallet => wallet.address === connection.address,
        )
        if (!existsInPositions) {
          const placeholderWallet: CryptoCurrencyWallet = {
            id: connection.id,
            wallet_connection_id: connection.id,
            address: connection.address,
            name: connection.name,
            symbol: "N/A",
            crypto: "N/A",
            amount: 0,
            initial_investment: null,
            average_buy_price: null,
            market_value: null,
            currency: null,
            tokens: null,
          }
          combinedWallets.push(placeholderWallet)
        }
      })

      if (combinedWallets.length > 0) {
        const totalValue = combinedWallets.reduce((sum, wallet) => {
          return sum + getTotalWalletValue(wallet)
        }, 0)

        walletsByEntity.push({
          entity,
          wallets: combinedWallets,
          totalValue,
        })
      }
    })

    return walletsByEntity
  }, [positionsData, entities, getTotalWalletValue])

  // Filter wallets based on selected entities
  const filteredCryptoWallets = useMemo(() => {
    const base =
      selectedEntities.length === 0
        ? allCryptoWallets
        : allCryptoWallets.filter(item =>
            selectedEntities.includes(item.entity.id),
          )
    // sort entities by total value desc
    return [...base]
      .sort((a, b) => b.totalValue - a.totalValue)
      .map(group => ({
        ...group,
        // ensure wallets inside each group are sorted desc by wallet total value
        wallets: [...group.wallets].sort(
          (a, b) => getTotalWalletValue(b) - getTotalWalletValue(a),
        ),
      }))
  }, [allCryptoWallets, selectedEntities, getTotalWalletValue])

  // Get entity options for the filter
  const entityOptions: MultiSelectOption[] = useMemo(() => {
    return (
      entities
        ?.filter(entity => {
          // Check if entity has crypto positions or connected wallets
          const entityWalletsGroup = allCryptoWallets.find(
            group => group.entity.id === entity.id,
          )
          return entityWalletsGroup && entityWalletsGroup.wallets.length > 0
        })
        .map(entity => ({
          value: entity.id,
          label: entity.name,
        })) || []
    )
  }, [entities, allCryptoWallets])

  // Calculate chart data - aggregate all assets across all wallets
  const chartData = useMemo(() => {
    const assetValues: Record<string, { value: number; name: string }> = {}

    filteredCryptoWallets.forEach(({ wallets }) => {
      wallets.forEach(wallet => {
        if (wallet.amount && wallet.symbol && wallet.symbol !== "N/A") {
          const value = calculateCryptoValue(
            wallet.amount,
            wallet.symbol,
            settings.general.defaultCurrency,
            exchangeRates,
          )
          const displayName = getCryptoDisplayName(wallet.symbol, wallet.crypto)
          if (!assetValues[wallet.symbol]) {
            assetValues[wallet.symbol] = { value: 0, name: displayName }
          }
          assetValues[wallet.symbol].value += value
        }

        if (wallet.tokens) {
          wallet.tokens.forEach(token => {
            if (token.amount && token.symbol) {
              const value = calculateCryptoValue(
                token.amount,
                token.symbol,
                settings.general.defaultCurrency,
                exchangeRates,
              )
              const displayName = getCryptoDisplayName(token.symbol, token.name)
              if (!assetValues[token.symbol]) {
                assetValues[token.symbol] = { value: 0, name: displayName }
              }
              assetValues[token.symbol].value += value
            }
          })
        }
      })
    })

    const totalValue = Object.values(assetValues).reduce(
      (sum, asset) => sum + asset.value,
      0,
    )

    // Generate colors for crypto assets
    const cryptoColors = [
      "#f59e0b",
      "#ef4444",
      "#8b5cf6",
      "#06b6d4",
      "#10b981",
      "#f97316",
      "#ec4899",
      "#84cc16",
      "#6366f1",
      "#14b8a6",
      "#f59e0b",
      "#ef4444",
      "#8b5cf6",
      "#06b6d4",
      "#10b981",
    ]

    return Object.entries(assetValues)
      .map(([, asset], index) => ({
        name: asset.name,
        value: asset.value,
        color: cryptoColors[index % cryptoColors.length],
        percentage: totalValue > 0 ? (asset.value / totalValue) * 100 : 0,
      }))
      .sort((a, b) => b.value - a.value)
  }, [
    filteredCryptoWallets,
    settings.general.defaultCurrency,
    exchangeRates,
    getCryptoDisplayName,
  ])

  const totalInitialInvestment = useMemo(() => {
    return filteredCryptoWallets.reduce((sum, { wallets }) => {
      return (
        sum +
        wallets.reduce((walletSum, wallet) => {
          return walletSum + (wallet.initial_investment || 0)
        }, 0)
      )
    }, 0)
  }, [filteredCryptoWallets])

  const totalValue = useMemo(() => {
    return filteredCryptoWallets.reduce((sum, item) => sum + item.totalValue, 0)
  }, [filteredCryptoWallets])

  const totalCryptoAssets = useMemo(() => {
    const uniqueAssets = new Set<string>()

    filteredCryptoWallets.forEach(({ wallets }) => {
      wallets.forEach(wallet => {
        if (wallet.amount && wallet.symbol && wallet.symbol !== "N/A") {
          const displayName = getCryptoDisplayName(wallet.symbol, wallet.crypto)
          uniqueAssets.add(displayName)
        }
        if (wallet.tokens) {
          wallet.tokens.forEach(token => {
            if (token.amount && token.symbol) {
              const displayName = getCryptoDisplayName(token.symbol, token.name)
              uniqueAssets.add(displayName)
            }
          })
        }
      })
    })

    return uniqueAssets.size
  }, [filteredCryptoWallets, getCryptoDisplayName])

  const formattedTotalValue = useMemo(() => {
    return formatCurrency(totalValue, locale, settings.general.defaultCurrency)
  }, [totalValue, locale, settings.general.defaultCurrency])

  const handleCopyAddress = async (address: string) => {
    try {
      await navigator.clipboard.writeText(address)
      setCopiedAddress(address)
      setTimeout(() => setCopiedAddress(null), 2000)
    } catch {
      /* ignore */
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
            <ArrowLeft size={20} />
          </Button>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold">{t.common.cryptoInvestments}</h1>
            <PinAssetButton assetId="crypto" />
          </div>
        </div>
        <Button
          variant="default"
          size="sm"
          onClick={() => navigate("/entities#crypto-enabled")}
        >
          <Pencil className="h-4 w-4 mr-2" /> {t.walletManagement.manage}
        </Button>
      </div>

      {/* Filters */}
      <InvestmentFilters
        entityOptions={entityOptions}
        selectedEntities={selectedEntities}
        onEntitiesChange={setSelectedEntities}
      />

      {filteredCryptoWallets.length === 0 ? (
        <Card className="p-14 text-center flex flex-col items-center gap-4">
          {getIconForAssetType(
            ProductType.CRYPTO,
            "h-16 w-16",
            "text-gray-400 dark:text-gray-600",
          )}
          <div className="text-gray-500 dark:text-gray-400 text-sm max-w-md">
            {selectedEntities.length > 0
              ? t.investments.noPositionsFound.replace(
                  "{type}",
                  "crypto wallets",
                )
              : t.investments.noPositionsAvailable.replace(
                  "{type}",
                  "crypto wallets",
                )}
          </div>
        </Card>
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 items-stretch">
            <div className="flex flex-col gap-4 xl:col-span-1 order-1 xl:order-1">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-600 dark:text-gray-400">
                    {t.common.cryptoInvestments}
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-0">
                  <div className="flex justify-between items-baseline">
                    <p className="text-2xl font-bold">{formattedTotalValue}</p>
                    {totalInitialInvestment > 0 &&
                      (() => {
                        const percentageValue =
                          ((totalValue - totalInitialInvestment) /
                            totalInitialInvestment) *
                          100
                        const sign = percentageValue >= 0 ? "+" : "-"
                        return (
                          <p
                            className={`text-sm font-medium ${percentageValue === 0 ? "text-gray-500 dark:text-gray-400" : percentageValue > 0 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}
                          >
                            {sign}
                            {formatPercentage(
                              Math.abs(percentageValue),
                              locale,
                            )}
                          </p>
                        )
                      })()}
                  </div>
                  {totalInitialInvestment > 0 && (
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      {t.dashboard.investedAmount}{" "}
                      {formatCurrency(
                        totalInitialInvestment,
                        locale,
                        settings.general.defaultCurrency,
                      )}
                    </p>
                  )}
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-600 dark:text-gray-400">
                    {t.investments.numberOfAssets}
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-0">
                  <p className="text-2xl font-bold">{totalCryptoAssets}</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    {totalCryptoAssets === 1
                      ? t.investments.asset
                      : t.investments.assets}
                  </p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-600 dark:text-gray-400">
                    {t.walletManagement.wallets}
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-0">
                  <p className="text-2xl font-bold">
                    {filteredCryptoWallets.reduce(
                      (sum, item) => sum + item.wallets.length,
                      0,
                    )}
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    {filteredCryptoWallets.reduce(
                      (sum, item) => sum + item.wallets.length,
                      0,
                    ) === 1
                      ? t.walletManagement.wallet
                      : t.walletManagement.wallets}
                  </p>
                </CardContent>
              </Card>
            </div>
            <div className="xl:col-span-2 order-2 xl:order-2 flex items-center">
              <InvestmentDistributionChart
                data={chartData}
                title={t.common.distribution}
                locale={locale}
                currency={settings.general.defaultCurrency}
                hideLegend
                containerClassName="overflow-visible w-full"
                variant="bare"
                onSliceClick={slice => {
                  const ref = symbolRefs.current[slice.name]
                  if (ref) {
                    ref.scrollIntoView({ behavior: "smooth", block: "center" })
                    setHighlightedAsset(slice.name)
                    setTimeout(
                      () =>
                        setHighlightedAsset(prev =>
                          prev === slice.name ? null : prev,
                        ),
                      1500,
                    )
                  }
                }}
              />
            </div>
          </div>

          {/* Wallets grouped by entity */}
          <motion.div
            variants={fadeListContainer}
            initial="hidden"
            animate="show"
            className="space-y-6 pb-6"
          >
            {filteredCryptoWallets.map(
              ({ entity, wallets, totalValue: entityTotalValue }) => (
                <motion.div key={entity.id} variants={fadeListItem}>
                  <Card>
                    <CardHeader className="pb-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="p-2 bg-blue-100 dark:bg-blue-900 rounded-lg">
                            <Wallet className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                          </div>
                          <div>
                            <CardTitle className="text-xl">
                              {entity.name}
                            </CardTitle>
                            <p className="text-sm text-gray-600 dark:text-gray-400">
                              {wallets.length}{" "}
                              {wallets.length !== 1
                                ? t.walletManagement.wallets
                                : t.walletManagement.wallet}
                            </p>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-2xl font-bold">
                            {formatCurrency(
                              entityTotalValue,
                              locale,
                              settings.general.defaultCurrency,
                            )}
                          </div>
                          <div className="text-sm text-gray-600 dark:text-gray-400">
                            {t.walletManagement.totalValue}
                          </div>
                        </div>
                      </div>
                    </CardHeader>

                    <CardContent className="pb-6">
                      <div className="grid gap-4 grid-cols-1 sm:[grid-template-columns:repeat(auto-fit,minmax(280px,1fr))]">
                        {wallets.map(wallet => (
                          <div
                            key={wallet.id}
                            className={`flex h-full flex-col gap-3 rounded-lg border p-4 transition-all ${
                              wallet.market_value === null
                                ? "opacity-75 border-dashed bg-gray-50 dark:bg-gray-900/50"
                                : "bg-white dark:bg-gray-900 hover:shadow-sm"
                            }`}
                          >
                            {/* Wallet Header */}
                            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                              <div className="flex items-center gap-3 flex-1 min-w-0">
                                <div className="w-8 h-8 flex items-center justify-center flex-shrink-0">
                                  <img
                                    src={`entities/${entity.id}.png`}
                                    alt={wallet.crypto}
                                    className="w-8 h-8 object-contain"
                                    onError={e => {
                                      e.currentTarget.style.display = "none"
                                      e.currentTarget.nextElementSibling?.classList.remove(
                                        "hidden",
                                      )
                                    }}
                                  />
                                  <span className="hidden text-white text-xs font-bold">
                                    {wallet.symbol}
                                  </span>
                                </div>
                                <div className="min-w-0 flex-1">
                                  <div className="flex items-center gap-2">
                                    <h4 className="font-medium truncate">
                                      {wallet.name}
                                    </h4>
                                    {wallet.market_value === null && (
                                      <span className="text-xs bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-400 px-2 py-1 rounded flex-shrink-0">
                                        No data
                                      </span>
                                    )}
                                  </div>
                                  <div className="flex items-center gap-2 group">
                                    <p className="text-sm text-gray-600 dark:text-gray-400 font-mono truncate">
                                      {wallet.address.slice(0, 8)}...
                                      {wallet.address.slice(-6)}
                                    </p>
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      className={`p-1 h-6 w-6 opacity-70 hover:opacity-100 transition-all duration-200 flex-shrink-0 ${
                                        copiedAddress === wallet.address
                                          ? "text-green-600 dark:text-green-400"
                                          : "text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                                      }`}
                                      onClick={() =>
                                        handleCopyAddress(wallet.address)
                                      }
                                      title={
                                        copiedAddress === wallet.address
                                          ? t.common.copied
                                          : t.common.copy
                                      }
                                    >
                                      {copiedAddress === wallet.address ? (
                                        <Check className="h-3 w-3" />
                                      ) : (
                                        <Copy className="h-3 w-3" />
                                      )}
                                    </Button>
                                  </div>
                                </div>
                              </div>
                              <div className="text-left sm:text-right flex-shrink-0">
                                <div className="text-lg font-medium">
                                  {formatCurrency(
                                    getTotalWalletValue(wallet),
                                    locale,
                                    settings.general.defaultCurrency,
                                  )}
                                </div>
                              </div>
                            </div>

                            {/* Main Crypto */}
                            {wallet.amount > 0 && wallet.symbol !== "N/A" && (
                              <div
                                className={`rounded-lg border-l-4 bg-gray-50 p-3 dark:bg-gray-800 ${highlightedAsset && highlightedAsset === getCryptoDisplayName(wallet.symbol, wallet.crypto) ? "ring-2 ring-primary" : ""}`}
                                ref={el => {
                                  const displayName = getCryptoDisplayName(
                                    wallet.symbol,
                                    wallet.crypto,
                                  )
                                  if (!symbolRefs.current[displayName])
                                    symbolRefs.current[displayName] = el
                                }}
                                style={{
                                  borderLeftColor:
                                    chartData.find(
                                      c =>
                                        c.name ===
                                        getCryptoDisplayName(
                                          wallet.symbol,
                                          wallet.crypto,
                                        ),
                                    )?.color || "transparent",
                                }}
                              >
                                <div className="flex items-center justify-between">
                                  <div>
                                    <p className="font-medium">
                                      {getCryptoDisplayName(
                                        wallet.symbol,
                                        wallet.crypto,
                                      )}
                                    </p>
                                    <p className="text-sm text-gray-600 dark:text-gray-400">
                                      {wallet.amount.toLocaleString()}{" "}
                                      {wallet.symbol}
                                    </p>
                                  </div>
                                  <div className="text-right">
                                    <p className="font-medium">
                                      {formatCurrency(
                                        calculateCryptoValue(
                                          wallet.amount,
                                          wallet.symbol,
                                          settings.general.defaultCurrency,
                                          exchangeRates,
                                        ),
                                        locale,
                                        settings.general.defaultCurrency,
                                      )}
                                    </p>
                                    {wallet.initial_investment && (
                                      <div className="flex items-center gap-1 text-sm">
                                        <TrendingUp className="h-3 w-3" />
                                        <span
                                          className={
                                            calculateCryptoValue(
                                              wallet.amount,
                                              wallet.symbol,
                                              settings.general.defaultCurrency,
                                              exchangeRates,
                                            ) >= wallet.initial_investment
                                              ? "text-green-600"
                                              : "text-red-600"
                                          }
                                        >
                                          {(
                                            ((calculateCryptoValue(
                                              wallet.amount,
                                              wallet.symbol,
                                              settings.general.defaultCurrency,
                                              exchangeRates,
                                            ) -
                                              wallet.initial_investment) /
                                              wallet.initial_investment) *
                                            100
                                          ).toFixed(1)}
                                          %
                                        </span>
                                      </div>
                                    )}
                                  </div>
                                </div>
                              </div>
                            )}

                            {/* Tokens */}
                            {wallet.tokens && wallet.tokens.length > 0 && (
                              <div className="space-y-2">
                                <h5 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                                  Tokens ({wallet.tokens.length})
                                </h5>
                                <div className="space-y-2 max-h-40 overflow-y-auto">
                                  {wallet.tokens.map(token => {
                                    const displayName = getCryptoDisplayName(
                                      token.symbol,
                                      token.name,
                                    )
                                    const color =
                                      chartData.find(
                                        c => c.name === displayName,
                                      )?.color || "transparent"
                                    const isHighlighted =
                                      highlightedAsset === displayName
                                    return (
                                      <div
                                        key={token.id}
                                        ref={el => {
                                          if (!symbolRefs.current[displayName])
                                            symbolRefs.current[displayName] = el
                                        }}
                                        className={`flex items-center justify-between p-2 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded border-l-4 ${isHighlighted ? "ring-2 ring-primary" : ""}`}
                                        // force min border width for visibility in dense layouts
                                        style={{
                                          borderLeftColor: color,
                                          borderLeftWidth: 6,
                                        }}
                                      >
                                        <div className="flex items-center gap-2">
                                          <div className="w-6 h-6 flex items-center justify-center">
                                            <img
                                              src={`entities/tokens/${token.symbol.toUpperCase()}.png`}
                                              alt={token.symbol}
                                              className="w-6 h-6 object-contain"
                                              onError={e => {
                                                e.currentTarget.style.display =
                                                  "none"
                                                const parent =
                                                  e.currentTarget.parentElement
                                                if (parent) {
                                                  parent.innerHTML = `<div class="w-6 h-6 rounded-full bg-gray-300 dark:bg-gray-600 flex items-center justify-center"><span class="text-gray-700 dark:text-gray-300 text-xs font-bold">${token.symbol.slice(0, 2)}</span></div>`
                                                }
                                              }}
                                            />
                                          </div>
                                          <div>
                                            <p className="text-sm font-medium">
                                              {getCryptoDisplayName(
                                                token.symbol,
                                                token.name,
                                              )}
                                            </p>
                                            <p className="text-xs text-gray-600 dark:text-gray-400">
                                              {token.amount.toLocaleString()}{" "}
                                              {token.symbol}
                                            </p>
                                          </div>
                                        </div>
                                        <div className="text-right">
                                          <p className="text-sm font-medium">
                                            {formatCurrency(
                                              calculateCryptoValue(
                                                token.amount,
                                                token.symbol,
                                                settings.general
                                                  .defaultCurrency,
                                                exchangeRates,
                                              ),
                                              locale,
                                              settings.general.defaultCurrency,
                                            )}
                                          </p>
                                        </div>
                                      </div>
                                    )
                                  })}
                                </div>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                </motion.div>
              ),
            )}
          </motion.div>
        </div>
      )}
    </div>
  )
}
