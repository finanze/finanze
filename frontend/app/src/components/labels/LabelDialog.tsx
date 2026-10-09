import { useEffect, useState, type CSSProperties } from "react"
import {
  Check,
  EyeOff,
  ImagePlus,
  Loader2,
  Pencil,
  Save,
  TrendingDown,
  TrendingUp,
  X,
  type LucideIcon,
} from "lucide-react"
import { useI18n } from "@/i18n"
import { useAppContext } from "@/context/AppContext"
import { useLabels } from "@/context/LabelsContext"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { Label as FieldLabel } from "@/components/ui/Label"
import { Icon, IconPicker, type IconName } from "@/components/ui/icon-picker"
import { createLabel, updateLabel } from "@/services/api"
import { cn } from "@/lib/utils"
import { LabelCategory, type Label } from "@/types/labeling"
import { LabelingModal } from "./LabelingModal"
import { hexToRgba } from "./LabelChip"

const PRESET_COLORS = [
  "#16a34a",
  "#0d9488",
  "#0891b2",
  "#2563eb",
  "#6366f1",
  "#8b5cf6",
  "#db2777",
  "#ef4444",
  "#f97316",
  "#eab308",
  "#84cc16",
  "#78716c",
  "#6b7280",
]

const MAX_NAME_LENGTH = 64
const MAX_DESCRIPTION_LENGTH = 300

const CATEGORY_OPTIONS: {
  category: LabelCategory
  Icon: LucideIcon
  iconClass: string
}[] = [
  {
    category: LabelCategory.EXPENSE,
    Icon: TrendingDown,
    iconClass: "text-red-600 dark:text-red-400",
  },
  {
    category: LabelCategory.INCOME,
    Icon: TrendingUp,
    iconClass: "text-green-600 dark:text-green-400",
  },
  {
    category: LabelCategory.EXCLUDED,
    Icon: EyeOff,
    iconClass: "text-muted-foreground",
  },
]

interface LabelDialogProps {
  isOpen: boolean
  label: Label | null
  onClose: () => void
}

