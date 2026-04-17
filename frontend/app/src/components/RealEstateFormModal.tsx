import React, { useState, useEffect, useMemo, useCallback } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { useI18n } from "@/i18n"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { DecimalInput } from "@/components/ui/DecimalInput"
import { Label } from "@/components/ui/Label"
import { DatePicker } from "@/components/ui/DatePicker"
import { Switch } from "@/components/ui/Switch"
import { ConfirmationDialog } from "@/components/ui/ConfirmationDialog"
import { UnassignedFlowsDialog } from "@/components/ui/UnassignedFlowsDialog"
import { useModalBackHandler } from "@/hooks/useModalBackHandler"
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from "@/components/ui/Popover"
import {
  ChevronDown,
  ChevronRight,
  Plus,
  Trash2,
  Upload,
  X,
  Building2,
  Lightbulb,
  MapPin,
  ShoppingCart,
  TrendingUp,
  CreditCard,
  Receipt,
  Zap,
  Home,
  Landmark,
  Calculator,
  Percent,
  Info,
  Link,
  Unlink,
} from "lucide-react"
import { formatCurrency } from "@/lib/formatters"
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
  TooltipProvider,
} from "@/components/ui/tooltip"
import { IconPicker, Icon, type IconName } from "@/components/ui/icon-picker"
import RealEstateStats from "@/components/real-estate/RealEstateStats"
import { getCurrencySymbol, cn } from "@/lib/utils"
import {
  RealEstate,
  CreateRealEstateRequest,
  UpdateRealEstateRequest,
  RealEstateFlow,
  RealEstateFlowSubtype,
  LoanPayload,
  LoanCalculationRequest,
  PurchaseExpense,
  Valuation,
  FlowType,
  FlowFrequency,
  PeriodicFlow,
} from "@/types"
import { ProductType, Loans } from "@/types/position"

import {
  createRealEstate,
  updateRealEstate,
  getImageUrl,
  calculateLoan,
} from "@/services/api"
import { useAppContext } from "@/context/AppContext"
import { useFinancialData } from "@/context/FinancialDataContext"
import { compressImageForUpload } from "@/lib/mobile"

interface RealEstateFormModalProps {
  isOpen: boolean
  onClose: () => void
  property?: RealEstate | null
  onSuccess: () => void
}

interface FormData {
  currency: string
  basic_info: {
    name: string
    is_residence: boolean
    is_rented: boolean
    bathrooms?: number
    bedrooms?: number
  }
  location: {
    address?: string
    cadastral_reference?: string
  }
  purchase_info: {
    date: string
    price: number | null
    expenses: PurchaseExpense[]
  }
  valuation_info: {
    estimated_market_value: number | null
    valuations: Valuation[]
    annual_appreciation?: number | null
  }
  flows: RealEstateFlow[]
  rental_data?: {
    marginal_tax_rate?: number
    vacancy_rate?: number | null
    amortizations: {
      concept: string
      base_amount: number
      percentage: number
      amount: number
    }[]
  }
}

