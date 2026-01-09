import React, { useCallback } from "react"
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  Modal,
  Pressable,
  Image,
  Platform,
} from "react-native"
import { X, Check, ChevronRight, Calendar } from "lucide-react-native"
import Animated, { FadeIn, FadeOut, Layout } from "react-native-reanimated"
import { useSafeAreaInsets } from "react-native-safe-area-context"
import { useTheme } from "@/presentation/context"
import { useI18n } from "@/presentation/i18n"
import { getThemeColors, spacing, borderRadius } from "@/presentation/theme"
import { ProductType, TxType, AvailableSource } from "@/domain"
import DateTimePicker, {
  type DateTimePickerEvent,
} from "@react-native-community/datetimepicker"
import * as FileSystem from "expo-file-system/legacy"
import {
  getIconForAssetType,
  getIconForTxType,
} from "@/presentation/utils/iconUtils"
import { ASSET_TYPE_COLOR_MAP } from "@/presentation/utils/colorUtils"
import { SensitiveText } from "@/presentation/components/ui"

export interface TransactionFiltersState {
  entities: string[]
  productTypes: ProductType[]
  txTypes: TxType[]
  fromDate: string
  toDate: string
}

interface TransactionFiltersProps {
  filters: TransactionFiltersState
  onFiltersChange: (filters: TransactionFiltersState) => void
  entities: AvailableSource[]
  onApply: () => void
  onClear: () => void
  isVisible: boolean
  onClose: () => void
}

interface FilterOption {
  value: string
  label: string
  iconUri?: string | null
  leadingIcon?: React.ReactNode
}

interface FilterSectionProps {
  title: string
  options: FilterOption[]
  selected: string[]
  onToggle: (value: string) => void
}

function FilterSection({
  title,
  options,
  selected,
  onToggle,
}: FilterSectionProps) {
  const { resolvedTheme } = useTheme()
  const colors = getThemeColors(resolvedTheme)

  return (
    <View style={styles.filterSection}>
      <Text style={[styles.filterSectionTitle, { color: colors.textMuted }]}>
        {title}
      </Text>
      <View style={styles.filterOptions}>
        {options.map(option => {
          const isSelected = selected.includes(option.value)
          return (
            <TouchableOpacity
              key={option.value}
              onPress={() => onToggle(option.value)}
              style={[
                styles.filterChip,
                {
                  backgroundColor: isSelected ? colors.text : colors.surface,
                  borderColor: isSelected ? colors.text : colors.border,
                },
              ]}
              activeOpacity={0.7}
            >
              {option.iconUri ? (
                <View
                  style={[
                    styles.chipIconWrap,
                    {
                      backgroundColor: colors.background,
                      borderColor: colors.border,
                    },
                  ]}
                >
                  <Image
                    source={{ uri: option.iconUri }}
                    style={styles.chipIconImage}
                    resizeMode="cover"
                  />
                </View>
              ) : option.leadingIcon ? (
                <View style={styles.leadingIconWrap}>{option.leadingIcon}</View>
              ) : null}
              <Text
                style={[
                  styles.filterChipText,
                  {
                    color: isSelected ? colors.background : colors.text,
                  },
                ]}
                numberOfLines={1}
              >
                {option.label}
              </Text>
              {isSelected ? (
                <Check size={12} color={colors.background} strokeWidth={2.5} />
              ) : null}
            </TouchableOpacity>
          )
        })}
      </View>
    </View>
  )
}

function resolveIconUri(
  iconUrl: string | null | undefined,
  entityId?: string | null,
): string | null {
  const docDir = FileSystem.documentDirectory
  if (!docDir) return null

  // If iconUrl is provided, use it
  if (iconUrl) {
    const trimmed = iconUrl.trim()
    if (trimmed) {
      if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
        return trimmed
      }
      if (trimmed.startsWith("file://")) {
        return trimmed
      }
      const normalized = trimmed.startsWith("/") ? trimmed.slice(1) : trimmed
      return `${docDir}${normalized}`
    }
  }

  // Fallback: use entities/{entity_id}.png
  if (entityId) {
    return `${docDir}entities/${entityId}.png`
  }

  return null
}

function parseDateString(value: string): Date | null {
  if (!value) return null
  const dateOnly = value.includes("T") ? value.split("T")[0] : value
  const parsed = new Date(dateOnly)
  return Number.isFinite(parsed.getTime()) ? parsed : null
}

function toIsoDateString(date: Date): string {
  // Keep as date-only for stable filtering (matches tx.dateKey behavior)
  return date.toISOString().split("T")[0]
}

