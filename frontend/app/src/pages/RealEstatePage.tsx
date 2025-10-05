import { useState, useEffect } from "react"
import { motion } from "framer-motion"
import { PinAssetButton } from "@/components/ui/PinAssetButton"
import { useNavigate } from "react-router-dom"
import { useI18n } from "@/i18n"
import { useAppContext } from "@/context/AppContext"
import { useFinancialData } from "@/context/FinancialDataContext"
import { Button } from "@/components/ui/Button"
import { Card } from "@/components/ui/Card"
import { DeletePropertyDialog } from "@/components/ui/DeletePropertyDialog"
import {
  Plus,
  Edit,
  Trash2,
  Home,
  MapPin,
  Calendar,
  Bed,
  Bath,
  ArrowLeft,
} from "lucide-react"
import { formatCurrency, formatDate } from "@/lib/formatters"
import {
  RealEstate,
  DeleteRealEstateRequest,
  FlowFrequency,
  RealEstateFlowSubtype,
  LoanPayload,
} from "@/types"
import { deleteRealEstate, getImageUrl } from "@/services/api"
import { RealEstateFormModal } from "@/components/RealEstateFormModal"
import { fadeListContainer, fadeListItem } from "@/lib/animations"

export default function RealEstatePage() {
  const { t, locale } = useI18n()
  const { showToast } = useAppContext()
  const { refreshFlows, realEstateList, refreshRealEstate } = useFinancialData()
  const navigate = useNavigate()

  const [loading, setLoading] = useState(true)
  const [isFormModalOpen, setIsFormModalOpen] = useState(false)
  const [editingProperty, setEditingProperty] = useState<RealEstate | null>(
    null,
  )
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false)
  const [deletingProperty, setDeletingProperty] = useState<RealEstate | null>(
    null,
  )
  const [imageUrls, setImageUrls] = useState<Record<string, string>>({})

  // Load real estate data
  useEffect(() => {
    let cancelled = false
    const init = async () => {
      setLoading(true)
      try {
        await refreshRealEstate()
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    init()
    return () => {
      cancelled = true
    }
  }, [refreshRealEstate])

  // Load image URLs for properties that have photos
  useEffect(() => {
    const loadImageUrls = async () => {
      const urlsToLoad: Record<string, string> = {}

      for (const property of realEstateList) {
        if (
          property.basic_info.photo_url &&
          !imageUrls[property.basic_info.photo_url]
        ) {
          try {
            const url = await getImageUrl(property.basic_info.photo_url)
            urlsToLoad[property.basic_info.photo_url] = url
          } catch (error) {
            console.error("Failed to load image URL:", error)
          }
        }
      }

      if (Object.keys(urlsToLoad).length > 0) {
        setImageUrls(prev => ({ ...prev, ...urlsToLoad }))
      }
    }

    if (realEstateList.length > 0) {
      loadImageUrls()
    }
  }, [realEstateList, imageUrls])

  // Calculate monthly net cashflow for a property (before taxes)
  const calculateMonthlyCashflow = (property: RealEstate) => {
    let monthlyIncome = 0
    let monthlyExpenses = 0

    property.flows.forEach(flow => {
      if (!flow.periodic_flow?.enabled) return

      const amount = flow.periodic_flow.amount
      const frequency = flow.periodic_flow.frequency

      // Convert to monthly amount
      let monthlyAmount = 0
      switch (frequency) {
        case FlowFrequency.DAILY:
          monthlyAmount = amount * 30
          break
        case FlowFrequency.WEEKLY:
          monthlyAmount = amount * 4.33
          break
        case FlowFrequency.MONTHLY:
          monthlyAmount = amount
          break
        case FlowFrequency.EVERY_TWO_MONTHS:
          monthlyAmount = amount / 2
          break
        case FlowFrequency.QUARTERLY:
          monthlyAmount = amount / 3
          break
        case FlowFrequency.EVERY_FOUR_MONTHS:
          monthlyAmount = amount / 4
          break
        case FlowFrequency.SEMIANNUALLY:
          monthlyAmount = amount / 6
          break
        case FlowFrequency.YEARLY:
          monthlyAmount = amount / 12
          break
        default:
          monthlyAmount = amount
      }

      if (flow.flow_subtype === "RENT") {
        monthlyIncome += monthlyAmount
      } else if (
        flow.flow_subtype === "COST" ||
        flow.flow_subtype === "SUPPLY" ||
        flow.flow_subtype === "LOAN"
      ) {
        monthlyExpenses += monthlyAmount
      }
    })

    return monthlyIncome - monthlyExpenses
  }

  const loadRealEstate = async () => {
    try {
      setLoading(true)
      await refreshRealEstate()
    } catch {
      showToast(t.realEstate.errors.loadFailed, "error")
    } finally {
      setLoading(false)
    }
  }

  const handleAddProperty = () => {
    setEditingProperty(null)
    setIsFormModalOpen(true)
  }

  // Editing is handled via dedicated route /real-estate/:id/edit

  const handleDeleteProperty = (property: RealEstate) => {
    setDeletingProperty(property)
    setIsDeleteDialogOpen(true)
  }

  const confirmDelete = async (removeRelatedFlows: boolean) => {
    if (!deletingProperty?.id) return

    try {
      const request: DeleteRealEstateRequest = {
        remove_related_flows: removeRelatedFlows,
      }

      await deleteRealEstate(deletingProperty.id, request)
      await loadRealEstate()
      showToast(t.realEstate.success.deleted, "success")

      // Refresh flows if related flows were removed
      if (removeRelatedFlows) {
        await refreshFlows()
      }
    } catch {
      showToast(t.realEstate.errors.deleteFailed, "error")
    } finally {
      setIsDeleteDialogOpen(false)
      setDeletingProperty(null)
    }
  }

  const handleFormSuccess = () => {
    setIsFormModalOpen(false)
    setEditingProperty(null)
    loadRealEstate()
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

  return (
    <motion.div
      className="space-y-6 pb-6"
      variants={fadeListContainer}
      initial="hidden"
      animate="show"
    >
      {/* Header */}
      <motion.div
        variants={fadeListItem}
        className="flex items-center justify-between"
      >
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
            <ArrowLeft size={20} />
          </Button>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              {t.realEstate.title}
            </h1>
            <PinAssetButton assetId="real-estate" />
          </div>
        </div>
        <Button
          onClick={handleAddProperty}
          className="flex items-center gap-2 bg-black dark:bg-white hover:bg-gray-800 dark:hover:bg-gray-200 text-white dark:text-black"
        >
          <Plus className="w-4 h-4" />
          {t.realEstate.addProperty}
        </Button>
      </motion.div>

      {/* Properties Grid */}
      {realEstateList.length === 0 ? (
        <motion.div variants={fadeListItem}>
          <Card className="p-8 text-center">
            <Home className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
              {t.realEstate.addProperty}
            </h3>
            <p className="text-gray-600 dark:text-gray-400 mb-4">
              {t.realEstate.emptyStateDescription}
            </p>
            <Button
              onClick={handleAddProperty}
              className="bg-black dark:bg-white hover:bg-gray-800 dark:hover:bg-gray-200 text-white dark:text-black"
            >
              <Plus className="w-4 h-4 mr-2" />
              {t.realEstate.addProperty}
            </Button>
          </Card>
        </motion.div>
      ) : (
        <motion.div variants={fadeListItem}>
          <motion.div
            variants={fadeListContainer}
            className="grid grid-cols-1 lg:grid-cols-2 gap-6 auto-rows-fr"
          >
            {realEstateList.map(property => (
              <motion.div
                key={property.id}
                variants={fadeListItem}
                className="h-full"
              >
                <Card
                  className="overflow-hidden hover:shadow-lg transition-shadow flex flex-col cursor-pointer h-full"
                  onClick={() => navigate(`/real-estate/${property.id}`)}
                >
                  {/* Property Image Header */}
                  <div className="relative h-48">
                    {property.basic_info.photo_url &&
                    imageUrls[property.basic_info.photo_url] ? (
                      <img
                        src={imageUrls[property.basic_info.photo_url]}
                        alt={property.basic_info.name}
                        className="w-full h-48 object-cover"
                        onError={e => {
                          const target = e.target as HTMLImageElement
                          target.style.display = "none"
                          const fallback =
                            target.nextElementSibling as HTMLElement
                          if (fallback) fallback.style.display = "flex"
                        }}
                      />
                    ) : null}
                    <div
                      className={`w-full h-48 bg-gray-200 dark:bg-gray-700 flex items-center justify-center ${property.basic_info.photo_url && imageUrls[property.basic_info.photo_url] ? "hidden" : "flex"}`}
                    >
                      <Home className="w-16 h-16 text-gray-500" />
                    </div>

                    {/* Action buttons overlay */}
                    <div className="absolute top-3 right-3 flex items-center gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={e => {
                          e.stopPropagation()
                          navigate(`/real-estate/${property.id}/edit`)
                        }}
                        className="bg-black/30 backdrop-blur-sm text-white hover:bg-black/50 h-9 w-9 p-0"
                      >
                        <Edit className="w-4 h-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={e => {
                          e.stopPropagation()
                          handleDeleteProperty(property)
                        }}
                        className="bg-black/30 backdrop-blur-sm text-white hover:bg-red-600/80 h-9 w-9 p-0"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>

                    {/* Property badges overlay */}
                    <div className="absolute bottom-3 left-3 flex gap-2">
                      {property.basic_info.is_residence && (
                        <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-black/50 backdrop-blur-sm text-white">
                          {t.realEstate.residence}
                        </span>
                      )}
                      {property.basic_info.is_rented && (
                        <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-black/50 backdrop-blur-sm text-white">
                          {t.realEstate.rented}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Property Content */}
                  <div className="p-6 flex-1 flex flex-col justify-center">
                    <div className="mb-6">
                      <h3 className="font-semibold text-xl text-gray-900 dark:text-white mb-2">
                        {property.basic_info.name}
                      </h3>

                      {property.location.address && (
                        <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 mb-2">
                          <MapPin className="w-4 h-4" />
                          <span>{property.location.address}</span>
                        </div>
                      )}

                      <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 mb-3">
                        <Calendar className="w-4 h-4" />
                        <span>
                          {formatDate(property.purchase_info.date, locale)}
                        </span>
                      </div>

                      {(property.basic_info.bedrooms ||
                        property.basic_info.bathrooms) && (
                        <div className="flex items-center gap-4 text-sm text-gray-600 dark:text-gray-400">
                          {property.basic_info.bedrooms && (
                            <span className="flex items-center gap-1">
                              <Bed className="w-4 h-4" />
                              {property.basic_info.bedrooms}{" "}
                              {t.realEstate.bedrooms}
                            </span>
                          )}
                          {property.basic_info.bathrooms && (
                            <span className="flex items-center gap-1">
                              <Bath className="w-4 h-4" />
                              {property.basic_info.bathrooms}{" "}
                              {t.realEstate.bathrooms}
                            </span>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Enhanced Financial KPIs */}
                    <div className="space-y-4">
                      {/* Market Value - Primary KPI */}
                      <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
                        <span className="text-sm text-gray-600 dark:text-gray-400 block mb-1">
                          {t.realEstate.estimatedMarketValue}
                        </span>
                        <div className="text-2xl font-bold text-gray-900 dark:text-white">
                          {formatCurrency(
                            property.valuation_info.estimated_market_value,
                            locale,
                            property.currency,
                          )}
                        </div>
                      </div>

                      {/* Financial Summary Grid */}
                      {property.basic_info.is_rented && (
                        <div className="grid grid-cols-2 gap-4">
                          <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-3">
                            <span className="text-xs text-gray-600 dark:text-gray-400 block mb-1">
                              {t.realEstate.initialExpenses}
                            </span>
                            <div className="font-semibold text-gray-900 dark:text-white">
                              {formatCurrency(
                                property.purchase_info.price +
                                  property.purchase_info.expenses.reduce(
                                    (sum, exp) => sum + exp.amount,
                                    0,
                                  ) -
                                  property.flows
                                    .filter(
                                      flow =>
                                        flow.flow_subtype ===
                                        RealEstateFlowSubtype.LOAN,
                                    )
                                    .reduce((sum, flow) => {
                                      const loanPayload =
                                        flow.payload as LoanPayload
                                      return (
                                        sum + (loanPayload.loan_amount || 0)
                                      )
                                    }, 0),
                                locale,
                                property.currency,
                              )}
                            </div>
                          </div>
                          <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-3">
                            <span className="text-xs text-gray-600 dark:text-gray-400 block mb-1">
                              {t.realEstate.analysis.monthlyCashflow}
                            </span>
                            <div
                              className={`font-semibold ${
                                calculateMonthlyCashflow(property) >= 0
                                  ? "text-green-600 dark:text-green-400"
                                  : "text-red-600 dark:text-red-400"
                              }`}
                            >
                              {calculateMonthlyCashflow(property) >= 0
                                ? "+"
                                : ""}
                              {formatCurrency(
                                calculateMonthlyCashflow(property),
                                locale,
                                property.currency,
                              )}
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </Card>
              </motion.div>
            ))}
          </motion.div>
        </motion.div>
      )}

      {/* Form Modal */}
      {isFormModalOpen && (
        <RealEstateFormModal
          isOpen={isFormModalOpen}
          onClose={() => {
            setIsFormModalOpen(false)
            setEditingProperty(null)
          }}
          property={editingProperty}
          onSuccess={handleFormSuccess}
        />
      )}

      {/* Delete Confirmation Dialog */}
      <DeletePropertyDialog
        isOpen={isDeleteDialogOpen}
        propertyName={deletingProperty?.basic_info.name || ""}
        onCancel={() => setIsDeleteDialogOpen(false)}
        onConfirm={confirmDelete}
      />
    </motion.div>
  )
}
