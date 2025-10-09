import type React from "react"
import { useEffect, useMemo } from "react"
import { useAppContext } from "@/context/AppContext"
import { Button } from "@/components/ui/Button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import { Switch } from "@/components/ui/Switch"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover"
import {
  BarChart,
  CheckCircle,
  ChevronDown,
  Clock,
  History,
  ArrowLeftRight,
  PiggyBank,
  Send,
  Settings,
} from "lucide-react"
import type { Feature } from "@/types"
import { useI18n } from "@/i18n"
import { motion } from "framer-motion"
import { formatTimeAgo } from "@/lib/timeUtils"

export function FeatureSelector() {
  const {
    selectedEntity,
    scrape,
    fetchingEntityState,
    selectedFeatures,
    setSelectedFeatures,
    fetchOptions,
    setFetchOptions,
  } = useAppContext()
  const { t } = useI18n()

  if (!selectedEntity) return null

  const isEntityFetching = fetchingEntityState.fetchingEntityIds.includes(
    selectedEntity.id,
  )

  const { deep } = fetchOptions

  const setDeepScrape = (value: boolean) => {
    setFetchOptions({ ...fetchOptions, deep: value })
  }

  const availableFeatures = useMemo(
    () => selectedEntity.features,
    [selectedEntity],
  )

  const allFeaturesSelected =
    availableFeatures.length > 0 &&
    availableFeatures.every(feature => selectedFeatures.includes(feature))

  const hasTransactionsSelected = selectedFeatures.includes("TRANSACTIONS")
  const lastTransactionsFetchRaw = selectedEntity.last_fetch?.TRANSACTIONS
  const hasTransactionsHistory =
    typeof lastTransactionsFetchRaw === "string" &&
    lastTransactionsFetchRaw.trim() !== ""
  const showTransactionsLoadingNotice =
    isEntityFetching &&
    hasTransactionsSelected &&
    (!hasTransactionsHistory || deep)

  // Default-select all available features when entity changes or when none selected
  useEffect(() => {
    if (availableFeatures.length > 0) {
      setSelectedFeatures(availableFeatures)
    }
  }, [availableFeatures, setSelectedFeatures])

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

  const unselectAllFeatures = () => {
    setSelectedFeatures([])
  }

  const handleSubmit = () => {
    scrape(selectedEntity, selectedFeatures, { deep: deep })
  }

  // Map features to icons
  const featureIcons: Record<Feature, React.ReactNode> = {
    POSITION: <BarChart className="h-5 w-5" />,
    AUTO_CONTRIBUTIONS: <PiggyBank className="h-5 w-5" />,
    TRANSACTIONS: <ArrowLeftRight className="h-5 w-5" />,
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
              onClick={
                allFeaturesSelected ? unselectAllFeatures : selectAllFeatures
              }
            >
              {allFeaturesSelected
                ? t.features.unselectAll
                : t.features.selectAll}
            </Button>
          )}

          <div className="grid grid-cols-2 gap-3">
            {availableFeatures.map(feature => {
              // Determine last fetch string for this feature
              const lastFetchRaw = selectedEntity.last_fetch?.[feature]
              let lastFetchDisplay: string = t.common.never
              if (lastFetchRaw && lastFetchRaw.trim() !== "") {
                const date = new Date(lastFetchRaw)
                if (!isNaN(date.getTime())) {
                  lastFetchDisplay = formatTimeAgo(date, t)
                }
              }

              return (
                <motion.div
                  key={feature}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                >
                  <Button
                    variant={
                      selectedFeatures.includes(feature) ? "default" : "outline"
                    }
                    className="w-full h-24 flex flex-col justify-center items-center gap-1 relative"
                    onClick={() => toggleFeature(feature)}
                  >
                    {selectedFeatures.includes(feature) && (
                      <CheckCircle className="absolute top-2 right-2 h-4 w-4" />
                    )}
                    {featureIcons[feature]}
                    <span className="text-sm font-medium">
                      {t.features[feature]}
                    </span>
                    <span className="text-[10px] text-muted-foreground leading-tight">
                      {lastFetchDisplay}
                    </span>
                  </Button>
                </motion.div>
              )
            })}
          </div>

          <div className="flex justify-center">
            {availableFeatures.includes("TRANSACTIONS") && (
              <Popover>
                <PopoverTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-muted-foreground"
                  >
                    <Settings className="mr-2 h-4 w-4" />
                    {t.features.advancedOptions}
                    <ChevronDown className="ml-2 h-4 w-4" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-80" align="center">
                  <div className="space-y-4">
                    <div className="flex items-center justify-between space-x-2">
                      <div className="flex-1">
                        <div className="text-sm font-medium">
                          {t.features.deepScrape}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {t.features.deepScrapeDescription}
                        </div>
                      </div>
                      <Switch checked={deep} onCheckedChange={setDeepScrape} />
                    </div>
                  </div>
                </PopoverContent>
              </Popover>
            )}
          </div>

          {showTransactionsLoadingNotice && (
            <div className="flex items-start gap-2 rounded-lg border border-amber-200/50 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-100">
              <Clock className="mt-[2px] h-4 w-4 flex-shrink-0" />
              <span>{t.features.transactionsLoadingNotice}</span>
            </div>
          )}

          <Button
            className="w-full mt-4"
            disabled={selectedFeatures.length === 0 || isEntityFetching}
            onClick={handleSubmit}
          >
            <Send className="mr-2 h-4 w-4" />
            {isEntityFetching ? t.common.loading : t.features.fetchSelected}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