interface DateRowProps {
  label: string
  value: string
  onPress: () => void
  onClear: () => void
}

function DateRow({ label, value, onPress, onClear }: DateRowProps) {
  const { resolvedTheme } = useTheme()
  const colors = getThemeColors(resolvedTheme)

  return (
    <View style={styles.dateRow}>
      <Text style={[styles.filterSectionTitle, { color: colors.textMuted }]}>
        {label}
      </Text>
      <View style={styles.dateRowRight}>
        <Pressable
          onPress={onPress}
          style={({ pressed }) => [
            styles.dateChip,
            {
              backgroundColor: colors.surface,
              borderColor: colors.border,
              opacity: pressed ? 0.8 : 1,
            },
          ]}
        >
          <Calendar size={14} color={colors.textMuted} strokeWidth={1.5} />
          {value ? (
            <SensitiveText
              kind="date"
              value={value}
              style={[styles.dateChipText, { color: colors.text }]}
            />
          ) : (
            <Text style={[styles.dateChipText, { color: colors.textMuted }]}>
              —
            </Text>
          )}
        </Pressable>

        {value ? (
          <TouchableOpacity
            onPress={onClear}
            style={styles.dateClearButton}
            hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
          >
            <X size={14} color={colors.textMuted} strokeWidth={1.5} />
          </TouchableOpacity>
        ) : null}
      </View>
    </View>
  )
}