export function RealEstateFormModal({
  isOpen,
  onClose,
  property,
  onSuccess,
}: RealEstateFormModalProps) {
  const { t, locale } = useI18n()
  const { settings, showToast } = useAppContext()
  const {
    periodicFlows,
    positionsData,
    refreshFlows,
    refreshRealEstate,
    ensurePeriodicFlows,
  } = useFinancialData()

  const initialFormData: FormData = {
    currency: settings.general.defaultCurrency,
    basic_info: {
      name: "",
      is_residence: true,
      is_rented: false,
    },
    location: {},
    purchase_info: {
      date: new Date().toISOString().split("T")[0],
      price: null,
      expenses: [],
    },
    valuation_info: {
      estimated_market_value: null,
      valuations: [],
      annual_appreciation: null,
    },
    flows: [],
    rental_data: {
      amortizations: [],
      vacancy_rate: null,
      marginal_tax_rate: undefined,
    },
  }

  const [formData, setFormData] = useState<FormData>(initialFormData)
  const [photo, setPhoto] = useState<File | null>(null)
  const [photoPreview, setPhotoPreview] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false)
  const [showUnsavedDialog, setShowUnsavedDialog] = useState(false)
  const [showRemoveUnassignedDialog, setShowRemoveUnassignedDialog] =
    useState(false)
  const [removeUnassignedFlows, setRemoveUnassignedFlows] = useState(false)
  const [validationErrors, setValidationErrors] = useState<string[]>([])
  const [hasTriedSubmit, setHasTriedSubmit] = useState(false)
  const [availableFlows, setAvailableFlows] = useState<PeriodicFlow[]>([])
  const [showFlowSuggestions, setShowFlowSuggestions] = useState<{
    type: "loans" | "costs" | "utilities" | "rent" | "purchase" | null
    position: { x: number; y: number } | null
  }>({ type: null, position: null })
  const [percentagePopoverOpen, setPercentagePopoverOpen] = useState<
    number | null
  >(null)
  const [tempPercentage, setTempPercentage] = useState("")
  const [rentPercentagePopoverOpen, setRentPercentagePopoverOpen] = useState<
    number | null
  >(null)
  const [tempRentPercentage, setTempRentPercentage] = useState("")
  const [loanPercentagePopoverOpen, setLoanPercentagePopoverOpen] = useState<
    number | null
  >(null)
  const [tempLoanPercentage, setTempLoanPercentage] = useState("")
  const [calculatingLoanIndex, setCalculatingLoanIndex] = useState<
    number | null
  >(null)
  const [unlinkConfirmIndex, setUnlinkConfirmIndex] = useState<number | null>(
    null,
  )
  const [amortizationsExpanded, setAmortizationsExpanded] = useState(false)

  // Track existing periodic flow ids already linked in the form to avoid suggesting them again
  const usedExistingFlowIds = useMemo(() => {
    const ids: string[] = []
    for (const f of formData.flows) {
      const id = (f.periodic_flow_id || f.periodic_flow?.id) as
        | string
        | undefined
      if (id) ids.push(id)
    }
    return new Set(ids)
  }, [formData.flows])

  // Reusable helper to infer an icon "kind" from a suggested flow, reused both
  // for suggestion chips and for the icon applied on accepting a suggestion.
  type SuggestionSection = "loans" | "costs" | "utilities" | "rent" | null
  type IconKind =
    | "electricity"
    | "gas"
    | "water"
    | "internet"
    | "loanPosition"
    | "generic"
    | "money"

  const getSuggestionKind = (
    f: PeriodicFlow,
    section: SuggestionSection,
  ): IconKind => {
    const isGeneric = (f.amount ?? 0) === 0
    if (section === "utilities") {
      const n = (f.name || "").toLowerCase()
      if (n.includes("electric")) return "electricity"
      if (n.includes("gas")) return "gas"
      if (n.includes("water")) return "water"
      if (n.includes("internet")) return "internet"
      return isGeneric ? "generic" : "money"
    }
    if (section === "loans") {
      if (f.id?.startsWith("loan-suggestion-")) return "loanPosition"
      return isGeneric ? "generic" : "money"
    }
    if (section === "costs") return isGeneric ? "generic" : "money"
    if (section === "rent") return isGeneric ? "generic" : "money"
    return isGeneric ? "generic" : "money"
  }

  const iconKindToName: Record<IconKind, IconName> = {
    electricity: "zap",
    gas: "flame",
    water: "droplets",
    internet: "wifi",
    loanPosition: "banknote",
    generic: "lightbulb",
    money: "dollar-sign",
  }

  const getSuggestionIconName = (
    f: PeriodicFlow,
    section: "loans" | "costs" | "utilities" | "rent" | null,
  ): IconName | undefined => {
    if (f.icon) return f.icon as IconName
    const kind = getSuggestionKind(f, section)
    if (kind === "generic") {
      if (section === "utilities") return "house-plug"
      if (section === "costs") return "house"
      if (section === "rent") return "hand-coins"
    }
    return iconKindToName[kind]
  }

  // Map each generic flow id to the section where it should be suggested
  // This ensures, for example, that insurance/community/IBI appear under costs,
  // while electricity/gas/water/internet appear under utilities, and rent under rent.
  const genericSectionMap: Record<string, "costs" | "utilities" | "rent"> = {
    "generic-community": "costs",
    "generic-insurance": "costs",
    "generic-ibi": "costs",
    "generic-electricity": "utilities",
    "generic-gas": "utilities",
    "generic-water": "utilities",
    "generic-internet": "utilities",
    "generic-rent": "rent",
  }

  useEffect(() => {
    if (isOpen) {
      ensurePeriodicFlows()
    }
  }, [isOpen, ensurePeriodicFlows])

  useEffect(() => {
    const getLoanSuggestionsFromPositions = (): PeriodicFlow[] => {
      if (!positionsData?.positions) {
        return []
      }

      const loanSuggestions: PeriodicFlow[] = []

      Object.values(positionsData.positions)
        .flat()
        .forEach(globalPosition => {
          if (
            globalPosition.products &&
            globalPosition.products[ProductType.LOAN]
          ) {
            const loanProducts = globalPosition.products[
              ProductType.LOAN
            ] as Loans

            if (loanProducts && loanProducts.entries) {
              loanProducts.entries.forEach(loan => {
                if (
                  !loan ||
                  typeof loan.current_installment !== "number" ||
                  loan.current_installment <= 0
                ) {
                  return
                }

                const sinceDate =
                  loan.creation ||
                  loan.next_payment_date ||
                  new Date().toISOString().split("T")[0]

                loanSuggestions.push({
                  id: `loan-suggestion-${loan.id}`,
                  name: loan.name || t.realEstate.flows.genericNames.mortgage,
                  flow_type: FlowType.EXPENSE,
                  amount: loan.current_installment,
                  frequency: FlowFrequency.MONTHLY,
                  category: t.realEstate.flows.categories.loans,
                  enabled: true,
                  since: sinceDate,
                  until: loan.maturity || "",
                  currency: loan.currency,
                })
              })
            }
          }
        })

      return loanSuggestions
    }

    const genericFlows: PeriodicFlow[] = [
      {
        id: "generic-community",
        name: t.realEstate.flows.genericNames.community,
        flow_type: FlowType.EXPENSE,
        amount: 0,
        frequency: FlowFrequency.MONTHLY,
        category: t.realEstate.flows.categories.propertyCosts,
        enabled: true,
        since: new Date().toISOString().split("T")[0],
        currency: formData.currency,
      },
      {
        id: "generic-insurance",
        name: t.realEstate.flows.genericNames.homeInsurance,
        flow_type: FlowType.EXPENSE,
        amount: 0,
        frequency: FlowFrequency.MONTHLY,
        category: t.realEstate.flows.categories.propertyCosts,
        enabled: true,
        since: new Date().toISOString().split("T")[0],
        currency: formData.currency,
      },
      {
        id: "generic-ibi",
        name: t.realEstate.flows.genericNames.ibi,
        flow_type: FlowType.EXPENSE,
        amount: 0,
        frequency: FlowFrequency.YEARLY,
        category: t.realEstate.flows.categories.propertyCosts,
        enabled: true,
        since: new Date().toISOString().split("T")[0],
        currency: formData.currency,
      },
      {
        id: "generic-electricity",
        name: t.realEstate.flows.genericNames.electricity,
        flow_type: FlowType.EXPENSE,
        amount: 0,
        frequency: FlowFrequency.MONTHLY,
        category: t.realEstate.flows.categories.utilities,
        enabled: true,
        since: new Date().toISOString().split("T")[0],
        currency: formData.currency,
      },
      {
        id: "generic-gas",
        name: t.realEstate.flows.genericNames.gas,
        flow_type: FlowType.EXPENSE,
        amount: 0,
        frequency: FlowFrequency.MONTHLY,
        category: t.realEstate.flows.categories.utilities,
        enabled: true,
        since: new Date().toISOString().split("T")[0],
        currency: formData.currency,
      },
      {
        id: "generic-water",
        name: t.realEstate.flows.genericNames.water,
        flow_type: FlowType.EXPENSE,
        amount: 0,
        frequency: FlowFrequency.MONTHLY,
        category: t.realEstate.flows.categories.utilities,
        enabled: true,
        since: new Date().toISOString().split("T")[0],
        currency: formData.currency,
      },
      {
        id: "generic-internet",
        name: t.realEstate.flows.genericNames.internet,
        flow_type: FlowType.EXPENSE,
        amount: 0,
        frequency: FlowFrequency.MONTHLY,
        category: t.realEstate.flows.categories.utilities,
        enabled: true,
        since: new Date().toISOString().split("T")[0],
        currency: formData.currency,
      },
      {
        id: "generic-rent",
        name: t.realEstate.flows.genericNames.rent,
        flow_type: FlowType.EARNING,
        amount: 0,
        frequency: FlowFrequency.MONTHLY,
        category: t.realEstate.flows.categories.propertyIncome,
        enabled: true,
        since: new Date().toISOString().split("T")[0],
        currency: formData.currency,
      },
    ]

    const loanSuggestionsFromPositions = getLoanSuggestionsFromPositions()

    setAvailableFlows([
      ...periodicFlows,
      ...genericFlows,
      ...loanSuggestionsFromPositions,
    ])
  }, [periodicFlows, positionsData, formData.currency, t])

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (showFlowSuggestions.type && showFlowSuggestions.position) {
        const target = event.target as HTMLElement
        const popover = document.querySelector("[data-suggestions-popover]")
        if (popover && !popover.contains(target)) {
          setShowFlowSuggestions({ type: null, position: null })
        }
      }
    }

    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [showFlowSuggestions])

  const handleSuggestionClick = (
    event: React.MouseEvent,
    type: "loans" | "costs" | "utilities" | "rent" | "purchase",
  ) => {
    event.preventDefault()
    event.stopPropagation()

    if (showFlowSuggestions.type === type) {
      setShowFlowSuggestions({ type: null, position: null })
      return
    }

    const rect = event.currentTarget.getBoundingClientRect()
    setShowFlowSuggestions({
      type,
      position: { x: rect.right + 10, y: rect.top },
    })
  }

  const applyPurchaseConcept = (concept: string) => {
    setFormData(prev => ({
      ...prev,
      purchase_info: {
        ...prev.purchase_info,
        expenses: [
          ...prev.purchase_info.expenses,
          { concept, amount: 0, description: "" },
        ],
      },
    }))
    setHasUnsavedChanges(true)
    setShowFlowSuggestions({ type: null, position: null })
  }

  const applyFlowSuggestion = (flow: PeriodicFlow) => {
    let flowSubtype: RealEstateFlowSubtype
    switch (showFlowSuggestions.type) {
      case "loans":
        flowSubtype = RealEstateFlowSubtype.LOAN
        break
      case "costs":
        flowSubtype = RealEstateFlowSubtype.COST
        break
      case "utilities":
        flowSubtype = RealEstateFlowSubtype.SUPPLY
        break
      case "rent":
        flowSubtype = RealEstateFlowSubtype.RENT
        break
      default:
        return
    }

    const category =
      flow.category || `${flow.name} ${formData.basic_info.name}`.trim()
    const periodicFlowData: PeriodicFlow = {
      ...flow,
      id:
        flow.id?.startsWith("generic-") ||
        flow.id?.startsWith("loan-suggestion-")
          ? undefined
          : flow.id,
      name: flow.name,
      category,
      since: flow.id?.startsWith("generic-")
        ? new Date().toISOString().split("T")[0]
        : flow.since,
      until: flow.id?.startsWith("generic-") ? undefined : flow.until,
      currency: formData.currency,
      icon: (getSuggestionIconName(flow, showFlowSuggestions.type) ||
        flow.icon) as IconName | undefined,
    }

    const newFlow: RealEstateFlow = {
      periodic_flow_id:
        flow.id?.startsWith("generic-") ||
        flow.id?.startsWith("loan-suggestion-")
          ? undefined
          : flow.id,
      periodic_flow: periodicFlowData,
      flow_subtype: flowSubtype,
      description: flow.name,
      payload:
        flowSubtype === RealEstateFlowSubtype.COST
          ? { tax_deductible: formData.basic_info.is_rented }
          : flowSubtype === RealEstateFlowSubtype.SUPPLY
            ? { tax_deductible: formData.basic_info.is_rented }
            : flowSubtype === RealEstateFlowSubtype.LOAN
              ? (() => {
                  if (flow.id?.startsWith("loan-suggestion-")) {
                    const loanId = flow.id?.replace("loan-suggestion-", "")
                    let loanData: any = null
                    if (positionsData?.positions) {
                      Object.values(positionsData.positions)
                        .flat()
                        .forEach(globalPosition => {
                          if (
                            globalPosition.products &&
                            globalPosition.products[ProductType.LOAN]
                          ) {
                            const loanProducts = globalPosition.products[
                              ProductType.LOAN
                            ] as Loans
                            if (loanProducts && loanProducts.entries) {
                              const foundLoan = loanProducts.entries.find(
                                loan => loan.id === loanId,
                              )
                              if (foundLoan) {
                                loanData = foundLoan
                              }
                            }
                          }
                        })
                    }
                    if (loanData) {
                      console.log(
                        "Found loan data for loan ID:",
                        loanId,
                        loanData,
                      )
                      return {
                        type: loanData.type || "MORTGAGE",
                        loan_amount: loanData.loan_amount || null,
                        interest_rate: loanData.interest_rate || 0,
                        payment_date:
                          loanData.next_payment_date ||
                          new Date().toISOString().split("T")[0],
                        principal_outstanding:
                          loanData.principal_outstanding || 0,
                        euribor_rate: loanData.euribor_rate ?? null,
                        interest_type: loanData.interest_type || "FIXED",
                        fixed_years: loanData.fixed_years ?? null,
                        fixed_interest_rate:
                          loanData.fixed_interest_rate ?? null,
                        principal_paid: loanData.principal_paid ?? null,
                        monthly_interests:
                          loanData.installment_interests ?? null,
                        monthly_payment: loanData.current_installment ?? null,
                        linked_loan_hash: loanData.hash ?? null,
                        installment_frequency:
                          loanData.installment_frequency ?? "MONTHLY",
                      }
                    } else {
                      console.log("No loan data found for loan ID:", loanId)
                    }
                  }
                  return {
                    type: "MORTGAGE",
                    loan_amount: null,
                    interest_rate: 0,
                    payment_date: new Date().toISOString().split("T")[0],
                    euribor_rate: null,
                    interest_type: "FIXED",
                    fixed_years: null,
                    principal_paid: null,
                    monthly_interests: null,
                  }
                })()
              : {},
    }

    // Move linked_loan_hash from payload to flow level
    if ((newFlow.payload as any)?.linked_loan_hash) {
      newFlow.linked_loan_hash = (newFlow.payload as any).linked_loan_hash
      delete (newFlow.payload as any).linked_loan_hash
    }

    setFormData(prev => ({
      ...prev,
      flows: [...prev.flows, newFlow],
    }))
    setHasUnsavedChanges(true)
    setShowFlowSuggestions({ type: null, position: null })
  }

  const [expandedSections, setExpandedSections] = useState({
    basic: true,
    location: false,
    purchase: false,
    valuation: false,
    loans: false,
    costs: false,
    utilities: false,
    rent: false,
  })

  useEffect(() => {
    if (isOpen) {
      if (property) {
        setFormData({
          currency: property.currency,
          basic_info: {
            ...property.basic_info,
            bathrooms: property.basic_info.bathrooms || undefined,
            bedrooms: property.basic_info.bedrooms || undefined,
          },
          location: {
            address: property.location.address || undefined,
            cadastral_reference:
              property.location.cadastral_reference || undefined,
          },
          purchase_info: property.purchase_info,
          valuation_info: property.valuation_info,
          flows: property.flows,
          rental_data: {
            marginal_tax_rate:
              property.rental_data?.marginal_tax_rate || undefined,
            amortizations: property.rental_data?.amortizations || [],
            vacancy_rate: property.rental_data?.vacancy_rate ?? null,
          },
        })
        if (property.basic_info.photo_url) {
          getImageUrl(
            property.basic_info.photo_url,
            property.updated_at || Date.now(),
          )
            .then(fullUrl => {
              setPhotoPreview(fullUrl)
            })
            .catch(error => {
              console.error("Error loading image:", error)
            })
        }
      } else {
        setFormData(initialFormData)
        setPhoto(null)
        setPhotoPreview(null)
      }
      setHasUnsavedChanges(false)
      setValidationErrors([])
      setHasTriedSubmit(false)
      setRemoveUnassignedFlows(false)
    }
  }, [isOpen, property])

  const handleInputChange = (field: string, value: any) => {
    setFormData(prev => {
      const keys = field.split(".")
      const newData = { ...prev }
      let current: any = newData

      for (let i = 0; i < keys.length - 1; i++) {
        current = current[keys[i]]
      }
      current[keys[keys.length - 1]] = value

      return newData
    })
    setHasUnsavedChanges(true)
  }

  // Auto-calculate monthly interests for linked loans with empty monthly_interests
  useEffect(() => {
    const linkedLoansToCalc = formData.flows
      .map((flow, idx) => ({ flow, idx }))
      .filter(({ flow }) => {
        if (flow.flow_subtype !== RealEstateFlowSubtype.LOAN) return false
        const payload = flow.payload as any
        return flow.linked_loan_hash && payload?.monthly_interests == null
      })

    if (linkedLoansToCalc.length === 0) return

    let cancelled = false
    ;(async () => {
      for (const { flow, idx } of linkedLoansToCalc) {
        if (cancelled) return
        const loanPayload = flow.payload as any
        const startStr =
          flow.periodic_flow?.since || new Date().toISOString().split("T")[0]
        const endStr =
          flow.periodic_flow?.until && flow.periodic_flow.until.trim() !== ""
            ? flow.periodic_flow.until
            : startStr

        const req: LoanCalculationRequest = {
          interest_rate: loanPayload.interest_rate || 0,
          interest_type: loanPayload.interest_type || "FIXED",
          euribor_rate: loanPayload.euribor_rate ?? undefined,
          fixed_years: loanPayload.fixed_years ?? undefined,
          fixed_interest_rate: loanPayload.fixed_interest_rate ?? undefined,
          start: startStr,
          end: endStr,
        }

        if (
          loanPayload.principal_outstanding &&
          loanPayload.principal_outstanding > 0
        ) {
          req.principal_outstanding = loanPayload.principal_outstanding
        } else if (loanPayload.loan_amount && loanPayload.loan_amount > 0) {
          req.loan_amount = loanPayload.loan_amount
        } else {
          continue
        }

        try {
          const result = await calculateLoan(req)
          if (cancelled) return
          setFormData(prev => {
            const flows = [...prev.flows]
            const f = { ...flows[idx] }
            const payload = { ...(f.payload as any) }
            if (result.current_installment_interests != null) {
              payload.monthly_interests = result.current_installment_interests
            }
            f.payload = payload
            flows[idx] = f
            return { ...prev, flows }
          })
        } catch {
          // Silently ignore — not critical
        }
      }
    })()

    return () => {
      cancelled = true
    }
  }, [formData.flows.map(f => f.linked_loan_hash).join(",")])

  const toggleSection = (section: keyof typeof expandedSections) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section],
    }))
  }

  const handlePhotoChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    const processedFile = await compressImageForUpload(file)
    setPhoto(processedFile)
    const reader = new FileReader()
    reader.onload = e => {
      setPhotoPreview(e.target?.result as string)
    }
    reader.readAsDataURL(processedFile)
    setHasUnsavedChanges(true)
  }

  const addPurchaseExpense = () => {
    setFormData(prev => ({
      ...prev,
      purchase_info: {
        ...prev.purchase_info,
        expenses: [
          ...prev.purchase_info.expenses,
          { concept: "", amount: 0, description: "" },
        ],
      },
    }))
    setHasUnsavedChanges(true)
  }

  const removePurchaseExpense = (index: number) => {
    setFormData(prev => ({
      ...prev,
      purchase_info: {
        ...prev.purchase_info,
        expenses: prev.purchase_info.expenses.filter((_, i) => i !== index),
      },
    }))
    setHasUnsavedChanges(true)
  }

  const calculateAmountFromPercentage = (percentage: number) => {
    const purchasePrice = formData.purchase_info.price || 0
    return (purchasePrice * percentage) / 100
  }

  const applyPercentageToExpense = (
    expenseIndex: number,
    percentage: number,
  ) => {
    const calculatedAmount = calculateAmountFromPercentage(percentage)
    const newExpenses = [...formData.purchase_info.expenses]
    newExpenses[expenseIndex] = {
      ...newExpenses[expenseIndex],
      amount: calculatedAmount,
    }
    handleInputChange("purchase_info.expenses", newExpenses)
    setPercentagePopoverOpen(null)
    setTempPercentage("")
  }

  const openPercentagePopover = (expenseIndex: number) => {
    setPercentagePopoverOpen(expenseIndex)
    setTempPercentage("")
  }

  const calculateLoanAmountFromPercentage = (percentage: number) => {
    const purchasePrice = formData.purchase_info.price || 0
    return (purchasePrice * percentage) / 100
  }

  const applyLoanPercentage = (flowIndex: number, percentage: number) => {
    const calculatedAmount = calculateLoanAmountFromPercentage(percentage)
    updateFlowPayload(flowIndex, "loan_amount", calculatedAmount)
    setLoanPercentagePopoverOpen(null)
    setTempLoanPercentage("")
  }

  const openLoanPercentagePopover = (flowIndex: number) => {
    setLoanPercentagePopoverOpen(flowIndex)
    setTempLoanPercentage("")
  }

  const calculateAmountFromRentPercentage = (percentage: number) => {
    // Use rent income AFTER applying vacancy rate (default 0)
    const totalRentGross = calculateMonthlyIncome()
    const vacancyRate = formData.rental_data?.vacancy_rate ?? 0
    const totalRentNet = totalRentGross * (1 - vacancyRate)
    return Math.round(totalRentNet * percentage) / 100
  }

  const applyRentPercentageToFlow = (flowIndex: number, percentage: number) => {
    const calculatedAmount = calculateAmountFromRentPercentage(percentage)
    setFormData(prev => ({
      ...prev,
      flows: prev.flows.map((flow, i) =>
        i === flowIndex && flow.periodic_flow
          ? {
              ...flow,
              periodic_flow: {
                ...flow.periodic_flow,
                amount: calculatedAmount,
              },
            }
          : flow,
      ),
    }))
    setHasUnsavedChanges(true)
    setRentPercentagePopoverOpen(null)
    setTempRentPercentage("")
  }

  const openRentPercentagePopover = (flowIndex: number) => {
    setRentPercentagePopoverOpen(flowIndex)
    setTempRentPercentage("")
  }

  const addValuation = () => {
    setFormData(prev => ({
      ...prev,
      valuation_info: {
        ...prev.valuation_info,
        valuations: [
          ...prev.valuation_info.valuations,
          {
            date: new Date().toISOString().split("T")[0],
            amount: 0,
            notes: "",
          },
        ],
      },
    }))
    setHasUnsavedChanges(true)
  }

  const removeValuation = (index: number) => {
    setFormData(prev => ({
      ...prev,
      valuation_info: {
        ...prev.valuation_info,
        valuations: prev.valuation_info.valuations.filter(
          (_, i) => i !== index,
        ),
      },
    }))
    setHasUnsavedChanges(true)
  }

  const addFlow = (flowSubtype: RealEstateFlowSubtype) => {
    const newFlow: RealEstateFlow = {
      flow_subtype: flowSubtype,
      description: "",
      payload:
        flowSubtype === RealEstateFlowSubtype.LOAN
          ? {
              type: "MORTGAGE",
              loan_amount: null,
              interest_rate: 0,
              payment_date: new Date().toISOString().split("T")[0],
              principal_outstanding: 0,
              euribor_rate: null,
              interest_type: "FIXED",
              fixed_years: null,
              principal_paid: null,
            }
          : flowSubtype === RealEstateFlowSubtype.COST
            ? {
                tax_deductible: formData.basic_info.is_rented,
              }
            : flowSubtype === RealEstateFlowSubtype.SUPPLY
              ? {
                  tax_deductible: formData.basic_info.is_rented,
                }
              : {},
      periodic_flow: {
        id: undefined,
        name: "",
        amount: 0,
        flow_type:
          flowSubtype === RealEstateFlowSubtype.RENT
            ? FlowType.EARNING
            : FlowType.EXPENSE,
        frequency:
          flowSubtype === RealEstateFlowSubtype.LOAN
            ? FlowFrequency.MONTHLY
            : flowSubtype === RealEstateFlowSubtype.COST ||
                flowSubtype === RealEstateFlowSubtype.SUPPLY
              ? FlowFrequency.MONTHLY
              : FlowFrequency.MONTHLY,
        category: "",
        enabled: true,
        since: new Date().toISOString().split("T")[0],
        until: undefined,
        currency: formData.currency,
        icon:
          flowSubtype === RealEstateFlowSubtype.RENT
            ? ("hand-coins" as IconName)
            : flowSubtype === RealEstateFlowSubtype.COST
              ? ("house" as IconName)
              : flowSubtype === RealEstateFlowSubtype.SUPPLY
                ? ("house-plug" as IconName)
                : flowSubtype === RealEstateFlowSubtype.LOAN
                  ? ("banknote" as IconName)
                  : undefined,
      },
    }

    setFormData(prev => ({
      ...prev,
      flows: [...prev.flows, newFlow],
    }))
    setHasUnsavedChanges(true)
  }

  const removeFlow = (index: number) => {
    setFormData(prev => ({
      ...prev,
      flows: prev.flows.filter((_, i) => i !== index),
    }))
    setHasUnsavedChanges(true)
  }

  const updateFlowAmount = (index: number, amount: number) => {
    setFormData(prev => ({
      ...prev,
      flows: prev.flows.map((flow, i) =>
        i === index && flow.periodic_flow
          ? {
              ...flow,
              periodic_flow: { ...flow.periodic_flow, amount },
            }
          : flow,
      ),
    }))
    setHasUnsavedChanges(true)
  }

  const updateFlowPayload = (index: number, field: string, value: any) => {
    setFormData(prev => ({
      ...prev,
      flows: prev.flows.map((flow, i) =>
        i === index
          ? {
              ...flow,
              payload: { ...flow.payload, [field]: value },
            }
          : flow,
      ),
    }))
    setHasUnsavedChanges(true)
  }

  const updateFlowName = (index: number, name: string) => {
    setFormData(prev => ({
      ...prev,
      flows: prev.flows.map((flow, i) =>
        i === index
          ? {
              ...flow,
              description: name,
            }
          : flow,
      ),
    }))
    setHasUnsavedChanges(true)
  }

  const updateFlowFrequency = (index: number, frequency: FlowFrequency) => {
    setFormData(prev => ({
      ...prev,
      flows: prev.flows.map((flow, i) =>
        i === index && flow.periodic_flow
          ? {
              ...flow,
              periodic_flow: { ...flow.periodic_flow, frequency },
            }
          : flow,
      ),
    }))
    setHasUnsavedChanges(true)
  }

  const calculateTotalPurchaseCost = () => {
    const expensesTotal = formData.purchase_info.expenses.reduce(
      (sum, expense) => sum + expense.amount,
      0,
    )
    return (formData.purchase_info.price || 0) + expensesTotal
  }

  const calculateMonthlyIncome = () => {
    return formData.flows
      .filter(flow => flow.flow_subtype === RealEstateFlowSubtype.RENT)
      .reduce((sum, flow) => {
        if (flow.periodic_flow) {
          return sum + flow.periodic_flow.amount
        }
        return sum
      }, 0)
  }

  const validate = (): boolean => {
    const errors: string[] = []

    if (!formData.basic_info.name.trim()) {
      errors.push("basic_info.name")
    }
    if (!formData.purchase_info.date) {
      errors.push("purchase_info.date")
    }
    if (!formData.purchase_info.price || formData.purchase_info.price <= 0) {
      errors.push("purchase_info.price")
    }
    if (
      !formData.valuation_info.estimated_market_value ||
      formData.valuation_info.estimated_market_value <= 0
    ) {
      errors.push("valuation_info.estimated_market_value")
    }

    // Validate flows
    formData.flows.forEach((flow, index) => {
      if (!flow.description?.trim()) {
        errors.push(`flow.${index}.name`)
      }

      if (!flow.periodic_flow?.amount || flow.periodic_flow.amount <= 0) {
        errors.push(`flow.${index}.amount`)
      }

      // Validate rent flows have payment date
      if (
        flow.flow_subtype === RealEstateFlowSubtype.RENT &&
        !flow.periodic_flow?.since
      ) {
        errors.push(`flow.${index}.since`)
      }

      // Validate loan flows require since and until dates
      if (flow.flow_subtype === RealEstateFlowSubtype.LOAN) {
        if (!flow.periodic_flow?.since) {
          errors.push(`flow.${index}.since`)
        }
        if (!flow.periodic_flow?.until) {
          errors.push(`flow.${index}.until`)
        }
      }
    })

    // Validate amortizations (all fields required when renting)
    if (formData.basic_info.is_rented) {
      const amorts = formData.rental_data?.amortizations || []
      amorts.forEach((a, idx) => {
        if (!a.concept || !a.concept.trim()) {
          errors.push(`amortizations.${idx}.concept`)
        }
        if (!(a.base_amount > 0)) {
          errors.push(`amortizations.${idx}.base_amount`)
        }
        if (!(a.percentage > 0)) {
          errors.push(`amortizations.${idx}.percentage`)
        }
        if (!(a.amount > 0)) {
          errors.push(`amortizations.${idx}.amount`)
        }
      })
    }

    setValidationErrors(errors)
    return errors.length === 0
  }

  const hasValidationError = (field: string): boolean => {
    return hasTriedSubmit && validationErrors.includes(field)
  }

  const handleSubmit = async () => {
    setHasTriedSubmit(true)
    if (!validate()) return

    // Check if we need to ask about removing unassigned flows
    if (property && hasUnassignedFlows()) {
      setShowRemoveUnassignedDialog(true)
      return
    }

    await submitForm()
  }

  const hasUnassignedFlows = (): boolean => {
    if (!property) return false

    const originalFlowIds = new Set(
      property.flows.map(f => f.periodic_flow_id).filter(Boolean),
    )
    const currentFlowIds = new Set(
      formData.flows.map(f => f.periodic_flow_id).filter(Boolean),
    )

    for (const originalId of originalFlowIds) {
      if (!currentFlowIds.has(originalId)) {
        return true
      }
    }
    return false
  }

  const submitForm = async (forceRemoveUnassignedFlows?: boolean) => {
    try {
      setLoading(true)

      // Use the forced value if provided, otherwise use the state
      const shouldRemoveUnassignedFlows =
        forceRemoveUnassignedFlows !== undefined
          ? forceRemoveUnassignedFlows
          : removeUnassignedFlows

      // Process flows to set proper names and categories
      const processedFlows = formData.flows.map(flow => {
        let processedFlow = flow
        if (flow.description?.trim()) {
          processedFlow = {
            ...flow,
            periodic_flow: flow.periodic_flow
              ? {
                  ...flow.periodic_flow,
                  name: `${flow.description} ${formData.basic_info.name}`.trim(),
                  category: formData.basic_info.name,
                }
              : undefined,
          } as RealEstateFlow
        }

        // For linked loans, no payload needed — backend injects real data on read
        if (
          processedFlow.flow_subtype === RealEstateFlowSubtype.LOAN &&
          processedFlow.linked_loan_hash
        ) {
          processedFlow = {
            ...processedFlow,
            payload: {},
          }
        }

        return processedFlow
      })

      const processedFormData = {
        ...formData,
        flows: processedFlows,
      }

      if (property?.id) {
        // Update
        const request: UpdateRealEstateRequest = {
          data: {
            ...processedFormData,
            currency: processedFormData.currency,
            purchase_info: {
              ...processedFormData.purchase_info,
              price: processedFormData.purchase_info.price || 0,
            },
            valuation_info: {
              ...processedFormData.valuation_info,
              estimated_market_value:
                processedFormData.valuation_info.estimated_market_value || 0,
            },
            rental_data: processedFormData.rental_data || {
              amortizations: [],
              vacancy_rate: null,
            },
            id: property.id,
            remove_unassigned_flows: shouldRemoveUnassignedFlows,
          },
          photo: photo || undefined,
        }
        await updateRealEstate(request)
        showToast(t.realEstate.success.updated, "success")
        // Refresh lists after updating
        await Promise.all([refreshFlows(), refreshRealEstate()])
      } else {
        // Create
        const request: CreateRealEstateRequest = {
          data: {
            ...processedFormData,
            currency: processedFormData.currency,
            purchase_info: {
              ...processedFormData.purchase_info,
              price: processedFormData.purchase_info.price || 0,
            },
            valuation_info: {
              ...processedFormData.valuation_info,
              estimated_market_value:
                processedFormData.valuation_info.estimated_market_value || 0,
            },
            rental_data: processedFormData.rental_data || {
              amortizations: [],
              vacancy_rate: null,
            },
          },
          photo: photo || undefined,
        }
        await createRealEstate(request)
        showToast(t.realEstate.success.created, "success")
        // Refresh lists after creating
        await Promise.all([refreshFlows(), refreshRealEstate()])
      }

      onSuccess()
    } catch (error) {
      console.error("Error saving property:", error)
      showToast(
        property
          ? t.realEstate.errors.updateFailed
          : t.realEstate.errors.createFailed,
        "error",
      )
    } finally {
      setLoading(false)
    }
  }

  const handleClose = useCallback(() => {
    if (hasUnsavedChanges) {
      setShowUnsavedDialog(true)
    } else {
      onClose()
    }
  }, [hasUnsavedChanges, onClose])

  useModalBackHandler(isOpen, handleClose)

  const getFrequencyLabel = (
    freq?: FlowFrequency | string,
    lowercase = false,
  ): string => {
    if (!freq) return ""
    const labels: Record<string, string> = {
      DAILY: t.realEstate.frequency.daily,
      WEEKLY: t.realEstate.frequency.weekly,
      BIWEEKLY: (t.realEstate.frequency as any).biweekly || "Biweekly",
      SEMIMONTHLY: (t.realEstate.frequency as any).semimonthly || "Semimonthly",
      MONTHLY: t.realEstate.frequency.monthly,
      EVERY_TWO_MONTHS: t.realEstate.frequency.bimonthly,
      QUARTERLY: t.realEstate.frequency.quarterly,
      EVERY_FOUR_MONTHS: t.realEstate.frequency.fourMonthly,
      SEMIANNUALLY: t.realEstate.frequency.semiannually,
      YEARLY: t.realEstate.frequency.yearly,
    }
    const label = labels[String(freq)] || String(freq)
    return lowercase ? label.toLowerCase() : label
  }

  // Purchase expense concepts (not flows)
  const purchaseConcepts = [
    t.realEstate.flows.purchaseConcepts.notary,
    t.realEstate.flows.purchaseConcepts.propertyRegistry,
    t.realEstate.flows.purchaseConcepts.realEstate,
    t.realEstate.flows.purchaseConcepts.transferTax,
    t.realEstate.flows.purchaseConcepts.management,
    t.realEstate.flows.purchaseConcepts.renovation,
    t.realEstate.flows.purchaseConcepts.appraisal,
    t.realEstate.flows.purchaseConcepts.bankCommission,
    t.realEstate.flows.purchaseConcepts.mortgageFormalization,
    t.realEstate.flows.purchaseConcepts.damageInsurance,
  ]

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[70] p-2"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2, ease: "easeOut" }}
        >
          <motion.div
            className="bg-card text-card-foreground rounded-lg max-w-4xl w-full max-h-[95vh] relative z-[80] shadow-xl flex flex-col"
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
          >
            <div className="flex-1 overflow-y-auto p-4 space-y-6">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-semibold">
                  {property
                    ? t.realEstate.editProperty
                    : t.realEstate.addProperty}
                </h2>
              </div>
              <div>
                <button
                  type="button"
                  onClick={() => toggleSection("basic")}
                  className="flex items-center justify-between w-full text-left"
                >
                  <h3 className="text-lg font-medium flex items-center gap-2">
                    <Building2 size={18} />
                    {t.realEstate.sections.basic}
                    {expandedSections.basic ? (
                      <ChevronDown
                        size={18}
                        className="text-muted-foreground"
                      />
                    ) : (
                      <ChevronRight
                        size={18}
                        className="text-muted-foreground"
                      />
                    )}
                  </h3>
                </button>

                {expandedSections.basic && (
                  <div className="mt-4 space-y-4">
                    <div>
                      <Label htmlFor="name">
                        {t.realEstate.basicInfo.name}
                        <span className="text-gray-400 ml-1">*</span>
                      </Label>
                      <Input
                        id="name"
                        value={formData.basic_info.name}
                        onChange={e =>
                          handleInputChange("basic_info.name", e.target.value)
                        }
                        placeholder={t.realEstate.placeholders.propertyName}
                        className={
                          hasValidationError("basic_info.name")
                            ? "border-red-500"
                            : ""
                        }
                      />
                    </div>

                    <div>
                      <Label>{t.realEstate.basicInfo.photo}</Label>
                      <div className="mt-2 flex items-center gap-4">
                        <input
                          type="file"
                          accept="image/*"
                          onChange={handlePhotoChange}
                          className="hidden"
                          id="photo-upload"
                        />
                        <label
                          htmlFor="photo-upload"
                          className="cursor-pointer flex items-center gap-2 px-4 py-2 border border-input rounded-md text-foreground bg-background hover:bg-accent hover:text-accent-foreground"
                        >
                          <Upload size={16} />
                          {t.common.upload}
                        </label>
                        {photoPreview && (
                          <img
                            src={photoPreview}
                            alt="Preview"
                            className="w-16 h-16 rounded-lg object-cover select-none"
                            style={{ WebkitTouchCallout: "none" }}
                            draggable={false}
                            onContextMenu={e => e.preventDefault()}
                          />
                        )}
                      </div>
                    </div>

                    <div>
                      <Label>
                        {t.realEstate.basicInfo.purchaseDate}
                        <span className="text-gray-400 ml-1">*</span>
                      </Label>
                      <DatePicker
                        value={formData.purchase_info.date}
                        onChange={value =>
                          handleInputChange("purchase_info.date", value)
                        }
                        placeholder={t.realEstate.placeholders.selectDate}
                        className={
                          hasValidationError("purchase_info.date")
                            ? "border-red-500"
                            : ""
                        }
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div className="flex items-center justify-between">
                        <Label>{t.realEstate.basicInfo.isResidence}</Label>
                        <Switch
                          checked={formData.basic_info.is_residence}
                          onCheckedChange={checked =>
                            handleInputChange(
                              "basic_info.is_residence",
                              checked,
                            )
                          }
                        />
                      </div>

                      <div className="flex items-center justify-between">
                        <Label>{t.realEstate.basicInfo.isRented}</Label>
                        <Switch
                          checked={formData.basic_info.is_rented}
                          onCheckedChange={checked => {
                            handleInputChange("basic_info.is_rented", checked)
                            if (checked) {
                              setExpandedSections(prev => ({
                                ...prev,
                                rent: true,
                              }))
                            }
                          }}
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label>{t.realEstate.basicInfo.bedrooms}</Label>
                        <Input
                          type="text"
                          inputMode="numeric"
                          value={formData.basic_info.bedrooms || ""}
                          onChange={e =>
                            handleInputChange(
                              "basic_info.bedrooms",
                              e.target.value
                                ? parseInt(e.target.value)
                                : undefined,
                            )
                          }
                        />
                      </div>
                      <div>
                        <Label>{t.realEstate.basicInfo.bathrooms}</Label>
                        <Input
                          type="text"
                          inputMode="numeric"
                          value={formData.basic_info.bathrooms || ""}
                          onChange={e =>
                            handleInputChange(
                              "basic_info.bathrooms",
                              e.target.value
                                ? parseInt(e.target.value)
                                : undefined,
                            )
                          }
                        />
                      </div>
                    </div>
                  </div>
                )}
              </div>

              <div className="border-t border-border pt-6">
                <button
                  type="button"
                  onClick={() => toggleSection("location")}
                  className="flex items-center justify-between w-full text-left"
                >
                  <h3 className="text-lg font-medium flex items-center gap-2">
                    <MapPin size={18} />
                    {t.realEstate.sections.location}
                    {expandedSections.location ? (
                      <ChevronDown
                        size={18}
                        className="text-muted-foreground"
                      />
                    ) : (
                      <ChevronRight
                        size={18}
                        className="text-muted-foreground"
                      />
                    )}
                  </h3>
                </button>

                {expandedSections.location && (
                  <div className="mt-4 space-y-4">
                    <div>
                      <Label>{t.realEstate.location.address}</Label>
                      <Input
                        value={formData.location.address || ""}
                        onChange={e =>
                          handleInputChange("location.address", e.target.value)
                        }
                        placeholder={t.realEstate.placeholders.fullAddress}
                      />
                    </div>
                    <div>
                      <Label>{t.realEstate.location.cadastralReference}</Label>
                      <Input
                        value={formData.location.cadastral_reference || ""}
                        onChange={e =>
                          handleInputChange(
                            "location.cadastral_reference",
                            e.target.value,
                          )
                        }
                        placeholder={t.realEstate.placeholders.cadastralRef}
                      />
                    </div>
                  </div>
                )}
              </div>

              <div className="border-t border-border pt-6">
                <button
                  type="button"
                  onClick={() => toggleSection("purchase")}
                  className="flex items-center justify-between w-full text-left"
                >
                  <h3 className="text-lg font-medium flex items-center gap-2">
                    <ShoppingCart size={18} />
                    {t.realEstate.sections.purchase}
                    {expandedSections.purchase ? (
                      <ChevronDown
                        size={18}
                        className="text-muted-foreground"
                      />
                    ) : (
                      <ChevronRight
                        size={18}
                        className="text-muted-foreground"
                      />
                    )}
                  </h3>
                  <span className="text-sm text-muted-foreground">
                    {formData.purchase_info.expenses.length > 0
                      ? `${formData.purchase_info.expenses.length}`
                      : ""}
                  </span>
                </button>

                {expandedSections.purchase && (
                  <div className="mt-4 space-y-4">
                    <div>
                      <Label>
                        {t.realEstate.purchase.price}
                        <span className="text-gray-400 ml-1">*</span>
                      </Label>
                      <div className="relative">
                        <DecimalInput
                          value={formData.purchase_info.price || ""}
                          onValueChange={v =>
                            handleInputChange("purchase_info.price", v)
                          }
                          className={`pr-12 ${hasValidationError("purchase_info.price") ? "border-red-500" : ""}`}
                        />
                        <span className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-500 text-sm">
                          {getCurrencySymbol(formData.currency)}
                        </span>
                      </div>
                    </div>

                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <Label>{t.realEstate.purchase.expenses}</Label>
                        <div className="flex gap-2">
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            onClick={e => handleSuggestionClick(e, "purchase")}
                            className="text-xs"
                          >
                            <Lightbulb size={14} className="sm:mr-1" />
                            <span className="hidden sm:inline">
                              {t.realEstate.buttons.suggest}
                            </span>
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            onClick={addPurchaseExpense}
                          >
                            <Plus size={16} className="sm:mr-1" />
                            <span className="hidden sm:inline">
                              {t.realEstate.purchase.addExpense}
                            </span>
                          </Button>
                        </div>
                      </div>

                      {showFlowSuggestions.type === "purchase" && (
                        <div className="mb-4 p-4 bg-black dark:bg-black rounded-lg">
                          <div className="flex justify-between items-center mb-3">
                            <h4 className="font-medium text-sm text-white">
                              {t.realEstate.suggestions.availableSuggestions}
                            </h4>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() =>
                                setShowFlowSuggestions({
                                  type: null,
                                  position: null,
                                })
                              }
                              className="p-1 h-6 w-6"
                            >
                              <X size={12} />
                            </Button>
                          </div>
                          <div className="max-h-60 overflow-y-auto space-y-2">
                            {purchaseConcepts.map((concept, index) => (
                              <div
                                key={index}
                                className="flex items-center p-3 rounded cursor-pointer bg-gray-800 hover:bg-gray-700 transition-colors"
                                onClick={() => applyPurchaseConcept(concept)}
                              >
                                <div className="mr-3 text-gray-600 dark:text-gray-400">
                                  <Receipt size={18} />
                                </div>
                                <div className="flex-1">
                                  <div className="text-sm font-medium text-white">
                                    {concept}
                                  </div>
                                  <div className="text-xs text-gray-300">
                                    {
                                      t.realEstate.purchase
                                        .purchaseConceptDescription
                                    }
                                  </div>
                                </div>
                              </div>
                            ))}
                            {purchaseConcepts.length === 0 && (
                              <div className="text-sm text-gray-400 text-center py-2">
                                {t.realEstate.emptyStates.noConceptsAvailable}
                              </div>
                            )}
                          </div>
                        </div>
                      )}

                      <div className="space-y-2">
                        {formData.purchase_info.expenses.map(
                          (expense, index) => (
                            <div key={index} className="flex gap-2 items-end">
                              <div className="flex-1">
                                <Input
                                  placeholder={
                                    t.realEstate.placeholders.concept
                                  }
                                  value={expense.concept}
                                  onChange={e => {
                                    const newExpenses = [
                                      ...formData.purchase_info.expenses,
                                    ]
                                    newExpenses[index] = {
                                      ...expense,
                                      concept: e.target.value,
                                    }
                                    handleInputChange(
                                      "purchase_info.expenses",
                                      newExpenses,
                                    )
                                  }}
                                />
                              </div>
                              <div className="w-32">
                                <div className="relative">
                                  <DecimalInput
                                    placeholder={
                                      t.realEstate.placeholders.amount
                                    }
                                    value={expense.amount || ""}
                                    onValueChange={v => {
                                      const newExpenses = [
                                        ...formData.purchase_info.expenses,
                                      ]
                                      newExpenses[index] = {
                                        ...expense,
                                        amount: v ?? 0,
                                      }
                                      handleInputChange(
                                        "purchase_info.expenses",
                                        newExpenses,
                                      )
                                    }}
                                    className="pr-8"
                                  />
                                  <span className="absolute right-2 top-1/2 transform -translate-y-1/2 text-gray-500 text-sm">
                                    {getCurrencySymbol(formData.currency)}
                                  </span>
                                </div>
                              </div>
                              <Popover
                                open={percentagePopoverOpen === index}
                                onOpenChange={open => {
                                  if (!open) {
                                    setPercentagePopoverOpen(null)
                                    setTempPercentage("")
                                  }
                                }}
                              >
                                <PopoverTrigger asChild>
                                  <Button
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    onClick={() => openPercentagePopover(index)}
                                    className="hover:bg-blue-50 hover:text-blue-600 h-10"
                                    title={
                                      t.realEstate.purchase
                                        .calculateByPercentage
                                    }
                                  >
                                    <Percent size={16} />
                                  </Button>
                                </PopoverTrigger>
                                <PopoverContent className="w-64">
                                  <div className="space-y-3">
                                    <div>
                                      <Label className="text-sm font-medium">
                                        {
                                          t.realEstate.purchase
                                            .percentageOfPurchasePrice
                                        }
                                      </Label>
                                      <div className="mt-1">
                                        <DecimalInput
                                          value={tempPercentage}
                                          onStringChange={setTempPercentage}
                                          placeholder="0.00"
                                          className="text-sm"
                                        />
                                      </div>
                                    </div>
                                    <div className="text-xs text-gray-500">
                                      {tempPercentage &&
                                        !isNaN(
                                          parseFloat(
                                            tempPercentage.replace(",", "."),
                                          ),
                                        ) && (
                                          <>
                                            {parseFloat(
                                              tempPercentage.replace(",", "."),
                                            )}
                                            % {t.realEstate.purchase.of}{" "}
                                            {formatCurrency(
                                              formData.purchase_info.price || 0,
                                              locale,
                                              formData.currency,
                                            )}{" "}
                                            ={" "}
                                            {formatCurrency(
                                              calculateAmountFromPercentage(
                                                parseFloat(
                                                  tempPercentage.replace(
                                                    ",",
                                                    ".",
                                                  ),
                                                ),
                                              ),
                                              locale,
                                              formData.currency,
                                            )}
                                          </>
                                        )}
                                    </div>
                                    <Button
                                      type="button"
                                      onClick={() => {
                                        const percentage = parseFloat(
                                          tempPercentage.replace(",", "."),
                                        )
                                        if (!isNaN(percentage)) {
                                          applyPercentageToExpense(
                                            index,
                                            percentage,
                                          )
                                        }
                                      }}
                                      disabled={
                                        !tempPercentage ||
                                        isNaN(
                                          parseFloat(
                                            tempPercentage.replace(",", "."),
                                          ),
                                        )
                                      }
                                      className="w-full"
                                      size="sm"
                                    >
                                      {t.realEstate.purchase.apply}
                                    </Button>
                                  </div>
                                </PopoverContent>
                              </Popover>
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                onClick={() => removePurchaseExpense(index)}
                                className="hover:bg-red-50 hover:text-red-600"
                              >
                                <Trash2 size={16} className="text-red-600" />
                              </Button>
                            </div>
                          ),
                        )}
                      </div>
                    </div>

                    <div className="pt-4 border-t">
                      <div className="text-lg font-medium">
                        {t.realEstate.purchase.totalCost}:{" "}
                        {formatCurrency(
                          calculateTotalPurchaseCost(),
                          locale,
                          formData.currency,
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>

              <div className="border-t border-border pt-6">
                <button
                  type="button"
                  onClick={() => toggleSection("valuation")}
                  className="flex items-center justify-between w-full text-left"
                >
                  <h3 className="text-lg font-medium flex items-center gap-2">
                    <TrendingUp size={18} />
                    {t.realEstate.sections.valuation}
                    {expandedSections.valuation ? (
                      <ChevronDown
                        size={18}
                        className="text-muted-foreground"
                      />
                    ) : (
                      <ChevronRight
                        size={18}
                        className="text-muted-foreground"
                      />
                    )}
                  </h3>
                  <span className="text-sm text-muted-foreground">
                    {formData.valuation_info.valuations.length > 0
                      ? `${formData.valuation_info.valuations.length}`
                      : ""}
                  </span>
                </button>

                {expandedSections.valuation && (
                  <div className="mt-4 space-y-4">
                    <div>
                      <Label>
                        {t.realEstate.valuation.estimatedMarketValue}
                        <span className="text-gray-400 ml-1">*</span>
                      </Label>
                      <div className="relative">
                        <DecimalInput
                          value={
                            formData.valuation_info.estimated_market_value || ""
                          }
                          onValueChange={v =>
                            handleInputChange(
                              "valuation_info.estimated_market_value",
                              v,
                            )
                          }
                          className={`pr-12 ${hasValidationError("valuation_info.estimated_market_value") ? "border-red-500" : ""}`}
                        />
                        <span className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-500 text-sm">
                          {getCurrencySymbol(formData.currency)}
                        </span>
                      </div>
                    </div>
                    <div>
                      <Label>{t.realEstate.valuation.annualAppreciation}</Label>
                      <div className="relative">
                        <DecimalInput
                          value={
                            typeof formData.valuation_info
                              .annual_appreciation === "number"
                              ? formData.valuation_info.annual_appreciation *
                                100
                              : ""
                          }
                          onValueChange={v =>
                            handleInputChange(
                              "valuation_info.annual_appreciation",
                              v != null ? v / 100 : null,
                            )
                          }
                          className="pr-8"
                          placeholder={t.realEstate.placeholders.example24}
                        />
                        <span className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-500 text-sm">
                          %
                        </span>
                      </div>
                    </div>

                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <Label>{t.realEstate.valuation.valuations}</Label>
                        <Button type="button" size="sm" onClick={addValuation}>
                          <Plus size={16} className="sm:mr-1" />
                          <span className="hidden sm:inline">
                            {t.realEstate.valuation.addValuation}
                          </span>
                        </Button>
                      </div>

                      <div className="space-y-2">
                        {formData.valuation_info.valuations.map(
                          (valuation, index) => (
                            <div key={index} className="space-y-3">
                              <div className="flex items-center gap-2">
                                <DatePicker
                                  value={valuation.date}
                                  onChange={value => {
                                    const newValuations = [
                                      ...formData.valuation_info.valuations,
                                    ]
                                    newValuations[index] = {
                                      ...valuation,
                                      date: value,
                                    }
                                    handleInputChange(
                                      "valuation_info.valuations",
                                      newValuations,
                                    )
                                  }}
                                  placeholder={t.realEstate.placeholders.date}
                                />
                                <div className="relative flex-1">
                                  <DecimalInput
                                    placeholder={
                                      t.realEstate.placeholders.value
                                    }
                                    value={valuation.amount || ""}
                                    onValueChange={v => {
                                      const newValuations = [
                                        ...formData.valuation_info.valuations,
                                      ]
                                      newValuations[index] = {
                                        ...valuation,
                                        amount: v ?? 0,
                                      }
                                      handleInputChange(
                                        "valuation_info.valuations",
                                        newValuations,
                                      )
                                    }}
                                    className="pr-8 w-full"
                                  />
                                  <span className="absolute right-2 top-1/2 transform -translate-y-1/2 text-gray-500 text-sm">
                                    {getCurrencySymbol(formData.currency)}
                                  </span>
                                </div>
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => removeValuation(index)}
                                  className="text-red-500 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-900/20"
                                >
                                  <Trash2 size={16} />
                                </Button>
                              </div>
                              <div>
                                <Input
                                  placeholder={t.realEstate.placeholders.notes}
                                  value={valuation.notes || ""}
                                  onChange={e => {
                                    const newValuations = [
                                      ...formData.valuation_info.valuations,
                                    ]
                                    newValuations[index] = {
                                      ...valuation,
                                      notes: e.target.value,
                                    }
                                    handleInputChange(
                                      "valuation_info.valuations",
                                      newValuations,
                                    )
                                  }}
                                />
                              </div>
                            </div>
                          ),
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>

              <div className="border-t border-border pt-6">
                <button
                  type="button"
                  onClick={() => toggleSection("loans")}
                  className="flex items-center justify-between w-full text-left"
                >
                  <h3 className="text-lg font-medium flex items-center gap-2">
                    <CreditCard size={18} />
                    {t.realEstate.sections.loans}
                    {expandedSections.loans ? (
                      <ChevronDown
                        size={18}
                        className="text-muted-foreground"
                      />
                    ) : (
                      <ChevronRight
                        size={18}
                        className="text-muted-foreground"
                      />
                    )}
                  </h3>
                  <span className="text-sm text-muted-foreground">
                    {formData.flows.filter(
                      f => f.flow_subtype === RealEstateFlowSubtype.LOAN,
                    ).length > 0
                      ? `${formData.flows.filter(f => f.flow_subtype === RealEstateFlowSubtype.LOAN).length}`
                      : ""}
                  </span>
                </button>

                {expandedSections.loans && (
                  <div className="mt-4 space-y-4">
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-sm text-gray-600 dark:text-gray-400">
                        {t.realEstate.loans.associatedLoans}
                      </p>
                      <div className="flex gap-2">
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={e => handleSuggestionClick(e, "loans")}
                          className="text-xs"
                        >
                          <Lightbulb size={14} className="sm:mr-1" />
                          <span className="hidden sm:inline">
                            {t.realEstate.buttons.suggest}
                          </span>
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          onClick={() => addFlow(RealEstateFlowSubtype.LOAN)}
                          className="bg-white dark:bg-gray-100 hover:bg-gray-100 dark:hover:bg-gray-200 text-black border border-gray-300 dark:border-gray-400 shadow-sm"
                        >
                          <Plus size={16} className="sm:mr-1" />
                          <span className="hidden sm:inline">
                            {t.realEstate.loans.addLoan}
                          </span>
                        </Button>
                      </div>
                    </div>

                    {showFlowSuggestions.type === "loans" && (
                      <div className="mb-4 p-4 bg-black dark:bg-black rounded-lg">
                        <div className="flex justify-between items-center mb-3">
                          <h4 className="font-medium text-sm text-white">
                            {t.realEstate.suggestions.availableSuggestions}
                          </h4>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() =>
                              setShowFlowSuggestions({
                                type: null,
                                position: null,
                              })
                            }
                            className="p-1 h-6 w-6"
                          >
                            <X size={12} />
                          </Button>
                        </div>
                        <div className="max-h-60 overflow-y-auto space-y-2">
                          {availableFlows
                            .filter(flow => {
                              // For loans section, show existing periodic flows AND loan suggestions from positions (no generic suggestions)
                              // Exclude flows that are already linked to other properties
                              return (
                                flow.flow_type === FlowType.EXPENSE &&
                                !flow.id?.startsWith("generic-") &&
                                !flow.linked &&
                                !usedExistingFlowIds.has(flow.id as string)
                              )
                            })
                            .filter(
                              (flow, index, self) =>
                                self.findIndex(f => f.id === flow.id) === index,
                            )
                            .sort((a, b) => {
                              // Sort loan suggestions from positions first
                              const aIsLoanSuggestion =
                                a.id?.startsWith("loan-suggestion-")
                              const bIsLoanSuggestion =
                                b.id?.startsWith("loan-suggestion-")

                              if (aIsLoanSuggestion && !bIsLoanSuggestion)
                                return -1
                              if (!aIsLoanSuggestion && bIsLoanSuggestion)
                                return 1
                              return 0
                            })
                            .map((flow, index) => {
                              const isGeneric = flow.amount === 0
                              const isLoanFromPosition =
                                flow.id?.startsWith("loan-suggestion-")
                              const frequencyLabel = getFrequencyLabel(
                                flow.frequency,
                                true,
                              )
                              const isCurrencyMismatch =
                                !flow.id?.startsWith("generic-") &&
                                flow.currency !== formData.currency

                              const iconName = getSuggestionIconName(
                                flow,
                                "loans",
                              )

                              const content = (
                                <div
                                  key={`${flow.id}-${index}`}
                                  className={`flex items-center p-3 rounded transition-colors ${isCurrencyMismatch ? "opacity-40 cursor-not-allowed bg-gray-800" : "cursor-pointer bg-gray-800 hover:bg-gray-700"}`}
                                  onClick={
                                    isCurrencyMismatch
                                      ? undefined
                                      : () => applyFlowSuggestion(flow)
                                  }
                                >
                                  <div className="mr-3 flex items-center justify-center w-8 h-8 rounded-full bg-gray-600">
                                    <Icon
                                      name={
                                        (iconName ||
                                          "square-dashed") as IconName
                                      }
                                      className="w-4 h-4 text-white"
                                    />
                                  </div>
                                  <div className="flex-1">
                                    <div className="text-sm font-medium">
                                      {flow.name}
                                      {isLoanFromPosition && (
                                        <span className="ml-2 text-xs bg-blue-600 text-white px-2 py-1 rounded">
                                          {t.realEstate.loans.existingLoan}
                                        </span>
                                      )}
                                      {isCurrencyMismatch && (
                                        <span className="ml-2 text-xs bg-yellow-600 text-white px-2 py-0.5 rounded">
                                          {flow.currency}
                                        </span>
                                      )}
                                    </div>
                                    <div className="text-xs text-gray-500 dark:text-gray-400">
                                      {isGeneric
                                        ? t.realEstate.analysis.genericConceptWithFrequency.replace(
                                            "{frequency}",
                                            frequencyLabel,
                                          )
                                        : `${formatCurrency(flow.amount, locale, flow.currency)} ${frequencyLabel}`}
                                    </div>
                                  </div>
                                </div>
                              )

                              if (isCurrencyMismatch) {
                                return (
                                  <TooltipProvider key={`${flow.id}-${index}`}>
                                    <Tooltip>
                                      <TooltipTrigger asChild>
                                        {content}
                                      </TooltipTrigger>
                                      <TooltipContent
                                        side="top"
                                        className="max-w-xs"
                                      >
                                        {t.realEstate.suggestions.currencyMismatch
                                          .replace("{currency}", flow.currency)
                                          .replace(
                                            "{propertyCurrency}",
                                            formData.currency,
                                          )}
                                      </TooltipContent>
                                    </Tooltip>
                                  </TooltipProvider>
                                )
                              }

                              return content
                            })}
                          {availableFlows.filter(flow => {
                            return (
                              flow.flow_type === FlowType.EXPENSE &&
                              (!flow.id?.startsWith("generic-") ||
                                flow.id?.startsWith("loan-suggestion-"))
                            )
                          }).length === 0 && (
                            <div className="text-sm text-gray-500 dark:text-gray-400 text-center py-2">
                              {t.realEstate.emptyStates.noSuggestionsAvailable}
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    <div className="space-y-3">
                      {formData.flows
                        .filter(
                          flow =>
                            flow.flow_subtype === RealEstateFlowSubtype.LOAN,
                        )
                        .map(flow => {
                          const originalIndex = formData.flows.findIndex(
                            f => f === flow,
                          )
                          const loanPayload = flow.payload as any
                          const isLinked = !!flow.linked_loan_hash
                          return (
                            <div
                              key={originalIndex}
                              className={`border rounded-lg p-4 ${isLinked ? "border-blue-300 dark:border-blue-600 bg-blue-50/30 dark:bg-blue-950/20" : "border-gray-200 dark:border-gray-700"}`}
                            >
                              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-3 gap-3">
                                <div className="flex items-end gap-2 flex-1 mr-2">
                                  <div>
                                    <Label className="sr-only">
                                      {t.management.iconLabel}
                                    </Label>
                                    <IconPicker
                                      value={
                                        flow.periodic_flow?.icon as
                                          | IconName
                                          | undefined
                                      }
                                      onValueChange={value => {
                                        setFormData(prev => ({
                                          ...prev,
                                          flows: prev.flows.map((f, i) =>
                                            i === originalIndex &&
                                            f.periodic_flow
                                              ? {
                                                  ...f,
                                                  periodic_flow: {
                                                    ...f.periodic_flow,
                                                    icon: value,
                                                  },
                                                }
                                              : f,
                                          ),
                                        }))
                                        setHasUnsavedChanges(true)
                                      }}
                                      modal
                                    >
                                      <Button
                                        variant="outline"
                                        size="icon"
                                        className="h-9 w-9"
                                        aria-label={
                                          flow.periodic_flow?.icon ||
                                          t.management.iconLabel
                                        }
                                      >
                                        {flow.periodic_flow?.icon ? (
                                          <Icon
                                            name={
                                              flow.periodic_flow
                                                .icon as IconName
                                            }
                                            className="w-5 h-5"
                                          />
                                        ) : (
                                          <Icon
                                            name={"square-dashed" as IconName}
                                            size={18}
                                            className="text-muted-foreground w-5 h-5"
                                          />
                                        )}
                                      </Button>
                                    </IconPicker>
                                  </div>
                                  <div className="flex-1">
                                    <Label>
                                      {t.realEstate.placeholders.loanName}
                                      <span className="text-gray-400 ml-1">
                                        *
                                      </span>
                                    </Label>
                                    <Input
                                      placeholder={
                                        t.realEstate.placeholders.loanName
                                      }
                                      value={flow.description || ""}
                                      onChange={e =>
                                        updateFlowName(
                                          originalIndex,
                                          e.target.value,
                                        )
                                      }
                                      className={
                                        hasValidationError(
                                          `flow.${originalIndex}.name`,
                                        )
                                          ? "border-red-500"
                                          : ""
                                      }
                                    />
                                  </div>
                                </div>
                                <div className="flex gap-2 w-full sm:w-auto justify-end">
                                  <Button
                                    type="button"
                                    size="sm"
                                    variant={isLinked ? "outline" : "ghost"}
                                    onClick={() => {
                                      if (isLinked) {
                                        setUnlinkConfirmIndex(originalIndex)
                                      }
                                    }}
                                    className={`mt-0 sm:mt-6 ${isLinked ? "border-blue-400 text-blue-600 hover:bg-blue-50 dark:border-blue-500 dark:text-blue-400 dark:hover:bg-blue-950/40" : "text-gray-400 hover:text-gray-600"}`}
                                    title={
                                      isLinked
                                        ? t.realEstate.linkedToPosition
                                        : t.realEstate.notLinked
                                    }
                                  >
                                    {isLinked ? (
                                      <Link size={16} />
                                    ) : (
                                      <Unlink size={16} />
                                    )}
                                  </Button>
                                  <Button
                                    type="button"
                                    size="sm"
                                    disabled={
                                      calculatingLoanIndex === originalIndex ||
                                      isLinked
                                    }
                                    onClick={async () => {
                                      try {
                                        setCalculatingLoanIndex(originalIndex)
                                        // Build request using loan's own date range (since/until)
                                        const startStr =
                                          flow.periodic_flow?.since ||
                                          new Date().toISOString().split("T")[0]
                                        const endStr =
                                          flow.periodic_flow?.until &&
                                          flow.periodic_flow.until.trim() !== ""
                                            ? flow.periodic_flow.until
                                            : startStr

                                        const req: LoanCalculationRequest = {
                                          interest_rate:
                                            loanPayload.interest_rate || 0,
                                          interest_type:
                                            loanPayload.interest_type ||
                                            "FIXED",
                                          euribor_rate:
                                            loanPayload.euribor_rate ??
                                            undefined,
                                          fixed_years:
                                            loanPayload.fixed_years ??
                                            undefined,
                                          fixed_interest_rate:
                                            loanPayload.fixed_interest_rate ??
                                            undefined,
                                          start: startStr,
                                          end: endStr,
                                        }

                                        const principalProvided =
                                          loanPayload.principal_outstanding &&
                                          loanPayload.principal_outstanding > 0

                                        if (principalProvided) {
                                          req.principal_outstanding =
                                            loanPayload.principal_outstanding
                                        } else if (
                                          loanPayload.loan_amount &&
                                          loanPayload.loan_amount > 0
                                        ) {
                                          req.loan_amount =
                                            loanPayload.loan_amount
                                        } else {
                                          showToast(
                                            t.realEstate.errors
                                              .missingLoanAmounts,
                                            "error",
                                          )
                                          return
                                        }

                                        const result = await calculateLoan(req)

                                        setFormData(prev => {
                                          const flows = [...prev.flows]
                                          const f = { ...flows[originalIndex] }
                                          const payload: LoanPayload = {
                                            ...(f.payload as LoanPayload),
                                            monthly_interests:
                                              result.current_installment_interests ??
                                              null,
                                          }

                                          // Only set principal_outstanding if not provided in form
                                          const currentPrincipal = (
                                            f.payload as LoanPayload
                                          ).principal_outstanding
                                          if (
                                            !currentPrincipal ||
                                            currentPrincipal <= 0
                                          ) {
                                            if (
                                              typeof result.principal_outstanding ===
                                              "number"
                                            ) {
                                              payload.principal_outstanding =
                                                result.principal_outstanding
                                            }
                                          }

                                          // Also fill the monthly installment amount if provided by the API
                                          if (f.periodic_flow) {
                                            const pf = { ...f.periodic_flow }
                                            if (
                                              typeof result.current_installment_payment ===
                                              "number"
                                            ) {
                                              pf.amount =
                                                result.current_installment_payment
                                            }
                                            f.periodic_flow = pf
                                          }

                                          f.payload = payload
                                          flows[originalIndex] = f
                                          return { ...prev, flows }
                                        })
                                        setHasUnsavedChanges(true)
                                      } catch (e) {
                                        console.error(e)
                                        showToast(
                                          t.realEstate.errors
                                            .loanCalculationFailed,
                                          "error",
                                        )
                                      } finally {
                                        setCalculatingLoanIndex(null)
                                      }
                                    }}
                                    className="bg-blue-500 hover:bg-blue-600 text-white border border-blue-600 mt-0 sm:mt-6 disabled:opacity-60"
                                  >
                                    <Calculator size={16} className="mr-1" />
                                    {t.realEstate.buttons.calculateInterests}
                                  </Button>
                                  <Button
                                    type="button"
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => removeFlow(originalIndex)}
                                    className="text-red-500 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-900/20 mt-0 sm:mt-6"
                                  >
                                    <Trash2 size={16} />
                                  </Button>
                                </div>
                              </div>

                              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
                                <div>
                                  <Label>
                                    {t.realEstate.labels.monthlyPayment}
                                    <span className="text-gray-400 ml-1">
                                      *
                                    </span>
                                  </Label>
                                  <div className="relative">
                                    <DecimalInput
                                      value={flow.periodic_flow?.amount || ""}
                                      onValueChange={v =>
                                        updateFlowAmount(originalIndex, v ?? 0)
                                      }
                                      disabled={isLinked}
                                      className={`pr-12 ${hasValidationError(`flow.${originalIndex}.amount`) ? "border-red-500" : ""} ${isLinked ? "opacity-60" : ""}`}
                                    />
                                    <span className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-500 text-sm">
                                      {getCurrencySymbol(formData.currency)}
                                    </span>
                                  </div>
                                </div>
                                <div>
                                  <Label className="inline-flex items-center gap-1">
                                    {t.realEstate.labels.monthlyInterest}
                                    <Popover>
                                      <PopoverTrigger asChild>
                                        <span
                                          aria-label={t.common.viewDetails}
                                          title={t.common.viewDetails}
                                          className="inline-flex items-center cursor-help text-gray-400 hover:text-gray-500"
                                        >
                                          <Info className="h-3.5 w-3.5" />
                                        </span>
                                      </PopoverTrigger>
                                      <PopoverContent className="w-80 text-xs">
                                        {
                                          t.realEstate.popovers.loans
                                            .monthlyInterestInfo
                                        }
                                      </PopoverContent>
                                    </Popover>
                                  </Label>
                                  <div className="relative">
                                    <DecimalInput
                                      value={
                                        loanPayload.monthly_interests || ""
                                      }
                                      onValueChange={v =>
                                        updateFlowPayload(
                                          originalIndex,
                                          "monthly_interests",
                                          v,
                                        )
                                      }
                                      disabled={isLinked}
                                      className={`pr-12 ${isLinked ? "opacity-60" : ""}`}
                                    />
                                    <span className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-500 text-sm">
                                      {getCurrencySymbol(formData.currency)}
                                    </span>
                                  </div>
                                </div>
                              </div>

                              {isLinked &&
                                flow.periodic_flow?.frequency &&
                                flow.periodic_flow.frequency !==
                                  FlowFrequency.MONTHLY && (
                                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
                                    <div>
                                      <Label>
                                        {
                                          t.realEstate.loans
                                            .installmentFrequencyLabel
                                        }
                                      </Label>
                                      <select
                                        value={flow.periodic_flow.frequency}
                                        disabled
                                        className="w-full p-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 opacity-60"
                                      >
                                        {Object.values(FlowFrequency).map(
                                          freq => (
                                            <option key={freq} value={freq}>
                                              {getFrequencyLabel(freq)}
                                            </option>
                                          ),
                                        )}
                                      </select>
                                    </div>
                                  </div>
                                )}

                              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
                                <div>
                                  <Label>
                                    {t.realEstate.loans.loanTypeLabel}
                                  </Label>
                                  <div className="flex flex-wrap items-center gap-2 min-h-[2.5rem] py-1">
                                    {[
                                      {
                                        value: "MORTGAGE",
                                        label: t.realEstate.loans.mortgage,
                                        icon: <Home className="h-3 w-3" />,
                                      },
                                      {
                                        value: "STANDARD",
                                        label: t.realEstate.loans.standard,
                                        icon: <Landmark className="h-3 w-3" />,
                                      },
                                    ].map(option => {
                                      const isActive =
                                        (loanPayload.type || "MORTGAGE") ===
                                        option.value
                                      return (
                                        <button
                                          key={option.value}
                                          type="button"
                                          disabled={isLinked}
                                          onClick={() =>
                                            updateFlowPayload(
                                              originalIndex,
                                              "type",
                                              option.value,
                                            )
                                          }
                                          className={cn(
                                            "px-2.5 py-1 text-xs font-semibold rounded-full border transition-all inline-flex items-center gap-1.5",
                                            isActive
                                              ? "bg-foreground text-background border-foreground"
                                              : "bg-transparent text-muted-foreground border-border hover:border-foreground/40 hover:text-foreground",
                                            isLinked &&
                                              "opacity-60 cursor-not-allowed",
                                          )}
                                        >
                                          {option.icon}
                                          {option.label}
                                        </button>
                                      )
                                    })}
                                  </div>
                                </div>
                                <div>
                                  <Label className="inline-flex items-center gap-1">
                                    {t.realEstate.loans.totalLoanAmountLabel}
                                    <Popover>
                                      <PopoverTrigger asChild>
                                        <span
                                          aria-label={t.common.viewDetails}
                                          title={t.common.viewDetails}
                                          className="inline-flex items-center cursor-help text-gray-400 hover:text-gray-500"
                                        >
                                          <Info className="h-3.5 w-3.5" />
                                        </span>
                                      </PopoverTrigger>
                                      <PopoverContent className="w-80 text-xs">
                                        {
                                          t.realEstate.popovers.loans
                                            .totalLoanAmountInfo
                                        }
                                      </PopoverContent>
                                    </Popover>
                                  </Label>
                                  <div className="flex gap-2 items-end">
                                    <div className="relative flex-1">
                                      <DecimalInput
                                        value={loanPayload.loan_amount || ""}
                                        onValueChange={v =>
                                          updateFlowPayload(
                                            originalIndex,
                                            "loan_amount",
                                            v,
                                          )
                                        }
                                        disabled={isLinked}
                                        className={`pr-12 ${isLinked ? "opacity-60" : ""}`}
                                      />
                                      <span className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-500 text-sm">
                                        {getCurrencySymbol(formData.currency)}
                                      </span>
                                    </div>
                                    <Popover
                                      open={
                                        loanPercentagePopoverOpen ===
                                        originalIndex
                                      }
                                      onOpenChange={open => {
                                        if (!open) {
                                          setLoanPercentagePopoverOpen(null)
                                          setTempLoanPercentage("")
                                        }
                                      }}
                                    >
                                      <PopoverTrigger asChild>
                                        <Button
                                          type="button"
                                          variant="outline"
                                          size="sm"
                                          onClick={() =>
                                            openLoanPercentagePopover(
                                              originalIndex,
                                            )
                                          }
                                          disabled={isLinked}
                                          className="hover:bg-blue-50 hover:text-blue-600 h-10"
                                          title={
                                            t.realEstate.purchase
                                              .calculateByPercentage
                                          }
                                        >
                                          <Percent size={16} />
                                        </Button>
                                      </PopoverTrigger>
                                      <PopoverContent className="w-64">
                                        <div className="space-y-3">
                                          <div>
                                            <Label className="text-sm font-medium">
                                              {
                                                t.realEstate.purchase
                                                  .percentageOfPurchasePrice
                                              }
                                            </Label>
                                            <div className="mt-1">
                                              <DecimalInput
                                                value={tempLoanPercentage}
                                                onStringChange={
                                                  setTempLoanPercentage
                                                }
                                                placeholder="0.00"
                                                className="text-sm"
                                              />
                                            </div>
                                          </div>
                                          <div className="flex gap-2">
                                            {[70, 80, 90].map(pct => (
                                              <Button
                                                key={pct}
                                                type="button"
                                                variant="outline"
                                                size="sm"
                                                className="flex-1"
                                                onClick={() =>
                                                  applyLoanPercentage(
                                                    originalIndex,
                                                    pct,
                                                  )
                                                }
                                              >
                                                {pct}%
                                              </Button>
                                            ))}
                                          </div>
                                          <div className="text-xs text-gray-500">
                                            {tempLoanPercentage &&
                                              !isNaN(
                                                parseFloat(
                                                  tempLoanPercentage.replace(
                                                    ",",
                                                    ".",
                                                  ),
                                                ),
                                              ) && (
                                                <>
                                                  {parseFloat(
                                                    tempLoanPercentage.replace(
                                                      ",",
                                                      ".",
                                                    ),
                                                  )}
                                                  % {t.realEstate.purchase.of}{" "}
                                                  {formatCurrency(
                                                    formData.purchase_info
                                                      .price || 0,
                                                    locale,
                                                    formData.currency,
                                                  )}{" "}
                                                  ={" "}
                                                  {formatCurrency(
                                                    calculateLoanAmountFromPercentage(
                                                      parseFloat(
                                                        tempLoanPercentage.replace(
                                                          ",",
                                                          ".",
                                                        ),
                                                      ),
                                                    ),
                                                    locale,
                                                    formData.currency,
                                                  )}
                                                </>
                                              )}
                                          </div>
                                          <Button
                                            type="button"
                                            onClick={() => {
                                              const percentage = parseFloat(
                                                tempLoanPercentage.replace(
                                                  ",",
                                                  ".",
                                                ),
                                              )
                                              if (!isNaN(percentage)) {
                                                applyLoanPercentage(
                                                  originalIndex,
                                                  percentage,
                                                )
                                              }
                                            }}
                                            disabled={
                                              !tempLoanPercentage ||
                                              isNaN(
                                                parseFloat(
                                                  tempLoanPercentage.replace(
                                                    ",",
                                                    ".",
                                                  ),
                                                ),
                                              )
                                            }
                                            className="w-full"
                                            size="sm"
                                          >
                                            {t.realEstate.purchase.apply}
                                          </Button>
                                        </div>
                                      </PopoverContent>
                                    </Popover>
                                  </div>
                                </div>
                                <div>
                                  <Label className="inline-flex items-center gap-1">
                                    {t.realEstate.loans.principalOutstanding}
                                    <Popover>
                                      <PopoverTrigger asChild>
                                        <span
                                          aria-label={t.common.viewDetails}
                                          title={t.common.viewDetails}
                                          className="inline-flex items-center cursor-help text-gray-400 hover:text-gray-500"
                                        >
                                          <Info className="h-3.5 w-3.5" />
                                        </span>
                                      </PopoverTrigger>
                                      <PopoverContent className="w-80 text-xs">
                                        {
                                          t.realEstate.popovers.loans
                                            .principalOutstandingInfo
                                        }
                                      </PopoverContent>
                                    </Popover>
                                  </Label>
                                  <div className="relative">
                                    <DecimalInput
                                      value={
                                        loanPayload.principal_outstanding || ""
                                      }
                                      onValueChange={v =>
                                        updateFlowPayload(
                                          originalIndex,
                                          "principal_outstanding",
                                          v ?? 0,
                                        )
                                      }
                                      disabled={isLinked}
                                      className={`pr-12 ${isLinked ? "opacity-60" : ""}`}
                                    />
                                    <span className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-500 text-sm">
                                      {getCurrencySymbol(formData.currency)}
                                    </span>
                                  </div>
                                </div>
                              </div>

                              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
                                <div>
                                  <Label>
                                    {t.realEstate.loans.interestTypeLabel}
                                  </Label>
                                  <div className="flex flex-wrap items-center gap-2 min-h-[2.5rem] py-1">
                                    {[
                                      {
                                        value: "FIXED",
                                        label:
                                          t.realEstate.loans.interestTypes
                                            .fixed,
                                      },
                                      {
                                        value: "VARIABLE",
                                        label:
                                          t.realEstate.loans.interestTypes
                                            .variable,
                                      },
                                      {
                                        value: "MIXED",
                                        label:
                                          t.realEstate.loans.interestTypes
                                            .mixed,
                                      },
                                    ].map(option => {
                                      const isActive =
                                        (loanPayload.interest_type ||
                                          "FIXED") === option.value
                                      return (
                                        <button
                                          key={option.value}
                                          type="button"
                                          disabled={isLinked}
                                          onClick={() =>
                                            updateFlowPayload(
                                              originalIndex,
                                              "interest_type",
                                              option.value,
                                            )
                                          }
                                          className={cn(
                                            "px-2.5 py-1 text-xs font-semibold rounded-full border transition-all",
                                            isActive
                                              ? "bg-foreground text-background border-foreground"
                                              : "bg-transparent text-muted-foreground border-border hover:border-foreground/40 hover:text-foreground",
                                            isLinked &&
                                              "opacity-60 cursor-not-allowed",
                                          )}
                                        >
                                          {option.label}
                                        </button>
                                      )
                                    })}
                                  </div>
                                </div>
                                <div>
                                  <Label>
                                    {t.realEstate.loans.interestRateLabel}
                                  </Label>
                                  <div className="relative">
                                    <DecimalInput
                                      value={
                                        loanPayload.interest_rate
                                          ? Math.round(
                                              loanPayload.interest_rate * 10000,
                                            ) / 100
                                          : ""
                                      }
                                      onValueChange={v =>
                                        updateFlowPayload(
                                          originalIndex,
                                          "interest_rate",
                                          v != null
                                            ? Math.round(v * 100) / 10000
                                            : 0,
                                        )
                                      }
                                      disabled={isLinked}
                                      className={`pr-8 ${isLinked ? "opacity-60" : ""}`}
                                    />
                                    <span className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-500 text-sm">
                                      %
                                    </span>
                                  </div>
                                </div>
                                {loanPayload.interest_type === "VARIABLE" ||
                                loanPayload.interest_type === "MIXED" ? (
                                  <div>
                                    <Label>
                                      {t.realEstate.loans.euriborRate}
                                    </Label>
                                    <div className="relative">
                                      <DecimalInput
                                        value={
                                          loanPayload.euribor_rate
                                            ? loanPayload.euribor_rate * 100
                                            : ""
                                        }
                                        onValueChange={v =>
                                          updateFlowPayload(
                                            originalIndex,
                                            "euribor_rate",
                                            v != null ? v / 100 : null,
                                          )
                                        }
                                        disabled={isLinked}
                                        className={`pr-8 ${isLinked ? "opacity-60" : ""}`}
                                      />
                                      <span className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-500 text-sm">
                                        %
                                      </span>
                                    </div>
                                  </div>
                                ) : null}
                                {loanPayload.interest_type === "MIXED" ? (
                                  <div>
                                    <Label>
                                      {t.realEstate.loans.fixedYearsLabel}
                                    </Label>
                                    <Input
                                      type="text"
                                      inputMode="numeric"
                                      value={loanPayload.fixed_years || ""}
                                      onChange={e =>
                                        updateFlowPayload(
                                          originalIndex,
                                          "fixed_years",
                                          parseFloat(
                                            e.target.value.replace(",", "."),
                                          ) || null,
                                        )
                                      }
                                      disabled={isLinked}
                                      className={isLinked ? "opacity-60" : ""}
                                    />
                                  </div>
                                ) : null}
                                {loanPayload.interest_type === "MIXED" ? (
                                  <div>
                                    <Label>
                                      {t.realEstate.loans
                                        .fixedInterestRateLabel ||
                                        "Fixed interest rate"}
                                    </Label>
                                    <div className="relative">
                                      <DecimalInput
                                        value={
                                          loanPayload.fixed_interest_rate
                                            ? Math.round(
                                                loanPayload.fixed_interest_rate *
                                                  10000,
                                              ) / 100
                                            : ""
                                        }
                                        onValueChange={v =>
                                          updateFlowPayload(
                                            originalIndex,
                                            "fixed_interest_rate",
                                            v != null
                                              ? Math.round(v * 100) / 10000
                                              : null,
                                          )
                                        }
                                        disabled={isLinked}
                                        className={`pr-8 ${isLinked ? "opacity-60" : ""}`}
                                      />
                                      <span className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-500 text-sm">
                                        %
                                      </span>
                                    </div>
                                  </div>
                                ) : null}
                              </div>

                              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                <div>
                                  <Label>
                                    {t.realEstate.loans.fromLabel}
                                    <span className="text-gray-400 ml-1">
                                      *
                                    </span>
                                  </Label>
                                  <DatePicker
                                    value={flow.periodic_flow?.since || ""}
                                    onChange={value => {
                                      setFormData(prev => ({
                                        ...prev,
                                        flows: prev.flows.map((f, i) =>
                                          i === originalIndex && f.periodic_flow
                                            ? {
                                                ...f,
                                                periodic_flow: {
                                                  ...f.periodic_flow,
                                                  since: value,
                                                },
                                              }
                                            : f,
                                        ),
                                      }))
                                      setHasUnsavedChanges(true)
                                    }}
                                    disabled={isLinked}
                                    className={`${
                                      hasValidationError(
                                        `flow.${originalIndex}.since`,
                                      )
                                        ? "border-red-500"
                                        : ""
                                    } ${isLinked ? "opacity-60" : ""}`}
                                  />
                                </div>
                                <div>
                                  <Label>
                                    {t.realEstate.loans.untilLabel}
                                    <span className="text-gray-400 ml-1">
                                      *
                                    </span>
                                  </Label>
                                  <DatePicker
                                    value={flow.periodic_flow?.until || ""}
                                    onChange={value => {
                                      setFormData(prev => ({
                                        ...prev,
                                        flows: prev.flows.map((f, i) =>
                                          i === originalIndex && f.periodic_flow
                                            ? {
                                                ...f,
                                                periodic_flow: {
                                                  ...f.periodic_flow,
                                                  until: value || undefined,
                                                },
                                              }
                                            : f,
                                        ),
                                      }))
                                      setHasUnsavedChanges(true)
                                    }}
                                    disabled={isLinked}
                                    className={`${
                                      hasValidationError(
                                        `flow.${originalIndex}.until`,
                                      )
                                        ? "border-red-500"
                                        : ""
                                    } ${isLinked ? "opacity-60" : ""}`}
                                  />
                                </div>
                              </div>
                            </div>
                          )
                        })}

                      {formData.flows.filter(
                        flow =>
                          flow.flow_subtype === RealEstateFlowSubtype.LOAN,
                      ).length === 0 && (
                        <div className="text-center py-6 text-gray-500 dark:text-gray-400">
                          {t.realEstate.loans.noAssociatedLoans}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>

              <div className="border-t border-border pt-6">
                <button
                  type="button"
                  onClick={() => toggleSection("costs")}
                  className="flex items-center justify-between w-full text-left"
                >
                  <h3 className="text-lg font-medium flex items-center gap-2">
                    <Receipt size={18} />
                    {t.realEstate.sections.costs}
                    {expandedSections.costs ? (
                      <ChevronDown
                        size={18}
                        className="text-muted-foreground"
                      />
                    ) : (
                      <ChevronRight
                        size={18}
                        className="text-muted-foreground"
                      />
                    )}
                  </h3>
                  <span className="text-sm text-muted-foreground">
                    {formData.flows.filter(
                      f => f.flow_subtype === RealEstateFlowSubtype.COST,
                    ).length > 0
                      ? `${formData.flows.filter(f => f.flow_subtype === RealEstateFlowSubtype.COST).length}`
                      : ""}
                  </span>
                </button>

                {expandedSections.costs && (
                  <div className="mt-4 space-y-4">
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-sm text-gray-600 dark:text-gray-400">
                        {t.realEstate.descriptions.manageCostsDescription}
                      </p>
                      <div className="flex gap-2">
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={e => handleSuggestionClick(e, "costs")}
                          className="text-xs"
                        >
                          <Lightbulb size={14} className="sm:mr-1" />
                          <span className="hidden sm:inline">
                            {t.realEstate.buttons.suggest}
                          </span>
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          onClick={() => addFlow(RealEstateFlowSubtype.COST)}
                          className="bg-white dark:bg-gray-100 hover:bg-gray-100 dark:hover:bg-gray-200 text-black border border-gray-300 dark:border-gray-400 shadow-sm"
                        >
                          <Plus size={16} className="sm:mr-1" />
                          <span className="hidden sm:inline">
                            {t.realEstate.flows.addExpense}
                          </span>
                        </Button>
                      </div>
                    </div>

                    {showFlowSuggestions.type === "costs" && (
                      <div className="mb-4 p-4 bg-black dark:bg-black rounded-lg">
                        <div className="flex justify-between items-center mb-3">
                          <h4 className="font-medium text-sm text-white">
                            {t.realEstate.suggestions.availableSuggestions}
                          </h4>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() =>
                              setShowFlowSuggestions({
                                type: null,
                                position: null,
                              })
                            }
                            className="p-1 h-6 w-6"
                          >
                            <X size={12} />
                          </Button>
                        </div>
                        <div className="max-h-60 overflow-y-auto space-y-2">
                          {availableFlows
                            .filter(flow => {
                              // For costs section, exclude loan suggestions and linked flows
                              if (
                                flow.id?.startsWith("loan-suggestion-") ||
                                flow.linked ||
                                (flow.id && usedExistingFlowIds.has(flow.id))
                              ) {
                                return false
                              }

                              // If it's a known generic, ensure it's mapped to this section
                              if (flow.id?.startsWith("generic-")) {
                                const mapped = genericSectionMap[flow.id]
                                if (mapped && mapped !== "costs") return false
                              }

                              // Include purchase costs and general property costs
                              return flow.flow_type === FlowType.EXPENSE
                            })
                            .filter(
                              (flow, index, self) =>
                                self.findIndex(f => f.id === flow.id) === index,
                            )
                            .map((flow, index) => {
                              const isGeneric = flow.amount === 0
                              const frequencyLabel = getFrequencyLabel(
                                flow.frequency,
                                true,
                              )
                              const isCurrencyMismatch =
                                !flow.id?.startsWith("generic-") &&
                                flow.currency !== formData.currency

                              const iconName = getSuggestionIconName(
                                flow,
                                "costs",
                              )

                              const content = (
                                <div
                                  key={`${flow.id}-${index}`}
                                  className={`flex items-center p-3 rounded transition-colors ${isCurrencyMismatch ? "opacity-40 cursor-not-allowed bg-gray-800" : "cursor-pointer bg-gray-800 hover:bg-gray-700"}`}
                                  onClick={
                                    isCurrencyMismatch
                                      ? undefined
                                      : () => applyFlowSuggestion(flow)
                                  }
                                >
                                  <div className="mr-3 flex items-center justify-center w-8 h-8 rounded-full bg-gray-600">
                                    <Icon
                                      name={
                                        (iconName || "lightbulb") as IconName
                                      }
                                      className="w-4 h-4 text-white"
                                    />
                                  </div>
                                  <div className="flex-1">
                                    <div className="text-sm font-medium text-white">
                                      {flow.name}
                                      {isCurrencyMismatch && (
                                        <span className="ml-2 text-xs bg-yellow-600 text-white px-2 py-0.5 rounded">
                                          {flow.currency}
                                        </span>
                                      )}
                                    </div>
                                    <div className="text-xs text-gray-300">
                                      {isGeneric
                                        ? t.realEstate.analysis.genericConceptWithFrequency.replace(
                                            "{frequency}",
                                            frequencyLabel,
                                          )
                                        : `${formatCurrency(flow.amount, locale, flow.currency)} ${frequencyLabel}`}
                                    </div>
                                  </div>
                                </div>
                              )

                              if (isCurrencyMismatch) {
                                return (
                                  <TooltipProvider key={`${flow.id}-${index}`}>
                                    <Tooltip>
                                      <TooltipTrigger asChild>
                                        {content}
                                      </TooltipTrigger>
                                      <TooltipContent
                                        side="top"
                                        className="max-w-xs"
                                      >
                                        {t.realEstate.suggestions.currencyMismatch
                                          .replace("{currency}", flow.currency)
                                          .replace(
                                            "{propertyCurrency}",
                                            formData.currency,
                                          )}
                                      </TooltipContent>
                                    </Tooltip>
                                  </TooltipProvider>
                                )
                              }

                              return content
                            })}
                          {availableFlows.filter(flow => {
                            return flow.flow_type === FlowType.EXPENSE
                          }).length === 0 && (
                            <div className="text-sm text-gray-400 text-center py-2">
                              {t.realEstate.emptyStates.noSuggestionsAvailable}
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    <div className="space-y-3">
                      {formData.flows
                        .filter(
                          flow =>
                            flow.flow_subtype === RealEstateFlowSubtype.COST,
                        )
                        .map(flow => {
                          const originalIndex = formData.flows.findIndex(
                            f => f === flow,
                          )
                          return (
                            <div
                              key={originalIndex}
                              className="border border-gray-200 dark:border-gray-700 rounded-lg p-4"
                            >
                              <div className="flex items-center justify-between mb-3">
                                <div className="flex items-end gap-2 flex-1 mr-2">
                                  <div>
                                    <Label className="sr-only">
                                      {t.management.iconLabel}
                                    </Label>
                                    <IconPicker
                                      value={
                                        flow.periodic_flow?.icon as
                                          | IconName
                                          | undefined
                                      }
                                      onValueChange={value => {
                                        setFormData(prev => ({
                                          ...prev,
                                          flows: prev.flows.map((f, i) =>
                                            i === originalIndex &&
                                            f.periodic_flow
                                              ? {
                                                  ...f,
                                                  periodic_flow: {
                                                    ...f.periodic_flow,
                                                    icon: value,
                                                  },
                                                }
                                              : f,
                                          ),
                                        }))
                                        setHasUnsavedChanges(true)
                                      }}
                                      modal
                                    >
                                      <Button
                                        variant="outline"
                                        size="icon"
                                        className="h-9 w-9"
                                        aria-label={
                                          flow.periodic_flow?.icon ||
                                          t.management.iconLabel
                                        }
                                      >
                                        {flow.periodic_flow?.icon ? (
                                          <Icon
                                            name={
                                              flow.periodic_flow
                                                .icon as IconName
                                            }
                                            className="w-5 h-5"
                                          />
                                        ) : (
                                          <Icon
                                            name={"square-dashed" as IconName}
                                            size={18}
                                            className="text-muted-foreground w-5 h-5"
                                          />
                                        )}
                                      </Button>
                                    </IconPicker>
                                  </div>
                                  <div className="flex-1">
                                    <Label>
                                      {t.realEstate.placeholders.expenseName}
                                      <span className="text-gray-400 ml-1">
                                        *
                                      </span>
                                    </Label>
                                    <Input
                                      placeholder={
                                        t.realEstate.placeholders.expenseName
                                      }
                                      value={flow.description || ""}
                                      onChange={e =>
                                        updateFlowName(
                                          originalIndex,
                                          e.target.value,
                                        )
                                      }
                                      className={
                                        hasValidationError(
                                          `flow.${originalIndex}.name`,
                                        )
                                          ? "border-red-500"
                                          : ""
                                      }
                                    />
                                  </div>
                                </div>
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => removeFlow(originalIndex)}
                                  className="text-red-500 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-900/20 mt-6"
                                >
                                  <Trash2 size={16} />
                                </Button>
                              </div>

                              <div
                                className={`grid gap-4 ${formData.basic_info.is_rented ? "grid-cols-1 sm:grid-cols-6" : "grid-cols-1 sm:grid-cols-2"}`}
                              >
                                <div
                                  className={`flex gap-2 items-end ${formData.basic_info.is_rented ? "sm:col-span-3" : ""}`}
                                >
                                  <div className="flex-1">
                                    <Label>
                                      {t.realEstate.labels.amount}
                                      <span className="text-gray-400 ml-1">
                                        *
                                      </span>
                                    </Label>
                                    <div className="relative">
                                      <DecimalInput
                                        value={flow.periodic_flow?.amount || ""}
                                        onValueChange={v =>
                                          updateFlowAmount(
                                            originalIndex,
                                            v ?? 0,
                                          )
                                        }
                                        className={`pr-12 ${hasValidationError(`flow.${originalIndex}.amount`) ? "border-red-500" : ""}`}
                                      />
                                      <span className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-500 text-sm">
                                        {getCurrencySymbol(formData.currency)}
                                      </span>
                                    </div>
                                  </div>
                                  {formData.basic_info.is_rented && (
                                    <Popover
                                      open={
                                        rentPercentagePopoverOpen ===
                                        originalIndex
                                      }
                                      onOpenChange={open => {
                                        if (!open) {
                                          setRentPercentagePopoverOpen(null)
                                          setTempRentPercentage("")
                                        }
                                      }}
                                    >
                                      <PopoverTrigger asChild>
                                        <Button
                                          type="button"
                                          variant="outline"
                                          size="sm"
                                          onClick={() =>
                                            openRentPercentagePopover(
                                              originalIndex,
                                            )
                                          }
                                          className="hover:bg-blue-50 hover:text-blue-600 h-10"
                                          title={
                                            t.realEstate.costs
                                              .calculateByRentPercentage
                                          }
                                        >
                                          <Percent size={16} />
                                        </Button>
                                      </PopoverTrigger>
                                      <PopoverContent className="w-64">
                                        <div className="space-y-3">
                                          <div>
                                            <Label className="text-sm font-medium">
                                              {
                                                t.realEstate.costs
                                                  .percentageOfTotalRent
                                              }
                                            </Label>
                                            <div className="mt-1">
                                              <DecimalInput
                                                value={tempRentPercentage}
                                                onStringChange={
                                                  setTempRentPercentage
                                                }
                                                placeholder="0.00"
                                                className="text-sm"
                                              />
                                            </div>
                                          </div>
                                          <div className="text-xs text-gray-500">
                                            {tempRentPercentage &&
                                              !isNaN(
                                                parseFloat(
                                                  tempRentPercentage.replace(
                                                    ",",
                                                    ".",
                                                  ),
                                                ),
                                              ) && (
                                                <>
                                                  {parseFloat(
                                                    tempRentPercentage.replace(
                                                      ",",
                                                      ".",
                                                    ),
                                                  )}
                                                  % {t.realEstate.purchase.of}{" "}
                                                  {formatCurrency(
                                                    calculateMonthlyIncome() *
                                                      (1 -
                                                        (formData.rental_data
                                                          ?.vacancy_rate ?? 0)),
                                                    locale,
                                                    formData.currency,
                                                  )}{" "}
                                                  ={" "}
                                                  {formatCurrency(
                                                    calculateAmountFromRentPercentage(
                                                      parseFloat(
                                                        tempRentPercentage.replace(
                                                          ",",
                                                          ".",
                                                        ),
                                                      ),
                                                    ),
                                                    locale,
                                                    formData.currency,
                                                  )}
                                                </>
                                              )}
                                          </div>
                                          <Button
                                            type="button"
                                            onClick={() => {
                                              const percentage = parseFloat(
                                                tempRentPercentage.replace(
                                                  ",",
                                                  ".",
                                                ),
                                              )
                                              if (!isNaN(percentage)) {
                                                applyRentPercentageToFlow(
                                                  originalIndex,
                                                  percentage,
                                                )
                                              }
                                            }}
                                            disabled={
                                              !tempRentPercentage ||
                                              isNaN(
                                                parseFloat(
                                                  tempRentPercentage.replace(
                                                    ",",
                                                    ".",
                                                  ),
                                                ),
                                              )
                                            }
                                            className="w-full"
                                            size="sm"
                                          >
                                            {t.realEstate.purchase.apply}
                                          </Button>
                                        </div>
                                      </PopoverContent>
                                    </Popover>
                                  )}
                                </div>
                                <div
                                  className={
                                    formData.basic_info.is_rented
                                      ? "sm:col-span-2"
                                      : ""
                                  }
                                >
                                  <Label>{t.realEstate.labels.frequency}</Label>
                                  <select
                                    value={
                                      flow.periodic_flow?.frequency ||
                                      FlowFrequency.MONTHLY
                                    }
                                    onChange={e =>
                                      updateFlowFrequency(
                                        originalIndex,
                                        e.target.value as FlowFrequency,
                                      )
                                    }
                                    className="w-full p-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white [&>option]:bg-white [&>option]:dark:bg-gray-800 [&>option]:text-gray-900 [&>option]:dark:text-white"
                                  >
                                    <option value={FlowFrequency.DAILY}>
                                      {t.realEstate.frequency.daily}
                                    </option>
                                    <option value={FlowFrequency.WEEKLY}>
                                      {t.realEstate.frequency.weekly}
                                    </option>
                                    <option value={FlowFrequency.MONTHLY}>
                                      {t.realEstate.frequency.monthly}
                                    </option>
                                    <option
                                      value={FlowFrequency.EVERY_TWO_MONTHS}
                                    >
                                      {t.realEstate.frequency.bimonthly}
                                    </option>
                                    <option value={FlowFrequency.QUARTERLY}>
                                      {t.realEstate.frequency.quarterly}
                                    </option>
                                    <option
                                      value={FlowFrequency.EVERY_FOUR_MONTHS}
                                    >
                                      {t.realEstate.frequency.fourMonthly}
                                    </option>
                                    <option value={FlowFrequency.SEMIANNUALLY}>
                                      {t.realEstate.frequency.semiannually}
                                    </option>
                                    <option value={FlowFrequency.YEARLY}>
                                      {t.realEstate.frequency.yearly}
                                    </option>
                                    {flow.periodic_flow?.frequency ===
                                      FlowFrequency.BIWEEKLY && (
                                      <option value={FlowFrequency.BIWEEKLY}>
                                        {
                                          (t.realEstate.frequency as any)
                                            .biweekly
                                        }
                                      </option>
                                    )}
                                    {flow.periodic_flow?.frequency ===
                                      FlowFrequency.SEMIMONTHLY && (
                                      <option value={FlowFrequency.SEMIMONTHLY}>
                                        {
                                          (t.realEstate.frequency as any)
                                            .semimonthly
                                        }
                                      </option>
                                    )}
                                  </select>
                                </div>

                                {formData.basic_info.is_rented && (
                                  <div className="flex flex-col items-end sm:items-center sm:justify-end gap-1 sm:gap-2 sm:col-span-1 mt-2 sm:mt-[2px]">
                                    <Label className="text-[11px] sm:text-xs font-medium whitespace-nowrap">
                                      {t.realEstate.labels.taxDeductible}
                                    </Label>
                                    <Switch
                                      checked={
                                        (flow.payload as any)?.tax_deductible ||
                                        false
                                      }
                                      onCheckedChange={checked =>
                                        updateFlowPayload(
                                          originalIndex,
                                          "tax_deductible",
                                          checked,
                                        )
                                      }
                                    />
                                  </div>
                                )}
                              </div>
                            </div>
                          )
                        })}

                      {formData.flows.filter(
                        flow =>
                          flow.flow_subtype === RealEstateFlowSubtype.COST,
                      ).length === 0 && (
                        <div className="text-center py-6 text-gray-500 dark:text-gray-400">
                          {t.realEstate.emptyStates.noCostsRegistered}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>

              <div className="border-t border-border pt-6">
                <button
                  type="button"
                  onClick={() => toggleSection("utilities")}
                  className="flex items-center justify-between w-full text-left"
                >
                  <h3 className="text-lg font-medium flex items-center gap-2">
                    <Zap size={18} />
                    {t.realEstate.sections.utilities}
                    {expandedSections.utilities ? (
                      <ChevronDown
                        size={18}
                        className="text-muted-foreground"
                      />
                    ) : (
                      <ChevronRight
                        size={18}
                        className="text-muted-foreground"
                      />
                    )}
                  </h3>
                  <span className="text-sm text-muted-foreground">
                    {formData.flows.filter(
                      f => f.flow_subtype === RealEstateFlowSubtype.SUPPLY,
                    ).length > 0
                      ? `${formData.flows.filter(f => f.flow_subtype === RealEstateFlowSubtype.SUPPLY).length}`
                      : ""}
                  </span>
                </button>

                {expandedSections.utilities && (
                  <div className="mt-4 space-y-4">
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-sm text-gray-600 dark:text-gray-400">
                        {t.realEstate.descriptions.manageUtilitiesDescription}
                      </p>
                      <div className="flex gap-2">
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={e => handleSuggestionClick(e, "utilities")}
                          className="text-xs"
                        >
                          <Lightbulb size={14} className="sm:mr-1" />
                          <span className="hidden sm:inline">
                            {t.realEstate.buttons.suggest}
                          </span>
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          onClick={() => addFlow(RealEstateFlowSubtype.SUPPLY)}
                          className="bg-white dark:bg-gray-100 hover:bg-gray-100 dark:hover:bg-gray-200 text-black border border-gray-300 dark:border-gray-400 shadow-sm"
                        >
                          <Plus size={16} className="sm:mr-1" />
                          <span className="hidden sm:inline">
                            {t.realEstate.flows.addSupply}
                          </span>
                        </Button>
                      </div>
                    </div>

                    {showFlowSuggestions.type === "utilities" && (
                      <div className="mb-4 p-4 bg-black dark:bg-black rounded-lg">
                        <div className="flex justify-between items-center mb-3">
                          <h4 className="font-medium text-sm text-white">
                            {t.realEstate.suggestions.availableSuggestions}
                          </h4>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() =>
                              setShowFlowSuggestions({
                                type: null,
                                position: null,
                              })
                            }
                            className="p-1 h-6 w-6"
                          >
                            <X size={12} />
                          </Button>
                        </div>
                        <div className="max-h-60 overflow-y-auto space-y-2">
                          {availableFlows
                            .filter(flow => {
                              // Exclude loan suggestions, linked, and already-used
                              if (
                                flow.id?.startsWith("loan-suggestion-") ||
                                flow.linked ||
                                (flow.id && usedExistingFlowIds.has(flow.id))
                              ) {
                                return false
                              }

                              // Only EXPENSE flows belong here
                              if (flow.flow_type !== FlowType.EXPENSE)
                                return false

                              // For GENERIC flows, only include ones mapped to utilities
                              if (flow.id?.startsWith("generic-")) {
                                const mapped = genericSectionMap[flow.id]
                                return mapped === "utilities"
                              }

                              // For non-generic existing flows, include those categorized as utilities
                              return true
                            })
                            .filter(
                              (flow, index, self) =>
                                self.findIndex(f => f.id === flow.id) === index,
                            )
                            .map((flow, index) => {
                              const isGeneric = flow.amount === 0
                              const frequencyLabel = getFrequencyLabel(
                                flow.frequency,
                                true,
                              )
                              const isCurrencyMismatch =
                                !flow.id?.startsWith("generic-") &&
                                flow.currency !== formData.currency

                              const iconName = getSuggestionIconName(
                                flow,
                                "utilities",
                              )

                              const content = (
                                <div
                                  key={`${flow.id}-${index}`}
                                  className={`flex items-center p-3 rounded transition-colors ${isCurrencyMismatch ? "opacity-40 cursor-not-allowed bg-gray-800" : "cursor-pointer bg-gray-800 hover:bg-gray-700"}`}
                                  onClick={
                                    isCurrencyMismatch
                                      ? undefined
                                      : () => applyFlowSuggestion(flow)
                                  }
                                >
                                  <div className="mr-3 flex items-center justify-center w-8 h-8 rounded-full bg-gray-600">
                                    <Icon
                                      name={
                                        (iconName ||
                                          "square-dashed") as IconName
                                      }
                                      className="w-4 h-4 text-white"
                                    />
                                  </div>
                                  <div className="flex-1">
                                    <div className="text-sm font-medium text-white">
                                      {flow.name}
                                      {isCurrencyMismatch && (
                                        <span className="ml-2 text-xs bg-yellow-600 text-white px-2 py-0.5 rounded">
                                          {flow.currency}
                                        </span>
                                      )}
                                    </div>
                                    <div className="text-xs text-gray-300">
                                      {isGeneric
                                        ? t.realEstate.analysis.genericConceptWithFrequency.replace(
                                            "{frequency}",
                                            frequencyLabel,
                                          )
                                        : `${formatCurrency(flow.amount, locale, flow.currency)} ${frequencyLabel}`}
                                    </div>
                                  </div>
                                </div>
                              )

                              if (isCurrencyMismatch) {
                                return (
                                  <TooltipProvider key={`${flow.id}-${index}`}>
                                    <Tooltip>
                                      <TooltipTrigger asChild>
                                        {content}
                                      </TooltipTrigger>
                                      <TooltipContent
                                        side="top"
                                        className="max-w-xs"
                                      >
                                        {t.realEstate.suggestions.currencyMismatch
                                          .replace("{currency}", flow.currency)
                                          .replace(
                                            "{propertyCurrency}",
                                            formData.currency,
                                          )}
                                      </TooltipContent>
                                    </Tooltip>
                                  </TooltipProvider>
                                )
                              }

                              return content
                            })}
                          {availableFlows.filter(flow => {
                            return flow.flow_type === FlowType.EXPENSE
                          }).length === 0 && (
                            <div className="text-sm text-gray-500 dark:text-gray-400 text-center py-2">
                              {t.realEstate.emptyStates.noSuggestionsAvailable}
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    <div className="space-y-3">
                      {formData.flows
                        .filter(
                          flow =>
                            flow.flow_subtype === RealEstateFlowSubtype.SUPPLY,
                        )
                        .map(flow => {
                          const originalIndex = formData.flows.findIndex(
                            f => f === flow,
                          )
                          return (
                            <div
                              key={originalIndex}
                              className="border border-gray-200 dark:border-gray-700 rounded-lg p-4"
                            >
                              <div className="flex items-center justify-between mb-3">
                                <div className="flex items-end gap-2 flex-1 mr-2">
                                  <div>
                                    <Label className="sr-only">
                                      {t.management.iconLabel}
                                    </Label>
                                    <IconPicker
                                      value={
                                        flow.periodic_flow?.icon as
                                          | IconName
                                          | undefined
                                      }
                                      onValueChange={value => {
                                        setFormData(prev => ({
                                          ...prev,
                                          flows: prev.flows.map((f, i) =>
                                            i === originalIndex &&
                                            f.periodic_flow
                                              ? {
                                                  ...f,
                                                  periodic_flow: {
                                                    ...f.periodic_flow,
                                                    icon: value,
                                                  },
                                                }
                                              : f,
                                          ),
                                        }))
                                        setHasUnsavedChanges(true)
                                      }}
                                      modal
                                    >
                                      <Button
                                        variant="outline"
                                        size="icon"
                                        className="h-9 w-9"
                                        aria-label={
                                          flow.periodic_flow?.icon ||
                                          t.management.iconLabel
                                        }
                                      >
                                        {flow.periodic_flow?.icon ? (
                                          <Icon
                                            name={
                                              flow.periodic_flow
                                                .icon as IconName
                                            }
                                            className="w-5 h-5"
                                          />
                                        ) : (
                                          <Icon
                                            name={"square-dashed" as IconName}
                                            size={18}
                                            className="text-muted-foreground w-5 h-5"
                                          />
                                        )}
                                      </Button>
                                    </IconPicker>
                                  </div>
                                  <div className="flex-1">
                                    <Label>
                                      {t.realEstate.placeholders.utilityName}
                                      <span className="text-gray-400 ml-1">
                                        *
                                      </span>
                                    </Label>
                                    <Input
                                      placeholder={
                                        t.realEstate.placeholders.utilityName
                                      }
                                      value={flow.description || ""}
                                      onChange={e =>
                                        updateFlowName(
                                          originalIndex,
                                          e.target.value,
                                        )
                                      }
                                      className={
                                        hasValidationError(
                                          `flow.${originalIndex}.name`,
                                        )
                                          ? "border-red-500"
                                          : ""
                                      }
                                    />
                                  </div>
                                </div>
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => removeFlow(originalIndex)}
                                  className="text-red-500 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-900/20 mt-6"
                                >
                                  <Trash2 size={16} />
                                </Button>
                              </div>

                              <div
                                className={`grid gap-4 ${formData.basic_info.is_rented ? "grid-cols-1 sm:grid-cols-6" : "grid-cols-1 sm:grid-cols-2"}`}
                              >
                                <div
                                  className={
                                    formData.basic_info.is_rented
                                      ? "sm:col-span-3"
                                      : ""
                                  }
                                >
                                  <Label>
                                    {t.realEstate.labels.amount}
                                    <span className="text-gray-400 ml-1">
                                      *
                                    </span>
                                  </Label>
                                  <div className="relative">
                                    <DecimalInput
                                      value={flow.periodic_flow?.amount || ""}
                                      onValueChange={v =>
                                        updateFlowAmount(originalIndex, v ?? 0)
                                      }
                                      className={`pr-12 ${hasValidationError(`flow.${originalIndex}.amount`) ? "border-red-500" : ""}`}
                                    />
                                    <span className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-500 text-sm">
                                      {getCurrencySymbol(
                                        flow.periodic_flow?.currency ||
                                          formData.currency,
                                      )}
                                    </span>
                                  </div>
                                </div>
                                <div
                                  className={
                                    formData.basic_info.is_rented
                                      ? "sm:col-span-2"
                                      : ""
                                  }
                                >
                                  <Label>{t.realEstate.labels.frequency}</Label>
                                  <select
                                    value={
                                      flow.periodic_flow?.frequency ||
                                      FlowFrequency.MONTHLY
                                    }
                                    onChange={e =>
                                      updateFlowFrequency(
                                        originalIndex,
                                        e.target.value as FlowFrequency,
                                      )
                                    }
                                    className="w-full p-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white [&>option]:bg-white [&>option]:dark:bg-gray-800 [&>option]:text-gray-900 [&>option]:dark:text-white"
                                  >
                                    <option value={FlowFrequency.DAILY}>
                                      {t.realEstate.frequency.daily}
                                    </option>
                                    <option value={FlowFrequency.WEEKLY}>
                                      {t.realEstate.frequency.weekly}
                                    </option>
                                    <option value={FlowFrequency.MONTHLY}>
                                      {t.realEstate.frequency.monthly}
                                    </option>
                                    <option
                                      value={FlowFrequency.EVERY_TWO_MONTHS}
                                    >
                                      {t.realEstate.frequency.bimonthly}
                                    </option>
                                    <option value={FlowFrequency.QUARTERLY}>
                                      {t.realEstate.frequency.quarterly}
                                    </option>
                                    <option
                                      value={FlowFrequency.EVERY_FOUR_MONTHS}
                                    >
                                      {t.realEstate.frequency.fourMonthly}
                                    </option>
                                    <option value={FlowFrequency.SEMIANNUALLY}>
                                      {t.realEstate.frequency.semiannually}
                                    </option>
                                    <option value={FlowFrequency.YEARLY}>
                                      {t.realEstate.frequency.yearly}
                                    </option>
                                    {flow.periodic_flow?.frequency ===
                                      FlowFrequency.BIWEEKLY && (
                                      <option value={FlowFrequency.BIWEEKLY}>
                                        {
                                          (t.realEstate.frequency as any)
                                            .biweekly
                                        }
                                      </option>
                                    )}
                                    {flow.periodic_flow?.frequency ===
                                      FlowFrequency.SEMIMONTHLY && (
                                      <option value={FlowFrequency.SEMIMONTHLY}>
                                        {
                                          (t.realEstate.frequency as any)
                                            .semimonthly
                                        }
                                      </option>
                                    )}
                                  </select>
                                </div>

                                {formData.basic_info.is_rented && (
                                  <div className="flex flex-col items-end sm:items-center sm:justify-end gap-1 sm:gap-2 sm:col-span-1 mt-2 sm:mt-[2px]">
                                    <Label className="text-[11px] sm:text-xs font-medium whitespace-nowrap">
                                      {t.realEstate.labels.taxDeductible}
                                    </Label>
                                    <Switch
                                      checked={
                                        (flow.payload as any)?.tax_deductible ||
                                        false
                                      }
                                      onCheckedChange={checked =>
                                        updateFlowPayload(
                                          originalIndex,
                                          "tax_deductible",
                                          checked,
                                        )
                                      }
                                    />
                                  </div>
                                )}
                              </div>
                            </div>
                          )
                        })}

                      {formData.flows.filter(
                        flow =>
                          flow.flow_subtype === RealEstateFlowSubtype.SUPPLY,
                      ).length === 0 && (
                        <div className="text-center py-6 text-gray-500 dark:text-gray-400">
                          {t.realEstate.emptyStates.noUtilitiesRegistered}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {formData.basic_info.is_rented && (
                <div className="border-t border-border pt-6">
                  <button
                    type="button"
                    onClick={() => toggleSection("rent")}
                    className="flex items-center justify-between w-full text-left"
                  >
                    <h3 className="text-lg font-medium flex items-center gap-2">
                      <Home size={18} />
                      {t.realEstate.sections.rent}
                      {expandedSections.rent ? (
                        <ChevronDown
                          size={18}
                          className="text-muted-foreground"
                        />
                      ) : (
                        <ChevronRight
                          size={18}
                          className="text-muted-foreground"
                        />
                      )}
                    </h3>
                    <span className="text-sm text-muted-foreground">
                      {formData.flows.filter(
                        f => f.flow_subtype === RealEstateFlowSubtype.RENT,
                      ).length > 0
                        ? `${formData.flows.filter(f => f.flow_subtype === RealEstateFlowSubtype.RENT).length}`
                        : ""}
                    </span>
                  </button>

                  {expandedSections.rent && (
                    <div className="mt-4 space-y-4">
                      <div className="flex items-center justify-between mb-2">
                        <p className="text-sm text-gray-600 dark:text-gray-400">
                          {t.realEstate.descriptions.manageRentDescription}
                        </p>
                        <div className="flex gap-2">
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            onClick={e => handleSuggestionClick(e, "rent")}
                            className="text-xs"
                          >
                            <Lightbulb size={14} className="sm:mr-1" />
                            <span className="hidden sm:inline">
                              {t.realEstate.buttons.suggest}
                            </span>
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            onClick={() => addFlow(RealEstateFlowSubtype.RENT)}
                            className="bg-white dark:bg-gray-100 hover:bg-gray-100 dark:hover:bg-gray-200 text-black border border-gray-300 dark:border-gray-400 shadow-sm"
                          >
                            <Plus size={16} className="sm:mr-1" />
                            <span className="hidden sm:inline">
                              {t.realEstate.flows.addRental}
                            </span>
                          </Button>
                        </div>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div>
                          <Label>{t.realEstate.rent.vacancyRate}</Label>
                          <div className="relative">
                            <DecimalInput
                              value={
                                typeof formData.rental_data?.vacancy_rate ===
                                "number"
                                  ? (formData.rental_data?.vacancy_rate || 0) *
                                    100
                                  : ""
                              }
                              onValueChange={v =>
                                handleInputChange(
                                  "rental_data.vacancy_rate",
                                  v != null ? v / 100 : null,
                                )
                              }
                              className="pr-8"
                              placeholder={t.realEstate.placeholders.example24}
                            />
                            <span className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-500 text-sm">
                              %
                            </span>
                          </div>
                        </div>
                      </div>

                      {showFlowSuggestions.type === "rent" && (
                        <div className="mb-4 p-4 bg-black dark:bg-black rounded-lg">
                          <div className="flex justify-between items-center mb-3">
                            <h4 className="font-medium text-sm text-white">
                              {t.realEstate.suggestions.availableSuggestions}
                            </h4>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() =>
                                setShowFlowSuggestions({
                                  type: null,
                                  position: null,
                                })
                              }
                              className="p-1 h-6 w-6"
                            >
                              <X size={12} />
                            </Button>
                          </div>
                          <div className="max-h-60 overflow-y-auto space-y-2">
                            {availableFlows
                              .filter(flow => {
                                if (
                                  flow.linked ||
                                  (flow.id && usedExistingFlowIds.has(flow.id))
                                )
                                  return false
                                // Only EARNING flows in rent
                                if (flow.flow_type !== FlowType.EARNING)
                                  return false
                                // For generics, ensure they are mapped to rent
                                if (flow.id?.startsWith("generic-")) {
                                  const mapped = genericSectionMap[flow.id]
                                  return mapped === "rent"
                                }
                                return true
                              })
                              .filter(
                                (flow, index, self) =>
                                  self.findIndex(f => f.id === flow.id) ===
                                  index,
                              )
                              .map((flow, index) => {
                                const isGeneric = flow.amount === 0
                                const frequencyLabel = getFrequencyLabel(
                                  flow.frequency,
                                  true,
                                )
                                const isCurrencyMismatch =
                                  !flow.id?.startsWith("generic-") &&
                                  flow.currency !== formData.currency

                                const iconName = getSuggestionIconName(
                                  flow,
                                  "rent",
                                )

                                const content = (
                                  <div
                                    key={`${flow.id}-${index}`}
                                    className={`flex items-center p-3 rounded transition-colors ${isCurrencyMismatch ? "opacity-40 cursor-not-allowed bg-gray-800" : "cursor-pointer bg-gray-800 hover:bg-gray-700"}`}
                                    onClick={
                                      isCurrencyMismatch
                                        ? undefined
                                        : () => applyFlowSuggestion(flow)
                                    }
                                  >
                                    <div className="mr-3 flex items-center justify-center w-8 h-8 rounded-full bg-gray-600">
                                      <Icon
                                        name={
                                          (iconName ||
                                            "square-dashed") as IconName
                                        }
                                        className="w-4 h-4 text-white"
                                      />
                                    </div>
                                    <div className="flex-1">
                                      <div className="text-sm font-medium text-white">
                                        {flow.name}
                                        {isCurrencyMismatch && (
                                          <span className="ml-2 text-xs bg-yellow-600 text-white px-2 py-0.5 rounded">
                                            {flow.currency}
                                          </span>
                                        )}
                                      </div>
                                      <div className="text-xs text-gray-300">
                                        {isGeneric
                                          ? t.realEstate.analysis.genericConceptWithFrequency.replace(
                                              "{frequency}",
                                              frequencyLabel,
                                            )
                                          : `${formatCurrency(flow.amount, locale, flow.currency)} ${frequencyLabel}`}
                                      </div>
                                    </div>
                                  </div>
                                )

                                if (isCurrencyMismatch) {
                                  return (
                                    <TooltipProvider
                                      key={`${flow.id}-${index}`}
                                    >
                                      <Tooltip>
                                        <TooltipTrigger asChild>
                                          {content}
                                        </TooltipTrigger>
                                        <TooltipContent
                                          side="top"
                                          className="max-w-xs"
                                        >
                                          {t.realEstate.suggestions.currencyMismatch
                                            .replace(
                                              "{currency}",
                                              flow.currency,
                                            )
                                            .replace(
                                              "{propertyCurrency}",
                                              formData.currency,
                                            )}
                                        </TooltipContent>
                                      </Tooltip>
                                    </TooltipProvider>
                                  )
                                }

                                return content
                              })}
                            {availableFlows.filter(
                              flow =>
                                flow.flow_type === FlowType.EARNING &&
                                !flow.linked,
                            ).length === 0 && (
                              <div className="text-sm text-gray-400 text-center py-2">
                                {
                                  t.realEstate.emptyStates
                                    .noSuggestionsAvailable
                                }
                              </div>
                            )}
                          </div>
                        </div>
                      )}

                      <div className="space-y-3">
                        {formData.flows
                          .filter(
                            flow =>
                              flow.flow_subtype === RealEstateFlowSubtype.RENT,
                          )
                          .map(flow => {
                            const originalIndex = formData.flows.findIndex(
                              f => f === flow,
                            )
                            return (
                              <div
                                key={originalIndex}
                                className="border border-gray-200 dark:border-gray-700 rounded-lg p-4"
                              >
                                <div className="flex items-center justify-between mb-3">
                                  <div className="flex items-end gap-2 flex-1 mr-2">
                                    <div>
                                      <Label className="sr-only">
                                        {t.management.iconLabel}
                                      </Label>
                                      <IconPicker
                                        value={
                                          flow.periodic_flow?.icon as
                                            | IconName
                                            | undefined
                                        }
                                        onValueChange={value => {
                                          setFormData(prev => ({
                                            ...prev,
                                            flows: prev.flows.map((f, i) =>
                                              i === originalIndex &&
                                              f.periodic_flow
                                                ? {
                                                    ...f,
                                                    periodic_flow: {
                                                      ...f.periodic_flow,
                                                      icon: value,
                                                    },
                                                  }
                                                : f,
                                            ),
                                          }))
                                          setHasUnsavedChanges(true)
                                        }}
                                        modal
                                      >
                                        <Button
                                          variant="outline"
                                          size="icon"
                                          className="h-9 w-9"
                                          aria-label={
                                            flow.periodic_flow?.icon ||
                                            t.management.iconLabel
                                          }
                                        >
                                          {flow.periodic_flow?.icon ? (
                                            <Icon
                                              name={
                                                flow.periodic_flow
                                                  .icon as IconName
                                              }
                                              className="w-5 h-5"
                                            />
                                          ) : (
                                            <Icon
                                              name={"square-dashed" as IconName}
                                              size={18}
                                              className="text-muted-foreground w-5 h-5"
                                            />
                                          )}
                                        </Button>
                                      </IconPicker>
                                    </div>
                                    <div className="flex-1">
                                      <Label>
                                        {t.realEstate.placeholders.rentName}
                                        <span className="text-gray-400 ml-1">
                                          *
                                        </span>
                                      </Label>
                                      <Input
                                        placeholder={
                                          t.realEstate.placeholders.rentName
                                        }
                                        value={flow.description || ""}
                                        onChange={e =>
                                          updateFlowName(
                                            originalIndex,
                                            e.target.value,
                                          )
                                        }
                                        className={
                                          hasValidationError(
                                            `flow.${originalIndex}.name`,
                                          )
                                            ? "border-red-500"
                                            : ""
                                        }
                                      />
                                    </div>
                                  </div>
                                  <Button
                                    type="button"
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => removeFlow(originalIndex)}
                                    className="text-red-500 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-900/20 mt-6"
                                  >
                                    <Trash2 size={16} />
                                  </Button>
                                </div>

                                <div className="grid grid-cols-2 gap-4">
                                  <div>
                                    <Label>
                                      {t.realEstate.labels.monthlyAmount}
                                      <span className="text-gray-400 ml-1">
                                        *
                                      </span>
                                    </Label>
                                    <div className="relative">
                                      <DecimalInput
                                        value={flow.periodic_flow?.amount || ""}
                                        onValueChange={v =>
                                          updateFlowAmount(
                                            originalIndex,
                                            v ?? 0,
                                          )
                                        }
                                        className={`pr-12 ${hasValidationError(`flow.${originalIndex}.amount`) ? "border-red-500" : ""}`}
                                      />
                                      <span className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-500 text-sm">
                                        {getCurrencySymbol(formData.currency)}
                                      </span>
                                    </div>
                                  </div>
                                  <div>
                                    <Label>
                                      {t.realEstate.loans.paymentDate}
                                      <span className="text-gray-400 ml-1">
                                        *
                                      </span>
                                    </Label>
                                    <DatePicker
                                      value={flow.periodic_flow?.since || ""}
                                      onChange={value => {
                                        setFormData(prev => ({
                                          ...prev,
                                          flows: prev.flows.map((f, i) =>
                                            i === originalIndex &&
                                            f.periodic_flow
                                              ? {
                                                  ...f,
                                                  periodic_flow: {
                                                    ...f.periodic_flow,
                                                    since: value,
                                                  },
                                                }
                                              : f,
                                          ),
                                        }))
                                        setHasUnsavedChanges(true)
                                      }}
                                      placeholder={
                                        t.realEstate.placeholders.selectDate
                                      }
                                      className={
                                        hasValidationError(
                                          `flow.${originalIndex}.since`,
                                        )
                                          ? "border-red-500"
                                          : ""
                                      }
                                    />
                                  </div>
                                </div>
                              </div>
                            )
                          })}

                        {formData.flows.filter(
                          flow =>
                            flow.flow_subtype === RealEstateFlowSubtype.RENT,
                        ).length === 0 && (
                          <div className="text-center py-6 text-gray-500 dark:text-gray-400">
                            {t.realEstate.emptyStates.noRentRegistered}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {formData.basic_info.is_rented && (
                <div className="border-t border-border pt-6">
                  <button
                    type="button"
                    className="flex items-center justify-between w-full text-left"
                    onClick={() => setAmortizationsExpanded(v => !v)}
                  >
                    <h3 className="text-lg font-medium flex items-center gap-2">
                      <Calculator size={18} />{" "}
                      {t.realEstate.amortizations.title}
                      {amortizationsExpanded ? (
                        <ChevronDown
                          size={18}
                          className="text-muted-foreground"
                        />
                      ) : (
                        <ChevronRight
                          size={18}
                          className="text-muted-foreground"
                        />
                      )}
                    </h3>
                    <span className="text-sm text-muted-foreground">
                      {(formData.rental_data?.amortizations || []).length > 0
                        ? `${(formData.rental_data?.amortizations || []).length}`
                        : ""}
                    </span>
                  </button>
                  {amortizationsExpanded && (
                    <>
                      <div className="flex justify-end mt-4">
                        <Button
                          type="button"
                          size="sm"
                          onClick={() => {
                            const list =
                              formData.rental_data?.amortizations || []
                            const newItem = {
                              concept: "",
                              base_amount: 0,
                              percentage: 100,
                              amount: 0,
                            }
                            handleInputChange("rental_data.amortizations", [
                              ...list,
                              newItem,
                            ])
                          }}
                        >
                          <Plus size={16} className="sm:mr-1" />
                          <span className="hidden sm:inline">
                            {t.realEstate.amortizations.add}
                          </span>
                        </Button>
                      </div>
                      <div className="mt-4 space-y-2">
                        {(formData.rental_data?.amortizations || []).map(
                          (a, idx) => (
                            <div
                              key={idx}
                              className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-12 gap-2 items-end"
                            >
                              <div className="col-span-12 md:col-span-4">
                                <Label>
                                  {t.realEstate.amortizations.concept}
                                </Label>
                                <Input
                                  value={a.concept}
                                  onChange={e => {
                                    const list = [
                                      ...(formData.rental_data?.amortizations ||
                                        []),
                                    ]
                                    list[idx] = {
                                      ...a,
                                      concept: e.target.value,
                                    }
                                    handleInputChange(
                                      "rental_data.amortizations",
                                      list,
                                    )
                                  }}
                                  placeholder={
                                    t.realEstate.placeholders.concept
                                  }
                                  className={
                                    hasValidationError(
                                      `amortizations.${idx}.concept`,
                                    )
                                      ? "border-red-500"
                                      : ""
                                  }
                                />
                              </div>
                              <div className="col-span-12 sm:col-span-6 md:col-span-3">
                                <Label>{t.realEstate.amortizations.base}</Label>
                                <div className="relative">
                                  <DecimalInput
                                    value={a.base_amount || ""}
                                    onValueChange={v => {
                                      const base = v ?? 0
                                      const list = [
                                        ...(formData.rental_data
                                          ?.amortizations || []),
                                      ]
                                      const amount =
                                        (base * (a.percentage || 0)) / 100
                                      list[idx] = {
                                        ...a,
                                        base_amount: base,
                                        amount,
                                      }
                                      handleInputChange(
                                        "rental_data.amortizations",
                                        list,
                                      )
                                    }}
                                    className={`pr-10 ${hasValidationError(`amortizations.${idx}.base_amount`) ? "border-red-500" : ""}`}
                                  />
                                  <span className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 text-sm">
                                    {getCurrencySymbol(formData.currency)}
                                  </span>
                                </div>
                              </div>
                              <div className="col-span-12 sm:col-span-6 md:col-span-2">
                                <Label>
                                  {t.realEstate.amortizations.percentage}
                                </Label>
                                <div className="relative">
                                  <DecimalInput
                                    value={a.percentage || ""}
                                    onValueChange={v => {
                                      const pct = v ?? 0
                                      const list = [
                                        ...(formData.rental_data
                                          ?.amortizations || []),
                                      ]
                                      const amount =
                                        ((a.base_amount || 0) * pct) / 100
                                      list[idx] = {
                                        ...a,
                                        percentage: pct,
                                        amount,
                                      }
                                      handleInputChange(
                                        "rental_data.amortizations",
                                        list,
                                      )
                                    }}
                                    className={`pr-8 ${hasValidationError(`amortizations.${idx}.percentage`) ? "border-red-500" : ""}`}
                                  />
                                  <span className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 text-sm">
                                    %
                                  </span>
                                </div>
                              </div>
                              <div className="col-span-12 sm:col-span-6 md:col-span-3">
                                <Label>
                                  {t.realEstate.amortizations.annual}
                                </Label>
                                <div className="relative">
                                  <DecimalInput
                                    value={a.amount || ""}
                                    onValueChange={v => {
                                      const amt = v ?? 0
                                      const list = [
                                        ...(formData.rental_data
                                          ?.amortizations || []),
                                      ]
                                      let pct = a.percentage
                                      if ((a.base_amount || 0) > 0) {
                                        pct = (amt / a.base_amount) * 100
                                      }
                                      list[idx] = {
                                        ...a,
                                        amount: amt,
                                        percentage: pct,
                                      }
                                      handleInputChange(
                                        "rental_data.amortizations",
                                        list,
                                      )
                                    }}
                                    className={`pr-10 ${hasValidationError(`amortizations.${idx}.amount`) ? "border-red-500" : ""}`}
                                  />
                                  <span className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 text-sm">
                                    {getCurrencySymbol(formData.currency)}
                                  </span>
                                </div>
                              </div>
                              <div className="col-span-12 flex justify-end">
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => {
                                    const list = [
                                      ...(formData.rental_data?.amortizations ||
                                        []),
                                    ]
                                    handleInputChange(
                                      "rental_data.amortizations",
                                      list.filter((_, i) => i !== idx),
                                    )
                                  }}
                                  className="text-red-500 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-900/20"
                                >
                                  <Trash2 size={16} />
                                </Button>
                              </div>
                            </div>
                          ),
                        )}
                        {(formData.rental_data?.amortizations || []).length ===
                          0 && (
                          <div className="text-sm text-gray-500 dark:text-gray-400">
                            {t.realEstate.amortizations.empty}
                          </div>
                        )}
                      </div>
                    </>
                  )}
                </div>
              )}

              <RealEstateStats
                currency={formData.currency}
                isRented={formData.basic_info.is_rented}
                flows={formData.flows}
                purchasePrice={formData.purchase_info.price || 0}
                purchaseExpenses={formData.purchase_info.expenses}
                estimatedMarketValue={
                  formData.valuation_info.estimated_market_value || 0
                }
                marginalTaxRate={formData.rental_data?.marginal_tax_rate}
                amortizationsAnnual={(
                  formData.rental_data?.amortizations || []
                ).map(a => ({ amount: a.amount }))}
                vacancyRate={formData.rental_data?.vacancy_rate ?? undefined}
                onChangeMarginalTaxRate={val =>
                  handleInputChange("rental_data.marginal_tax_rate", val)
                }
                cardClassName="p-4 -mx-4 rounded-none border-x-0"
              />
            </div>

            <div className="flex-shrink-0 border-t border-border p-2 rounded-b-lg">
              <div className="flex justify-end gap-3">
                <Button variant="outline" onClick={handleClose}>
                  {t.common.cancel}
                </Button>
                <Button onClick={handleSubmit} disabled={loading}>
                  {loading ? t.common.saving : t.common.save}
                </Button>
              </div>
            </div>
          </motion.div>

          <ConfirmationDialog
            isOpen={showUnsavedDialog}
            title={t.realEstate.modals.discardChangesTitle}
            message={t.realEstate.modals.unsavedChanges}
            confirmText={t.realEstate.modals.discardChanges}
            cancelText={t.realEstate.modals.saveChanges}
            onConfirm={() => {
              setShowUnsavedDialog(false)
              onClose()
            }}
            onCancel={() => setShowUnsavedDialog(false)}
          />

          <ConfirmationDialog
            isOpen={unlinkConfirmIndex !== null}
            title={t.realEstate.modals.unlinkLoanTitle}
            message={t.realEstate.modals.unlinkLoanMessage}
            warning={t.realEstate.modals.unlinkLoanWarning}
            confirmText={t.realEstate.modals.unlinkLoanConfirm}
            cancelText={t.realEstate.modals.unlinkLoanCancel}
            onConfirm={() => {
              if (unlinkConfirmIndex !== null) {
                setFormData(prev => ({
                  ...prev,
                  flows: prev.flows.map((flow, i) =>
                    i === unlinkConfirmIndex
                      ? { ...flow, linked_loan_hash: null }
                      : flow,
                  ),
                }))
                setHasUnsavedChanges(true)
              }
              setUnlinkConfirmIndex(null)
            }}
            onCancel={() => setUnlinkConfirmIndex(null)}
          />

          <UnassignedFlowsDialog
            isOpen={showRemoveUnassignedDialog}
            onConfirm={removeFlows => {
              setShowRemoveUnassignedDialog(false)
              submitForm(removeFlows)
            }}
            onCancel={() => {
              setShowRemoveUnassignedDialog(false)
              submitForm(false)
            }}
          />
        </motion.div>
      )}
    </AnimatePresence>
  )
}
