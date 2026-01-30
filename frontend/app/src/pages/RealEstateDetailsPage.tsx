import { useEffect, useState, useMemo } from "react"
import { useParams, useNavigate } from "react-router-dom"
import { useI18n } from "@/i18n"
import { useAppContext } from "@/context/AppContext"
import { Button } from "@/components/ui/Button"
import { Badge } from "@/components/ui/Badge"
import { Card } from "@/components/ui/Card"
import { getAllRealEstate, deleteRealEstate, getImageUrl } from "@/services/api"
import type {
  RealEstate,
  DeleteRealEstateRequest,
  SupplyPayload,
  CostPayload,
} from "@/types"
import { formatCurrency, formatDate } from "@/lib/formatters"
import {
  MapPin,
  Calendar,
  Bed,
  Bath,
  Edit,
  Trash2,
  Building2,
  ShoppingCart,
  TrendingUp,
  CreditCard,
  Receipt,
  Zap,
  DollarSign,
  Info,
  Home,
  Calculator,
  ArrowLeft,
} from "lucide-react"
import { Icon } from "@/components/ui/icon-picker"
import RealEstateStats from "@/components/real-estate/RealEstateStats"
import { DeletePropertyDialog } from "@/components/ui/DeletePropertyDialog"
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from "@/components/ui/Popover"
import { RealEstateFormModal } from "@/components/RealEstateFormModal"
import { FlowFrequency } from "@/types"
export default function RealEstateDetailsPage() {
  const { t, locale } = useI18n()
  const { showToast } = useAppContext()
  const navigate = useNavigate()
  const { id } = useParams()

  const [loading, setLoading] = useState(true)
  const [imageUrl, setImageUrl] = useState<string | null>(null)
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false)
  const [isEditModalOpen, setIsEditModalOpen] = useState(false)
  const [property, setProperty] = useState<RealEstate | null>(null)

  const frequencyLabel = (freq?: FlowFrequency | string) => {
    if (!freq) return ""
    const f = String(freq)
    return f === "MONTHLY"
      ? t.realEstate.frequency.monthly
      : f === "YEARLY"
        ? t.realEstate.frequency.yearly
        : f === "WEEKLY"
          ? t.realEstate.frequency.weekly
          : f === "DAILY"
            ? t.realEstate.frequency.daily
            : f === "QUARTERLY"
              ? t.realEstate.frequency.quarterly
              : f === "EVERY_TWO_MONTHS"
                ? t.realEstate.frequency.bimonthly
                : f === "EVERY_FOUR_MONTHS"
                  ? t.realEstate.frequency.fourMonthly
                  : f === "SEMIANNUALLY"
                    ? t.realEstate.frequency.semiannually
                    : f
  }

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true)
        const list = await getAllRealEstate()
        const found = list.find(p => p.id === id) || null
        setProperty(found)
        if (found?.basic_info.photo_url) {
          const url = await getImageUrl(found.basic_info.photo_url)
          setImageUrl(url)
        } else {
          setImageUrl(null)
        }
      } catch (e) {
        console.error(e)
        showToast(t.realEstate.errors.loadFailed, "error")
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [id])

  const monthlyCashflow = useMemo(() => {
    if (!property) return 0
    let income = 0
    let expenses = 0
    for (const flow of property.flows) {
      if (!flow.periodic_flow?.enabled) continue
      const amount = flow.periodic_flow.amount
      const freq = flow.periodic_flow.frequency
      let monthly = amount
      switch (freq) {
        case "DAILY":
          monthly = amount * 30
          break
        case "WEEKLY":
          monthly = amount * 4.33
          break
        case "EVERY_TWO_MONTHS":
          monthly = amount / 2
          break
        case "QUARTERLY":
          monthly = amount / 3
          break
        case "EVERY_FOUR_MONTHS":
          monthly = amount / 4
          break
        case "SEMIANNUALLY":
          monthly = amount / 6
          break
        case "YEARLY":
          monthly = amount / 12
          break
        default:
          monthly = amount
      }
      if (flow.flow_subtype === "RENT") income += monthly
      if (
        flow.flow_subtype === "COST" ||
        flow.flow_subtype === "SUPPLY" ||
        flow.flow_subtype === "LOAN"
      )
        expenses += monthly
    }
    return income - expenses
  }, [property])

  const handleEdit = () => {
    if (!property) return
    setIsEditModalOpen(true)
  }

  const handleEditSuccess = async () => {
    setIsEditModalOpen(false)
    // Reload property data
    try {
      const list = await getAllRealEstate()
      const found = list.find(p => p.id === id) || null
      setProperty(found)
      if (found?.basic_info.photo_url) {
        const url = await getImageUrl(found.basic_info.photo_url)
        setImageUrl(url)
      }
    } catch (e) {
      console.error(e)
    }
  }

  const handleDelete = async (removeRelatedFlows: boolean) => {
    if (!property?.id) return
    try {
      const req: DeleteRealEstateRequest = {
        remove_related_flows: removeRelatedFlows,
      }
      await deleteRealEstate(property.id, req)
      showToast(t.realEstate.success.deleted, "success")
      navigate("/real-estate")
    } catch {
      showToast(t.realEstate.errors.deleteFailed, "error")
    } finally {
      setIsDeleteDialogOpen(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-lg text-gray-600 dark:text-gray-400">
          {t.common.loading}
        </div>
      </div>
    )
  }

  if (!property) {
    return (
      <div className="p-6">
        <Card className="p-6">
          <div className="text-gray-600 dark:text-gray-400">
            {t.common.noDataAvailable}
          </div>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-3 md:gap-4">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <Button
            variant="ghost"
            size="sm"
            className="p-1 h-8 w-8"
            onClick={() => navigate(-1)}
            aria-label={t.common.back}
          >
            <ArrowLeft className="w-5 h-5" />
          </Button>
          <div className="flex-1 min-w-0">
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white leading-snug break-words">
              {property.basic_info.name}
            </h1>
            {property.location.address && (
              <div className="flex items-start gap-2 text-sm text-gray-600 dark:text-gray-400 mt-2 pr-1">
                <MapPin className="w-5 h-5 flex-shrink-0 mt-0.5" />
                <span className="leading-relaxed break-words">
                  {property.location.address}
                </span>
              </div>
            )}
          </div>
        </div>
        <div className="flex gap-2 flex-wrap md:flex-nowrap md:justify-end">
          <Button
            onClick={handleEdit}
            className="bg-black dark:bg-white hover:bg-gray-800 dark:hover:bg-gray-200 text-white dark:text-black px-3 py-2 h-auto text-sm"
          >
            <Edit className="w-4 h-4 mr-1" /> {t.common.edit}
          </Button>
          <Button
            variant="outline"
            onClick={() => setIsDeleteDialogOpen(true)}
            className="text-red-600 border-red-600 hover:bg-red-50 dark:text-red-400 dark:border-red-400 dark:hover:bg-red-950/30 px-3 py-2 h-auto text-sm"
          >
            <Trash2 className="w-4 h-4 mr-1" /> {t.common.delete}
          </Button>
        </div>
      </div>

      <div className="relative h-64 rounded-lg overflow-hidden">
        {property.basic_info.photo_url && imageUrl ? (
          <img
            src={imageUrl}
            alt={property.basic_info.name}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full bg-gray-200 dark:bg-gray-700 flex items-center justify-center">
            <Home className="w-16 h-16 text-gray-500" />
          </div>
        )}
      </div>

      <div
        className={`grid grid-cols-1 ${property.basic_info.is_rented ? "md:grid-cols-3" : "md:grid-cols-2"} gap-4`}
      >
        <Card className="p-4">
          <div className="text-sm text-gray-600 dark:text-gray-400">
            {t.realEstate.basicInfo.purchaseDate}
          </div>
          <div className="font-semibold text-gray-900 dark:text-white flex items-center gap-2 mt-1">
            <Calendar className="w-4 h-4" />
            {formatDate(property.purchase_info.date, locale)}
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-sm text-gray-600 dark:text-gray-400">
            {t.realEstate.purchase.price}
          </div>
          <div className="font-semibold text-gray-900 dark:text-white mt-1">
            {formatCurrency(
              property.purchase_info.price,
              locale,
              property.currency,
            )}
          </div>
        </Card>
        {property.basic_info.is_rented && (
          <>
            <Card className="p-4">
              <div className="text-sm text-gray-600 dark:text-gray-400">
                {t.realEstate.analysis.monthlyCashflow}
              </div>
              <div
                className={`font-semibold mt-1 ${monthlyCashflow >= 0 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}
              >
                {monthlyCashflow >= 0 ? "+" : ""}
                {formatCurrency(monthlyCashflow, locale, property.currency)}
              </div>
            </Card>

            {/* Amortizations card moved below Rent to respect ordering */}
          </>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
        <div className="lg:col-span-2 space-y-6">
          <Card className="p-4">
            <h3 className="text-lg font-medium mb-3 flex items-center gap-2">
              <Building2 className="w-5 h-5" /> {t.realEstate.sections.basic}
            </h3>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div className="col-span-2">
                <div className="font-semibold text-base md:text-lg">
                  {[
                    property.basic_info.is_residence
                      ? t.realEstate.residence
                      : null,
                    property.basic_info.is_rented ? t.realEstate.rented : null,
                  ]
                    .filter(Boolean)
                    .join(" & ") || "—"}
                </div>
              </div>
              {property.basic_info.bedrooms ? (
                <div>
                  <div className="text-gray-600 dark:text-gray-400 flex items-center gap-1">
                    <Bed className="w-4 h-4" /> {t.realEstate.bedrooms}
                  </div>
                  <div className="font-medium">
                    {property.basic_info.bedrooms}
                  </div>
                </div>
              ) : null}
              {property.basic_info.bathrooms ? (
                <div>
                  <div className="text-gray-600 dark:text-gray-400 flex items-center gap-1">
                    <Bath className="w-4 h-4" /> {t.realEstate.bathrooms}
                  </div>
                  <div className="font-medium">
                    {property.basic_info.bathrooms}
                  </div>
                </div>
              ) : null}
            </div>
          </Card>

          <Card className="p-4">
            <h3 className="text-lg font-medium mb-3 flex items-center gap-2">
              <ShoppingCart className="w-5 h-5" />{" "}
              {t.realEstate.sections.purchase}
            </h3>
            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-gray-600 dark:text-gray-400">
                  {t.realEstate.purchase.price}
                </span>
                <span className="font-medium">
                  {formatCurrency(
                    property.purchase_info.price,
                    locale,
                    property.currency,
                  )}
                </span>
              </div>
              {property.purchase_info.expenses.length > 0 ? (
                <div>
                  <div className="mb-2 text-gray-600 dark:text-gray-400">
                    {t.realEstate.purchase.expenses}
                  </div>
                  <div className="space-y-1">
                    {property.purchase_info.expenses
                      .slice()
                      .sort((a, b) => b.amount - a.amount)
                      .slice(0, 3)
                      .map((exp, idx) => (
                        <div
                          key={idx}
                          className="flex items-center justify-between"
                        >
                          <span className="text-gray-700 dark:text-gray-300">
                            {exp.concept || "—"}
                          </span>
                          <span className="font-medium">
                            {formatCurrency(
                              exp.amount,
                              locale,
                              property.currency,
                            )}
                          </span>
                        </div>
                      ))}
                  </div>
                  {property.purchase_info.expenses.length > 3 && (
                    <div className="mt-2 text-right">
                      <Popover>
                        <PopoverTrigger asChild>
                          <Button
                            variant="outline"
                            size="sm"
                            className="text-xs h-7 px-2"
                          >
                            {`${t.dashboard.viewAll} (${property.purchase_info.expenses.length})`}
                          </Button>
                        </PopoverTrigger>
                        <PopoverContent className="w-80">
                          <div className="text-sm font-medium mb-2">
                            {t.realEstate.purchase.expenses}
                          </div>
                          <div className="space-y-2 max-h-64 overflow-y-auto no-scrollbar">
                            {property.purchase_info.expenses
                              .slice()
                              .sort((a, b) => b.amount - a.amount)
                              .map((exp, idx) => (
                                <div
                                  key={idx}
                                  className="flex items-center justify-between py-1 border-b last:border-b-0 border-gray-100 dark:border-gray-800"
                                >
                                  <span className="text-gray-700 dark:text-gray-300">
                                    {exp.concept || "—"}
                                  </span>
                                  <span className="font-medium">
                                    {formatCurrency(
                                      exp.amount,
                                      locale,
                                      property.currency,
                                    )}
                                  </span>
                                </div>
                              ))}
                          </div>
                          <div className="mt-3 pt-3 border-t flex items-center justify-between">
                            <span className="text-gray-600 dark:text-gray-400">
                              {t.realEstate.purchase.totalCost}
                            </span>
                            <span className="font-semibold">
                              {formatCurrency(
                                property.purchase_info.price +
                                  property.purchase_info.expenses.reduce(
                                    (s, e) => s + e.amount,
                                    0,
                                  ),
                                locale,
                                property.currency,
                              )}
                            </span>
                          </div>
                        </PopoverContent>
                      </Popover>
                    </div>
                  )}
                </div>
              ) : null}
            </div>
          </Card>

          {/* Valuation moved right after Purchase */}
          <Card className="p-4">
            <h3 className="text-lg font-medium mb-3 flex items-center gap-2">
              <TrendingUp className="w-5 h-5" />{" "}
              {t.realEstate.sections.valuation}
            </h3>
            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-gray-600 dark:text-gray-400">
                  {t.realEstate.valuation.estimatedMarketValue}
                </span>
                <span className="font-semibold">
                  {formatCurrency(
                    property.valuation_info.estimated_market_value || 0,
                    locale,
                    property.currency,
                  )}
                </span>
              </div>
              {typeof property.valuation_info.annual_appreciation ===
              "number" ? (
                <div className="flex items-center justify-between">
                  <span className="text-gray-600 dark:text-gray-400">
                    {t.realEstate.valuation.annualAppreciation}
                  </span>
                  <span className="font-semibold">
                    {(
                      (property.valuation_info.annual_appreciation || 0) * 100
                    ).toFixed(2)}
                    %
                  </span>
                </div>
              ) : null}
              {property.valuation_info.valuations?.length ? (
                <div className="text-xs text-gray-500 dark:text-gray-400 -mb-2">
                  {t.realEstate.valuation.valuations}
                </div>
              ) : null}
              {property.valuation_info.valuations?.length ? (
                <div className="space-y-2">
                  {property.valuation_info.valuations.map((v, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between py-2 border-b last:border-b-0 border-gray-200 dark:border-gray-700"
                    >
                      <div className="text-sm flex items-center gap-2">
                        <Calendar className="w-4 h-4" />{" "}
                        {formatDate(v.date, locale)}
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium">
                          {formatCurrency(v.amount, locale, property.currency)}
                        </span>
                        {v.notes ? (
                          <Popover>
                            <PopoverTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon"
                                aria-label={t.common.viewDetails}
                                title={t.common.viewDetails}
                              >
                                <Info className="w-4 h-4" />
                              </Button>
                            </PopoverTrigger>
                            <PopoverContent className="w-80">
                              <div className="text-sm font-medium mb-2">
                                {t.realEstate.valuation.notes}
                              </div>
                              <div className="text-sm whitespace-pre-wrap">
                                {v.notes}
                              </div>
                            </PopoverContent>
                          </Popover>
                        ) : null}
                      </div>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          </Card>

          <Card className="p-4">
            <h3 className="text-lg font-medium mb-3 flex items-center gap-2">
              <CreditCard className="w-5 h-5" /> {t.realEstate.sections.loans}
            </h3>
            <div className="space-y-2">
              {property.flows
                .filter(f => f.flow_subtype === "LOAN")
                .map((f, idx) => (
                  <div
                    key={idx}
                    className="py-2 border-b last:border-b-0 border-gray-200 dark:border-gray-700"
                  >
                    <div className="flex items-center justify-between">
                      <div className="text-sm">
                        <div className="font-medium text-gray-900 dark:text-white flex items-center gap-2">
                          {f.periodic_flow?.icon ? (
                            <Icon
                              name={f.periodic_flow.icon as any}
                              className="w-5 h-5"
                            />
                          ) : null}
                          {f.description}
                        </div>
                        <div className="text-xs text-gray-500 dark:text-gray-400 flex flex-wrap gap-2 mt-1">
                          {f.periodic_flow?.next_date && (
                            <Badge variant="outline" className="text-[10px]">
                              {formatDate(f.periodic_flow.next_date, locale)}
                            </Badge>
                          )}
                          {f.periodic_flow?.frequency && (
                            <Badge variant="secondary" className="text-[10px]">
                              {frequencyLabel(f.periodic_flow.frequency)}
                            </Badge>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-gray-900 dark:text-white font-semibold">
                          {formatCurrency(
                            f.periodic_flow?.amount || 0,
                            locale,
                            property.currency,
                          )}
                        </span>
                        <Popover>
                          <PopoverTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              aria-label={t.common.viewDetails}
                              title={t.common.viewDetails}
                            >
                              <Info className="w-4 h-4" />
                            </Button>
                          </PopoverTrigger>
                          <PopoverContent className="w-80">
                            <div className="space-y-2 text-xs">
                              <div className="flex items-center justify-between">
                                <span className="text-gray-500 dark:text-gray-400">
                                  {t.realEstate.loans.fromLabel}
                                </span>
                                <span className="font-medium text-gray-900 dark:text-white">
                                  {f.periodic_flow?.since
                                    ? formatDate(f.periodic_flow.since, locale)
                                    : "—"}
                                </span>
                              </div>
                              <div className="flex items-center justify-between">
                                <span className="text-gray-500 dark:text-gray-400">
                                  {t.realEstate.loans.untilLabel}
                                </span>
                                <span className="font-medium text-gray-900 dark:text-white">
                                  {f.periodic_flow?.until
                                    ? formatDate(f.periodic_flow.until, locale)
                                    : "—"}
                                </span>
                              </div>
                              <div className="flex items-center justify-between">
                                <span className="text-gray-500 dark:text-gray-400">
                                  {t.realEstate.loans.principalOutstanding}
                                </span>
                                <span className="font-medium text-gray-900 dark:text-white">
                                  {formatCurrency(
                                    (f.payload as any)?.principal_outstanding ||
                                      0,
                                    locale,
                                    property.currency,
                                  )}
                                </span>
                              </div>
                              <div className="flex items-center justify-between">
                                <span className="text-gray-500 dark:text-gray-400">
                                  {t.realEstate.labels.monthlyInterest}
                                </span>
                                <span className="font-medium text-gray-900 dark:text-white">
                                  {((f.payload as any)?.monthly_interests ??
                                    null) !== null
                                    ? formatCurrency(
                                        (f.payload as any)?.monthly_interests ||
                                          0,
                                        locale,
                                        property.currency,
                                      )
                                    : "—"}
                                </span>
                              </div>
                              {typeof (f.payload as any)?.loan_amount ===
                                "number" && (
                                <div className="flex items-center justify-between">
                                  <span className="text-gray-500 dark:text-gray-400">
                                    {t.realEstate.loans.totalLoanAmountLabel}
                                  </span>
                                  <span className="font-medium text-gray-900 dark:text-white">
                                    {formatCurrency(
                                      (f.payload as any)?.loan_amount || 0,
                                      locale,
                                      property.currency,
                                    )}
                                  </span>
                                </div>
                              )}
                              {(f.payload as any)?.interest_rate != null && (
                                <div className="flex items-center justify-between">
                                  <span className="text-gray-500 dark:text-gray-400">
                                    {t.realEstate.loans.interestRateLabel}
                                  </span>
                                  <span className="font-medium text-gray-900 dark:text-white">
                                    {(
                                      ((f.payload as any)?.interest_rate || 0) *
                                      100
                                    ).toFixed(2)}
                                    %
                                  </span>
                                </div>
                              )}
                              {(f.payload as any)?.euribor_rate != null && (
                                <div className="flex items-center justify-between">
                                  <span className="text-gray-500 dark:text-gray-400">
                                    {t.realEstate.loans.euriborRate}
                                  </span>
                                  <span className="font-medium text-gray-900 dark:text-white">
                                    {(
                                      ((f.payload as any)?.euribor_rate || 0) *
                                      100
                                    ).toFixed(2)}
                                    %
                                  </span>
                                </div>
                              )}
                              {(f.payload as any)?.interest_type && (
                                <div className="flex items-center justify-between">
                                  <span className="text-gray-500 dark:text-gray-400">
                                    {t.realEstate.loans.interestTypeLabel}
                                  </span>
                                  <span className="font-medium text-gray-900 dark:text-white">
                                    {
                                      t.realEstate.loans.interestTypes[
                                        (
                                          f.payload as any
                                        )?.interest_type?.toLowerCase() as
                                          | "fixed"
                                          | "variable"
                                          | "mixed"
                                      ]
                                    }
                                  </span>
                                </div>
                              )}
                              {(f.payload as any)?.fixed_years != null && (
                                <div className="flex items-center justify-between">
                                  <span className="text-gray-500 dark:text-gray-400">
                                    {t.realEstate.loans.fixedYearsLabel}
                                  </span>
                                  <span className="font-medium text-gray-900 dark:text-white">
                                    {(f.payload as any)?.fixed_years}
                                  </span>
                                </div>
                              )}
                              <div className="flex items-center justify-between">
                                <span className="text-gray-500 dark:text-gray-400">
                                  {t.management.nextPayment}
                                </span>
                                <span className="font-medium text-gray-900 dark:text-white">
                                  {f.periodic_flow?.next_date
                                    ? formatDate(
                                        f.periodic_flow.next_date,
                                        locale,
                                      )
                                    : "—"}
                                </span>
                              </div>
                              {f.periodic_flow?.frequency && (
                                <div className="flex items-center justify-between">
                                  <span className="text-gray-500 dark:text-gray-400">
                                    {t.management.frequencyLabel}
                                  </span>
                                  <span className="font-medium text-gray-900 dark:text-white">
                                    {frequencyLabel(f.periodic_flow.frequency)}
                                  </span>
                                </div>
                              )}
                            </div>
                          </PopoverContent>
                        </Popover>
                      </div>
                    </div>
                  </div>
                ))}
              {property.flows.filter(f => f.flow_subtype === "LOAN").length ===
                0 && (
                <div className="text-sm text-gray-500 dark:text-gray-400">
                  {t.realEstate.loans.noAssociatedLoans}
                </div>
              )}
            </div>
          </Card>

          <Card className="p-4">
            <h3 className="text-lg font-medium mb-3 flex items-center gap-2">
              <Receipt className="w-5 h-5" /> {t.realEstate.sections.costs}
            </h3>
            <div className="space-y-2">
              {property.flows
                .filter(f => f.flow_subtype === "COST")
                .map((f, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between py-2 border-b last:border-b-0 border-gray-200 dark:border-gray-700"
                  >
                    <div className="text-sm">
                      <div className="font-medium text-gray-900 dark:text-white flex items-center gap-2">
                        {f.periodic_flow?.icon ? (
                          <Icon
                            name={f.periodic_flow.icon as any}
                            className="w-5 h-5"
                          />
                        ) : null}
                        {f.description}
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-400 flex flex-wrap gap-2 mt-1">
                        {f.periodic_flow?.next_date && (
                          <Badge variant="outline" className="text-[10px]">
                            {formatDate(f.periodic_flow.next_date, locale)}
                          </Badge>
                        )}
                        {f.periodic_flow?.frequency && (
                          <Badge variant="secondary" className="text-[10px]">
                            {frequencyLabel(f.periodic_flow.frequency)}
                          </Badge>
                        )}
                        {property.basic_info.is_rented &&
                          ((f.payload as CostPayload)?.tax_deductible ??
                            false) && (
                            <Badge variant="default" className="text-[10px]">
                              {t.realEstate.flows.taxDeductible}
                            </Badge>
                          )}
                      </div>
                    </div>
                    <div className="text-sm text-gray-900 dark:text-white font-semibold">
                      {formatCurrency(
                        f.periodic_flow?.amount || 0,
                        locale,
                        property.currency,
                      )}
                    </div>
                  </div>
                ))}
              {property.flows.filter(f => f.flow_subtype === "COST").length ===
                0 && (
                <div className="text-sm text-gray-500 dark:text-gray-400">
                  {t.realEstate.emptyStates.noCostsRegistered}
                </div>
              )}
            </div>
          </Card>

          <Card className="p-4">
            <h3 className="text-lg font-medium mb-3 flex items-center gap-2">
              <Zap className="w-5 h-5" /> {t.realEstate.sections.utilities}
            </h3>
            <div className="space-y-2">
              {property.flows
                .filter(f => f.flow_subtype === "SUPPLY")
                .map((f, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between py-2 border-b last:border-b-0 border-gray-200 dark:border-gray-700"
                  >
                    <div className="text-sm">
                      <div className="font-medium text-gray-900 dark:text-white flex items-center gap-2">
                        {f.periodic_flow?.icon ? (
                          <Icon
                            name={f.periodic_flow.icon as any}
                            className="w-5 h-5"
                          />
                        ) : null}
                        {f.description}
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-400 flex flex-wrap gap-2 mt-1">
                        {f.periodic_flow?.next_date && (
                          <Badge variant="outline" className="text-[10px]">
                            {formatDate(f.periodic_flow.next_date, locale)}
                          </Badge>
                        )}
                        {f.periodic_flow?.frequency && (
                          <Badge variant="secondary" className="text-[10px]">
                            {frequencyLabel(f.periodic_flow.frequency)}
                          </Badge>
                        )}
                        {property.basic_info.is_rented &&
                          ((f.payload as SupplyPayload)?.tax_deductible ??
                            false) && (
                            <Badge variant="default" className="text-[10px]">
                              {t.realEstate.flows.taxDeductible}
                            </Badge>
                          )}
                      </div>
                    </div>
                    <div className="text-sm text-gray-900 dark:text-white font-semibold">
                      {formatCurrency(
                        f.periodic_flow?.amount || 0,
                        locale,
                        property.currency,
                      )}
                    </div>
                  </div>
                ))}
              {property.flows.filter(f => f.flow_subtype === "SUPPLY")
                .length === 0 && (
                <div className="text-sm text-gray-500 dark:text-gray-400">
                  {t.realEstate.emptyStates.noUtilitiesRegistered}
                </div>
              )}
            </div>
          </Card>

          {property.basic_info.is_rented && (
            <Card className="p-4">
              <h3 className="text-lg font-medium mb-3 flex items-center gap-2">
                <DollarSign className="w-5 h-5" /> {t.realEstate.sections.rent}
              </h3>
              {typeof property.rental_data?.vacancy_rate === "number" ? (
                <div className="flex items-center justify-between mb-2 text-sm">
                  <span className="text-gray-600 dark:text-gray-400">
                    {t.realEstate.rent.vacancyRate}
                  </span>
                  <span className="font-medium">
                    {((property.rental_data?.vacancy_rate || 0) * 100).toFixed(
                      2,
                    )}
                    %
                  </span>
                </div>
              ) : null}
              <div className="space-y-2">
                {property.flows
                  .filter(f => f.flow_subtype === "RENT")
                  .map((f, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between py-2 border-b last:border-b-0 border-gray-200 dark:border-gray-700"
                    >
                      <div className="text-sm">
                        <div className="font-medium text-gray-900 dark:text-white flex items-center gap-2">
                          {f.periodic_flow?.icon ? (
                            <Icon
                              name={f.periodic_flow.icon as any}
                              className="w-5 h-5"
                            />
                          ) : null}
                          {f.description}
                        </div>
                        <div className="text-xs text-gray-500 dark:text-gray-400 flex flex-wrap gap-2 mt-1">
                          {f.periodic_flow?.next_date && (
                            <Badge variant="outline" className="text-[10px]">
                              {formatDate(f.periodic_flow.next_date, locale)}
                            </Badge>
                          )}
                          {f.periodic_flow?.frequency && (
                            <Badge variant="secondary" className="text-[10px]">
                              {frequencyLabel(f.periodic_flow.frequency)}
                            </Badge>
                          )}
                          {typeof f.periodic_flow?.max_amount === "number" && (
                            <Badge variant="secondary" className="text-[10px]">
                              {t.realEstate.flows.maximumAmount}:{" "}
                              {formatCurrency(
                                f.periodic_flow.max_amount,
                                locale,
                                property.currency,
                              )}
                            </Badge>
                          )}
                        </div>
                      </div>
                      <div className="text-sm text-gray-900 dark:text-white font-semibold">
                        {formatCurrency(
                          f.periodic_flow?.amount || 0,
                          locale,
                          property.currency,
                        )}
                      </div>
                    </div>
                  ))}
                {property.flows.filter(f => f.flow_subtype === "RENT")
                  .length === 0 && (
                  <div className="text-sm text-gray-500 dark:text-gray-400">
                    {t.realEstate.emptyStates.noRentRegistered}
                  </div>
                )}
              </div>
            </Card>
          )}

          {property.basic_info.is_rented &&
            (property.rental_data?.amortizations?.length || 0) > 0 && (
              <Card className="p-4">
                <h3 className="text-lg font-medium mb-3 flex items-center gap-2">
                  <Calculator className="w-5 h-5" />{" "}
                  {t.realEstate.amortizations.title}
                </h3>
                <div className="space-y-2 text-sm">
                  {(property.rental_data?.amortizations || []).map((a, idx) => (
                    <div
                      key={idx}
                      className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-12 gap-2 items-end py-1 border-b last:border-b-0 border-gray-200 dark:border-gray-700"
                    >
                      <div className="md:col-span-5">
                        <div className="text-gray-600 dark:text-gray-400">
                          {t.realEstate.amortizations.concept}
                        </div>
                        <div className="font-medium">{a.concept || "—"}</div>
                      </div>
                      <div className="sm:col-span-1 md:col-span-3">
                        <div className="text-gray-600 dark:text-gray-400">
                          {t.realEstate.amortizations.base}
                        </div>
                        <div className="font-medium">
                          {formatCurrency(
                            a.base_amount || 0,
                            locale,
                            property.currency,
                          )}
                        </div>
                      </div>
                      <div className="sm:col-span-1 md:col-span-2">
                        <div className="text-gray-600 dark:text-gray-400">
                          {t.realEstate.amortizations.percentage}
                        </div>
                        <div className="font-medium">
                          {(a.percentage ?? 0).toFixed(2)}%
                        </div>
                      </div>
                      <div className="sm:col-span-1 md:col-span-2">
                        <div className="text-gray-600 dark:text-gray-400">
                          {t.realEstate.amortizations.annual}
                        </div>
                        <div className="font-medium">
                          {formatCurrency(
                            a.amount || 0,
                            locale,
                            property.currency,
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            )}
        </div>

        <div className="lg:col-span-1 space-y-6">
          <RealEstateStats
            currency={property.currency}
            isRented={property.basic_info.is_rented}
            flows={property.flows}
            purchasePrice={property.purchase_info.price}
            purchaseExpenses={property.purchase_info.expenses}
            estimatedMarketValue={
              property.valuation_info.estimated_market_value
            }
            marginalTaxRate={
              property.rental_data?.marginal_tax_rate ?? undefined
            }
            amortizationsAnnual={(
              property.rental_data?.amortizations || []
            ).map(a => ({ amount: a.amount }))}
            vacancyRate={property.rental_data?.vacancy_rate ?? undefined}
            cardClassName="p-4 border border-gray-800 bg-gray-900 text-white dark:bg-gray-900 dark:border-gray-800"
          />
        </div>
      </div>

      <DeletePropertyDialog
        isOpen={isDeleteDialogOpen}
        propertyName={property.basic_info.name}
        onCancel={() => setIsDeleteDialogOpen(false)}
        onConfirm={handleDelete}
      />

      <RealEstateFormModal
        isOpen={isEditModalOpen}
        onClose={() => setIsEditModalOpen(false)}
        property={property}
        onSuccess={handleEditSuccess}
      />
    </div>
  )
}