export function TransactionFilters({
  filters,
  onFiltersChange,
  entities,
  onApply,
  onClear,
  isVisible,
  onClose,
}: TransactionFiltersProps) {
  const { resolvedTheme } = useTheme()
  const colors = getThemeColors(resolvedTheme)
  const { t } = useI18n()
  const insets = useSafeAreaInsets()

  const [activePicker, setActivePicker] = React.useState<"from" | "to" | null>(
    null,
  )

  const entityOptions: FilterOption[] = entities
    .filter(e => e.lastFetch?.TRANSACTIONS || e.virtualFeatures?.TRANSACTIONS)
    .map(e => ({
      value: e.id ?? "",
      label: e.name,
      iconUri: resolveIconUri(e.iconUrl, e.id),
    }))
    .filter(e => e.value)

  const productTypeOptions: FilterOption[] = [
    ProductType.STOCK_ETF,
    ProductType.FUND,
    ProductType.FUND_PORTFOLIO,
    ProductType.DEPOSIT,
    ProductType.FACTORING,
    ProductType.REAL_ESTATE_CF,
    ProductType.CRYPTO,
    ProductType.ACCOUNT,
  ].map(type => ({
    value: type,
    label: t.assets[type] ?? type,
    leadingIcon: getIconForAssetType(type, {
      color: ASSET_TYPE_COLOR_MAP[type] ?? colors.textMuted,
      size: 14,
    }),
  }))

  const txTypeOptions: FilterOption[] = Object.values(TxType).map(type => ({
    value: type,
    label: t.txTypes[type] ?? type,
    leadingIcon: getIconForTxType(type, {
      color: colors.textMuted,
      size: 14,
    }),
  }))

  const handleToggleEntity = useCallback(
    (entityId: string) => {
      const current = filters.entities
      const next = current.includes(entityId)
        ? current.filter(id => id !== entityId)
        : [...current, entityId]
      onFiltersChange({ ...filters, entities: next })
    },
    [filters, onFiltersChange],
  )

  const handleToggleProductType = useCallback(
    (type: string) => {
      const current = filters.productTypes
      const next = current.includes(type as ProductType)
        ? current.filter(t => t !== type)
        : [...current, type as ProductType]
      onFiltersChange({ ...filters, productTypes: next })
    },
    [filters, onFiltersChange],
  )

  const handleToggleTxType = useCallback(
    (type: string) => {
      const current = filters.txTypes
      const next = current.includes(type as TxType)
        ? current.filter(t => t !== type)
        : [...current, type as TxType]
      onFiltersChange({ ...filters, txTypes: next })
    },
    [filters, onFiltersChange],
  )

  const hasActiveFilters =
    filters.entities.length > 0 ||
    filters.productTypes.length > 0 ||
    filters.txTypes.length > 0 ||
    filters.fromDate ||
    filters.toDate

  const handleApply = () => {
    onApply()
    onClose()
  }

  const handleClear = () => {
    onClear()
  }

  const handleDateChange = useCallback(
    (event: DateTimePickerEvent, selected?: Date) => {
      // On Android, close picker immediately regardless of action
      if (Platform.OS === "android") {
        setActivePicker(null)
      }
      // Only apply the date if user actually selected (not dismissed/cancelled)
      if (event.type === "dismissed" || !selected || !activePicker) {
        return
      }
      const iso = toIsoDateString(selected)
      if (activePicker === "from") {
        onFiltersChange({ ...filters, fromDate: iso })
      } else {
        onFiltersChange({ ...filters, toDate: iso })
      }
    },
    [activePicker, filters, onFiltersChange],
  )

  const pickerValue =
    activePicker === "from"
      ? (parseDateString(filters.fromDate) ?? new Date())
      : (parseDateString(filters.toDate) ?? new Date())

  return (
    <Modal
      visible={isVisible}
      animationType="slide"
      presentationStyle="pageSheet"
      onRequestClose={onClose}
    >
      <View
        style={[
          styles.modalContainer,
          {
            backgroundColor: colors.background,
            paddingTop: insets.top,
          },
        ]}
      >
        {/* Header */}
        <View
          style={[styles.modalHeader, { borderBottomColor: colors.border }]}
        >
          <TouchableOpacity
            onPress={onClose}
            style={styles.closeButton}
            hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
          >
            <X size={20} color={colors.text} strokeWidth={1.5} />
          </TouchableOpacity>
          <Text style={[styles.modalTitle, { color: colors.text }]}>
            {t.transactions.filters}
          </Text>
          <TouchableOpacity
            onPress={handleClear}
            style={styles.clearButton}
            disabled={!hasActiveFilters}
            hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
          >
            <Text
              style={[
                styles.clearButtonText,
                {
                  color: hasActiveFilters ? colors.text : colors.textMuted,
                },
              ]}
            >
              {t.transactions.clearFilters}
            </Text>
          </TouchableOpacity>
        </View>

        {/* Content */}
        <ScrollView
          style={styles.modalContent}
          contentContainerStyle={[
            styles.modalContentInner,
            { paddingBottom: insets.bottom + 80 },
          ]}
          showsVerticalScrollIndicator={false}
        >
          {entityOptions.length > 0 ? (
            <FilterSection
              title={t.transactions.filterByEntity}
              options={entityOptions}
              selected={filters.entities}
              onToggle={handleToggleEntity}
            />
          ) : null}

          <View style={styles.filterSection}>
            <Text
              style={[styles.filterSectionTitle, { color: colors.textMuted }]}
            >
              {t.transactions.filterByDateFrom} /{" "}
              {t.transactions.filterByDateTo}
            </Text>
            <View style={styles.dateSection}>
              <DateRow
                label={t.transactions.filterByDateFrom}
                value={filters.fromDate}
                onPress={() => setActivePicker("from")}
                onClear={() => onFiltersChange({ ...filters, fromDate: "" })}
              />
              <DateRow
                label={t.transactions.filterByDateTo}
                value={filters.toDate}
                onPress={() => setActivePicker("to")}
                onClear={() => onFiltersChange({ ...filters, toDate: "" })}
              />
            </View>
          </View>

          <FilterSection
            title={t.transactions.filterByProductType}
            options={productTypeOptions}
            selected={filters.productTypes}
            onToggle={handleToggleProductType}
          />

          <FilterSection
            title={t.transactions.filterByTxType}
            options={txTypeOptions}
            selected={filters.txTypes}
            onToggle={handleToggleTxType}
          />
        </ScrollView>

        {activePicker ? (
          <View
            style={[styles.pickerWrap, { backgroundColor: colors.background }]}
          >
            <DateTimePicker
              value={pickerValue}
              mode="date"
              display={Platform.OS === "ios" ? "inline" : "default"}
              onChange={handleDateChange}
              themeVariant={resolvedTheme === "dark" ? "dark" : "light"}
            />
            {Platform.OS === "ios" ? (
              <View
                style={[
                  styles.pickerActions,
                  {
                    borderTopColor: colors.border,
                    backgroundColor: colors.background,
                  },
                ]}
              >
                <TouchableOpacity
                  onPress={() => setActivePicker(null)}
                  style={[styles.pickerDone, { backgroundColor: colors.text }]}
                  activeOpacity={0.8}
                >
                  <Text
                    style={[
                      styles.pickerDoneText,
                      { color: colors.background },
                    ]}
                  >
                    {t.common.done}
                  </Text>
                </TouchableOpacity>
              </View>
            ) : null}
          </View>
        ) : null}

        {/* Apply Button */}
        <View
          style={[
            styles.applyContainer,
            {
              backgroundColor: colors.background,
              borderTopColor: colors.border,
              paddingBottom: insets.bottom + spacing.md,
            },
          ]}
        >
          <TouchableOpacity
            onPress={handleApply}
            style={[styles.applyButton, { backgroundColor: colors.text }]}
            activeOpacity={0.8}
          >
            <Text
              style={[styles.applyButtonText, { color: colors.background }]}
            >
              {t.transactions.applyFilters}
            </Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  )
}

