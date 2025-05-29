import type React from "react"
import { useState } from "react"
import { useAppContext } from "@/context/AppContext"
import { Button } from "@/components/ui/Button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import {
  BarChart,
  CheckCircle,
  History,
  Receipt,
  Repeat,
  Send,
} from "lucide-react"
import type { Feature } from "@/types"
import { useI18n } from "@/i18n"
import { motion } from "framer-motion"

export function FeatureSelector() {
  const { selectedEntity, scrape, isLoading } = useAppContext()
  const [selectedFeatures, setSelectedFeatures] = useState<Feature[]>([])
  const { t } = useI18n()

  if (!selectedEntity) return null

  const availableFeatures = selectedEntity.features

  const toggleFeature = (feature: Feature) => {
    if (selectedFeatures.includes(feature)) {
      setSelectedFeatures(selectedFeatures.filter(f => f !== feature))
    } else {
      setSelectedFeatures([...selectedFeatures, feature])
    }
  }

  const selectAllFeatures = () => {
    setSelectedFeatures([...availableFeatures])
  }

  const handleSubmit = () => {
    scrape(selectedEntity, selectedFeatures)
  }

  // Map features to icons
  const featureIcons: Record<Feature, React.ReactNode> = {
    POSITION: <BarChart className="h-5 w-5" />,
    AUTO_CONTRIBUTIONS: <Repeat className="h-5 w-5" />,
    TRANSACTIONS: <Receipt className="h-5 w-5" />,
    HISTORIC: <History className="h-5 w-5" />,
  }

  return (
    <Card className="w-full max-w-md mx-auto">
      <CardHeader>
        <CardTitle className="text-center">
          {t.features.selectFeatures} {selectedEntity.name}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {availableFeatures.length > 1 && (
            <Button
              variant="outline"
              className="w-full"
              onClick={selectAllFeatures}
            >
              {t.features.selectAll}
            </Button>
          )}

          <div className="grid grid-cols-2 gap-3">
            {availableFeatures.map(feature => (
              <motion.div
                key={feature}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
              >
                <Button
                  variant={
                    selectedFeatures.includes(feature) ? "default" : "outline"
                  }
                  className="w-full h-20 flex flex-col justify-center items-center gap-2"
                  onClick={() => toggleFeature(feature)}
                >
                  {selectedFeatures.includes(feature) && (
                    <CheckCircle className="absolute top-2 right-2 h-4 w-4" />
                  )}
                  {featureIcons[feature]}
                  <span>{t.features[feature]}</span>
                </Button>
              </motion.div>
            ))}
          </div>

          <Button
            className="w-full mt-4"
            disabled={selectedFeatures.length === 0 || isLoading}
            onClick={handleSubmit}
          >
            <Send className="mr-2 h-4 w-4" />
            {isLoading ? t.common.loading : t.features.fetchSelected}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
