import React from "react"
import { CommodityType } from "@/types/position"

// Function to get active commodity types from positions data
export const getActiveCommodityTypes = (
  positionsData: any,
): CommodityType[] => {
  if (!positionsData?.positions) {
    return []
  }

  const activeCommodityTypes = new Set<CommodityType>()

  Object.values(positionsData.positions).forEach((entityPosition: any) => {
    const commodityProduct = entityPosition.products?.COMMODITY
    if (
      commodityProduct &&
      "entries" in commodityProduct &&
      commodityProduct.entries.length > 0
    ) {
      commodityProduct.entries.forEach((commodity: any) => {
        if (
          commodity.type &&
          Object.values(CommodityType).includes(commodity.type)
        ) {
          activeCommodityTypes.add(commodity.type as CommodityType)
        }
      })
    }
  })

  return Array.from(activeCommodityTypes)
}

// Chemical element symbols mapping
export const getChemicalSymbol = (commodityType: CommodityType): string => {
  switch (commodityType) {
    case CommodityType.GOLD:
      return "Au"
    case CommodityType.SILVER:
      return "Ag"
    case CommodityType.PLATINUM:
      return "Pt"
    case CommodityType.PALLADIUM:
      return "Pd"
    default:
      return ""
  }
}

// Chemical element colors mapping
export const getChemicalSymbolColor = (
  commodityType: CommodityType,
): string => {
  switch (commodityType) {
    case CommodityType.GOLD:
      return "bg-gradient-to-br from-yellow-400 to-yellow-600"
    case CommodityType.SILVER:
      return "bg-gradient-to-br from-gray-200 to-gray-500"
    case CommodityType.PLATINUM:
      return "bg-gradient-to-br from-gray-400 to-gray-700"
    case CommodityType.PALLADIUM:
      return "bg-gradient-to-br from-gray-300 to-gray-600"
    default:
      return "bg-gradient-to-br from-gray-400 to-gray-600"
  }
}

interface CommodityIconProps {
  type: CommodityType
  size?: "sm" | "md" | "lg"
  className?: string
}

// Single commodity icon component
export const CommodityIcon: React.FC<CommodityIconProps> = ({
  type,
  size = "md",
  className = "",
}) => {
  const sizeClasses = {
    sm: "w-6 h-6 text-xs",
    md: "w-8 h-8 text-sm",
    lg: "w-10 h-10 text-base",
  }

  return (
    <div
      className={`inline-flex items-center justify-center rounded-md ${getChemicalSymbolColor(type)} text-white font-bold shadow-lg ${sizeClasses[size]} ${className}`}
    >
      {getChemicalSymbol(type)}
    </div>
  )
}

interface CommodityIconsStackProps {
  types?: CommodityType[]
  positionsData?: any // Financial positions data to determine active commodities
  size?: "sm" | "md" | "lg"
  overlap?: "sm" | "md" | "lg"
  className?: string
}

// Stacked commodity icons component
export const CommodityIconsStack: React.FC<CommodityIconsStackProps> = ({
  types,
  positionsData,
  size = "md", // Changed default to md for bigger icons
  overlap = "md",
  className = "",
}) => {
  // If positionsData is provided, get active commodity types; otherwise use provided types or all types
  const displayTypes = React.useMemo(() => {
    if (positionsData) {
      const activeCommodityTypes = getActiveCommodityTypes(positionsData)
      return activeCommodityTypes.length > 0
        ? activeCommodityTypes
        : [
            CommodityType.GOLD,
            CommodityType.SILVER,
            CommodityType.PLATINUM,
            CommodityType.PALLADIUM,
          ]
    }
    return (
      types || [
        CommodityType.GOLD,
        CommodityType.SILVER,
        CommodityType.PLATINUM,
        CommodityType.PALLADIUM,
      ]
    )
  }, [positionsData, types])

  const overlapClasses = {
    sm: "-ml-1",
    md: "-ml-2",
    lg: "-ml-3",
  }

  const sizeClasses = {
    sm: "w-6 h-6 text-xs",
    md: "w-8 h-8 text-sm",
    lg: "w-10 h-10 text-base",
  }

  return (
    <div className={`flex items-center ${className}`}>
      {displayTypes.map((type, index) => (
        <div
          key={type}
          className={`inline-flex items-center justify-center rounded-md ${getChemicalSymbolColor(type)} text-white font-bold shadow-lg border-2 border-white dark:border-gray-900 ${sizeClasses[size]} ${index > 0 ? overlapClasses[overlap] : ""}`}
          style={{ zIndex: displayTypes.length - index }}
        >
          {getChemicalSymbol(type)}
        </div>
      ))}
    </div>
  )
}

// Default export for convenience
export default {
  CommodityIcon,
  CommodityIconsStack,
  getChemicalSymbol,
  getChemicalSymbolColor,
  getActiveCommodityTypes,
}
