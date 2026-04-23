import React from "react"
import { useI18n } from "@/i18n"
import { Button } from "@/components/ui/Button"
import { MultiSelect, MultiSelectOption } from "@/components/ui/MultiSelect"
import { EntitySelector } from "@/components/EntitySelector"
import { FilterX, Filter } from "lucide-react"
import type { Entity } from "@/types"

interface InvestmentFiltersProps {
  filteredEntities: Entity[]
  selectedEntities: string[]
  onEntitiesChange: (entities: string[]) => void
  walletOptions?: MultiSelectOption[]
  selectedWallets?: string[]
  onWalletsChange?: (wallets: string[]) => void
  minimal?: boolean
  placeholderOverride?: string
  extraFilters?: React.ReactNode
  entityImageOverride?: (entity: Entity) => string | null | undefined
}

export function InvestmentFilters({
  filteredEntities,
  selectedEntities,
  onEntitiesChange,
  walletOptions,
  selectedWallets,
  onWalletsChange,
  minimal = false,
  placeholderOverride,
  extraFilters,
  entityImageOverride,
}: InvestmentFiltersProps) {
  const { t } = useI18n()

  const handleClearFilters = () => {
    onEntitiesChange([])
    if (onWalletsChange) {
      onWalletsChange([])
    }
  }

  if (minimal) {
    return (
      <div className="max-w-sm">
        <EntitySelector
          entities={filteredEntities}
          selectedEntityIds={selectedEntities}
          onSelectionChange={onEntitiesChange}
          placeholder={placeholderOverride || t.transactions.selectEntities}
          entityImageOverride={entityImageOverride}
        />
      </div>
    )
  }

  return (
    <div className="pb-2">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between flex-wrap">
        <div className="flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300">
            <Filter size={16} />
            <span>{t.transactions.filters}:</span>
          </div>
          <div className="flex-1 min-w-[200px] max-w-sm">
            <EntitySelector
              entities={filteredEntities}
              selectedEntityIds={selectedEntities}
              onSelectionChange={onEntitiesChange}
              entityImageOverride={entityImageOverride}
            />
          </div>
          {walletOptions && walletOptions.length > 0 && onWalletsChange && (
            <div className="flex-1 min-w-[200px] max-w-sm">
              <MultiSelect
                options={walletOptions}
                value={selectedWallets || []}
                onChange={onWalletsChange}
                placeholder={t.walletManagement.walletFilterPlaceholder}
              />
            </div>
          )}
          {extraFilters && (
            <div className="flex items-center gap-2">{extraFilters}</div>
          )}
        </div>
        {(selectedEntities.length > 0 ||
          (selectedWallets && selectedWallets.length > 0)) && (
          <Button
            variant="outline"
            size="sm"
            onClick={handleClearFilters}
            className="flex items-center gap-2"
          >
            <FilterX size={16} />
            {t.transactions.clear}
          </Button>
        )}
      </div>
    </div>
  )
}
