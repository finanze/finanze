import React from "react"
import { useI18n } from "@/i18n"
import { Button } from "@/components/ui/Button"
import { MultiSelect, MultiSelectOption } from "@/components/ui/MultiSelect"
import { FilterX, Filter } from "lucide-react"

interface InvestmentFiltersProps {
  entityOptions: MultiSelectOption[]
  selectedEntities: string[]
  onEntitiesChange: (entities: string[]) => void
}

export function InvestmentFilters({
  entityOptions,
  selectedEntities,
  onEntitiesChange,
}: InvestmentFiltersProps) {
  const { t } = useI18n()

  const handleClearFilters = () => {
    onEntitiesChange([])
  }

  return (
    <div className="pb-6 border-b border-gray-200 dark:border-gray-800">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300">
          <Filter size={16} />
          <span>{t.transactions.filters}:</span>
        </div>

        <div className="flex-1 max-w-sm">
          <MultiSelect
            options={entityOptions}
            value={selectedEntities}
            onChange={onEntitiesChange}
            placeholder={t.transactions.selectEntities}
          />
        </div>

        {selectedEntities.length > 0 && (
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
