import type { ReactNode } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { useRef } from "react"
import { useCallback, useEffect, useMemo, useState } from "react"
import {
  ArrowLeftRight,
  BarChart,
  CalendarClock,
  ChevronLeft,
  Edit3,
  GripVertical,
  LayoutTemplate,
  Layers,
  Check,
  PlusCircle,
  Sparkles,
  ToggleLeft,
  Trash2,
  Type,
  X,
  Hash,
  ListChecks,
  Lock,
  Info,
} from "lucide-react"
import type {
  Feature,
  Template,
  TemplateCreatePayload,
  TemplateCreateField,
  TemplateFeatureDefinition,
  TemplateFeatureField,
  TemplateUpdatePayload,
} from "@/types"
import { TemplateFieldType, TemplateType } from "@/types"
import type { ProductType } from "@/types/position"
import type { Translations } from "@/i18n"
import { cn } from "@/lib/utils"
import { getIconForProductType } from "@/utils/dashboardUtils"
import { Badge } from "@/components/ui/Badge"
import { Button } from "@/components/ui/Button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card"
import { Input } from "@/components/ui/Input"
import { Label } from "@/components/ui/Label"
import { ConfirmationDialog } from "@/components/ui/ConfirmationDialog"
import { LoadingSpinner } from "@/components/ui/LoadingSpinner"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover"
import { TooltipProvider } from "@/components/ui/tooltip"

type TemplateFieldsMap = Partial<Record<Feature, TemplateFeatureDefinition[]>>

interface TemplateManagerDialogProps {
  isOpen: boolean
  onClose: () => void
  templates: Template[]
  templateType: TemplateType
  templateFields: TemplateFieldsMap | null
  isLoadingTemplates: boolean
  isLoadingFields: boolean
  onCreate: (payload: TemplateCreatePayload) => Promise<void>
  onUpdate: (payload: TemplateUpdatePayload) => Promise<void>
  onDelete: (id: string) => Promise<void>
  featureLabels: Record<string, string>
  productLabels: Record<string, string>
  t: Translations
}

interface TemplateFieldDraft {
  field: string
  customName: string
  selected: boolean
  type: TemplateFieldType
  enumValues?: string[]
  defaultValue: string
  defaultError?: string
  systemDefaultValue?: string
  useSystemDefault: boolean
}

interface TemplateEditorState {
  id?: string
  name: string
  feature: Feature | null
  products: ProductType[]
  fields: TemplateFieldDraft[]
}

type FeatureDraftSnapshot = Pick<TemplateEditorState, "products" | "fields">
type TemplateFormErrors = Partial<
  Record<"name" | "feature" | "products" | "fields" | "submit", string>
>

export const featureIcons: Record<Feature, ReactNode> = {
  POSITION: <BarChart className="h-4 w-4" />,
  AUTO_CONTRIBUTIONS: <PiggyBankIcon />,
  TRANSACTIONS: <ArrowLeftRight className="h-4 w-4" />,
  HISTORIC: <HistoryIcon />,
}

const IMPORT_ALLOWED_FEATURES: Feature[] = ["POSITION", "TRANSACTIONS"]

function PiggyBankIcon() {
  return <Layers className="h-4 w-4" />
}

function HistoryIcon() {
  return <CalendarClock className="h-4 w-4" />
}

const fieldTypeIcons: Record<TemplateFieldType, ReactNode> = {
  TEXT: <Type className="h-4 w-4" />,
  CURRENCY: <Type className="h-4 w-4" />,
  ENUM: <ListChecks className="h-4 w-4" />,
  INTEGER: <Hash className="h-4 w-4" />,
  DECIMAL: <Hash className="h-4 w-4" />,
  BOOLEAN: <ToggleLeft className="h-4 w-4" />,
  DATE: <CalendarClock className="h-4 w-4" />,
  DATETIME: <CalendarClock className="h-4 w-4" />,
}

const typePriority: TemplateFieldType[] = [
  TemplateFieldType.TEXT,
  TemplateFieldType.ENUM,
  TemplateFieldType.CURRENCY,
  TemplateFieldType.DECIMAL,
  TemplateFieldType.INTEGER,
  TemplateFieldType.DATETIME,
  TemplateFieldType.DATE,
]

const unsupportedDefaultTypes = new Set<TemplateFieldType>([
  TemplateFieldType.DATE,
  TemplateFieldType.DATETIME,
])

const canFieldUseDefault = (type: TemplateFieldType) =>
  !unsupportedDefaultTypes.has(type)

const serializeDefaultValue = (value: any, type: TemplateFieldType): string => {
  if (value === undefined || value === null) {
    return ""
  }
  if (type === TemplateFieldType.BOOLEAN) {
    return value ? "true" : "false"
  }
  if (type === TemplateFieldType.CURRENCY) {
    return String(value).toUpperCase()
  }
  return String(value)
}

const deriveSystemDefaultValue = (
  definition: TemplateFeatureField,
): string | undefined => {
  if (
    !canFieldUseDefault(definition.type) ||
    definition.default === undefined ||
    definition.default === null
  ) {
    return undefined
  }
  return serializeDefaultValue(definition.default, definition.type)
}

const mergeFieldTypes = (
  a: TemplateFieldType,
  b: TemplateFieldType,
): TemplateFieldType => {
  if (a === b) {
    return a
  }
  const types = [a, b]
  const effective = typePriority.find(type => types.includes(type))
  return effective ?? TemplateFieldType.BOOLEAN
}

const mergeEnumValues = (
  existing?: string[] | null,
  incoming?: string[] | null,
): string[] | undefined => {
  const values = [...(existing ?? []), ...(incoming ?? [])]
  if (values.length === 0) {
    return undefined
  }
  return Array.from(new Set(values))
}

const mergeFieldDefinition = (
  existing: TemplateFeatureField | undefined,
  incoming: TemplateFeatureField,
): TemplateFeatureField => {
  if (!existing) {
    return {
      ...incoming,
      enum_values: mergeEnumValues(incoming.enum_values),
      required: incoming.required,
      or_requires: incoming.or_requires,
      default: incoming.default,
    }
  }
  const type = mergeFieldTypes(existing.type, incoming.type)
  return {
    ...incoming,
    ...existing,
    type,
    enum_values:
      type === TemplateFieldType.ENUM
        ? mergeEnumValues(existing.enum_values, incoming.enum_values)
        : undefined,
    required: existing.required || incoming.required,
    or_requires: Array.from(
      new Set([
        ...(existing.or_requires || []),
        ...(incoming.or_requires || []),
      ]),
    ),
    default: existing.default ?? incoming.default,
  }
}