export function LabelDialog({ isOpen, label, onClose }: LabelDialogProps) {
  const { t } = useI18n()
  const { showToast } = useAppContext()
  const { refreshLabels, getLabelName } = useLabels()
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [color, setColor] = useState(PRESET_COLORS[0])
  const [icon, setIcon] = useState<IconName | undefined>(undefined)
  const [category, setCategory] = useState<LabelCategory>(LabelCategory.EXPENSE)
  const [saving, setSaving] = useState(false)
  const [nameError, setNameError] = useState(false)

  const isBase = Boolean(label?.key)
  const baseName = label?.key ? getLabelName({ ...label, name: null }) : ""

  useEffect(() => {
    if (!isOpen) return
    setName(label?.name ?? "")
    setDescription(label?.description ?? "")
    setColor(label?.color ?? PRESET_COLORS[0])
    setIcon((label?.icon as IconName | undefined) ?? undefined)
    setCategory(label?.category ?? LabelCategory.EXPENSE)
    setNameError(false)
  }, [isOpen, label])

  const handleClose = () => {
    if (saving) return
    onClose()
  }

  const handleSave = async () => {
    const trimmedName = name.trim()
    if (!isBase && !trimmedName) {
      setNameError(true)
      return
    }
    setSaving(true)
    const request = {
      name: trimmedName || null,
      description: description.trim() || null,
      color,
      icon: icon ?? null,
      category,
    }
    try {
      if (label) {
        await updateLabel(label.id, request)
      } else {
        await createLabel(request)
      }
      await refreshLabels()
      showToast(t.labels.labelSaved, "success")
      onClose()
    } catch (error) {
      console.error("Error saving label:", error)
      showToast(t.labels.saveError, "error")
    } finally {
      setSaving(false)
    }
  }

  const previewName = name.trim() || baseName || t.labels.labelName
  const isCustomColor = !PRESET_COLORS.includes(color)

  return (
    <LabelingModal
      isOpen={isOpen}
      title={label ? t.labels.editLabel : t.labels.newLabel}
      onClose={handleClose}
      testId="label-dialog"
      footer={
        <>
          <Button
            variant="outline"
            onClick={handleClose}
            disabled={saving}
            aria-label={t.common.cancel}
            title={t.common.cancel}
            className="h-9 w-9 p-0"
          >
            <X className="h-4 w-4" />
          </Button>
          <Button
            onClick={handleSave}
            disabled={saving}
            aria-label={saving ? t.common.saving : t.common.save}
            title={saving ? t.common.saving : t.common.save}
            className="h-9 w-9 p-0"
          >
            {saving ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
          </Button>
        </>
      }
    >
      <div className="space-y-1.5">
        <FieldLabel htmlFor="label-name">{t.labels.labelName}</FieldLabel>
        <div className="flex items-center gap-2">
          <IconPicker
            value={icon}
            onValueChange={value => setIcon(value)}
            modal
          >
            <button
              type="button"
              title={t.labels.changeIcon}
              aria-label={t.labels.changeIcon}
              disabled={saving}
              className="group relative flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border transition-transform hover:scale-105"
              style={{
                backgroundColor: hexToRgba(color, 0.15),
                borderColor: hexToRgba(color, 0.4),
                color,
              }}
            >
              {icon ? (
                <Icon name={icon} className="h-5 w-5" />
              ) : (
                <ImagePlus className="h-5 w-5 opacity-70" />
              )}
              <span className="absolute -bottom-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full border border-border bg-background text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100">
                <Pencil className="h-2.5 w-2.5" />
              </span>
            </button>
          </IconPicker>
          <Input
            id="label-name"
            value={name}
            maxLength={MAX_NAME_LENGTH}
            placeholder={baseName || previewName}
            onChange={event => {
              setName(event.target.value)
              setNameError(false)
            }}
            className={cn("flex-1", nameError && "border-red-500")}
            disabled={saving}
          />
        </div>
        {isBase && (
          <p className="text-xs text-muted-foreground">
            {t.labels.baseLabelNameHint}
          </p>
        )}
        {nameError && (
          <p className="text-xs text-red-600 dark:text-red-400">
            {t.labels.nameRequired}
          </p>
        )}
      </div>

      <div className="space-y-2">
        <FieldLabel>{t.labels.color}</FieldLabel>
        <div className="flex flex-wrap items-center gap-2">
          {PRESET_COLORS.map(preset => (
            <button
              key={preset}
              type="button"
              onClick={() => setColor(preset)}
              className={cn(
                "flex h-7 w-7 items-center justify-center rounded-full transition-transform hover:scale-110",
                color === preset &&
                  "ring-2 ring-offset-2 ring-offset-background",
              )}
              style={
                {
                  backgroundColor: preset,
                  "--tw-ring-color": preset,
                } as CSSProperties
              }
              aria-label={preset}
              aria-pressed={color === preset}
            >
              {color === preset && <Check className="h-3.5 w-3.5 text-white" />}
            </button>
          ))}
          <label
            title={t.labels.customColor}
            className={cn(
              "relative flex h-7 w-7 cursor-pointer items-center justify-center rounded-full transition-transform hover:scale-110",
              isCustomColor && "ring-2 ring-offset-2 ring-offset-background",
            )}
            style={
              {
                background: isCustomColor
                  ? color
                  : "conic-gradient(#ef4444, #eab308, #22c55e, #06b6d4, #3b82f6, #a855f7, #ef4444)",
                "--tw-ring-color": color,
              } as CSSProperties
            }
          >
            <input
              type="color"
              value={color}
              onChange={event => setColor(event.target.value)}
              className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
              aria-label={t.labels.customColor}
            />
            {isCustomColor && <Check className="h-3.5 w-3.5 text-white" />}
          </label>
        </div>
      </div>

      <div className="space-y-1.5">
        <FieldLabel htmlFor="label-description">
          {t.labels.labelDescription}
        </FieldLabel>
        <textarea
          id="label-description"
          value={description}
          maxLength={MAX_DESCRIPTION_LENGTH}
          onChange={event => setDescription(event.target.value)}
          rows={2}
          disabled={saving}
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        />
        <p className="text-xs text-muted-foreground">
          {t.labels.labelDescriptionHint}
        </p>
      </div>

      <div className="space-y-2">
        <FieldLabel>{t.labels.category}</FieldLabel>
        <div
          className="grid grid-cols-3 gap-2"
          role="radiogroup"
          aria-label={t.labels.category}
        >
          {CATEGORY_OPTIONS.map(({ category: option, Icon, iconClass }) => {
            const active = category === option
            return (
              <button
                key={option}
                type="button"
                role="radio"
                aria-checked={active}
                onClick={() => setCategory(option)}
                disabled={saving}
                data-testid={`label-category-${option.toLowerCase()}`}
                className={cn(
                  "flex flex-col items-center justify-center gap-1.5 rounded-lg border px-2 py-2.5 text-center text-xs font-medium transition-colors disabled:opacity-50",
                  active
                    ? "border-foreground bg-muted/50 text-foreground"
                    : "border-border text-muted-foreground hover:bg-muted/30 hover:text-foreground",
                )}
              >
                <Icon className={cn("h-4 w-4", iconClass)} />
                {t.labels.categories[option]}
              </button>
            )
          })}
        </div>
        <p className="text-xs text-muted-foreground">
          {t.labels.categoryHints[category]}
        </p>
      </div>
    </LabelingModal>
  )
}
