import React, { useState, useEffect, useMemo, useCallback, useRef } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { fadeListContainer, fadeListItem } from "@/lib/animations"
import { useNavigate } from "react-router-dom"
import {
  ArrowLeft,
  Plus,
  Save,
  Edit,
  ChevronDown,
  ChevronUp,
  Trash2,
} from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import { InvestmentDistributionChart } from "@/components/InvestmentDistributionChart"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { Label } from "@/components/ui/Label"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import { useI18n } from "@/i18n"
import { useAppContext } from "@/context/AppContext"
import { useFinancialData } from "@/context/FinancialDataContext"
import {
  Commodity,
  CommodityType,
  WeightUnit,
  ProductType,
  Commodities,
} from "@/types/position"
import { CommodityRegister } from "@/types"
import { saveCommodity } from "@/services/api"
import { convertWeight, convertCurrency } from "@/utils/financialDataUtils"
import { CommodityIcon, CommodityIconsStack } from "@/utils/commodityIcons"
import { cn, getCurrencySymbol } from "@/lib/utils"
import { formatCurrency, formatPercentage } from "@/lib/formatters"
import { PinAssetButton } from "@/components/ui/PinAssetButton"

interface CommodityEntry extends Commodity {
  isExpanded: boolean
  isModified: boolean
}

interface CommodityComputed extends CommodityEntry {
  currency: string
  convertedInitial: number
  convertedMarket: number | null
  convertedWeight: number
  valueForDistribution: number
}

const commodityTypeColors: Record<CommodityType, string> = {
  [CommodityType.GOLD]: "#f4b400",
  [CommodityType.SILVER]: "#9ca3af",
  [CommodityType.PLATINUM]: "#6b7280",
  [CommodityType.PALLADIUM]: "#94a3b8",
}