export function TemplateManagerDialog({
  isOpen,
  onClose,
  templates,
  templateType,
  templateFields,
  isLoadingTemplates,
  isLoadingFields,
  onCreate,
  onUpdate,
  onDelete,
  featureLabels,
  productLabels,
  t,
}: TemplateManagerDialogProps) {
  const templateTexts = t.export.templates
  const fieldLabelMap = useMemo(
    () => templateTexts.fieldLabels as Record<string, string>,
    [templateTexts.fieldLabels],
  )
  const getFieldLabel = useCallback(
    (fieldKey: string) => {
      const baseKey = fieldKey.split(".")[0]
      return fieldLabelMap[baseKey] ?? fieldKey
    },
    [fieldLabelMap],
  )
  const [mode, setMode] = useState<"list" | "create" | "edit">("list")
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(
    null,
  )
  const [draft, setDraft] = useState<TemplateEditorState | null>(null)
  const [formErrors, setFormErrors] = useState<TemplateFormErrors>({})
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [templateToDelete, setTemplateToDelete] = useState<Template | null>(
    null,
  )
  const [isDeleting, setIsDeleting] = useState(false)
  const [dragIndex, setDragIndex] = useState<number | null>(null)
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null)
  const [touchDragIndex, setTouchDragIndex] = useState<number | null>(null)
  const [isTouchDragging, setIsTouchDragging] = useState(false)
  const fieldListRef = useRef<HTMLDivElement | null>(null)
  const [featureDrafts, setFeatureDrafts] = useState<
    Partial<Record<Feature, FeatureDraftSnapshot>>
  >({})
  const [enumPreviewField, setEnumPreviewField] = useState<string | null>(null)
  const [blockedGroup, setBlockedGroup] = useState<{
    field: string
    members: string[]
  } | null>(null)
  useEffect(() => {
    if (!blockedGroup) return
    const timer = setTimeout(() => setBlockedGroup(null), 2500)
    return () => clearTimeout(timer)
  }, [blockedGroup])
  const isImportTemplate = templateType === TemplateType.IMPORT

  const currencyOptions = useMemo(() => {
    if (typeof Intl?.supportedValuesOf === "function") {
      try {
        return Array.from(
          new Set(
            Intl.supportedValuesOf("currency").map(code => code.toUpperCase()),
          ),
        ).sort()
      } catch {
        // fall through to fallback set
      }
    }
    return ["USD", "EUR", "GBP", "JPY"]
  }, [])

  const supportedCurrencySet = useMemo(
    () => new Set(currencyOptions),
    [currencyOptions],
  )

  const validateDefaultValue = useCallback(
    (
      rawValue: string,
      type: TemplateFieldType,
      definition?: TemplateFeatureField,
    ): string | null => {
      if (!rawValue) {
        return null
      }
      const errors = templateTexts.defaultValueErrors
      switch (type) {
        case TemplateFieldType.TEXT:
          return rawValue.trim().length === 0 ? errors.text : null
        case TemplateFieldType.ENUM: {
          const enumValues = definition?.enum_values || []
          if (enumValues.length === 0) {
            return errors.enum
          }
          return enumValues.includes(rawValue) ? null : errors.enum
        }
        case TemplateFieldType.BOOLEAN:
          return rawValue === "true" || rawValue === "false"
            ? null
            : errors.boolean
        case TemplateFieldType.INTEGER:
          return /^-?\d+$/.test(rawValue) ? null : errors.integer
        case TemplateFieldType.DECIMAL:
          return /^-?\d+(\.\d+)?$/.test(rawValue) ? null : errors.decimal
        case TemplateFieldType.CURRENCY: {
          const normalized = rawValue.toUpperCase()
          if (!/^[A-Z]{3}$/.test(normalized)) {
            return errors.currency
          }
          if (
            supportedCurrencySet.size > 0 &&
            !supportedCurrencySet.has(normalized)
          ) {
            return errors.currency
          }
          return null
        }
        default:
          return null
      }
    },
    [supportedCurrencySet, templateTexts.defaultValueErrors],
  )

  const handleDefaultValueChange = useCallback(
    (fieldKey: string, value: string, definition?: TemplateFeatureField) => {
      setDraft(prev => {
        if (!prev) {
          return prev
        }
        return {
          ...prev,
          fields: prev.fields.map(field => {
            if (field.field !== fieldKey) {
              return field
            }
            const normalizedValue = canFieldUseDefault(field.type)
              ? field.type === TemplateFieldType.CURRENCY
                ? value.toUpperCase()
                : value
              : ""
            const error = validateDefaultValue(
              normalizedValue,
              field.type,
              definition,
            )
            const isUsingSystemDefault = Boolean(
              field.systemDefaultValue &&
                normalizedValue === field.systemDefaultValue,
            )
            return {
              ...field,
              defaultValue: normalizedValue,
              defaultError: isUsingSystemDefault
                ? undefined
                : (error ?? undefined),
              useSystemDefault: isUsingSystemDefault,
            }
          }),
        }
      })
    },
    [validateDefaultValue],
  )

  const getDefaultValuePayload = useCallback((field: TemplateFieldDraft) => {
    if (!canFieldUseDefault(field.type)) {
      return undefined
    }
    if (field.useSystemDefault && field.systemDefaultValue) {
      return null
    }
    if (!field.defaultValue) {
      return undefined
    }
    switch (field.type) {
      case TemplateFieldType.BOOLEAN:
        return field.defaultValue === "true"
      case TemplateFieldType.INTEGER:
        return Number.parseInt(field.defaultValue, 10)
      case TemplateFieldType.DECIMAL:
        return Number(field.defaultValue)
      case TemplateFieldType.CURRENCY:
        return field.defaultValue.toUpperCase()
      default:
        return field.defaultValue
    }
  }, [])

  const renderDefaultValueEditor = (
    field: TemplateFieldDraft,
    definition?: TemplateFeatureField,
  ) => {
    if (
      !isImportTemplate ||
      !canFieldUseDefault(field.type) ||
      definition?.disabled_default
    ) {
      return null
    }
    const baseSelectClass = cn(
      "w-full rounded-md border border-border/60 bg-background px-3 py-2 text-sm text-foreground h-9",
      field.defaultError
        ? "border-red-500 focus-visible:ring-red-500"
        : undefined,
    )
    const controlId = `default-value-${field.field}`

    let control: ReactNode = null
    if (field.type === TemplateFieldType.BOOLEAN) {
      control = (
        <select
          id={controlId}
          draggable={false}
          disabled={!field.selected}
          className={baseSelectClass}
          value={field.defaultValue}
          onChange={event =>
            handleDefaultValueChange(
              field.field,
              event.target.value,
              definition,
            )
          }
        >
          <option value="">{templateTexts.defaultValueNoneOption}</option>
          <option value="true">{templateTexts.defaultValueBooleanTrue}</option>
          <option value="false">
            {templateTexts.defaultValueBooleanFalse}
          </option>
        </select>
      )
    } else if (field.type === TemplateFieldType.ENUM) {
      const enumOptions = field.enumValues ?? definition?.enum_values ?? []
      const hasSystemDefault = Boolean(field.systemDefaultValue)
      control = (
        <select
          id={controlId}
          draggable={false}
          className={baseSelectClass}
          value={field.defaultValue}
          onChange={event =>
            handleDefaultValueChange(
              field.field,
              event.target.value,
              definition,
            )
          }
          disabled={!field.selected || enumOptions.length === 0}
        >
          {!hasSystemDefault && (
            <option value="">{templateTexts.defaultValueNoneOption}</option>
          )}
          {enumOptions.map(option => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      )
    } else if (field.type === TemplateFieldType.CURRENCY) {
      control = (
        <select
          id={controlId}
          draggable={false}
          disabled={!field.selected}
          className={baseSelectClass}
          value={field.defaultValue}
          onChange={event =>
            handleDefaultValueChange(
              field.field,
              event.target.value,
              definition,
            )
          }
        >
          <option value="">{templateTexts.defaultValueNoneOption}</option>
          {currencyOptions.map(code => (
            <option key={code} value={code}>
              {code}
            </option>
          ))}
        </select>
      )
    } else if (
      field.type === TemplateFieldType.INTEGER ||
      field.type === TemplateFieldType.DECIMAL
    ) {
      control = (
        <Input
          id={controlId}
          draggable={false}
          disabled={!field.selected}
          value={field.defaultValue}
          onChange={event =>
            handleDefaultValueChange(
              field.field,
              event.target.value,
              definition,
            )
          }
          placeholder={templateTexts.defaultValuePlaceholder}
          inputMode={
            field.type === TemplateFieldType.INTEGER ? "numeric" : "decimal"
          }
          className={cn(
            "h-9",
            field.defaultError
              ? "border-red-500 focus-visible:ring-red-500"
              : undefined,
          )}
        />
      )
    } else {
      control = (
        <Input
          id={controlId}
          draggable={false}
          disabled={!field.selected}
          value={field.defaultValue}
          onChange={event =>
            handleDefaultValueChange(
              field.field,
              event.target.value,
              definition,
            )
          }
          placeholder={templateTexts.defaultValuePlaceholder}
          className={cn(
            "h-9",
            field.defaultError
              ? "border-red-500 focus-visible:ring-red-500"
              : undefined,
          )}
        />
      )
    }

    return (
      <div>
        <div className="flex items-center gap-1 h-5">
          <Label className="text-xs leading-tight" htmlFor={controlId}>
            {templateTexts.defaultValueFormLabel}
          </Label>
          <Popover>
            <PopoverTrigger asChild>
              <button
                type="button"
                className="text-muted-foreground transition hover:text-foreground"
                aria-label={templateTexts.defaultValueInfoTrigger}
                onClick={event => event.stopPropagation()}
              >
                <Info className="h-3.5 w-3.5" />
              </button>
            </PopoverTrigger>
            <PopoverContent className="max-w-xs p-3 text-xs text-muted-foreground">
              {templateTexts.defaultValueInfo}
            </PopoverContent>
          </Popover>
        </div>
        <div className="mt-1">{control}</div>
        {field.defaultError ? (
          <p className="text-xs text-red-500 mt-1">{field.defaultError}</p>
        ) : null}
      </div>
    )
  }

  const normalizeProductsForFeature = useCallback(
    (products: ProductType[], feature: Feature | null) => {
      if (
        isImportTemplate &&
        (feature === "POSITION" || feature === "TRANSACTIONS")
      ) {
        return products.slice(0, 1)
      }
      return products
    },
    [isImportTemplate],
  )

  const renderFieldTypePill = useCallback(
    (type: TemplateFieldType, fieldKey: string, enumValues?: string[]) => {
      const label = templateTexts.fieldTypes[type]
      const pillId = `${fieldKey}-${type}`
      const pill = (
        <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
          {fieldTypeIcons[type]}
          {label}
        </span>
      )
      if (type === TemplateFieldType.ENUM && enumValues?.length) {
        return (
          <Popover
            open={enumPreviewField === pillId}
            onOpenChange={open => setEnumPreviewField(open ? pillId : null)}
          >
            <PopoverTrigger
              asChild
              onMouseEnter={() => setEnumPreviewField(pillId)}
              onMouseLeave={() => setEnumPreviewField(null)}
            >
              {pill}
            </PopoverTrigger>
            <PopoverContent
              className="max-h-64 w-64 overflow-auto p-3 text-sm"
              onMouseEnter={() => setEnumPreviewField(pillId)}
              onMouseLeave={() => setEnumPreviewField(null)}
            >
              <p className="text-xs font-semibold uppercase text-muted-foreground">
                {templateTexts.enumValuesTitle}
              </p>
              <div className="mt-2 space-y-1">
                {enumValues.map(value => (
                  <div key={value} className="truncate text-xs">
                    {value}
                  </div>
                ))}
              </div>
            </PopoverContent>
          </Popover>
        )
      }
      return pill
    },
    [templateTexts, enumPreviewField, setEnumPreviewField],
  )

  const availableFeatures = useMemo(() => {
    if (!templateFields) {
      return []
    }
    const baseFeatures = Object.keys(templateFields) as Feature[]
    const filtered = isImportTemplate
      ? baseFeatures.filter(feature =>
          IMPORT_ALLOWED_FEATURES.includes(feature),
        )
      : baseFeatures
    if (
      draft?.feature &&
      !filtered.includes(draft.feature) &&
      templateFields[draft.feature]
    ) {
      return [...filtered, draft.feature]
    }
    return filtered
  }, [draft?.feature, isImportTemplate, templateFields])

  const selectedTemplate = useMemo(() => {
    if (!selectedTemplateId) {
      return templates[0] ?? null
    }
    return (
      templates.find(template => template.id === selectedTemplateId) ?? null
    )
  }, [selectedTemplateId, templates])

  useEffect(() => {
    if (!isOpen) {
      setMode("list")
      setDraft(null)
      setFormErrors({})
      setSelectedTemplateId(null)
      setDragIndex(null)
      setDragOverIndex(null)
      return
    }
    if (templates.length > 0) {
      setSelectedTemplateId(templates[0]?.id ?? null)
    }
  }, [isOpen, templates])

  const productOptionsForFeature = useMemo(() => {
    if (!draft?.feature || !templateFields) {
      return []
    }
    const featureDefinitions = templateFields[draft.feature] ?? []
    const filteredDefinitions = featureDefinitions.filter(
      def => !def.template_type || def.template_type === templateType,
    )
    const products = filteredDefinitions
      .map(def => def.product)
      .filter((product): product is ProductType => Boolean(product))
    return Array.from(new Set(products))
  }, [draft?.feature, templateFields, templateType])

  const allowedFieldDefinitions = useMemo(() => {
    if (!draft?.feature || !templateFields) {
      return []
    }
    const definitions = templateFields[draft.feature] ?? []
    // First filter by definition-level template_type
    const typeMatchedDefinitions = definitions.filter(
      def => !def.template_type || def.template_type === templateType,
    )
    // Then filter by product selection
    const filtered = typeMatchedDefinitions.filter(def => {
      if (!def.product) return true
      if (draft.products.length === 0) return false
      return draft.products.includes(def.product)
    })
    const merged = new Map<string, TemplateFeatureField>()
    filtered.forEach(def => {
      def.fields.forEach(field => {
        // Field-level template_type (if present) also must match
        if (field.template_type && field.template_type !== templateType) return
        const existing = merged.get(field.field)
        merged.set(field.field, mergeFieldDefinition(existing, field))
      })
    })
    return Array.from(merged.values())
  }, [draft?.feature, draft?.products, templateFields, templateType])

  useEffect(() => {
    if (!draft) {
      return
    }
    if (!draft.feature || allowedFieldDefinitions.length === 0) {
      if (draft.fields.length > 0) {
        setDraft(prev => (prev ? { ...prev, fields: [] } : prev))
      }
      return
    }
    setDraft(prev => {
      if (!prev) {
        return prev
      }
      const allowedMap = new Map(
        allowedFieldDefinitions.map(def => [def.field, def]),
      )
      const nextFields: TemplateFieldDraft[] = []
      prev.fields.forEach(field => {
        const definition = allowedMap.get(field.field)
        if (definition) {
          const systemDefaultValue = deriveSystemDefaultValue(definition)
          const shouldInheritDefault = Boolean(
            systemDefaultValue && field.useSystemDefault,
          )
          nextFields.push({
            ...field,
            type: definition.type,
            enumValues:
              definition.type === TemplateFieldType.ENUM
                ? definition.enum_values
                : undefined,
            systemDefaultValue,
            useSystemDefault: shouldInheritDefault,
            defaultValue: shouldInheritDefault
              ? (systemDefaultValue ?? "")
              : field.defaultValue,
            defaultError: shouldInheritDefault ? undefined : field.defaultError,
          })
          allowedMap.delete(field.field)
        }
      })
      const defaultSelected = mode === "create" || !draft?.id
      allowedMap.forEach(def => {
        const systemDefaultValue = deriveSystemDefaultValue(def)
        nextFields.push({
          field: def.field,
          customName: "",
          selected: defaultSelected || (isImportTemplate && def.required),
          type: def.type,
          enumValues:
            def.type === TemplateFieldType.ENUM ? def.enum_values : undefined,
          defaultValue: systemDefaultValue ?? "",
          defaultError: undefined,
          systemDefaultValue,
          useSystemDefault: Boolean(systemDefaultValue),
        })
      })
      const changed =
        nextFields.length !== prev.fields.length ||
        nextFields.some(
          (field, index) => field.field !== prev.fields[index]?.field,
        )
      if (!changed) {
        return prev
      }
      return { ...prev, fields: nextFields }
    })
  }, [allowedFieldDefinitions, draft, mode])

  const resetEditor = useCallback(() => {
    setDraft(null)
    setMode("list")
    setFormErrors({})
    setFeatureDrafts({})
  }, [])

  const startCreate = () => {
    setDraft({
      name: "",
      feature: null,
      products: [],
      fields: [],
    })
    setMode("create")
    setFormErrors({})
    setFeatureDrafts({})
  }

  const startEdit = (template: Template) => {
    const normalizedProducts = normalizeProductsForFeature(
      template.products ?? [],
      template.feature,
    )
    setDraft({
      id: template.id ?? undefined,
      name: template.name,
      feature: template.feature,
      products: normalizedProducts,
      fields: (template.fields ?? []).map(field => ({
        field: field.field,
        customName: field.name ?? "",
        selected: true,
        type: field.type,
        enumValues:
          field.type === TemplateFieldType.ENUM ? field.enum_values : undefined,
        defaultValue: serializeDefaultValue(field.default, field.type),
        defaultError: undefined,
        systemDefaultValue: undefined,
        useSystemDefault:
          (field.default === undefined || field.default === null) &&
          canFieldUseDefault(field.type),
      })),
    })
    setMode("edit")
    setFormErrors({})
    setFeatureDrafts({
      [template.feature]: {
        products: normalizedProducts,
        fields: (template.fields ?? []).map(field => ({
          field: field.field,
          customName: field.name ?? "",
          selected: true,
          type: field.type,
          enumValues:
            field.type === TemplateFieldType.ENUM
              ? field.enum_values
              : undefined,
          defaultValue: serializeDefaultValue(field.default, field.type),
          defaultError: undefined,
          systemDefaultValue: undefined,
          useSystemDefault:
            (field.default === undefined || field.default === null) &&
            canFieldUseDefault(field.type),
        })),
      },
    })
  }

  const handleSelectFeature = useCallback(
    (nextFeature: Feature) => {
      if (draft?.feature === nextFeature) {
        return
      }
      const cached = featureDrafts[nextFeature]
      setFeatureDrafts(prev => {
        if (!draft?.feature) {
          return prev
        }
        return {
          ...prev,
          [draft.feature]: {
            products: normalizeProductsForFeature(
              draft.products,
              draft.feature,
            ),
            fields: draft.fields,
          },
        }
      })
      setDraft(prev => {
        const base = prev ?? {
          name: "",
          feature: null,
          products: [],
          fields: [],
        }
        return {
          ...base,
          feature: nextFeature,
          products: normalizeProductsForFeature(
            cached?.products ?? [],
            nextFeature,
          ),
          fields: cached?.fields ?? [],
        }
      })
      setFormErrors({})
    },
    [draft, featureDrafts, normalizeProductsForFeature],
  )

  const handleToggleProduct = (product: ProductType) => {
    if (!draft) {
      return
    }
    setDraft(prev => {
      if (!prev) {
        return prev
      }
      const isSelected = prev.products.includes(product)
      const singleSelectionActive =
        templateType === TemplateType.IMPORT &&
        (prev.feature === "POSITION" || prev.feature === "TRANSACTIONS")
      if (singleSelectionActive) {
        const products = isSelected ? [] : [product]
        // Reset fields when switching product in import templates to avoid stale ordering/defaults
        return { ...prev, products, fields: isSelected ? prev.fields : [] }
      }
      const products = isSelected
        ? prev.products.filter(item => item !== product)
        : [...prev.products, product]
      return { ...prev, products }
    })
  }

  const handleToggleField = (fieldKey: string) => {
    if (!draft) return
    setDraft(prev => {
      if (!prev) return prev
      const isFieldRequired =
        templateType === TemplateType.IMPORT &&
        allowedFieldDefinitions.some(
          def => def.field === fieldKey && def.required,
        )
      // Prevent deselecting last selected field in an OR requirement group
      const def = allowedFieldDefinitions.find(d => d.field === fieldKey)
      const groupMembers =
        def?.or_requires && !def.required
          ? [def.field, ...def.or_requires].filter(f =>
              allowedFieldDefinitions.some(d => d.field === f),
            )
          : null
      let blockDeselect = false
      if (
        templateType === TemplateType.IMPORT &&
        groupMembers &&
        groupMembers.length > 1
      ) {
        const selectedInGroup = prev.fields.filter(
          f => groupMembers.includes(f.field) && f.selected,
        )
        if (
          selectedInGroup.length === 1 &&
          selectedInGroup[0].field === fieldKey
        ) {
          blockDeselect = true
          setBlockedGroup({ field: fieldKey, members: groupMembers })
        }
      }
      return {
        ...prev,
        fields: prev.fields.map(field =>
          field.field === fieldKey
            ? isFieldRequired && field.selected
              ? field // cannot deselect required
              : blockDeselect
                ? field // cannot deselect last in OR group
                : { ...field, selected: !field.selected }
            : field,
        ),
      }
    })
  }

  const handleRenameField = (fieldKey: string, value: string) => {
    if (!draft) return
    setDraft(prev => {
      if (!prev) return prev
      return {
        ...prev,
        fields: prev.fields.map(field =>
          field.field === fieldKey ? { ...field, customName: value } : field,
        ),
      }
    })
  }

  const handleFieldDragStart = (index: number) => {
    setDragIndex(index)
    setDragOverIndex(null)
  }

  const handleFieldDragEnter = (index: number) => {
    if (dragIndex === null || dragIndex === index) {
      return
    }
    setDragOverIndex(index)
  }

  const handleFieldDragEnd = () => {
    setDragIndex(null)
    setDragOverIndex(null)
  }

  const handleFieldDragLeave = (
    event: React.DragEvent<HTMLDivElement>,
    index: number,
  ) => {
    if (
      !event.currentTarget.contains(event.relatedTarget as Node) &&
      dragOverIndex === index
    ) {
      setDragOverIndex(null)
    }
  }

  const handleFieldDrop = (index: number) => {
    setDraft(prev => {
      if (!prev || dragIndex === null || dragIndex === index) {
        return prev
      }
      const nextFields = [...prev.fields]
      const [moved] = nextFields.splice(dragIndex, 1)
      nextFields.splice(index, 0, moved)
      return { ...prev, fields: nextFields }
    })
    setDragIndex(null)
    setDragOverIndex(null)
  }

  const handleFieldTouchStart = (index: number) => {
    setTouchDragIndex(index)
    setIsTouchDragging(true)
  }

  const handleFieldTouchMove = (index: number, event: React.TouchEvent) => {
    if (touchDragIndex === null) return
    const y = event.touches[0].clientY
    // Collect all row center positions
    const rows = Array.from(
      (fieldListRef.current ?? document).querySelectorAll(
        "[data-template-field-row]",
      ),
    ) as HTMLElement[]
    if (rows.length === 0) return
    let closestIndex = index
    let minDist = Infinity
    rows.forEach((row, i) => {
      const rect = row.getBoundingClientRect()
      const center = rect.top + rect.height / 2
      const dist = Math.abs(center - y)
      if (dist < minDist) {
        minDist = dist
        closestIndex = i
      }
    })
    if (closestIndex !== dragOverIndex && closestIndex !== touchDragIndex) {
      setDragOverIndex(closestIndex)
    }
  }

  const handleFieldTouchEnd = () => {
    if (
      touchDragIndex !== null &&
      dragOverIndex !== null &&
      touchDragIndex !== dragOverIndex
    ) {
      setDraft(prev => {
        if (!prev) return prev
        const nextFields = [...prev.fields]
        const [moved] = nextFields.splice(touchDragIndex, 1)
        nextFields.splice(dragOverIndex, 0, moved)
        return { ...prev, fields: nextFields }
      })
    }
    setTouchDragIndex(null)
    setDragOverIndex(null)
    setIsTouchDragging(false)
  }

  const validateDraft = () => {
    if (!draft) return false
    const errors: TemplateFormErrors = {}
    if (!draft.name.trim()) {
      errors.name = templateTexts.errors.nameRequired
    }
    if (!draft.feature) {
      errors.feature = templateTexts.errors.featureRequired
    }
    if (
      draft?.feature &&
      productOptionsForFeature.length > 0 &&
      draft.products.length === 0
    ) {
      errors.products = templateTexts.errors.productsRequired
    }
    if (draft.fields.filter(field => field.selected).length === 0) {
      errors.fields = templateTexts.errors.fieldsRequired
    }
    // Enforce required import field defaults: cannot clear a system default
    if (templateType === TemplateType.IMPORT) {
      draft.fields.forEach(f => {
        // Only enforce if field has system default and user tries to clear it
        if (
          f.selected &&
          f.systemDefaultValue &&
          canFieldUseDefault(f.type) &&
          !f.useSystemDefault &&
          !f.defaultValue
        ) {
          errors.fields = errors.fields
            ? `${errors.fields}\n${templateTexts.errors.defaultValueInvalid}`
            : templateTexts.errors.defaultValueInvalid
        }
      })
    }
    const invalidDefault = draft.fields.find(field => field.defaultError)
    if (invalidDefault) {
      errors.fields = errors.fields
        ? `${errors.fields}\n${templateTexts.errors.defaultValueInvalid}`
        : templateTexts.errors.defaultValueInvalid
    }
    // OR requirement groups validation (import templates only)
    if (templateType === TemplateType.IMPORT) {
      const defsMap = new Map(allowedFieldDefinitions.map(d => [d.field, d]))
      const groups = new Map<string, string[]>()
      allowedFieldDefinitions.forEach(def => {
        if (!def.required && def.or_requires && def.or_requires.length > 0) {
          const members = [def.field, ...def.or_requires].filter(f =>
            defsMap.has(f),
          )
          if (members.length > 1) {
            const key = members.slice().sort().join("|")
            groups.set(key, members)
          }
        }
      })
      const selectedFields = new Set(
        draft.fields.filter(f => f.selected).map(f => f.field),
      )
      const unsatisfied: string[] = []
      groups.forEach(members => {
        const satisfied = members.some(m => selectedFields.has(m))
        if (!satisfied) {
          unsatisfied.push(members.join(", "))
        }
      })
      if (unsatisfied.length > 0) {
        const message = unsatisfied
          .map(group =>
            templateTexts.errors.fieldsOrGroupRequired.replace(
              "{group}",
              group,
            ),
          )
          .join("\n")
        errors.fields = errors.fields ? `${errors.fields}\n${message}` : message
      }
    }
    setFormErrors(errors)
    return Object.keys(errors).length === 0
  }

  const handleSubmitDraft = async () => {
    if (!draft || !validateDraft()) {
      return
    }
    const payloadFields = draft.fields
      .filter(field => field.selected)
      .map(field => {
        const customName = field.customName.trim()
        const payloadField: TemplateCreateField = {
          field: field.field,
        }
        if (customName) {
          payloadField.custom_name = customName
        }
        const defaultValue = getDefaultValuePayload(field)
        if (defaultValue !== undefined) {
          payloadField.default = defaultValue
        }
        return payloadField
      })
    const basePayload = {
      name: draft.name.trim(),
      feature: draft.feature!,
      type: templateType,
      products: draft.products,
      fields: payloadFields,
    }
    const isEdit = mode === "edit" && draft.id
    try {
      setIsSubmitting(true)
      if (isEdit) {
        await onUpdate({ ...basePayload, id: draft.id! })
      } else {
        await onCreate(basePayload)
      }
      resetEditor()
    } catch {
      setFormErrors({ submit: templateTexts.errors.submitFailed })
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleConfirmDelete = async () => {
    if (!templateToDelete?.id) {
      return
    }
    try {
      setIsDeleting(true)
      await onDelete(templateToDelete.id)
      setTemplateToDelete(null)
    } catch {
      setFormErrors({ submit: templateTexts.errors.deleteFailed })
    } finally {
      setIsDeleting(false)
    }
  }

  const renderTemplateList = () => (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-muted-foreground">
            {templateTexts.listTitle}
          </h3>
          <p className="text-xs text-muted-foreground">
            {templateTexts.listSubtitle}
          </p>
        </div>
        <Badge variant="secondary">{templates.length}</Badge>
      </div>
      {templates.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border/60 bg-muted/30 p-4 text-center text-sm text-muted-foreground">
          {templateTexts.emptyState}
        </div>
      ) : (
        <div className="space-y-2">
          {templates.map(template => {
            const isActive = template.id === selectedTemplate?.id
            return (
              <button
                key={template.id ?? template.name}
                type="button"
                onClick={() => setSelectedTemplateId(template.id ?? null)}
                className={cn(
                  "w-full rounded-lg border px-4 py-3 text-left transition-colors",
                  isActive
                    ? "border-primary/60 bg-primary/5"
                    : "border-border/60 hover:bg-muted/40",
                )}
              >
                <div className="flex items-center justify-between">
                  <div className="flex flex-col">
                    <span className="text-sm font-semibold">
                      {template.name}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {featureLabels[template.feature] ?? template.feature}
                    </span>
                  </div>
                  <div className="flex items-center gap-1">
                    <Badge variant="secondary">
                      {template.fields?.length ?? 0} {templateTexts.fieldsLabel}
                    </Badge>
                  </div>
                </div>
                {template.products && template.products.length > 0 ? (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {template.products.map(product => (
                      <Badge key={product} variant="outline">
                        {productLabels[product] ?? product}
                      </Badge>
                    ))}
                  </div>
                ) : null}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )

  const renderTemplateDetails = () => {
    if (!selectedTemplate) {
      return (
        <div className="h-full rounded-lg border border-dashed border-border/60 p-6 text-center text-sm text-muted-foreground">
          {templateTexts.selectTemplate}
        </div>
      )
    }
    return (
      <div className="flex h-full min-h-0 flex-col rounded-lg border border-border/60 bg-card/70">
        <div className="flex items-center justify-between border-b border-border/60 px-4 py-3">
          <div>
            <p className="text-base font-semibold">{selectedTemplate.name}</p>
            <p className="text-xs text-muted-foreground">
              {templateTexts.templateFor} {templateTexts.types[templateType]}
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => startEdit(selectedTemplate)}
            >
              <Edit3 className="mr-2 h-4 w-4" />
              {t.common.edit}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="text-red-500 hover:text-red-600"
              onClick={() => setTemplateToDelete(selectedTemplate)}
            >
              <Trash2 className="mr-2 h-4 w-4" />
              {t.common.delete}
            </Button>
          </div>
        </div>
        <div className="flex-1 space-y-4 overflow-y-auto p-4 text-sm">
          <div className="space-y-1">
            <p className="text-xs font-semibold uppercase text-muted-foreground">
              {templateTexts.featureLabel}
            </p>
            <div className="flex items-center gap-2">
              <Badge variant="outline">
                {featureIcons[selectedTemplate.feature]}
                <span className="ml-2">
                  {featureLabels[selectedTemplate.feature] ??
                    selectedTemplate.feature}
                </span>
              </Badge>
            </div>
          </div>
          <div className="space-y-1">
            <p className="text-xs font-semibold uppercase text-muted-foreground">
              {templateTexts.productsLabel}
            </p>
            {selectedTemplate.products &&
            selectedTemplate.products.length > 0 ? (
              <div className="flex flex-wrap gap-1">
                {selectedTemplate.products.map(product => (
                  <Badge
                    key={product}
                    variant="secondary"
                    className="flex items-center gap-1"
                  >
                    {getIconForProductType(product, "h-3 w-3")}
                    <span>{productLabels[product] ?? product}</span>
                  </Badge>
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">
                {templateTexts.allProducts}
              </p>
            )}
          </div>
          <div>
            <p className="mb-2 text-xs font-semibold uppercase text-muted-foreground">
              {templateTexts.fieldsLabel}
            </p>
            <div className="space-y-2">
              <AnimatePresence>
                {(selectedTemplate.fields ?? []).map(field => {
                  const defaultLabel = getFieldLabel(field.field)
                  const finalColumn = field.name?.trim() || field.field
                  return (
                    <motion.div
                      key={field.field}
                      className="flex items-center justify-between rounded-md border border-border/60 px-3 py-2"
                      layout
                      initial={{ opacity: 0, y: -4 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: 4 }}
                      transition={{
                        type: "spring",
                        stiffness: 320,
                        damping: 30,
                        mass: 0.6,
                      }}
                    >
                      <div>
                        <p className="text-sm font-semibold">{defaultLabel}</p>
                        <p className="text-[11px] text-muted-foreground">
                          {templateTexts.finalColumnLabel}:{" "}
                          <span className="font-medium text-foreground">
                            {finalColumn}
                          </span>
                        </p>
                        {isImportTemplate &&
                          field.default !== undefined &&
                          field.default !== null && (
                            <p className="text-[11px] text-muted-foreground">
                              {templateTexts.defaultValueFormLabel}:{" "}
                              <span className="font-medium text-foreground">
                                {serializeDefaultValue(
                                  field.default,
                                  field.type,
                                )}
                              </span>
                            </p>
                          )}
                      </div>
                      <div className="text-right">
                        {renderFieldTypePill(
                          field.type,
                          field.field,
                          field.enum_values,
                        )}
                      </div>
                    </motion.div>
                  )
                })}
              </AnimatePresence>
            </div>
          </div>
        </div>
      </div>
    )
  }

  const renderFieldsEditor = () => {
    if (!draft?.feature) {
      return (
        <div className="rounded-lg border border-dashed border-border/60 p-4 text-center text-sm text-muted-foreground">
          {templateTexts.selectFeaturePlaceholder}
        </div>
      )
    }
    if (draft.products.length === 0 && productOptionsForFeature.length > 0) {
      return (
        <div className="rounded-lg border border-dashed border-border/60 p-4 text-center text-sm text-muted-foreground">
          {templateTexts.selectProductsPlaceholder}
        </div>
      )
    }
    if (draft.fields.length === 0) {
      return (
        <div className="rounded-lg border border-dashed border-border/60 p-4 text-center text-sm text-muted-foreground">
          {templateTexts.noFieldsPlaceholder}
        </div>
      )
    }
    const selectedCount = draft.fields.filter(field => field.selected).length
    return (
      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm text-muted-foreground">
            {templateTexts.fieldsHint.replace("{count}", String(selectedCount))}
          </p>
          <Badge variant="outline">
            {selectedCount} / {draft.fields.length}
          </Badge>
        </div>
        <div className="space-y-2" ref={fieldListRef}>
          {draft.fields.map((field, index) => {
            const isDragTarget =
              dragIndex !== null &&
              dragIndex !== index &&
              dragOverIndex === index
            const defaultLabel = getFieldLabel(field.field)
            const customName = field.customName.trim()
            const effectiveName = customName || field.field
            const fieldDef = allowedFieldDefinitions.find(
              def => def.field === field.field,
            )
            const defaultEditor = renderDefaultValueEditor(field, fieldDef)
            const hasDefaultEditor = Boolean(defaultEditor)
            const groupMembers =
              isImportTemplate &&
              fieldDef &&
              !fieldDef.required &&
              fieldDef.or_requires &&
              fieldDef.or_requires.length > 0
                ? [fieldDef.field, ...fieldDef.or_requires].filter(f =>
                    allowedFieldDefinitions.some(d => d.field === f),
                  )
                : null
            return (
              <motion.div
                key={field.field}
                data-template-field-row
                className={cn(
                  "relative rounded-xl border px-3 py-2 transition-colors will-change-transform",
                  field.selected
                    ? "border-primary/40 bg-primary/5"
                    : "border-border/60 bg-muted/30",
                  dragIndex === index
                    ? cn(
                        "outline outline-2 outline-primary/60 bg-primary/10 scale-[1.015]",
                        isTouchDragging
                          ? "shadow-none"
                          : "shadow-md shadow-primary/10",
                      )
                    : undefined,
                  isDragTarget
                    ? "outline outline-2 outline-primary/50"
                    : undefined,
                )}
                layout
                layoutId={`template-field-${field.field}`}
                transition={{
                  type: "spring",
                  stiffness: 300,
                  damping: 28,
                  mass: 0.5,
                }}
                onDragEnter={() => handleFieldDragEnter(index)}
                onDragLeave={event => handleFieldDragLeave(event, index)}
                onDragOver={event => event.preventDefault()}
                onDrop={() => handleFieldDrop(index)}
              >
                {isDragTarget ? (
                  <span className="pointer-events-none absolute inset-x-4 -top-1 h-1 rounded-full bg-gradient-to-r from-primary/60 via-primary to-primary/60 opacity-95" />
                ) : null}
                <div className="flex flex-1 flex-col gap-2">
                  <div className="flex items-start justify-between gap-2">
                    <button
                      type="button"
                      onClick={() => handleToggleField(field.field)}
                      className="flex min-w-0 flex-1 items-start gap-3 text-left"
                    >
                      <span
                        className="shrink-0 text-muted-foreground cursor-grab select-none w-7 h-7 flex items-center justify-center rounded-md hover:bg-muted/40 active:bg-muted/60 touch-none"
                        draggable
                        onDragStart={event => {
                          handleFieldDragStart(index)
                          const row = (
                            event.currentTarget as HTMLElement
                          ).closest(
                            "[data-template-field-row]",
                          ) as HTMLElement | null
                          if (row && event.dataTransfer) {
                            const rect = row.getBoundingClientRect()
                            const offsetX = event.clientX - rect.left
                            const offsetY = event.clientY - rect.top
                            const clone = row.cloneNode(true) as HTMLElement
                            clone.style.position = "absolute"
                            clone.style.top = "0"
                            clone.style.left = "0"
                            clone.style.width = `${rect.width}px`
                            clone.style.boxSizing = "border-box"
                            clone.style.pointerEvents = "none"
                            clone.classList.add("opacity-90")
                            const wrapper = document.createElement("div")
                            wrapper.style.position = "absolute"
                            wrapper.style.top = "-10000px"
                            wrapper.style.left = "-10000px"
                            wrapper.style.padding = "0 0 0 4px"
                            wrapper.appendChild(clone)
                            document.body.appendChild(wrapper)
                            try {
                              event.dataTransfer.setDragImage(
                                wrapper,
                                offsetX + 4,
                                offsetY,
                              )
                            } catch {
                              // ignore if not supported
                            }
                            requestAnimationFrame(() => {
                              if (wrapper.parentNode)
                                wrapper.parentNode.removeChild(wrapper)
                            })
                          }
                        }}
                        onDragEnd={handleFieldDragEnd}
                        onTouchStart={() => handleFieldTouchStart(index)}
                        onTouchMove={event =>
                          handleFieldTouchMove(index, event)
                        }
                        onTouchEnd={handleFieldTouchEnd}
                        aria-label={t.export.templates.dragHandleLabel}
                        tabIndex={0}
                      >
                        <GripVertical className="h-5 w-5" />
                      </span>
                      <div className="min-w-0 flex-1 space-y-1">
                        <div className="flex min-w-0 items-center gap-2">
                          <span className="text-sm font-semibold text-foreground transition-colors hover:text-primary">
                            {defaultLabel}
                          </span>
                          {renderFieldTypePill(
                            field.type,
                            field.field,
                            field.enumValues,
                          )}
                          {isImportTemplate &&
                            allowedFieldDefinitions.find(
                              def => def.field === field.field && def.required,
                            ) && (
                              <span className="inline-flex items-center rounded-full border border-border/60 bg-amber-500/15 px-2 py-0.5 text-[10px] font-medium text-amber-600 dark:text-amber-400">
                                {templateTexts.requiredFieldBadge}
                              </span>
                            )}
                          {groupMembers && (
                            <Popover>
                              <PopoverTrigger asChild>
                                <span
                                  className="cursor-help inline-flex items-center rounded-full border border-border/60 bg-indigo-500/15 px-2 py-0.5 text-[10px] font-medium text-indigo-600 dark:text-indigo-400"
                                  onClick={e => e.stopPropagation()}
                                >
                                  {templateTexts.orGroupFieldBadge}
                                </span>
                              </PopoverTrigger>
                              <PopoverContent className="max-w-sm p-3 text-xs">
                                <p className="font-semibold mb-1">
                                  {templateTexts.orGroupBadgeHint.replace(
                                    "{group}",
                                    groupMembers
                                      .map(m => getFieldLabel(m))
                                      .join(", "),
                                  )}
                                </p>
                                <p className="text-muted-foreground">
                                  {templateTexts.orGroupBadgeExplanation}
                                </p>
                              </PopoverContent>
                            </Popover>
                          )}
                        </div>
                        <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                          <span>
                            {templateTexts.finalColumnLabel}:{" "}
                            <span className="font-mono text-xs text-foreground">
                              {effectiveName}
                            </span>
                          </span>
                          {blockedGroup?.field === field.field && (
                            <span className="text-[11px] font-medium text-amber-600 dark:text-amber-400">
                              {templateTexts.orGroupBlockedToggle.replace(
                                "{group}",
                                (groupMembers || [])
                                  .map(m => getFieldLabel(m))
                                  .join(", "),
                              )}
                            </span>
                          )}
                        </div>
                      </div>
                    </button>
                    <button
                      type="button"
                      role="switch"
                      aria-checked={field.selected}
                      onClick={() => handleToggleField(field.field)}
                      className={cn(
                        "flex h-fit shrink-0 items-center justify-center rounded-full border p-1 transition-colors sm:gap-2 sm:px-3 sm:py-1",
                        field.selected
                          ? "border-primary bg-primary text-primary-foreground"
                          : "border-border bg-muted text-muted-foreground",
                      )}
                    >
                      <span className="flex h-4 w-4 items-center justify-center rounded-full bg-background/20">
                        {isImportTemplate &&
                        allowedFieldDefinitions.some(
                          def => def.field === field.field && def.required,
                        ) ? (
                          <Lock
                            className={cn(
                              "h-2.5 w-2.5",
                              field.selected ? "opacity-100" : "opacity-30",
                            )}
                          />
                        ) : (
                          <Check
                            className={cn(
                              "h-3 w-3",
                              field.selected ? "opacity-100" : "opacity-30",
                            )}
                          />
                        )}
                      </span>
                      <span className="hidden text-xs font-semibold sm:inline">
                        {field.selected
                          ? templateTexts.fieldStates.included
                          : templateTexts.fieldStates.excluded}
                      </span>
                    </button>
                  </div>
                  <div
                    className={cn(
                      "grid gap-3",
                      hasDefaultEditor ? "md:grid-cols-2" : undefined,
                    )}
                  >
                    <div>
                      <div className="h-5 flex items-center">
                        <Label
                          htmlFor={`custom-name-${field.field}`}
                          className="text-xs leading-tight"
                        >
                          {templateTexts.customNameLabel}
                        </Label>
                      </div>
                      <Input
                        id={`custom-name-${field.field}`}
                        draggable={false}
                        value={field.customName}
                        placeholder={field.field}
                        onChange={event =>
                          handleRenameField(field.field, event.target.value)
                        }
                        disabled={!field.selected}
                        className="mt-1 h-9"
                      />
                    </div>
                    {hasDefaultEditor ? <div>{defaultEditor}</div> : null}
                  </div>
                </div>
              </motion.div>
            )
          })}
        </div>
      </div>
    )
  }

  const renderEditor = () => {
    const singleProductSelection =
      templateType === TemplateType.IMPORT &&
      (draft?.feature === "POSITION" || draft?.feature === "TRANSACTIONS")
    const productsLabel = singleProductSelection
      ? (templateTexts.productsStepSingle ?? templateTexts.productsStep)
      : (templateTexts.productsStepMultiple ?? templateTexts.productsStep)

    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={resetEditor}>
            <ChevronLeft className="mr-1 h-4 w-4" />
            {t.common.back}
          </Button>
          <div>
            <p className="text-base font-semibold">
              {mode === "edit"
                ? templateTexts.editTitle
                : templateTexts.newTitle}
            </p>
          </div>
        </div>
        <div className="space-y-2">
          <Label
            htmlFor="template-name"
            className={cn(formErrors.name ? "text-red-500" : undefined)}
          >
            {templateTexts.nameLabel}
          </Label>
          <Input
            id="template-name"
            value={draft?.name ?? ""}
            placeholder={templateTexts.namePlaceholder}
            onChange={event =>
              setDraft(prev =>
                prev ? { ...prev, name: event.target.value } : prev,
              )
            }
            className={cn(
              formErrors.name
                ? "border-red-500 focus-visible:ring-red-500"
                : undefined,
            )}
          />
          {formErrors.name ? (
            <p className="text-xs text-red-500">{formErrors.name}</p>
          ) : null}
        </div>
        <div className="space-y-2">
          <Label
            className={cn(formErrors.feature ? "text-red-500" : undefined)}
          >
            {templateTexts.featureStep}
          </Label>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            {availableFeatures.map(feature => {
              const isSelected = draft?.feature === feature
              return (
                <Button
                  key={feature}
                  type="button"
                  variant={isSelected ? "default" : "outline"}
                  className="justify-start"
                  onClick={() => handleSelectFeature(feature)}
                >
                  <span className="mr-2 text-muted-foreground">
                    {featureIcons[feature as Feature]}
                  </span>
                  {featureLabels[feature] ?? feature}
                </Button>
              )
            })}
          </div>
          {formErrors.feature ? (
            <p className="text-xs text-red-500">{formErrors.feature}</p>
          ) : null}
        </div>
        {draft?.feature ? (
          <div className="space-y-2">
            <Label
              className={cn(formErrors.products ? "text-red-500" : undefined)}
            >
              {productsLabel}
            </Label>
            {productOptionsForFeature.length === 0 ? (
              <div className="rounded-lg border border-border/60 bg-muted/30 px-3 py-2 text-sm text-muted-foreground">
                {templateTexts.noProducts}
              </div>
            ) : (
              <div className="flex flex-wrap gap-2">
                {productOptionsForFeature.map(product => {
                  const isSelected = draft?.products.includes(product)
                  return (
                    <Button
                      key={product}
                      type="button"
                      variant={isSelected ? "default" : "outline"}
                      size="sm"
                      className="rounded-full gap-2"
                      onClick={() => handleToggleProduct(product)}
                    >
                      <span className="text-muted-foreground">
                        {getIconForProductType(product, "h-3 w-3")}
                      </span>
                      {productLabels[product] ?? product}
                    </Button>
                  )
                })}
              </div>
            )}
            {formErrors.products ? (
              <p className="text-xs text-red-500">{formErrors.products}</p>
            ) : null}
          </div>
        ) : null}
        <div className="space-y-2">
          <Label className={cn(formErrors.fields ? "text-red-500" : undefined)}>
            {templateTexts.fieldsStep}
          </Label>
          {formErrors.fields ? (
            <p className="text-xs text-red-500">{formErrors.fields}</p>
          ) : null}
          {renderFieldsEditor()}
        </div>
        {formErrors.submit ? (
          <p className="text-sm text-red-500">{formErrors.submit}</p>
        ) : null}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={resetEditor}>
            {t.common.cancel}
          </Button>
          <Button onClick={handleSubmitDraft} disabled={isSubmitting}>
            {isSubmitting ? (
              <>
                <LoadingSpinner className="mr-2 h-4 w-4" />
                {t.common.saving}
              </>
            ) : (
              <>
                <Sparkles className="mr-2 h-4 w-4" />
                {t.common.save}
              </>
            )}
          </Button>
        </div>
      </div>
    )
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <TooltipProvider>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-[10010] flex items-center justify-center bg-black/60 p-2 sm:p-6"
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              transition={{ duration: 0.2, ease: "easeOut" }}
              className="flex h-[90vh] w-full max-w-6xl"
            >
              <Card className="flex w-full flex-col overflow-hidden">
                <CardHeader className="flex flex-row items-center justify-between border-b border-border/60 pb-3">
                  <div>
                    <CardTitle className="flex items-center gap-2 text-lg">
                      <LayoutTemplate className="h-5 w-5 text-primary" />
                      {templateTexts.dialogTitle}
                    </CardTitle>
                    <CardDescription>
                      {templateTexts.dialogSubtitle}
                    </CardDescription>
                  </div>
                  <Button variant="ghost" size="icon" onClick={onClose}>
                    <X className="h-5 w-5" />
                  </Button>
                </CardHeader>
                <CardContent className="flex flex-1 flex-col gap-6 overflow-hidden py-4">
                  {formErrors.submit && mode !== "create" && mode !== "edit" ? (
                    <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-500/40 dark:bg-red-500/10 dark:text-red-200">
                      {formErrors.submit}
                    </div>
                  ) : null}
                  {isLoadingTemplates || isLoadingFields ? (
                    <div className="flex flex-1 items-center justify-center">
                      <LoadingSpinner className="h-6 w-6" />
                    </div>
                  ) : mode === "list" ? (
                    <div className="grid flex-1 min-h-0 gap-4 lg:grid-cols-[280px_1fr]">
                      <div className="min-h-0 overflow-y-auto pr-1">
                        {renderTemplateList()}
                        <Button
                          className="mt-4 w-full"
                          variant="outline"
                          onClick={startCreate}
                        >
                          <PlusCircle className="mr-2 h-4 w-4" />
                          {templateTexts.newTemplateButton}
                        </Button>
                      </div>
                      <div className="flex h-full min-h-0 flex-col overflow-hidden">
                        {renderTemplateDetails()}
                      </div>
                    </div>
                  ) : (
                    <div className="overflow-y-auto pr-1">{renderEditor()}</div>
                  )}
                </CardContent>
              </Card>
            </motion.div>
          </motion.div>

          <ConfirmationDialog
            isOpen={templateToDelete !== null}
            title={templateTexts.deleteTitle}
            message={templateTexts.deleteMessage.replace(
              "{name}",
              templateToDelete?.name ?? "",
            )}
            confirmText={t.common.delete}
            cancelText={t.common.cancel}
            onConfirm={handleConfirmDelete}
            onCancel={() => setTemplateToDelete(null)}
            isLoading={isDeleting}
          />
        </TooltipProvider>
      )}
    </AnimatePresence>
  )
}
