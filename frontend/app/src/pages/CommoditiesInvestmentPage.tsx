import React, { useState, useEffect, useMemo, useCallback, useRef } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { fadeListContainer, fadeListItem } from "@/lib/animations"
import { useNavigate } from "react-router-dom"
import {
  ArrowLeft,
  Plus,
  Save,
  Edit3,
  Trash2,
  X,
  Layers,
  Scale,
  TrendingUp,
  TrendingDown,
  MoreVertical,
  ChevronDown,
} from "lucide-react"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardFooter,
} from "@/components/ui/Card"
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
  COMMODITY_SYMBOLS,
} from "@/types/position"
import { CommodityRegister } from "@/types"
import { saveCommodity } from "@/services/api"
import { convertWeight, convertCurrency } from "@/utils/financialDataUtils"
import { CommodityIcon, CommodityIconsStack } from "@/utils/commodityIcons"
import { cn, getCurrencySymbol } from "@/lib/utils"
import { formatCurrency } from "@/lib/formatters"
import { PinAssetButton } from "@/components/ui/PinAssetButton"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover"

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
  const [editingCommodityId, setEditingCommodityId] = useState<string | null>(
    null,
  )
  const [editingDraft, setEditingDraft] = useState<CommodityEntry | null>(null)
  const [hasChanges, setHasChanges] = useState(false)
  const [fieldErrors, setFieldErrors] = useState<
    Record<string, { name?: string; amount?: string }>
  >({})
  const [expandedCards, setExpandedCards] = useState<Record<string, boolean>>(
    {},
  )

  const toggleCardExpanded = useCallback((key: string) => {
    setExpandedCards(prev => ({ ...prev, [key]: !prev[key] }))
  }, [])

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
    Object.values(positionsData.positions)
      .flat()
      .forEach(entityPosition => {
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

  const editingCommodity = useMemo(() => {
    if (!editingCommodityId) return null
    return commodities.find(c => c.id === editingCommodityId) || null
  }, [commodities, editingCommodityId])

  useEffect(() => {
    if (!editingCommodity) {
      setEditingDraft(null)
      return
    }
    setEditingDraft({ ...editingCommodity })
  }, [editingCommodity])

  const updateDraftField = (
    field: keyof Commodity,
    value: Commodity[keyof Commodity],
  ) => {
    setEditingDraft(prev => (prev ? { ...prev, [field]: value } : prev))
    setFieldErrors(prev => {
      if (!editingCommodityId) return prev
      const copy = { ...prev }
      const ce = copy[editingCommodityId] ? { ...copy[editingCommodityId] } : {}
      if (field === "name" && ce.name) delete ce.name
      if (field === "amount" && ce.amount) delete ce.amount
      if (Object.keys(ce).length) copy[editingCommodityId] = ce
      else delete copy[editingCommodityId]
      return copy
    })
  }

  const handleSaveEdit = () => {
    if (!editingCommodity || !editingDraft) return
    updateCommodity(editingCommodity.id, "name", editingDraft.name)
    updateCommodity(editingCommodity.id, "amount", editingDraft.amount)
    updateCommodity(editingCommodity.id, "unit", editingDraft.unit)
    updateCommodity(
      editingCommodity.id,
      "initial_investment",
      editingDraft.initial_investment,
    )
    updateCommodity(
      editingCommodity.id,
      "average_buy_price",
      editingDraft.average_buy_price,
    )
    updateCommodity(editingCommodity.id, "currency", editingDraft.currency)
    setEditingCommodityId(null)
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

  const commodityPricePerUnit = useMemo(() => {
    const prices: Partial<Record<CommodityType, number>> = {}
    if (!exchangeRates) return prices
    const rates = exchangeRates[defaultCurrency]
    if (!rates) return prices
    Object.values(CommodityType).forEach(type => {
      const symbol = COMMODITY_SYMBOLS[type]
      const rate = rates[symbol]
      if (rate && rate > 0) {
        const pricePerTroyOunce = 1 / rate
        const unitMultiplier = convertWeight(
          1,
          displayUnit as WeightUnit,
          WeightUnit.TROY_OUNCE,
        )
        prices[type] = pricePerTroyOunce * unitMultiplier
      }
    })
    return prices
  }, [exchangeRates, defaultCurrency, displayUnit])

  const groupedSorted = useMemo(() => {
    const typeTotals = new Map<CommodityType, number>()
    commoditiesWithComputed.forEach(c => {
      const value =
        c.convertedMarket !== null
          ? c.convertedMarket
          : c.valueForDistribution || 0
      typeTotals.set(c.type, (typeTotals.get(c.type) || 0) + value)
    })
    return Object.entries(grouped)
      .map(([type, list]) => ({
        type: type as CommodityType,
        list,
        groupTotal: typeTotals.get(type as CommodityType) || 0,
      }))
      .sort((a, b) => b.groupTotal - a.groupTotal)
  }, [grouped, commoditiesWithComputed])

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
    <div className="space-y-6 w-full">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-3 min-w-0">
          <Button
            variant="ghost"
            size="sm"
            className="p-1 h-8 w-8"
            onClick={() => navigate(-1)}
          >
            <ArrowLeft size={20} />
          </Button>
          <h2 className="text-2xl font-bold flex items-center gap-2 min-w-0">
            {t.commodityManagement.title}
            <PinAssetButton
              assetId="commodities"
              size="icon"
              className="hidden md:inline-flex"
            />
          </h2>
        </div>
        <div className="flex flex-wrap items-center justify-center [@media(min-width:450px)]:justify-end gap-2 w-full [@media(min-width:450px)]:w-auto">
          <Button
            variant="default"
            size="sm"
            onClick={() => setShowAddForm(true)}
            className="flex items-center gap-2"
          >
            <Plus className="h-3.5 w-3.5" />
            {t.common.add}
          </Button>
          {hasChanges && (
            <Button
              size="sm"
              onClick={saveChanges}
              disabled={isSaving}
              className="flex items-center gap-2"
            >
              <Save className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
      </div>

      {commodities.length > 0 && (
        <Card className="-mx-6 rounded-none border-x-0">
          <CardContent className="pt-6">
            <InvestmentDistributionChart
              data={chartData}
              title={t.common.distribution}
              locale={locale}
              currency={defaultCurrency}
              hideLegend
              containerClassName="overflow-visible w-full"
              variant="bare"
              onSliceClick={handleSliceClick}
              toggleConfig={{
                activeView: "asset",
                onViewChange: () => {},
                options: [{ value: "asset", label: t.investments.byAsset }],
              }}
              badges={[
                {
                  icon: <Layers className="h-3 w-3" />,
                  value: `${commodities.length} ${commodities.length === 1 ? t.investments.asset : t.investments.assets}`,
                },
                {
                  icon: <Scale className="h-3 w-3" />,
                  value: `${aggregates.totalWeight.toFixed(2)} ${t.enums.weightUnit[aggregates.displayUnit as WeightUnit]}`,
                },
              ]}
              centerContent={{
                rawValue: totalValue,
                gainPercentage:
                  totalInitialInvestmentConverted > 0
                    ? (percentageChange ?? undefined)
                    : undefined,
                infoRows: [
                  {
                    label: t.dashboard.totalValue,
                    value: formatCurrency(totalValue, locale, defaultCurrency),
                  },
                  ...(totalInitialInvestmentConverted > 0
                    ? [
                        {
                          label: t.dashboard.investedAmount,
                          value: formatCurrency(
                            totalInitialInvestmentConverted,
                            locale,
                            defaultCurrency,
                          ),
                        },
                        {
                          label: t.investments.sortAbsoluteGain,
                          value: `${totalValue - totalInitialInvestmentConverted >= 0 ? "+" : ""}${formatCurrency(
                            totalValue - totalInitialInvestmentConverted,
                            locale,
                            defaultCurrency,
                          )}`,
                          valueClassName:
                            totalValue - totalInitialInvestmentConverted >= 0
                              ? "text-green-500"
                              : "text-red-500",
                        },
                      ]
                    : []),
                ],
              }}
            />
          </CardContent>
        </Card>
      )}

      <AnimatePresence>
        {showAddForm && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-[18000]"
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              transition={{ duration: 0.2, ease: "easeOut" }}
              className="w-full max-w-3xl"
            >
              <Card className="max-h-[calc(100vh-2rem)] flex flex-col relative">
                <CardHeader className="pr-12">
                  <CardTitle className="text-lg flex items-center gap-2">
                    <CommodityIcon
                      type={
                        (newEntry.type || CommodityType.GOLD) as CommodityType
                      }
                      size="sm"
                    />
                    {t.commodityManagement.addEntry}
                  </CardTitle>
                </CardHeader>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setShowAddForm(false)}
                  className="absolute top-4 right-4"
                >
                  <X className="h-4 w-4" />
                </Button>
                <CardContent className="space-y-4 flex-1 overflow-y-auto">
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
                            average_buy_price:
                              parseFloat(e.target.value) || null,
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
                        !newEntry.name ||
                        !newEntry.amount ||
                        newEntry.amount <= 0
                      }
                    >
                      {t.common.add}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
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
          {groupedSorted.map(({ type, list, groupTotal }) => {
            const typedType = type
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
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-medium text-gray-700 dark:text-gray-300 flex items-center gap-2">
                    <CommodityIcon type={typedType} size="md" />{" "}
                    {t.enums.commodityType[typedType]}
                    {commodityPricePerUnit[typedType] != null &&
                      commodityPricePerUnit[typedType]! > 0 && (
                        <span className="text-xs font-normal text-gray-400 dark:text-gray-500">
                          {formatCurrency(
                            commodityPricePerUnit[typedType]!,
                            locale,
                            defaultCurrency,
                          )}
                          /{t.enums.weightUnit[displayUnit as WeightUnit]}
                        </span>
                      )}
                  </h3>
                  {groupTotal > 0 && (
                    <span className="text-xl font-bold">
                      {formatCurrency(groupTotal, locale, defaultCurrency)}
                    </span>
                  )}
                </div>
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

                    const hasRoi =
                      details &&
                      details.convertedMarket !== null &&
                      details.convertedInitial > 0
                    const roiAmount = hasRoi
                      ? details.convertedMarket! - details.convertedInitial
                      : null
                    const roiPercent =
                      hasRoi && details.convertedInitial > 0
                        ? ((details.convertedMarket! -
                            details.convertedInitial) /
                            details.convertedInitial) *
                          100
                        : null

                    const isExpanded = expandedCards[c.id] ?? false

                    return (
                      <Card
                        key={c.id}
                        className={cn(
                          "transition-all overflow-hidden",
                          c.isModified && "ring-2 ring-blue-500",
                        )}
                      >
                        <div
                          className="p-4 cursor-pointer hover:bg-accent/40 transition-colors"
                          role="button"
                          tabIndex={0}
                          aria-expanded={isExpanded}
                          onClick={e => {
                            if (
                              (e.target as HTMLElement).closest(
                                "[data-no-expand]",
                              )
                            )
                              return
                            toggleCardExpanded(c.id)
                          }}
                          onKeyDown={e => {
                            if (e.key === "Enter" || e.key === " ") {
                              e.preventDefault()
                              toggleCardExpanded(c.id)
                            }
                          }}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <h4 className="font-medium text-gray-900 dark:text-gray-100">
                                  {c.name}
                                </h4>
                                {c.isModified && (
                                  <span className="h-2 w-2 rounded-full bg-blue-500 flex-shrink-0" />
                                )}
                              </div>
                              <p className="text-sm text-gray-600 dark:text-gray-400 mt-0.5">
                                {formatWeight(c.amount, c.unit)}
                              </p>
                            </div>
                            <div className="flex items-start gap-1 flex-shrink-0">
                              <div className="text-right">
                                {formattedEntryValue && (
                                  <p className="font-semibold text-gray-900 dark:text-gray-100">
                                    {formattedEntryValue}
                                  </p>
                                )}
                                {roiPercent !== null && (
                                  <p
                                    className={cn(
                                      "text-xs font-medium",
                                      roiPercent >= 0
                                        ? "text-green-500"
                                        : "text-red-500",
                                    )}
                                  >
                                    {roiPercent >= 0 ? "+" : ""}
                                    {roiPercent.toFixed(2)}%
                                  </p>
                                )}
                              </div>
                              <div className="flex flex-col items-center">
                                <div data-no-expand>
                                  <Popover>
                                    <PopoverTrigger asChild>
                                      <Button
                                        variant="ghost"
                                        size="icon"
                                        className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground"
                                        type="button"
                                      >
                                        <MoreVertical className="h-4 w-4" />
                                      </Button>
                                    </PopoverTrigger>
                                    <PopoverContent
                                      align="end"
                                      sideOffset={8}
                                      className="w-44 p-2 space-y-1"
                                    >
                                      <button
                                        type="button"
                                        onClick={() =>
                                          setEditingCommodityId(c.id)
                                        }
                                        className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm font-medium text-left transition-colors hover:bg-accent hover:text-accent-foreground"
                                      >
                                        <Edit3 className="h-3.5 w-3.5" />
                                        {t.common.edit}
                                      </button>
                                      <button
                                        type="button"
                                        onClick={() =>
                                          requestDeleteCommodity(c)
                                        }
                                        className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm font-medium text-left text-red-600 transition-colors hover:bg-red-50 hover:text-red-700 dark:hover:bg-red-500/10"
                                      >
                                        <Trash2 className="h-3.5 w-3.5" />
                                        {t.common.delete}
                                      </button>
                                    </PopoverContent>
                                  </Popover>
                                </div>
                                <ChevronDown
                                  className={cn(
                                    "h-4 w-4 text-muted-foreground transition-transform duration-200",
                                    isExpanded && "rotate-180",
                                  )}
                                />
                              </div>
                            </div>
                          </div>
                        </div>

                        <AnimatePresence initial={false}>
                          {isExpanded && (
                            <motion.div
                              initial={{ height: 0, opacity: 0 }}
                              animate={{ height: "auto", opacity: 1 }}
                              exit={{ height: 0, opacity: 0 }}
                              transition={{ duration: 0.2, ease: "easeInOut" }}
                              className="overflow-hidden"
                            >
                              <div className="px-4 pb-4 pt-1 space-y-2 border-t border-border">
                                {roiAmount !== null && roiPercent !== null && (
                                  <div className="flex items-center justify-between text-sm pt-2">
                                    <span className="text-gray-500 dark:text-gray-400">
                                      {t.investments.sortAbsoluteGain}
                                    </span>
                                    <div
                                      className={cn(
                                        "flex items-center gap-1 font-medium",
                                        roiAmount >= 0
                                          ? "text-green-500"
                                          : "text-red-500",
                                      )}
                                    >
                                      {roiAmount >= 0 ? (
                                        <TrendingUp size={14} />
                                      ) : (
                                        <TrendingDown size={14} />
                                      )}
                                      <span>
                                        {roiAmount >= 0 ? "+" : ""}
                                        {formatCurrency(
                                          roiAmount,
                                          locale,
                                          defaultCurrency,
                                        )}
                                      </span>
                                      <span className="text-xs opacity-80">
                                        ({roiPercent >= 0 ? "+" : ""}
                                        {roiPercent.toFixed(2)}%)
                                      </span>
                                    </div>
                                  </div>
                                )}
                                {details && details.convertedInitial > 0 && (
                                  <div className="flex items-center justify-between text-sm pt-2">
                                    <span className="text-gray-500 dark:text-gray-400">
                                      {t.commodityManagement.initialInvestment}
                                    </span>
                                    <span className="text-gray-900 dark:text-gray-100 font-medium">
                                      {formatCurrency(
                                        details.convertedInitial,
                                        locale,
                                        defaultCurrency,
                                      )}
                                    </span>
                                  </div>
                                )}
                                <div className="text-sm text-gray-600 dark:text-gray-400">
                                  <span className="font-medium text-blue-600 dark:text-blue-400">
                                    {percentageOfPortfolio.toFixed(1)}%
                                  </span>{" "}
                                  {t.investments.ofInvestmentType.replace(
                                    "{type}",
                                    t.common.commodities.toLowerCase(),
                                  )}
                                </div>
                              </div>
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </Card>
                    )
                  })}
                </div>
              </motion.div>
            )
          })}
        </motion.div>
      )}
      <AnimatePresence>
        {editingCommodity && editingDraft && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-[18000]"
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              transition={{ duration: 0.2, ease: "easeOut" }}
              className="w-full max-w-3xl"
            >
              <Card className="max-h-[calc(100vh-2rem)] flex flex-col relative">
                <CardHeader className="pr-12">
                  <CardTitle className="text-lg flex items-center gap-2">
                    <CommodityIcon type={editingCommodity.type} size="sm" />
                    {editingCommodity.name}
                  </CardTitle>
                </CardHeader>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setEditingCommodityId(null)}
                  className="absolute top-4 right-4"
                >
                  <X className="h-4 w-4" />
                </Button>
                <CardContent className="space-y-4 flex-1 overflow-y-auto">
                  <div className="flex items-end gap-2">
                    <div className="flex-1">
                      <Label htmlFor={`name-${editingCommodity.id}`}>
                        {t.commodityManagement.name}
                      </Label>
                      <Input
                        id={`name-${editingCommodity.id}`}
                        value={editingDraft.name}
                        onChange={e => updateDraftField("name", e.target.value)}
                        className={cn(
                          fieldErrors[editingCommodity.id]?.name &&
                            "border-red-500",
                        )}
                      />
                      {fieldErrors[editingCommodity.id]?.name && (
                        <p className="text-red-500 text-xs mt-1">
                          {fieldErrors[editingCommodity.id].name}
                        </p>
                      )}
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => requestDeleteCommodity(editingCommodity)}
                      className="p-1 h-8 w-8 text-red-500 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-900/20"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor={`amount-${editingCommodity.id}`}>
                        {t.commodityManagement.amount}
                      </Label>
                      <Input
                        id={`amount-${editingCommodity.id}`}
                        type="number"
                        step="0.0001"
                        value={editingDraft.amount || ""}
                        onChange={e => {
                          const v = e.target.value
                          updateDraftField(
                            "amount",
                            v === "" ? 0 : parseFloat(v) || 0,
                          )
                        }}
                        onFocus={e => {
                          if (e.target.value === "0") e.target.select()
                        }}
                        className={cn(
                          fieldErrors[editingCommodity.id]?.amount &&
                            "border-red-500",
                        )}
                      />
                      {fieldErrors[editingCommodity.id]?.amount && (
                        <p className="text-red-500 text-xs mt-1">
                          {fieldErrors[editingCommodity.id].amount}
                        </p>
                      )}
                    </div>
                    <div>
                      <Label htmlFor={`unit-${editingCommodity.id}`}>
                        {t.commodityManagement.unit}
                      </Label>
                      <select
                        id={`unit-${editingCommodity.id}`}
                        value={editingDraft.unit}
                        onChange={e => updateDraftField("unit", e.target.value)}
                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 appearance-none leading-tight"
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
                      <Label
                        htmlFor={`initial-investment-${editingCommodity.id}`}
                      >
                        {t.commodityManagement.initialInvestment}{" "}
                        {editingDraft.currency &&
                          `(${getCurrencySymbol(editingDraft.currency)})`}
                      </Label>
                      <Input
                        id={`initial-investment-${editingCommodity.id}`}
                        type="number"
                        step="0.01"
                        value={editingDraft.initial_investment || ""}
                        onChange={e =>
                          updateDraftField(
                            "initial_investment",
                            parseFloat(e.target.value) || null,
                          )
                        }
                      />
                    </div>
                    <div className="md:col-span-5">
                      <Label
                        htmlFor={`average-buy-price-${editingCommodity.id}`}
                      >
                        {t.commodityManagement.averageBuyPrice}{" "}
                        {editingDraft.currency &&
                          editingDraft.unit &&
                          `(${getCurrencySymbol(editingDraft.currency)}/${t.enums.weightUnit[editingDraft.unit]})`}
                      </Label>
                      <Input
                        id={`average-buy-price-${editingCommodity.id}`}
                        type="number"
                        step="0.01"
                        value={editingDraft.average_buy_price || ""}
                        onChange={e =>
                          updateDraftField(
                            "average_buy_price",
                            parseFloat(e.target.value) || null,
                          )
                        }
                      />
                    </div>
                    <div className="md:col-span-2">
                      <Label htmlFor={`currency-${editingCommodity.id}`}>
                        {t.commodityManagement.currency}
                      </Label>
                      <select
                        id={`currency-${editingCommodity.id}`}
                        value={editingDraft.currency || ""}
                        onChange={e =>
                          updateDraftField("currency", e.target.value || null)
                        }
                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 appearance-none leading-tight"
                      >
                        {supportedCurrencies.map(cur => (
                          <option key={cur} value={cur}>
                            {getCurrencySymbol(cur)} {cur}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                </CardContent>
                <CardFooter className="flex flex-wrap justify-end gap-2">
                  <Button
                    variant="outline"
                    onClick={() => setEditingCommodityId(null)}
                    className="whitespace-nowrap"
                  >
                    {t.common.cancel}
                  </Button>
                  <Button
                    onClick={handleSaveEdit}
                    className="whitespace-nowrap"
                  >
                    {t.common.save}
                  </Button>
                </CardFooter>
              </Card>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
      {deleteTarget && (
        <div className="fixed inset-0 flex items-center justify-center bg-black/40 z-[19000] p-4">
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
