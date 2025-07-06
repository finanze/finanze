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

interface FeaturesBadgeProps {
  features: Feature[]
  className?: string
}

export function FeaturesBadge({
  features,
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
        className="w-auto p-3 bg-white dark:bg-black border border-gray-200 dark:border-gray-800 rounded-md shadow-lg"
        sideOffset={4}
        onMouseEnter={() => setIsOpen(true)}
        onMouseLeave={() => setIsOpen(false)}
      >
        <div className="space-y-2">
          <div className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-2">
            {t.features.availableFeatures}
          </div>
          {features.map(feature => (
            <Badge
              key={feature}
              variant="secondary"
              className="text-xs mr-1 mb-1"
            >
              {t.features[feature]}
            </Badge>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  )
}