interface FilterBarProps {
  onOpenFilters: () => void
  activeFilterCount: number
}

export function FilterBar({
  onOpenFilters,
  activeFilterCount,
}: FilterBarProps) {
  const { resolvedTheme } = useTheme()
  const colors = getThemeColors(resolvedTheme)
  const { t } = useI18n()

  return (
    <TouchableOpacity
      onPress={onOpenFilters}
      style={[
        styles.filterBar,
        {
          backgroundColor: colors.surface,
          borderColor: colors.border,
        },
      ]}
      activeOpacity={0.7}
    >
      <Text style={[styles.filterBarText, { color: colors.text }]}>
        {t.transactions.filters}
      </Text>
      {activeFilterCount > 0 ? (
        <View style={[styles.filterBadge, { backgroundColor: colors.text }]}>
          <Text style={[styles.filterBadgeText, { color: colors.background }]}>
            {activeFilterCount}
          </Text>
        </View>
      ) : null}
      <ChevronRight size={16} color={colors.textMuted} strokeWidth={1.5} />
    </TouchableOpacity>
  )
}

const styles = StyleSheet.create({
  modalContainer: {
    flex: 1,
  },
  modalHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  closeButton: {
    width: 32,
  },
  modalTitle: {
    fontSize: 16,
    fontWeight: "500",
    letterSpacing: 0.3,
  },
  clearButton: {
    width: 60,
    alignItems: "flex-end",
  },
  clearButtonText: {
    fontSize: 13,
    fontWeight: "400",
    letterSpacing: 0.2,
  },
  modalContent: {
    flex: 1,
  },
  modalContentInner: {
    padding: spacing.lg,
    gap: spacing.xl,
  },
  filterSection: {
    gap: spacing.sm,
  },
  filterSectionTitle: {
    fontSize: 11,
    fontWeight: "400",
    textTransform: "uppercase",
    letterSpacing: 1.2,
    marginBottom: spacing.xs,
  },
  filterOptions: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  filterChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.full,
    borderWidth: StyleSheet.hairlineWidth,
  },
  leadingIconWrap: {
    width: 16,
    height: 16,
    alignItems: "center",
    justifyContent: "center",
  },
  chipIconWrap: {
    width: 16,
    height: 16,
    borderRadius: 6,
    borderWidth: StyleSheet.hairlineWidth,
    overflow: "hidden",
  },
  chipIconImage: {
    width: 16,
    height: 16,
  },
  filterChipText: {
    fontSize: 13,
    fontWeight: "400",
    letterSpacing: 0.2,
  },
  dateSection: {
    gap: spacing.md,
  },
  dateRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.md,
  },
  dateRowRight: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
  },
  dateChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.full,
    borderWidth: StyleSheet.hairlineWidth,
    minWidth: 140,
    justifyContent: "center",
  },
  dateChipText: {
    fontSize: 13,
    fontWeight: "400",
    letterSpacing: 0.2,
  },
  dateClearButton: {
    padding: 6,
  },
  pickerWrap: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
  },
  pickerActions: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.lg,
    paddingTop: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  pickerDone: {
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: spacing.md,
    borderRadius: borderRadius.lg,
  },
  pickerDoneText: {
    fontSize: 15,
    fontWeight: "500",
    letterSpacing: 0.3,
  },
  applyContainer: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  applyButton: {
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: spacing.md,
    borderRadius: borderRadius.lg,
  },
  applyButtonText: {
    fontSize: 15,
    fontWeight: "500",
    letterSpacing: 0.3,
  },
  filterBar: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.lg,
    borderWidth: StyleSheet.hairlineWidth,
  },
  filterBarText: {
    flex: 1,
    fontSize: 13,
    fontWeight: "400",
    letterSpacing: 0.2,
  },
  filterBadge: {
    minWidth: 18,
    height: 18,
    borderRadius: 9,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 5,
  },
  filterBadgeText: {
    fontSize: 11,
    fontWeight: "600",
  },
})
