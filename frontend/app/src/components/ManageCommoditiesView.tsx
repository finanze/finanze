import React, { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  ArrowLeft,
  Plus,
  Save,
  Edit,
  ChevronDown,
  ChevronUp,
  Trash2,
} from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "./ui/Card"
import { Button } from "./ui/Button"
import { Input } from "./ui/Input"
import { Label } from "./ui/Label"
import { useI18n } from "@/i18n"
import { useAppContext } from "@/context/AppContext"
import { useFinancialData } from "../context/FinancialDataContext"
import {
  Commodity,
  CommodityType,
  WeightUnit,
  ProductType,
  Commodities,
} from "../types/position"
import { CommodityRegister } from "../types"
import { saveCommodity } from "../services/api"
import { convertWeight } from "../utils/financialDataUtils"
import { CommodityIcon } from "../utils/commodityIcons"
import { cn } from "@/lib/utils"

interface ManageCommoditiesViewProps {
  onBack: () => void
}

interface CommodityEntry extends Commodity {
  isExpanded: boolean
  isModified: boolean
}

export function ManageCommoditiesView({ onBack }: ManageCommoditiesViewProps) {
  const { t } = useI18n()
  const { settings, showToast } = useAppContext()
  const { positionsData, refreshData } = useFinancialData()

  const [commodities, setCommodities] = useState<CommodityEntry[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [showAddForm, setShowAddForm] = useState(false)
  const [hasChanges, setHasChanges] = useState(false)
  const [fieldErrors, setFieldErrors] = useState<
    Record<string, { name?: string; amount?: string }>
  >({})

  // New entry form state
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

  // Currency symbols mapping
  const getCurrencySymbol = (currency: string | null) => {
    if (!currency) return ""
    switch (currency) {
      case "EUR":
        return "€"
      case "USD":
        return "$"
      default:
        return currency
    }
  }

  // Supported currencies
  const supportedCurrencies = ["EUR", "USD"]

  // Get all commodity entries from all entities
  const getAllCommodityEntries = (): CommodityEntry[] => {
    if (!positionsData?.positions) return []

    const allCommodities: CommodityEntry[] = []

    Object.values(positionsData.positions).forEach(entityPosition => {
      if (entityPosition?.products[ProductType.COMMODITY]) {
        const commodityProduct = entityPosition.products[
          ProductType.COMMODITY
        ] as Commodities
        if (
          "entries" in commodityProduct &&
          commodityProduct.entries.length > 0
        ) {
          const commodityEntries: CommodityEntry[] =
            commodityProduct.entries.map(commodity => ({
              ...commodity,
              isExpanded: false,
              isModified: false,
            }))
          allCommodities.push(...commodityEntries)
        }
      }
    })

    return allCommodities
  }

  useEffect(() => {
    // Always stop loading when data is available
    if (positionsData !== null) {
      const commodityEntries = getAllCommodityEntries()
      setCommodities(commodityEntries)
      setIsLoading(false)
    }
  }, [positionsData])

  // Group commodities by type
  const groupedCommodities = commodities.reduce(
    (acc, commodity) => {
      if (!acc[commodity.type]) {
        acc[commodity.type] = []
      }
      acc[commodity.type].push(commodity)
      return acc
    },
    {} as Record<CommodityType, CommodityEntry[]>,
  )

  const formatWeight = (amount: number, unit: WeightUnit) => {
    const displayUnit =
      settings?.general?.defaultCommodityWeightUnit || WeightUnit.TROY_OUNCE
    const convertedAmount = convertWeight(
      amount,
      unit,
      displayUnit as WeightUnit,
    )
    return `${convertedAmount.toFixed(2)} ${t.enums.weightUnit[displayUnit as WeightUnit]}`
  }

  const toggleExpanded = (commodityId: string) => {
    setCommodities(prev =>
      prev.map(commodity =>
        commodity.id === commodityId
          ? { ...commodity, isExpanded: !commodity.isExpanded }
          : commodity,
      ),
    )
  }

  const updateCommodity = (
    commodityId: string,
    field: keyof Commodity,
    value: any,
  ) => {
    setCommodities(prev =>
      prev.map(commodity =>
        commodity.id === commodityId
          ? { ...commodity, [field]: value, isModified: true }
          : commodity,
      ),
    )
    setHasChanges(true)
    // Clear field error for this commodity and field
    setFieldErrors(prev => {
      const errs = { ...prev }
      const commodityErr = errs[commodityId] ? { ...errs[commodityId] } : {}
      if (field === "name" && commodityErr.name) delete commodityErr.name
      if (field === "amount" && commodityErr.amount) delete commodityErr.amount
      if (Object.keys(commodityErr).length) errs[commodityId] = commodityErr
      else delete errs[commodityId]
      return errs
    })
  }

  const deleteCommodity = (commodityId: string) => {
    setCommodities(prev =>
      prev.filter(commodity => commodity.id !== commodityId),
    )
    setHasChanges(true)
  }

  const addNewEntry = () => {
    if (!newEntry.name || !newEntry.amount || newEntry.amount <= 0) return

    const newCommodity: CommodityEntry = {
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

    setCommodities(prev => [...prev, newCommodity])
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
    // Validate entries and collect errors per commodity
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
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors)
      return
    }
    // Clear previous errors
    setFieldErrors({})

    setIsSaving(true)
    try {
      // Send ALL commodities, not just modified ones, since backend replaces entire position
      const commodityRegisters: CommodityRegister[] = commodities.map(
        commodity => ({
          name: commodity.name,
          amount: commodity.amount,
          unit: commodity.unit,
          type: commodity.type,
          initial_investment: commodity.initial_investment,
          average_buy_price: commodity.average_buy_price,
          currency: commodity.currency,
        }),
      )

      await saveCommodity({ registers: commodityRegisters })

      // Refresh data to get updated positions
      await refreshData()

      setHasChanges(false)
    } catch (error) {
      console.error("Error saving commodities:", error)
      showToast(t.commodityManagement.saveError, "error")
    } finally {
      setIsSaving(false)
    }
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

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900 dark:border-gray-100"></div>
      </div>
    )
  }

  return (
    <div
      className="space-y-6 max-h-[calc(100vh-8rem)] overflow-y-auto w-full p-0 m-0 pb-6"
      style={{
        scrollbarWidth: "none",
        msOverflowStyle: "none",
      }}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={onBack}
            className="p-1 h-8 w-8"
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h2 className="text-2xl font-bold">
              {t.commodityManagement.title}
            </h2>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowAddForm(true)}
            className="flex items-center gap-2"
          >
            <Plus className="h-4 w-4" />
            {t.common.add}
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

      {/* Add New Entry Form */}
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
                        setNewEntry(prev => ({ ...prev, name: e.target.value }))
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
                        setNewEntry(prev => ({
                          ...prev,
                          type: e.target.value as CommodityType,
                        }))
                      }
                      className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 appearance-none"
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
                        setNewEntry(prev => ({
                          ...prev,
                          amount: value === "" ? 0 : parseFloat(value) || 0,
                        }))
                      }}
                      onFocus={e => {
                        if (e.target.value === "0") {
                          e.target.select()
                        }
                      }}
                    />
                  </div>
                  <div>
                    <Label htmlFor="unit">{t.commodityManagement.unit}</Label>
                    <select
                      id="unit"
                      value={newEntry.unit}
                      onChange={e =>
                        setNewEntry(prev => ({
                          ...prev,
                          unit: e.target.value as WeightUnit,
                        }))
                      }
                      className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 appearance-none leading-tight min-h-[2.5rem]"
                    >
                      {Object.values(WeightUnit).map(unit => (
                        <option key={unit} value={unit}>
                          {t.enums.weightUnitName[unit]}
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
                        setNewEntry(prev => ({
                          ...prev,
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
                        setNewEntry(prev => ({
                          ...prev,
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
                        setNewEntry(prev => ({
                          ...prev,
                          currency: e.target.value || null,
                        }))
                      }
                      className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 appearance-none leading-tight"
                    >
                      {supportedCurrencies.map(currency => (
                        <option key={currency} value={currency}>
                          {getCurrencySymbol(currency)} {currency}
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

      {/* Commodities List */}
      {commodities.length === 0 ? (
        <div className="text-center py-12 text-gray-500 dark:text-gray-400">
          <p className="text-lg">{t.commodityManagement.noCommodities}</p>
          <p className="text-sm">{t.commodityManagement.addFirstCommodity}</p>
        </div>
      ) : (
        <motion.div
          variants={container}
          initial="hidden"
          animate="show"
          className="space-y-6"
        >
          {Object.entries(groupedCommodities).map(
            ([type, commoditiesOfType]) => (
              <motion.div key={type} variants={item} className="space-y-3">
                <h3 className="text-lg font-medium text-gray-700 dark:text-gray-300 flex items-center gap-2">
                  <CommodityIcon type={type as CommodityType} size="md" />
                  {t.enums.commodityType[type as CommodityType]}
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 px-1 items-start">
                  {commoditiesOfType.map(commodity => (
                    <Card
                      key={commodity.id}
                      className={`transition-all hover:shadow-md ${
                        commodity.isModified ? "ring-2 ring-blue-500" : ""
                      } ${commodity.isExpanded ? "h-auto" : "h-fit"}`}
                    >
                      <CardContent
                        className={`p-4 ${commodity.isExpanded ? "h-auto" : "h-fit"}`}
                      >
                        <div
                          className="flex items-center justify-between cursor-pointer"
                          onClick={() => toggleExpanded(commodity.id)}
                        >
                          <div className="flex-1">
                            <h4 className="font-medium text-gray-900 dark:text-gray-100 mb-1">
                              {commodity.name}
                            </h4>
                            <p className="text-sm text-gray-600 dark:text-gray-400">
                              {formatWeight(commodity.amount, commodity.unit)}
                            </p>
                          </div>
                          <div className="flex items-center gap-2">
                            {commodity.isModified && (
                              <Edit className="h-4 w-4 text-blue-500" />
                            )}
                            {commodity.isExpanded ? (
                              <ChevronUp className="h-4 w-4 text-gray-400" />
                            ) : (
                              <ChevronDown className="h-4 w-4 text-gray-400" />
                            )}
                          </div>
                        </div>

                        <AnimatePresence>
                          {commodity.isExpanded && (
                            <motion.div
                              initial={{ opacity: 0, height: 0 }}
                              animate={{ opacity: 1, height: "auto" }}
                              exit={{ opacity: 0, height: 0 }}
                              className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700 space-y-3"
                            >
                              <div className="flex items-end gap-2">
                                <div className="flex-1">
                                  <Label
                                    htmlFor={`name-${commodity.id}`}
                                    className="text-xs"
                                  >
                                    {t.commodityManagement.name}
                                  </Label>
                                  <Input
                                    id={`name-${commodity.id}`}
                                    value={commodity.name}
                                    onChange={e =>
                                      updateCommodity(
                                        commodity.id,
                                        "name",
                                        e.target.value,
                                      )
                                    }
                                    className={cn(
                                      "h-8 text-sm",
                                      fieldErrors[commodity.id]?.name &&
                                        "border-red-500",
                                    )}
                                  />
                                  {fieldErrors[commodity.id]?.name && (
                                    <p className="text-red-500 text-xs mt-1">
                                      {fieldErrors[commodity.id].name}
                                    </p>
                                  )}
                                </div>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={e => {
                                    e.stopPropagation()
                                    deleteCommodity(commodity.id)
                                  }}
                                  className="p-1 h-8 w-8 text-red-500 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-900/20"
                                >
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              </div>
                              <div className="grid grid-cols-2 gap-2">
                                <div>
                                  <Label
                                    htmlFor={`amount-${commodity.id}`}
                                    className="text-xs"
                                  >
                                    {t.commodityManagement.amount}
                                  </Label>
                                  <Input
                                    id={`amount-${commodity.id}`}
                                    type="number"
                                    step="0.0001"
                                    value={commodity.amount || ""}
                                    onChange={e => {
                                      const value = e.target.value
                                      updateCommodity(
                                        commodity.id,
                                        "amount",
                                        value === ""
                                          ? 0
                                          : parseFloat(value) || 0,
                                      )
                                    }}
                                    onFocus={e => {
                                      if (e.target.value === "0") {
                                        e.target.select()
                                      }
                                    }}
                                    className={cn(
                                      "h-8 text-sm",
                                      fieldErrors[commodity.id]?.amount &&
                                        "border-red-500",
                                    )}
                                  />
                                  {fieldErrors[commodity.id]?.amount && (
                                    <p className="text-red-500 text-xs mt-1">
                                      {fieldErrors[commodity.id].amount}
                                    </p>
                                  )}
                                </div>
                                <div>
                                  <Label
                                    htmlFor={`unit-${commodity.id}`}
                                    className="text-xs"
                                  >
                                    {t.commodityManagement.unit}
                                  </Label>
                                  <select
                                    value={commodity.unit}
                                    onChange={e =>
                                      updateCommodity(
                                        commodity.id,
                                        "unit",
                                        e.target.value,
                                      )
                                    }
                                    className="flex h-8 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 appearance-none leading-tight min-h-[2rem]"
                                  >
                                    {Object.values(WeightUnit).map(unit => (
                                      <option key={unit} value={unit}>
                                        {t.enums.weightUnitName[unit]}
                                      </option>
                                    ))}
                                  </select>
                                </div>
                              </div>
                              {(commodity.initial_investment !== null ||
                                commodity.average_buy_price !== null ||
                                commodity.currency) && (
                                <div className="space-y-2">
                                  <div className="grid grid-cols-12 gap-2">
                                    <div className="col-span-5">
                                      <Label
                                        htmlFor={`initial-investment-${commodity.id}`}
                                        className="text-xs"
                                      >
                                        {
                                          t.commodityManagement
                                            .initialInvestment
                                        }{" "}
                                        {commodity.currency &&
                                          `(${getCurrencySymbol(commodity.currency)})`}
                                      </Label>
                                      <Input
                                        id={`initial-investment-${commodity.id}`}
                                        type="number"
                                        step="0.01"
                                        value={
                                          commodity.initial_investment || ""
                                        }
                                        onChange={e =>
                                          updateCommodity(
                                            commodity.id,
                                            "initial_investment",
                                            parseFloat(e.target.value) || null,
                                          )
                                        }
                                        className="h-8 text-sm"
                                      />
                                    </div>
                                    <div className="col-span-5">
                                      <Label
                                        htmlFor={`average-buy-price-${commodity.id}`}
                                        className="text-xs"
                                      >
                                        {t.commodityManagement.averageBuyPrice}{" "}
                                        {commodity.currency &&
                                          commodity.unit &&
                                          `(${getCurrencySymbol(commodity.currency)}/${t.enums.weightUnit[commodity.unit]})`}
                                      </Label>
                                      <Input
                                        id={`average-buy-price-${commodity.id}`}
                                        type="number"
                                        step="0.01"
                                        value={
                                          commodity.average_buy_price || ""
                                        }
                                        onChange={e =>
                                          updateCommodity(
                                            commodity.id,
                                            "average_buy_price",
                                            parseFloat(e.target.value) || null,
                                          )
                                        }
                                        className="h-8 text-sm"
                                      />
                                    </div>
                                    <div className="col-span-2">
                                      <Label
                                        htmlFor={`currency-${commodity.id}`}
                                        className="text-xs"
                                      >
                                        {t.commodityManagement.currency}
                                      </Label>
                                      <select
                                        value={commodity.currency || ""}
                                        onChange={e =>
                                          updateCommodity(
                                            commodity.id,
                                            "currency",
                                            e.target.value || null,
                                          )
                                        }
                                        className="flex h-8 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 appearance-none leading-tight min-h-[2rem]"
                                      >
                                        {supportedCurrencies.map(currency => (
                                          <option
                                            key={currency}
                                            value={currency}
                                          >
                                            {getCurrencySymbol(currency)}
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
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </motion.div>
            ),
          )}
        </motion.div>
      )}
    </div>
  )
}