export default function CommoditiesInvestmentPage() {
  const { t, locale } = useI18n()
  const navigate = useNavigate()
  const { settings, showToast, exchangeRates } = useAppContext()
  const { positionsData, refreshData } = useFinancialData()

  const defaultCurrency = settings?.general?.defaultCurrency ?? "EUR"
  const displayUnit =
    settings?.general?.defaultCommodityWeightUnit || WeightUnit.TROY_OUNCE

  const [deleteTarget, setDeleteTarget] = useState<CommodityEntry | null>(null)
  const [commodities, setCommodities] = useState<CommodityEntry[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [showAddForm, setShowAddForm] = useState(false)
  const [hasChanges, setHasChanges] = useState(false)
  const [fieldErrors, setFieldErrors] = useState<
    Record<string, { name?: string; amount?: string }>
  >({})

  const [newEntry, setNewEntry] = useState<Partial<CommodityRegister>>({
    name: "",
    amount: 0,
    unit:
      (settings?.general?.defaultCommodityWeightUnit as WeightUnit) ||
      WeightUnit.TROY_OUNCE,
    type: CommodityType.GOLD,
    initial_investment: null,
    average_buy_price: null,
    currency: settings?.general?.defaultCurrency || null,
  })

  const supportedCurrencies = useMemo(() => {
    const base = ["EUR", "USD"]
    if (defaultCurrency && !base.includes(defaultCurrency)) {
      base.unshift(defaultCurrency)
    }
    return Array.from(new Set(base))
  }, [defaultCurrency])

  const getAllCommodityEntries = (): CommodityEntry[] => {
    if (!positionsData?.positions) return []
    const all: CommodityEntry[] = []
    Object.values(positionsData.positions).forEach(entityPosition => {
      if (entityPosition?.products[ProductType.COMMODITY]) {
        const commodityProduct = entityPosition.products[
          ProductType.COMMODITY
        ] as Commodities
        if (
          "entries" in commodityProduct &&
          commodityProduct.entries.length > 0
        ) {
          all.push(
            ...commodityProduct.entries.map(c => ({
              ...c,
              isExpanded: false,
              isModified: false,
            })),
          )
        }
      }
    })
    return all
  }

  useEffect(() => {
    if (positionsData !== null) {
      setCommodities(getAllCommodityEntries())
      setIsLoading(false)
    }
  }, [positionsData])

  const grouped = useMemo(
    () =>
      commodities.reduce(
        (acc, c) => {
          if (!acc[c.type]) acc[c.type] = []
          acc[c.type].push(c)
          return acc
        },
        {} as Record<CommodityType, CommodityEntry[]>,
      ),
    [commodities],
  )

  const formatWeight = (amount: number, unit: WeightUnit) => {
    const displayUnit =
      settings?.general?.defaultCommodityWeightUnit || WeightUnit.TROY_OUNCE
    const converted = convertWeight(amount, unit, displayUnit as WeightUnit)
    return `${converted.toFixed(2)} ${t.enums.weightUnit[displayUnit as WeightUnit]}`
  }

  const toggleExpanded = (id: string) =>
    setCommodities(prev =>
      prev.map(c => (c.id === id ? { ...c, isExpanded: !c.isExpanded } : c)),
    )

  const updateCommodity = (id: string, field: keyof Commodity, value: any) => {
    setCommodities(prev =>
      prev.map(c =>
        c.id === id ? { ...c, [field]: value, isModified: true } : c,
      ),
    )
    setHasChanges(true)
    setFieldErrors(prev => {
      const copy = { ...prev }
      const ce = copy[id] ? { ...copy[id] } : {}
      if (field === "name" && ce.name) delete ce.name
      if (field === "amount" && ce.amount) delete ce.amount
      if (Object.keys(ce).length) copy[id] = ce
      else delete copy[id]
      return copy
    })
  }

  const requestDeleteCommodity = (commodity: CommodityEntry) => {
    setDeleteTarget(commodity)
  }
  const confirmDelete = () => {
    if (deleteTarget) {
      setCommodities(prev => prev.filter(c => c.id !== deleteTarget.id))
      setHasChanges(true)
    }
    setDeleteTarget(null)
  }
  const cancelDelete = () => setDeleteTarget(null)

  const addNewEntry = () => {
    if (!newEntry.name || !newEntry.amount || newEntry.amount <= 0) return
    const created: CommodityEntry = {
      id: `new-${Date.now()}`,
      name: newEntry.name,
      amount: newEntry.amount,
      unit: newEntry.unit!,
      type: newEntry.type!,
      initial_investment: newEntry.initial_investment,
      average_buy_price: newEntry.average_buy_price,
      currency: newEntry.currency,
      market_value: null,
      isExpanded: false,
      isModified: true,
    }
    setCommodities(prev => [...prev, created])
    setNewEntry({
      name: "",
      amount: 0,
      unit:
        (settings?.general?.defaultCommodityWeightUnit as WeightUnit) ||
        WeightUnit.TROY_OUNCE,
      type: CommodityType.GOLD,
      initial_investment: null,
      average_buy_price: null,
      currency: settings?.general?.defaultCurrency || null,
    })
    setShowAddForm(false)
    setHasChanges(true)
  }

  const saveChanges = async () => {
    if (!hasChanges) return
    const errors: Record<string, { name?: string; amount?: string }> = {}
    commodities.forEach(c => {
      if (!c.name.trim()) {
        errors[c.id] = {
          ...(errors[c.id] || {}),
          name: t.commodityManagement.nameRequired,
        }
      }
      if (c.amount <= 0) {
        errors[c.id] = {
          ...(errors[c.id] || {}),
          amount: t.commodityManagement.amountRequired,
        }
      }
    })
    if (Object.keys(errors).length) {
      setFieldErrors(errors)
      return
    }
    setFieldErrors({})
    setIsSaving(true)
    try {
      const payload: CommodityRegister[] = commodities.map(c => ({
        name: c.name,
        amount: c.amount,
        unit: c.unit,
        type: c.type,
        initial_investment: c.initial_investment,
        average_buy_price: c.average_buy_price,
        currency: c.currency,
      }))
      await saveCommodity({ registers: payload })
      await refreshData()
      setHasChanges(false)
      showToast(t.commodityManagement.saveSuccess, "success")
    } catch (e) {
      console.error("Error saving commodities", e)
      showToast(t.commodityManagement.saveError, "error")
    } finally {
      setIsSaving(false)
    }
  }

  const aggregates = useMemo(() => {
    const byCurrency: Record<string, number> = {}
    let totalInitialInvestment = 0
    commodities.forEach(c => {
      if (c.initial_investment != null && c.currency) {
        byCurrency[c.currency] =
          (byCurrency[c.currency] || 0) + c.initial_investment
        totalInitialInvestment += c.initial_investment
      }
    })
    const totalWeight = commodities.reduce(
      (sum, c) =>
        sum + convertWeight(c.amount, c.unit, displayUnit as WeightUnit),
      0,
    )
    return { byCurrency, displayUnit, totalWeight, totalInitialInvestment }
  }, [commodities, displayUnit])

  const commoditiesWithComputed = useMemo<CommodityComputed[]>(() => {
    return commodities.map(c => {
      const currency = (c.currency || defaultCurrency) as string
      const initialOriginal = c.initial_investment ?? 0
      const marketOriginal = c.market_value ?? null
      const convertedInitial = convertCurrency(
        initialOriginal,
        currency,
        defaultCurrency,
        exchangeRates ?? null,
      )
      const convertedMarket =
        marketOriginal !== null && marketOriginal !== undefined
          ? convertCurrency(
              marketOriginal,
              currency,
              defaultCurrency,
              exchangeRates ?? null,
            )
          : null
      const convertedWeight = convertWeight(
        c.amount,
        c.unit,
        displayUnit as WeightUnit,
      )
      const valueForDistribution =
        convertedMarket !== null && convertedMarket !== undefined
          ? convertedMarket
          : convertedInitial

      return {
        ...c,
        currency,
        convertedInitial,
        convertedMarket,
        convertedWeight,
        valueForDistribution,
      }
    })
  }, [commodities, defaultCurrency, displayUnit, exchangeRates])

  const totalValue = useMemo(
    () =>
      commoditiesWithComputed.reduce(
        (sum, c) =>
          sum +
          (c.convertedMarket !== null
            ? c.convertedMarket
            : c.valueForDistribution || 0),
        0,
      ),
    [commoditiesWithComputed],
  )

  const totalInitialInvestmentConverted = useMemo(
    () =>
      commoditiesWithComputed.reduce(
        (sum, c) => sum + (c.convertedInitial || 0),
        0,
      ),
    [commoditiesWithComputed],
  )

  const totalConvertedWeight = useMemo(
    () =>
      commoditiesWithComputed.reduce((sum, c) => sum + c.convertedWeight, 0),
    [commoditiesWithComputed],
  )

  const formattedTotalValue = useMemo(
    () => formatCurrency(totalValue, locale, defaultCurrency),
    [totalValue, locale, defaultCurrency],
  )

  const percentageChange = useMemo(() => {
    if (!totalInitialInvestmentConverted) return null
    if (totalInitialInvestmentConverted === 0) return null
    const delta = totalValue - totalInitialInvestmentConverted
    return (delta / totalInitialInvestmentConverted) * 100
  }, [totalValue, totalInitialInvestmentConverted])

  const chartData = useMemo(() => {
    const groupedByType = commoditiesWithComputed.reduce(
      (acc, commodity) => {
        const value = commodity.valueForDistribution || 0
        if (value <= 0) {
          return acc
        }
        if (!acc[commodity.type]) {
          acc[commodity.type] = 0
        }
        acc[commodity.type] += value
        return acc
      },
      {} as Record<CommodityType, number>,
    )

    const entries = Object.entries(groupedByType)
      .map(([typeKey, totalValue]) => {
        if (totalValue <= 0) return null
        const typedType = typeKey as CommodityType
        return {
          id: typedType,
          type: typedType,
          name: t.enums.commodityType[typedType],
          value: totalValue,
        }
      })
      .filter(Boolean) as {
      id: CommodityType
      type: CommodityType
      name: string
      value: number
    }[]

    const total = entries.reduce((sum, entry) => sum + entry.value, 0)

    return entries.map(entry => ({
      ...entry,
      percentage: total > 0 ? (entry.value / total) * 100 : 0,
      color: commodityTypeColors[entry.type] ?? "#64748b",
      currency: defaultCurrency,
    }))
  }, [commoditiesWithComputed, defaultCurrency, t.enums.commodityType])

  const commodityDetailsLookup = useMemo(() => {
    const lookup: Record<string, CommodityComputed> = {}
    commoditiesWithComputed.forEach(c => {
      lookup[c.id] = c
    })
    return lookup
  }, [commoditiesWithComputed])

  const groupRefs = useRef<
    Partial<Record<CommodityType, HTMLDivElement | null>>
  >({})
  const [highlightedType, setHighlightedType] = useState<CommodityType | null>(
    null,
  )

  const handleSliceClick = useCallback(
    (slice: any) => {
      let targetType = slice?.id as CommodityType | undefined
      if (!targetType && slice?.name) {
        const match = (
          Object.entries(t.enums.commodityType) as [CommodityType, string][]
        ).find(([, label]) => label === slice.name)
        if (match) {
          targetType = match[0]
        }
      }
      if (!targetType) return
      const ref = groupRefs.current[targetType]
      if (ref) {
        ref.scrollIntoView({ behavior: "smooth", block: "start" })
        setHighlightedType(targetType)
        setTimeout(() => {
          setHighlightedType(prev => (prev === targetType ? null : prev))
        }, 1500)
      }
    },
    [t.enums.commodityType],
  )

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-6 w-full pb-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate(-1)}
            className="p-1 h-8 w-8"
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            {t.commodityManagement.title}
            <PinAssetButton assetId="commodities" />
          </h2>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="default"
            size="sm"
            onClick={() => setShowAddForm(true)}
            className="flex items-center gap-2"
          >
            <Plus className="h-4 w-4" /> {t.common.add}
          </Button>
          {hasChanges && (
            <Button
              size="sm"
              onClick={saveChanges}
              disabled={isSaving}
              className="flex items-center gap-2"
            >
              <Save className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>

      {commodities.length > 0 && (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 items-stretch">
          <div className="flex flex-col gap-4 xl:col-span-1 order-1 xl:order-1">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-gray-600 dark:text-gray-400">
                  {t.common.commodities}
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="flex justify-between items-baseline">
                  <p className="text-2xl font-bold">{formattedTotalValue}</p>
                  {percentageChange !== null && (
                    <p
                      className={`text-sm font-medium ${
                        percentageChange === 0
                          ? "text-gray-500 dark:text-gray-400"
                          : percentageChange > 0
                            ? "text-green-600 dark:text-green-400"
                            : "text-red-600 dark:text-red-400"
                      }`}
                    >
                      {percentageChange > 0
                        ? "+"
                        : percentageChange < 0
                          ? "-"
                          : ""}
                      {formatPercentage(Math.abs(percentageChange), locale)}
                    </p>
                  )}
                </div>
                {totalInitialInvestmentConverted > 0 && (
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    {t.dashboard.investedAmount}{" "}
                    {formatCurrency(
                      totalInitialInvestmentConverted,
                      locale,
                      defaultCurrency,
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
                <p className="text-2xl font-bold">{commodities.length}</p>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  {commodities.length === 1
                    ? t.investments.asset
                    : t.investments.assets}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-gray-600 dark:text-gray-400">
                  {t.commodityManagement.kpis.totalWeight}
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <p className="text-2xl font-bold">
                  {aggregates.totalWeight.toFixed(2)}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  {t.enums.weightUnit[aggregates.displayUnit as WeightUnit]}
                </p>
              </CardContent>
            </Card>
          </div>
          <div className="xl:col-span-2 order-2 xl:order-2 flex items-center">
            <InvestmentDistributionChart
              data={chartData}
              title={t.common.distribution}
              locale={locale}
              currency={defaultCurrency}
              hideLegend
              containerClassName="overflow-visible w-full"
              variant="bare"
              onSliceClick={handleSliceClick}
            />
          </div>
        </div>
      )}

      <AnimatePresence>
        {showAddForm && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <Card className="border-dashed border-2 border-gray-300 dark:border-gray-600">
              <CardHeader>
                <CardTitle className="text-lg">
                  {t.commodityManagement.addEntry}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="name">{t.commodityManagement.name}</Label>
                    <Input
                      id="name"
                      value={newEntry.name}
                      onChange={e =>
                        setNewEntry(p => ({ ...p, name: e.target.value }))
                      }
                      placeholder={t.commodityManagement.namePlaceholder}
                    />
                  </div>
                  <div>
                    <Label htmlFor="type">{t.commodityManagement.type}</Label>
                    <select
                      id="type"
                      value={newEntry.type}
                      onChange={e =>
                        setNewEntry(p => ({
                          ...p,
                          type: e.target.value as CommodityType,
                        }))
                      }
                      className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 appearance-none"
                    >
                      {Object.values(CommodityType).map(type => (
                        <option key={type} value={type}>
                          {t.enums.commodityType[type]}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <Label htmlFor="amount">
                      {t.commodityManagement.amount}
                    </Label>
                    <Input
                      id="amount"
                      type="number"
                      step="0.0001"
                      value={newEntry.amount || ""}
                      onChange={e => {
                        const value = e.target.value
                        setNewEntry(p => ({
                          ...p,
                          amount: value === "" ? 0 : parseFloat(value) || 0,
                        }))
                      }}
                      onFocus={e => {
                        if (e.target.value === "0") e.target.select()
                      }}
                    />
                  </div>
                  <div>
                    <Label htmlFor="unit">{t.commodityManagement.unit}</Label>
                    <select
                      id="unit"
                      value={newEntry.unit}
                      onChange={e =>
                        setNewEntry(p => ({
                          ...p,
                          unit: e.target.value as WeightUnit,
                        }))
                      }
                      className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 appearance-none leading-tight min-h-[2.5rem]"
                    >
                      {Object.values(WeightUnit).map(u => (
                        <option key={u} value={u}>
                          {t.enums.weightUnitName[u]}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-12 gap-4">
                  <div className="md:col-span-5">
                    <Label htmlFor="initial_investment">
                      {t.commodityManagement.initialInvestment}{" "}
                      {newEntry.currency &&
                        `(${getCurrencySymbol(newEntry.currency)})`}
                    </Label>
                    <Input
                      id="initial_investment"
                      type="number"
                      step="0.01"
                      value={newEntry.initial_investment || ""}
                      onChange={e =>
                        setNewEntry(p => ({
                          ...p,
                          initial_investment:
                            parseFloat(e.target.value) || null,
                        }))
                      }
                    />
                  </div>
                  <div className="md:col-span-5">
                    <Label htmlFor="average_buy_price">
                      {t.commodityManagement.averageBuyPrice}{" "}
                      {newEntry.currency &&
                        newEntry.unit &&
                        `(${getCurrencySymbol(newEntry.currency)}/${t.enums.weightUnit[newEntry.unit]})`}
                    </Label>
                    <Input
                      id="average_buy_price"
                      type="number"
                      step="0.01"
                      value={newEntry.average_buy_price || ""}
                      onChange={e =>
                        setNewEntry(p => ({
                          ...p,
                          average_buy_price: parseFloat(e.target.value) || null,
                        }))
                      }
                    />
                  </div>
                  <div className="md:col-span-2">
                    <Label htmlFor="currency">
                      {t.commodityManagement.currency}
                    </Label>
                    <select
                      id="currency"
                      value={newEntry.currency || ""}
                      onChange={e =>
                        setNewEntry(p => ({
                          ...p,
                          currency: e.target.value || null,
                        }))
                      }
                      className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 appearance-none leading-tight"
                    >
                      {supportedCurrencies.map(c => (
                        <option key={c} value={c}>
                          {getCurrencySymbol(c)} {c}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                <div className="flex justify-end gap-2">
                  <Button
                    variant="outline"
                    onClick={() => setShowAddForm(false)}
                  >
                    {t.common.cancel}
                  </Button>
                  <Button
                    onClick={addNewEntry}
                    disabled={
                      !newEntry.name || !newEntry.amount || newEntry.amount <= 0
                    }
                  >
                    {t.common.add}
                  </Button>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      {commodities.length === 0 ? (
        <Card className="p-14 text-center flex flex-col items-center gap-4">
          <CommodityIconsStack
            size="lg"
            overlap="md"
            className="justify-center"
          />
          <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100">
            {t.commodityManagement.noCommodities}
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 max-w-md">
            {t.commodityManagement.addFirstCommodity}
          </p>
        </Card>
      ) : (
        <motion.div
          variants={fadeListContainer}
          initial="hidden"
          animate="show"
          className="space-y-6"
        >
          {Object.entries(grouped).map(([type, list]) => {
            const typedType = type as CommodityType
            const isGroupHighlighted = highlightedType === typedType
            return (
              <motion.div
                key={type}
                variants={fadeListItem}
                ref={el => {
                  groupRefs.current[typedType] = el
                }}
                className={cn(
                  "space-y-3 scroll-mt-24",
                  isGroupHighlighted &&
                    "outline outline-2 outline-primary/60 outline-offset-4 rounded-lg",
                )}
              >
                <h3 className="text-lg font-medium text-gray-700 dark:text-gray-300 flex items-center gap-2">
                  <CommodityIcon type={typedType} size="md" />{" "}
                  {t.enums.commodityType[typedType]}
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 px-1 items-start">
                  {list.map(c => {
                    const details = commodityDetailsLookup[c.id]
                    const entryValue = details
                      ? details.valueForDistribution
                      : 0
                    const percentageOfPortfolio =
                      totalValue > 0
                        ? ((entryValue || 0) / totalValue) * 100
                        : totalConvertedWeight > 0
                          ? ((details?.convertedWeight || 0) /
                              totalConvertedWeight) *
                            100
                          : 0
                    const formattedEntryValue =
                      entryValue > 0
                        ? formatCurrency(entryValue, locale, defaultCurrency)
                        : null

                    return (
                      <Card
                        key={c.id}
                        className={`transition-all hover:shadow-md ${c.isModified ? "ring-2 ring-blue-500" : ""} ${c.isExpanded ? "h-auto" : "h-fit"}`}
                      >
                        <CardContent
                          className={`p-4 ${c.isExpanded ? "h-auto" : "h-fit"}`}
                        >
                          <div
                            className="flex items-center justify-between cursor-pointer"
                            onClick={() => toggleExpanded(c.id)}
                          >
                            <div className="flex-1">
                              <h4 className="font-medium text-gray-900 dark:text-gray-100 mb-1">
                                {c.name}
                              </h4>
                              <p className="text-sm text-gray-600 dark:text-gray-400">
                                {formatWeight(c.amount, c.unit)}
                              </p>
                              {formattedEntryValue && (
                                <p className="text-sm text-gray-500 dark:text-gray-400">
                                  {formattedEntryValue}
                                </p>
                              )}
                            </div>
                            <div className="flex items-center gap-2">
                              {c.isModified && (
                                <Edit className="h-4 w-4 text-blue-500" />
                              )}
                              {c.isExpanded ? (
                                <ChevronUp className="h-4 w-4 text-gray-400" />
                              ) : (
                                <ChevronDown className="h-4 w-4 text-gray-400" />
                              )}
                            </div>
                          </div>
                          <AnimatePresence>
                            {c.isExpanded && (
                              <motion.div
                                initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: "auto" }}
                                exit={{ opacity: 0, height: 0 }}
                                className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700 space-y-3"
                              >
                                <div className="flex items-end gap-2">
                                  <div className="flex-1">
                                    <Label
                                      htmlFor={`name-${c.id}`}
                                      className="text-xs"
                                    >
                                      {t.commodityManagement.name}
                                    </Label>
                                    <Input
                                      id={`name-${c.id}`}
                                      value={c.name}
                                      onChange={e =>
                                        updateCommodity(
                                          c.id,
                                          "name",
                                          e.target.value,
                                        )
                                      }
                                      className={cn(
                                        "h-8 text-sm",
                                        fieldErrors[c.id]?.name &&
                                          "border-red-500",
                                      )}
                                    />
                                    {fieldErrors[c.id]?.name && (
                                      <p className="text-red-500 text-xs mt-1">
                                        {fieldErrors[c.id].name}
                                      </p>
                                    )}
                                  </div>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={e => {
                                      e.stopPropagation()
                                      requestDeleteCommodity(c)
                                    }}
                                    className="p-1 h-8 w-8 text-red-500 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-900/20"
                                  >
                                    <Trash2 className="h-4 w-4" />
                                  </Button>
                                </div>
                                <div className="grid grid-cols-2 gap-2">
                                  <div>
                                    <Label
                                      htmlFor={`amount-${c.id}`}
                                      className="text-xs"
                                    >
                                      {t.commodityManagement.amount}
                                    </Label>
                                    <Input
                                      id={`amount-${c.id}`}
                                      type="number"
                                      step="0.0001"
                                      value={c.amount || ""}
                                      onChange={e => {
                                        const v = e.target.value
                                        updateCommodity(
                                          c.id,
                                          "amount",
                                          v === "" ? 0 : parseFloat(v) || 0,
                                        )
                                      }}
                                      onFocus={e => {
                                        if (e.target.value === "0")
                                          e.target.select()
                                      }}
                                      className={cn(
                                        "h-8 text-sm",
                                        fieldErrors[c.id]?.amount &&
                                          "border-red-500",
                                      )}
                                    />
                                    {fieldErrors[c.id]?.amount && (
                                      <p className="text-red-500 text-xs mt-1">
                                        {fieldErrors[c.id].amount}
                                      </p>
                                    )}
                                  </div>
                                  <div>
                                    <Label
                                      htmlFor={`unit-${c.id}`}
                                      className="text-xs"
                                    >
                                      {t.commodityManagement.unit}
                                    </Label>
                                    <select
                                      value={c.unit}
                                      onChange={e =>
                                        updateCommodity(
                                          c.id,
                                          "unit",
                                          e.target.value,
                                        )
                                      }
                                      className="flex h-8 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 appearance-none leading-tight min-h-[2rem]"
                                    >
                                      {Object.values(WeightUnit).map(u => (
                                        <option key={u} value={u}>
                                          {t.enums.weightUnitName[u]}
                                        </option>
                                      ))}
                                    </select>
                                  </div>
                                </div>
                                {(c.initial_investment !== null ||
                                  c.average_buy_price !== null ||
                                  c.currency) && (
                                  <div className="space-y-2">
                                    <div className="grid grid-cols-12 gap-2">
                                      <div className="col-span-5">
                                        <Label
                                          htmlFor={`initial-investment-${c.id}`}
                                          className="text-xs"
                                        >
                                          {
                                            t.commodityManagement
                                              .initialInvestment
                                          }{" "}
                                          {c.currency &&
                                            `(${getCurrencySymbol(c.currency)})`}
                                        </Label>
                                        <Input
                                          id={`initial-investment-${c.id}`}
                                          type="number"
                                          step="0.01"
                                          value={c.initial_investment || ""}
                                          onChange={e =>
                                            updateCommodity(
                                              c.id,
                                              "initial_investment",
                                              parseFloat(e.target.value) ||
                                                null,
                                            )
                                          }
                                          className="h-8 text-sm"
                                        />
                                      </div>
                                      <div className="col-span-5">
                                        <Label
                                          htmlFor={`average-buy-price-${c.id}`}
                                          className="text-xs"
                                        >
                                          {
                                            t.commodityManagement
                                              .averageBuyPrice
                                          }{" "}
                                          {c.currency &&
                                            c.unit &&
                                            `(${getCurrencySymbol(c.currency)}/${t.enums.weightUnit[c.unit]})`}
                                        </Label>
                                        <Input
                                          id={`average-buy-price-${c.id}`}
                                          type="number"
                                          step="0.01"
                                          value={c.average_buy_price || ""}
                                          onChange={e =>
                                            updateCommodity(
                                              c.id,
                                              "average_buy_price",
                                              parseFloat(e.target.value) ||
                                                null,
                                            )
                                          }
                                          className="h-8 text-sm"
                                        />
                                      </div>
                                      <div className="col-span-2">
                                        <Label
                                          htmlFor={`currency-${c.id}`}
                                          className="text-xs"
                                        >
                                          {t.commodityManagement.currency}
                                        </Label>
                                        <select
                                          value={c.currency || ""}
                                          onChange={e =>
                                            updateCommodity(
                                              c.id,
                                              "currency",
                                              e.target.value || null,
                                            )
                                          }
                                          className="flex h-8 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 appearance-none leading-tight min-h-[2rem]"
                                        >
                                          {supportedCurrencies.map(cur => (
                                            <option key={cur} value={cur}>
                                              {getCurrencySymbol(cur)}
                                            </option>
                                          ))}
                                        </select>
                                      </div>
                                    </div>
                                  </div>
                                )}
                              </motion.div>
                            )}
                          </AnimatePresence>
                          <div className="text-sm text-gray-600 dark:text-gray-400 mt-3">
                            <span className="font-medium text-blue-600 dark:text-blue-400">
                              {percentageOfPortfolio.toFixed(1)}%
                            </span>{" "}
                            {t.investments.ofInvestmentType.replace(
                              "{type}",
                              t.common.commodities.toLowerCase(),
                            )}
                          </div>
                        </CardContent>
                      </Card>
                    )
                  })}
                </div>
              </motion.div>
            )
          })}
        </motion.div>
      )}
      {deleteTarget && (
        <div className="fixed inset-0 flex items-center justify-center bg-black/40 z-50 p-4">
          <Card className="max-w-sm w-full">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg">
                {t.commodityManagement.deleteConfirmTitle}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-gray-600 dark:text-gray-400">
                {t.commodityManagement.deleteConfirmMessage.replace(
                  "{{name}}",
                  deleteTarget.name,
                )}
              </p>
              <div className="flex justify-end gap-2">
                <Button variant="outline" size="sm" onClick={cancelDelete}>
                  {t.common.cancel}
                </Button>
                <Button
                  size="sm"
                  onClick={confirmDelete}
                  className="bg-red-600 hover:bg-red-700 text-white"
                >
                  {t.common.delete}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
