import { useState } from "react"
import { Badge } from "@/components/ui/Badge"
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from "@/components/ui/Popover"
import { useI18n } from "@/i18n"
import { Sparkles } from "lucide-react"
import type { Feature } from "@/types"
import { ProductType } from "@/types/position"
import { getIconForProductType } from "@/utils/dashboardUtils"

interface FeaturesBadgeProps {
  features: Feature[]
  nativelySupportedProducts?: ProductType[] | null
  className?: string
}

export function FeaturesBadge({
  features,
  nativelySupportedProducts,
  className = "",
}: FeaturesBadgeProps) {
  const { t } = useI18n()
  const [isOpen, setIsOpen] = useState(false)

  if (features.length === 0) {
    return null
  }

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <Badge
          variant="secondary"
          className={`text-xs cursor-pointer hover:opacity-80 transition-opacity ${className}`}
          onMouseEnter={() => setIsOpen(true)}
          onMouseLeave={() => setIsOpen(false)}
        >
          <Sparkles className="h-3 w-3 mr-1" />
          {features.length}
        </Badge>
      </PopoverTrigger>
      <PopoverContent
        className="max-w-[280px] p-3 bg-white dark:bg-black border border-gray-200 dark:border-gray-800 rounded-md shadow-lg"
        sideOffset={4}
        onMouseEnter={() => setIsOpen(true)}
        onMouseLeave={() => setIsOpen(false)}
      >
        <div className="space-y-3">
          <div>
            <div className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-2">
              {t.features.availableFeatures}
            </div>
            <div className="flex flex-wrap gap-1">
              {features.map(feature => (
                <Badge key={feature} variant="secondary" className="text-xs">
                  {t.features[feature]}
                </Badge>
              ))}
            </div>
          </div>
          {nativelySupportedProducts &&
            nativelySupportedProducts.length > 0 && (
              <div>
                <div className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-2">
                  {t.features.supportedProducts}
                </div>
                <div className="flex flex-wrap gap-1">
                  {nativelySupportedProducts.map(productType => (
                    <Badge
                      key={productType}
                      variant="secondary"
                      className="text-xs"
                    >
                      {getIconForProductType(productType, "h-3 w-3 mr-1")}
                      {t.enums?.productType?.[productType] || productType}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
        </div>
      </PopoverContent>
    </Popover>
  )
}
